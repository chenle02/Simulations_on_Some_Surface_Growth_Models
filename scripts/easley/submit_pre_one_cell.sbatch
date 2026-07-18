#!/bin/bash

set -euo pipefail
umask 077

fail_deployment() {
    printf 'ERROR[78]: %s\n' "$1" >&2
    exit 78
}

is_normalized_absolute_path() {
    local value="$1"
    [[ "$value" == /* ]] &&
        [[ "$value" != / ]] &&
        [[ "$value" != //* ]] &&
        [[ "$value" != */ ]] &&
        [[ "$value" != *//* ]] &&
        [[ "$value" != */./* ]] &&
        [[ "$value" != */. ]] &&
        [[ "$value" != */../* ]] &&
        [[ "$value" != */.. ]] &&
        [[ "$value" != *[[:cntrl:]]* ]]
}

stat_executable="/usr/bin/stat"
[[ -f "$stat_executable" && ! -L "$stat_executable" && ! -O "$stat_executable" && \
    ! -w "$stat_executable" && -r "$stat_executable" && -x "$stat_executable" ]] ||
    fail_deployment "the fixed system stat executable is unavailable"

read_metadata() {
    local path="$1"
    local metadata=""
    local extra=""
    metadata="$("$stat_executable" --printf='%u %g %a %h %s %d %i' -- "$path")" ||
        fail_deployment "path metadata cannot be read"
    IFS=' ' read -r metadata_owner metadata_group metadata_mode metadata_links \
        metadata_size metadata_device metadata_inode extra <<<"$metadata"
    [[ -z "$extra" ]] || fail_deployment "path metadata is malformed"
    [[ "$metadata_owner" =~ ^(0|[1-9][0-9]*)$ ]] ||
        fail_deployment "path owner metadata is malformed"
    [[ "$metadata_group" =~ ^(0|[1-9][0-9]*)$ ]] ||
        fail_deployment "path group metadata is malformed"
    [[ "$metadata_mode" =~ ^[0-7]{3,4}$ ]] ||
        fail_deployment "path mode metadata is malformed"
    [[ "$metadata_links" =~ ^[1-9][0-9]*$ ]] ||
        fail_deployment "path link metadata is malformed"
    [[ "$metadata_size" =~ ^(0|[1-9][0-9]*)$ ]] ||
        fail_deployment "path size metadata is malformed"
    [[ "$metadata_device" =~ ^(0|[1-9][0-9]*)$ ]] ||
        fail_deployment "path device metadata is malformed"
    [[ "$metadata_inode" =~ ^[1-9][0-9]*$ ]] ||
        fail_deployment "path inode metadata is malformed"
}

mode_has_no_group_or_world_write() {
    local mode="$1"
    (( (8#$mode & 8#022) == 0 ))
}

administrator_namespace_is_safe() {
    local mode="$1"
    local group="$2"
    (( (8#$mode & 8#002) == 0 )) &&
        (( (8#$mode & 8#020) == 0 || group == 0 ))
}

path_is_within_limit() {
    local LC_ALL="C"
    local path="$1"
    (( ${#path} <= 4096 ))
}

sidecar_has_exact_line_size() {
    local LC_ALL="C"
    (( ${#python} + 1 == sidecar_size ))
}

check_directory_chain() {
    local path="$1"
    local home_anchor="$2"
    local remaining="${path#/}"
    local component=""
    local current=""
    local at_or_below_home_anchor=0
    [[ "$path" == "$home_anchor" || "$path" == "$home_anchor/"* ]] ||
        fail_deployment "path escapes the trusted home anchor"
    [[ -d / && ! -L / && -x / ]] || fail_deployment "the filesystem root is unavailable"
    read_metadata /
    [[ "$metadata_owner" == "0" ]] || fail_deployment "the filesystem root has an untrusted owner"
    administrator_namespace_is_safe "$metadata_mode" "$metadata_group" ||
        fail_deployment "the administrator namespace above the home anchor is unsafe"
    while [[ -n "$remaining" ]]; do
        component="${remaining%%/*}"
        if [[ "$remaining" == */* ]]; then
            remaining="${remaining#*/}"
        else
            remaining=""
        fi
        current="$current/$component"
        [[ -d "$current" && ! -L "$current" && -x "$current" ]] ||
            fail_deployment "a path ancestor is unavailable, linked, or unsearchable"
        read_metadata "$current"
        if [[ "$current" == "$home_anchor" ]]; then
            at_or_below_home_anchor=1
        fi
        if (( at_or_below_home_anchor == 1 )); then
            [[ "$metadata_owner" == "$EUID" ]] ||
                fail_deployment "a private path ancestor has an untrusted owner"
            mode_has_no_group_or_world_write "$metadata_mode" ||
                fail_deployment "a private path ancestor is group- or world-writable"
        else
            [[ "$metadata_owner" == "0" ]] ||
                fail_deployment "an administrator path ancestor has an untrusted owner"
            administrator_namespace_is_safe "$metadata_mode" "$metadata_group" ||
                fail_deployment "the administrator namespace above the home anchor is unsafe"
        fi
    done
}

kernel_hostname_file="/proc/sys/kernel/hostname"
[[ -f "$kernel_hostname_file" && ! -L "$kernel_hostname_file" && -r "$kernel_hostname_file" ]] ||
    fail_deployment "the kernel hostname is unavailable"
IFS= read -r kernel_hostname <"$kernel_hostname_file" ||
    fail_deployment "the kernel hostname cannot be read"
[[ -n "$kernel_hostname" && "$kernel_hostname" != *[[:cntrl:]]* ]] ||
    fail_deployment "the kernel hostname is malformed"
[[ "${SLURM_JOB_ID:-}" =~ ^[1-9][0-9]*$ ]] ||
    fail_deployment "a canonical administrative job ID is required"
[[ -n "${SLURMD_NODENAME:-}" && "$kernel_hostname" == "$SLURMD_NODENAME" ]] ||
    fail_deployment "the kernel hostname differs from the assigned compute node"
case "$kernel_hostname" in
    node8[0-9][0-9]|node90[0-7]|node92[6-9]|node9[3-7][0-9]|node98[0-2]) ;;
    *) fail_deployment "the assigned host is not an allowed nova compute node" ;;
esac
[[ "${SLURM_JOB_NODELIST:-}" == "$kernel_hostname" ]] ||
    fail_deployment "the administrative node list is not exact"
[[ "${SLURM_JOB_NAME:-}" == "tkpz-admin-submit" ]] ||
    fail_deployment "the administrative job name is not exact"
[[ "${SLURM_JOB_PARTITION:-}" == "nova_short" ]] ||
    fail_deployment "the administrative partition is not exact"
[[ "${SLURM_JOB_NUM_NODES:-}" == "1" && "${SLURM_NTASKS:-}" == "1" ]] ||
    fail_deployment "the administrative node or task count is not exact"
[[ "${SLURM_CPUS_PER_TASK:-}" == "1" && "${SLURM_MEM_PER_NODE:-}" == "4096" ]] ||
    fail_deployment "the administrative CPU or memory envelope is not exact"
[[ -z "${SLURM_ARRAY_JOB_ID+x}" && -z "${SLURM_ARRAY_TASK_ID+x}" && \
    -z "${SLURM_ARRAY_TASK_COUNT+x}" && -z "${SLURM_ARRAY_TASK_MIN+x}" && \
    -z "${SLURM_ARRAY_TASK_MAX+x}" && -z "${SLURM_ARRAY_TASK_STEP+x}" ]] ||
    fail_deployment "the administrative submission job must not be an array"
[[ -z "${SLURM_RESTART_COUNT+x}" || "$SLURM_RESTART_COUNT" == "0" ]] ||
    fail_deployment "the administrative submission job must not restart"

[[ "$#" -eq 1 ]] || fail_deployment "expected one authorization directory"
authorization_directory="$1"
is_normalized_absolute_path "$authorization_directory" ||
    fail_deployment "authorization directory is not an absolute normalized path"
path_is_within_limit "$authorization_directory" ||
    fail_deployment "authorization directory path is too long"
home_anchor="${HOME:-}"
is_normalized_absolute_path "$home_anchor" ||
    fail_deployment "the home trust anchor is not an absolute normalized path"
path_is_within_limit "$home_anchor" || fail_deployment "the home trust anchor path is too long"
[[ "$home_anchor" != [[:space:]]* && "$home_anchor" != *[[:space:]] ]] ||
    fail_deployment "the home trust anchor has boundary whitespace"
[[ -d "$home_anchor" && ! -L "$home_anchor" && -x "$home_anchor" ]] ||
    fail_deployment "the home trust anchor is unavailable, linked, or unsearchable"
check_directory_chain "$authorization_directory" "$home_anchor"
read_metadata "$authorization_directory"
[[ "$metadata_owner" == "$EUID" && "$metadata_mode" == "700" ]] ||
    fail_deployment "authorization directory must be current-user mode 0700"
[[ -r "$authorization_directory" && -w "$authorization_directory" && -x "$authorization_directory" ]] ||
    fail_deployment "authorization directory has unusable owner permissions"

runtime_python_file="$authorization_directory/runtime-python.path"
path_is_within_limit "$runtime_python_file" ||
    fail_deployment "runtime-python.path is too long"
[[ -f "$runtime_python_file" ]] ||
    fail_deployment "runtime-python.path is unavailable"
[[ ! -L "$runtime_python_file" ]] ||
    fail_deployment "runtime-python.path must not be a symlink"
read_metadata "$runtime_python_file"
[[ "$metadata_owner" == "$EUID" && "$metadata_mode" == "600" && "$metadata_links" == "1" ]] ||
    fail_deployment "runtime-python.path must be current-user mode 0600 and single-link"
(( metadata_size >= 2 && metadata_size <= 4096 )) ||
    fail_deployment "runtime-python.path has an invalid size"
sidecar_device="$metadata_device"
sidecar_inode="$metadata_inode"
sidecar_size="$metadata_size"
[[ -r "$runtime_python_file" && -w "$runtime_python_file" && ! -x "$runtime_python_file" ]] ||
    fail_deployment "runtime-python.path has unusable owner permissions"

exec 3<"$runtime_python_file" || fail_deployment "runtime-python.path cannot be opened"
IFS= read -r python <&3 || fail_deployment "runtime-python.path is not one LF-terminated line"
extra=""
if IFS= read -r extra <&3 || [[ -n "$extra" ]]; then
    fail_deployment "runtime-python.path contains more than one line"
fi
exec 3<&-
sidecar_has_exact_line_size ||
    fail_deployment "runtime-python.path is not exactly one path plus LF"
read_metadata "$runtime_python_file"
[[ "$metadata_owner" == "$EUID" && "$metadata_mode" == "600" && \
    "$metadata_links" == "1" && "$metadata_size" == "$sidecar_size" && \
    "$metadata_device" == "$sidecar_device" && "$metadata_inode" == "$sidecar_inode" ]] ||
    fail_deployment "runtime-python.path changed while being read"

is_normalized_absolute_path "$python" ||
    fail_deployment "runtime Python is not an absolute normalized path"
path_is_within_limit "$python" || fail_deployment "runtime Python path is too long"
python_parent="${python%/*}"
[[ -n "$python_parent" ]] || python_parent="/"
check_directory_chain "$python_parent" "$home_anchor"
[[ -f "$python" ]] || fail_deployment "runtime Python is unavailable"
[[ ! -L "$python" ]] || fail_deployment "runtime Python must not be a symlink"
read_metadata "$python"
[[ "$metadata_owner" == "$EUID" && "$metadata_links" == "1" ]] ||
    fail_deployment "runtime Python must be current-user-owned and single-link"
mode_has_no_group_or_world_write "$metadata_mode" ||
    fail_deployment "runtime Python is group- or world-writable"
(( metadata_size >= 1 && metadata_size <= 134217728 )) ||
    fail_deployment "runtime Python has an invalid size"
[[ -r "$python" && -x "$python" ]] || fail_deployment "runtime Python is not executable"

export LANG=C
export LC_ALL=C
exec "$python" -I -B -u -X utf8 -m tetris_ballistic_pre_one_cell_bootstrap \
  submit \
  --authorization "$authorization_directory" --execute
