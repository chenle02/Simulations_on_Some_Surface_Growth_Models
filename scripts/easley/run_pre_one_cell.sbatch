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
    metadata="$("$stat_executable" --printf='%u %a %h %s %d %i' -- "$path")" ||
        fail_deployment "path metadata cannot be read"
    IFS=' ' read -r metadata_owner metadata_mode metadata_links metadata_size \
        metadata_device metadata_inode extra <<<"$metadata"
    [[ -z "$extra" ]] || fail_deployment "path metadata is malformed"
    [[ "$metadata_owner" =~ ^(0|[1-9][0-9]*)$ ]] ||
        fail_deployment "path owner metadata is malformed"
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
    local remaining="${path#/}"
    local component=""
    local current=""
    [[ -d / && ! -L / && -x / ]] || fail_deployment "the filesystem root is unavailable"
    read_metadata /
    [[ "$metadata_owner" == "0" ]] || fail_deployment "the filesystem root has an untrusted owner"
    mode_has_no_group_or_world_write "$metadata_mode" ||
        fail_deployment "the filesystem root is group- or world-writable"
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
        [[ "$metadata_owner" == "$EUID" || "$metadata_owner" == "0" ]] ||
            fail_deployment "a path ancestor has an untrusted owner"
        mode_has_no_group_or_world_write "$metadata_mode" ||
            fail_deployment "a path ancestor is group- or world-writable"
    done
}

[[ "$#" -eq 1 ]] || fail_deployment "expected one authorization directory"
authorization_directory="$1"
is_normalized_absolute_path "$authorization_directory" ||
    fail_deployment "authorization directory is not an absolute normalized path"
path_is_within_limit "$authorization_directory" ||
    fail_deployment "authorization directory path is too long"
check_directory_chain "$authorization_directory"
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
check_directory_chain "$python_parent"
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

exec "$python" -I -B -u -X utf8 -m tetris_ballistic.scripts.run_pre_one_cell \
  --authorization "$authorization_directory" --execute
