# PRE one-cell runner and Slurm authorization gate

## Status and safety boundary

This document specifies the provisional Slice 8B runner. The runner is generic
software infrastructure; it is not a campaign, launch approval, or instruction
to submit work.

Slice 8B development and its tests:

- do not contact Easley or a Slurm controller;
- do not invoke a real `sbatch` or `scontrol`;
- do not create an F0, P0, P1, B1, or B2 task;
- do not run an Article horizon or write under a declared campaign root; and
- do not create `CAMPAIGN`, `DEPLOYMENT`, `ADMISSION`, or `LAUNCH` authority.

Production execution remains impossible until separately committed, pushed,
read-back coordinator artifacts bind the exact Article protocol, pushed source
commit, transported wheel, campaign, isolated deployment certificate,
lane-specific admission, ordered task set, resources, user approval, and
single-use launch. A command-line flag, environment variable, valid wheel,
Easley account, or valid campaign file is never launch authority.

## Explicit Python API

The runner is deliberately absent from package-root exports:

```python
from tetris_ballistic.engine.one_cell_runner import (
    OneCellAuthorizedTask,
    OneCellLaunchAuthority,
    OneCellLaunchTask,
    OneCellRunnerAuthorizationError,
    OneCellRunnerOutcome,
    OneCellRunnerPaths,
    OneCellRunnerValidationError,
    OneCellSchedulerError,
    OneCellSlurmResourceEnvelope,
    OneCellSubmissionOutcome,
    authorize_one_cell_slurm_task,
    explain_one_cell_launch_task,
    list_one_cell_launch_tasks,
    load_one_cell_launch_authority,
    run_one_cell_authorized_task,
    submit_one_cell_launch,
)
```

The three errors are direct sibling `RuntimeError` subclasses. Every record is
a sealed, frozen, slotted, keyword-only exact type. Public functions reject
subclasses, partially initialized objects, mutated annotations/classes,
non-built-in primitives, mutable nested mappings, and stale snapshots.

The public operations are keyword-only:

```text
load_one_cell_launch_authority(*, authorization_path: str)
  -> OneCellLaunchAuthority

list_one_cell_launch_tasks(*, launch: OneCellLaunchAuthority)
  -> tuple[OneCellLaunchTask, ...]

explain_one_cell_launch_task(*, launch: OneCellLaunchAuthority,
                             array_position: int)
  -> bytes

authorize_one_cell_slurm_task(*, launch: OneCellLaunchAuthority,
                              submission_claim_bytes: bytes,
                              submission_receipt_bytes: bytes)
  -> OneCellAuthorizedTask

run_one_cell_authorized_task(*, authorization: OneCellAuthorizedTask)
  -> OneCellRunnerOutcome

submit_one_cell_launch(*, launch: OneCellLaunchAuthority)
  -> OneCellSubmissionOutcome
```

Runner dispositions are `complete`, `reused`, and `requeue-submitted`.
Submission returns only `accepted`; rejected or ambiguous scheduling raises
`OneCellSchedulerError` after preserving immutable evidence.

## Authority graph

The runner enforces this acyclic graph:

```text
PROTO + SOURCE + WHEEL + CAMPAIGN -> DEPLOYMENT
DEPLOYMENT + lane evidence        -> ADMISSION
ADMISSION + exact tasks/resources -> LAUNCH
LAUNCH                             -> one durable claim
claim + one sbatch observation     -> one immutable receipt
accepted receipt + Slurm element   -> authorized task
authorized task + durable state    -> final or one permitted requeue
```

Branch authority is required only for conditional P0 confirmation and the
selected P1 map. F0, initial P0, B1, and B2 task identities reject a branch
digest; B1 admission nevertheless requires the completed P0/branch evidence.
Pilot and canary completions are permanently excluded from inference.
The branch rule profile is exactly
`tetris-pre-one-cell-horizon-branch@1`; its input digest equals the committed
initial-P0 `final-manifests.jsonl` digest. The selected P1 task-map digest and
the `l_star`/confirmation fields must reproduce the corresponding Slice 8A
campaign records.

