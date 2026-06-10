# Scripts Artifact

This directory packages the main Diversify2Verify Codex/Why3 driver scripts in a single place.

The scripts here cover:

- Stage 1A contract generation
- Stage 2A implementation generation
- Stage 3A final verification generation
- Stage 1A and Stage 3 repair flows
- Offline Why3 verification
- Batch execution over dataset directories

## Files

### Single-run entrypoints

- `run_stage1a_array_codex.py`
- `run_stage1a_list_codex.py`
- `run_stage2a_array_codex.py`
- `run_stage2a_list_codex.py`
- `run_stage3a_array_codex.py`
- `run_stage3a_list_codex.py`

These are the main public entrypoints. They are compatibility wrappers around the corresponding `generate_*_single.py` implementations.

### Single-run implementations

- `generate_stage1a_array_single.py`
- `generate_stage1a_list_single.py`
- `generate_stage2a_array_single.py`
- `generate_stage2a_list_single.py`
- `generate_stage3a_array_single.py`
- `generate_stage3a_list_single.py`

These build prompts, create run directories, invoke `codex exec`, and write generated outputs and logs.

### Batch runners

- `batch_run_stage2a_array.py`
- `batch_run_stage2a_list.py`
- `batch_run_stage3a_array.py`
- `batch_run_stage3a_list.py`

These discover instances under dataset directories and call the single-run entrypoints repeatedly.

Default dataset roots:

- Stage 2A batch: `dataset-verified/`
- Stage 3A batch: `dataset-final/`

### Repair scripts

- `repair_stage1a.py`
- `repair_stage3_step1.py`
- `repair_stage3_step2.py`

These scripts copy failing inputs into a fresh run directory, build a repair prompt, run Codex, and write repaired Why3 files plus reports.

### Verification helper

- `why3-verify.sh`

This is the offline full-verification shell script. It emits `VERIFY_*` summary markers and should be used instead of inventing an alternate verification flow.

## Typical usage

Generate a single Stage 1A array spec:

```bash
python3 run_stage1a_array_codex.py path/to/input.array.json --out-dir codex-runs/stage1a-array
```

Generate a single Stage 2A list implementation:

```bash
python3 run_stage2a_list_codex.py path/to/input.list.json path/to/stage1a_list.mlw --imperative --out-dir codex-runs/stage2a-list
```

Generate a single Stage 3A array verification file:

```bash
python3 run_stage3a_array_codex.py path/to/input.array.json path/to/stage1a_array.mlw path/to/stage2a_array_impl.mlw --out-dir codex-runs/stage3a-array
```

Run full verification offline:

```bash
bash why3-verify.sh path/to/file.mlw
```

Run a batch Stage 2A array job:

```bash
python3 batch_run_stage2a_array.py --modes imperative recursive
```

Run a batch Stage 3A list job:

```bash
python3 batch_run_stage3a_list.py --modes imperative recursive
```

Repair a failing Stage 1A or Stage 3 file:

```bash
python3 repair_stage1a.py path/to/file.mlw path/to/verifier.log --kind array
python3 repair_stage3_step1.py path/to/file.mlw path/to/verifier.log --kind list
```

## Prerequisites

These scripts assume the following tools are available:

- `python3`
- `codex`
- `why3`

They also expect the local `.agents/` skill/reference tree to be present when prompts instruct Codex to use repository skills.

## Notes

- The `run_stage*_codex.py` files are the stable names to call.
- The `generate_*_single.py` files contain the actual logic.
- Batch scripts in this artifact are configured to use the local packaged runner files by default.
- Stage 1A and Stage 2A runs are type-check oriented; full verification is handled through `why3-verify.sh` when needed.