The exact production and fixture profiles, JSON key sets, evidence matrix,
resource caps, and coordinator locations are frozen by the coordinator
roadmap. The software parser accepts no aliases, schema upgrades, optional
unknown keys, claimed `pushed` flags, or mutable fallback paths.

## Authorization directory

The CLI accepts one absolute authorization directory containing exactly:

```text
launch.json
ordered-tasks.jsonl
readback.json
runtime-python.path
```

The directory is private runtime state, not a Git checkout. `launch.json` and
`ordered-tasks.jsonl` must equal their exact objects in a clean detached
coordinator clone at pushed `origin/main`. `readback.json` is a post-push
sidecar binding that commit and launch digest. `runtime-python.path` contains
one absolute UTF-8 interpreter path plus LF, at most 4,096 bytes total, and is bound by exact bytes, size,
digest, executable realpath, owner, mode, size, and digest.

Authority JSON is strict duplicate-aware compact sorted-key UTF-8 plus LF.
Task lists are strict canonical JSONL with one row per contiguous zero-based
array position. Each row retains the full no-LF Slice 8A scientific identity,
its digest, wave, role, task map/index, and deterministic task-relative path.
The loader reproduces every identity through
`explain_one_cell_campaign_task`; a duplicate identity, task directory, or
map/index fails closed.

The coordinator clone is inspected with a content-bound Git executable, an
empty/scrubbed environment, a fixed safe local-config inventory, disabled
fsmonitor/hooks/external diff/credentials/replacement refs, bounded output, and
read-only argv. Working-tree bytes and claimed clean/detached Booleans are not
trusted. Deployment, launch, readback, and live local config all bind the
main-only fetch refspec
`+refs/heads/main:refs/remotes/origin/main`; another source branch cannot be
mapped into the trusted `origin/main` name. The pushed coordinator launch must
descend the frozen Slice 8B authority commit
`087cdaf8d8444de7d9548bc1c97ca42f221cef27`, and the clean detached software
`SOURCE` must descend the frozen implementation parent
`b33cc0191298d80f0bdc944a3a5e444952873e37`.
The bootstrap Git executable must be owned by a trusted administrator other
than the current user; scheduler tools may use an explicitly allowed owner.
Before the first Git process, the loader uses the closest existing held parent
to preflight every claim/receipt/permit/result target and 32-hex publication
temporary, task and maximum attempt component, checkpoint/final target and
temporary, log template, and complete `sbatch`/`scontrol` argv member against
the effective filesystem component/path limits.

## Nonmutating inspection

The in-job CLI requires `--authorization ABS_DIR` and exactly one mode:

```text
--validate-only
--list-tasks
--explain-task ZERO_BASED_ARRAY_POSITION
--execute
```

The submission CLI permits only `--validate-only` or `--execute` with the same
required authorization argument. There are no positional shorthands or
scientific, path, resource, scheduler, environment, partition, account, or
retry overrides.

Validation writes `<launch-sha256>\n`; task listing writes the byte-identical
ordered JSONL; explanation writes the exact compact scientific identity plus
LF. These routes create no directory, install no handler, import no checkpoint
or Numba module, run no scheduler tool, and perform no numerical mutation.
Every inspection entry reconstructs its public campaign, ordered-task,
resource, path, and authority projections from the held canonical bytes;
effect-bearing entries additionally reload and authenticate the current
authorization directory before any persistent or scheduler action. Public
launch and authorization inputs are recursively cloned down
through campaign identities, task rows, resources, paths, and environment
tuples, so no caller-owned nested record remains aliased after entry.

Only the paired `tetris-pre-one-cell-launch-fixture@1` and
`tetris-pre-one-cell-admission-fixture@1` profiles exist. Each contains the
same frozen `scientific_execution_permitted: false` fixture object; all
supporting records retain their sole production schema spelling, and every
other `-fixture@1` spelling is invalid. The pair can be parsed for inspection,
but submit, Slurm authorization, and lifecycle paths refuse the fixture launch
before a scheduler call, checkpoint import, or persistent write. The generic
shell wrapper may start the certified interpreter; the Python CLI then
performs the same early refusal.

## Process and executable identity

Deployment and launch bind the exact Python, Git, `sbatch`, and `scontrol`
files. Paths must equal non-symlink realpaths; owner/mode/size/digest and
content-version identities are revalidated before use. Scheduler binaries are
never invoked for an identity probe: their version identity is
`content-sha256:<digest>`. Git alone uses its local `--version` route.

Scheduler-client subprocesses receive exactly:

```text
LANG=C
LC_ALL=C
```

No ambient `SBATCH_*`, `SLURM_CONF*`, account, QoS, dependency, export, or
routing variable is inherited. Git receives its separately frozen scrubbed
environment and local-config policy.

After required Slurm values are copied and validated, scientific execution
clears the process environment and installs only the deployment-rendered
locale, private temporary/Numba cache, CPU-thread, BLAS/OpenMP, and dynamic-
thread settings. It fixes the C locale before the first checkpoint/Numba
import. The batch wrapper starts Python with isolated imports, no bytecode,
unbuffered streams, and UTF-8 mode.

Every generated component is checked against both the 255-byte hard ceiling
and the held parent descriptor's `PC_NAME_MAX`; every rendered path and argv
member is checked against both 4,096 bytes and the relevant filesystem's
`PC_PATH_MAX`. The Article, software, and coordinator checkouts, mutable
campaign tree, authorization readback tree, runtime environment, and deployed
batch root are pairwise non-ancestor domains. Directory creation and ledger
operations retain and recheck no-follow descriptor chains so pathname swaps,
mount/inode changes, and symlink redirection cannot redirect a write.

## Single-use submission

Submission holds a descriptor-relative exclusive lock on the certified
private ledger. Before any scheduler subprocess it installs one mode-`0600`,
no-replace, file- and directory-fsynced claim keyed by the full launch digest,
then reads back the exact bytes. An existing or partial claim consumes the
launch and causes zero new scheduler calls.
Before that claim write, the held claims and receipts descriptors validate the
complete target names and the receipt's fixed-length 32-hex temporary-link
shape against both component and rendered-path limits. An impossible durable
receipt therefore refuses the launch before either the claim or `sbatch`.

The only initial scheduler argv is the contract-frozen, no-shell `sbatch`
array request. It includes one node/task, exact CPU/memory/wall/partition,
contiguous array and concurrency, `--requeue`, `--export=NIL`, append-only
logs, `B:USR1@900`, the bound generic batch script, and the authorization
directory. Account, QoS, mail, dependency, job-name, `--wrap`, PATH lookup,
federated cluster suffixes, and caller options are forbidden.

Stdout and stderr are incrementally drained. Each receipt stores at most the
first 8,192 bytes and an explicit overflow Boolean; observing another byte
makes the result unknown and terminates the child. Acceptance requires zero,
one bounded positive decimal job ID plus LF, empty stderr, and no overflow.
Completed positive nonzero return is rejected. Timeout, signal termination,
spawn ambiguity, malformed zero-return output, overflow, crash, or loss before
observation is unknown. All outcomes consume the claim; only accepted is
executable. There is no automatic initial-call replay.

The immutable receipt is published no-replace under the same held ledger lock:
the temporary file and its directory entry are fsynced to establish the guard,
the target is linked at link count two, the directory is fsynced to prove the
target, the temporary guard is unlinked, and the directory is fsynced again.
The in-job reader uses a bounded monotonic
60-second handshake and a shared lock so it cannot observe the legitimate
two-link publication interval or a target before the proving fsync. A crash
before guard unlink leaves a refused two-link target; after guard unlink the
target is already durable and single-link, while non-durable cleanup can only
restore the refused guard after reboot. Failure of the proving fsync removes
the target before the guard and fsyncs cleanup. Stable missing, malformed,
linked, mismatched, or contradictory state fails before task creation or
checkpoint import. Held authority and ledger
reads recheck named identity, size, timestamps, owner, mode, and link policy
after reading. Private-directory creation likewise rechecks every retained
private descriptor's owner and mode throughout the walk.

The private reconciliation parser validates only committed evidence under the
exact `tetris-pre-one-cell-submission-reconciliation@1` schema. It freezes both
replay permissions to false and `superseding_launch_required` to true; it has
no ledger mutation or scheduler route. A reconciled initial call therefore
still requires a separately approved superseding launch.

## Signal, lifecycle, and requeue

The top-level CLI dispatcher only materializes argv and selects an entry. For
`--execute`, the dedicated execute entry blocks `SIGUSR1` in its first
statement, before argument or authority parsing, and retains the prior mask.
After all authority, receipt, Slurm, path, restart, fixture, and lazy-import
gates, the runner installs a handler that only calls
`OneCellInterruptionFlag.request()` and unblocks atomically. A signal pending
during validation/receipt wait is delivered safely to the latch. The runner
blocks again, restores the prior handler, and restores the prior mask in every
`finally` path.

One array element maps to one exact Slice 7 task directory. The attempt ID and
Slurm IDs are operational only and never change scientific identity. The
runner advances checkpoint generations until `ready`, `requeue-required`, or
`terminal`; it publishes the sole final only after the final signal
linearization point and reuses only a checksum-valid final.

Before deliberate requeue, the runner reads back durable generation state,
releases the task lock, revalidates the exact array element and retry cap, and
publishes a no-replace permit containing the exact `scontrol` argv. It may then
call only:

```text
ABS_SCONTROL requeue ARRAY_JOB_ID_ARRAY_POSITION
```

The held permit and result descriptors first validate both target names and
the result's fixed-length 32-hex temporary-link shape. An impossible durable
result therefore refuses before the permit write or `scontrol`.

An automatic restart above zero may touch task state only when the exact prior
permit exists and has no clear-rejection result. Accepted, rejected, unknown,
missing, or publication-failed results never permit another `scontrol` call.

## Controlled exits

```text
0   nonmutating success, complete/reused final, accepted submission,
    or successful requeue handoff
64  CLI usage
65  invalid canonical or schema input
66  required member absent/incomplete or receipt handshake timeout
69  certified scheduler executable unavailable or clear rejection
70  unexpected private/runtime/checkpoint publisher invariant
74  filesystem I/O or durability failure
75  scheduler timeout/unknown result or accepted result lacking receipt
76  digest/integrity/authority/Slurm/receipt/permit contradiction
77  valid-but-refused authority, replay, retry cap, or ownership policy
78  deployment/interpreter/resource/environment mismatch
```

Successful execute is silent; accepted submission prints the array job ID plus
LF. Controlled failure has empty stdout and one bounded ASCII diagnostic with
no traceback.

## Packaging and deployment

`scripts/easley/run_pre_one_cell.sbatch` is inert deployment material. It has
no `#SBATCH` directive, campaign, account, queue, resources, module load,
activation, `PYTHONPATH`, Git command, directory creation, trap, or fallback
interpreter. It accepts one authorization directory, performs only feasible
private path/interpreter checks, and `exec`s the installed in-job module.

The wrapper is included exactly once in the source distribution and excluded
from the wheel. The Python runner and both module CLIs are included in the
wheel. No console entry point, package-root export, legacy runner edit, or
dependency change is introduced.

Installed-wheel tests use permanently ineligible authorities and private
mocked scheduler/lifecycle drivers. They cover strict parsing, exact argv and
environment construction, concurrent claims, crash points, bounded output,
receipt handshake, restart permits, signals, lazy imports, package inventory,
and the private width-3/terminal-769 lifecycle case. They never run a declared
campaign root or contact a scheduler.
