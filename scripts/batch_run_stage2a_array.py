#!/usr/bin/env python3
"""Run Stage 2A array generation across dataset-verified benchmarks.

This script discovers array instances under a verified dataset root and invokes
`run_stage2a_array_codex.py` with configurable flags.

Examples:
  python3 run_stage2a_array_verified.py \
    --modes imperative \
    --model gpt-5.4 --reasoning-effort medium \
    --out-imperative array-imperative

  python3 run_stage2a_array_verified.py \
    --modes recursive \
    --out-recursive array-recursive

  python3 run_stage2a_array_verified.py \
    --modes imperative recursive \
    --out-dir codex-runs/array \
    --reasoning-effort high
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR
DEFAULT_DATASET_ROOT = SCRIPT_DIR / "dataset-verified"
DEFAULT_STAGE2_SCRIPT = SCRIPT_DIR / "run_stage2a_array_codex.py"


def resolve_in_script_root(path: Path | None, default: Path) -> Path:
    if path is None:
        return default
    p = Path(path)
    return p if p.is_absolute() else (SCRIPT_DIR / p)


def discover_instances(array_root: Path):
    instances = []
    skipped = []

    for slug_dir in sorted((p for p in array_root.iterdir() if p.is_dir()), key=lambda p: p.name):
        json_files = sorted(slug_dir.glob("*.array.json"))
        if not json_files:
            skipped.append((slug_dir.name, "missing *.array.json"))
            continue

        if len(json_files) > 1:
            skipped.append((slug_dir.name, f"multiple JSON files: {[p.name for p in json_files]}"))
            continue

        mlw_files = sorted(slug_dir.glob("*.mlw"))
        if not mlw_files:
            skipped.append((slug_dir.name, "missing *.mlw"))
            continue

        array_mlw = [p for p in mlw_files if p.name.endswith("_array.mlw")]
        if len(array_mlw) == 1:
            mlw_file = array_mlw[0]
        elif len(array_mlw) > 1:
            skipped.append((slug_dir.name, f"ambiguous Stage 1A files: {[p.name for p in mlw_files]}"))
            continue
        else:
            if len(mlw_files) > 1:
                skipped.append((slug_dir.name, f"ambiguous Stage 1A files: {[p.name for p in mlw_files]}"))
                continue
            mlw_file = mlw_files[0]

        instances.append((slug_dir.name, json_files[0].resolve(), mlw_file.resolve()))

    return instances, skipped


def build_command(
    *,
    stage2_script: Path,
    benchmark_json: Path,
    stage1a_mlw: Path,
    mode: str,
    out_dir: Path,
    args: argparse.Namespace,
) -> list[str]:
    cmd: list[str] = [
        sys.executable,
        str(stage2_script.resolve()),
        str(benchmark_json),
        str(stage1a_mlw),
        f"--{mode}",
        "--out-dir",
        str(out_dir),
        "--repo-root",
        str(args.repo_root),
        "--model",
        args.model,
    ]

    if args.reasoning_effort:
        cmd += ["--reasoning-effort", args.reasoning_effort]

    cmd += ["--min-test-count", str(args.min_test_count)]

    if args.max_repair_iterations is not None:
        cmd += ["--max-repair-iterations", str(args.max_repair_iterations)]

    if args.max_suspect_test_failures is not None:
        cmd += ["--max-suspect-test-failures", str(args.max_suspect_test_failures)]

    if args.timestamp:
        cmd.append("--timestamp")
    if args.no_json:
        cmd.append("--no-json")
    if args.skip_git_repo_check:
        cmd.append("--skip-git-repo-check")
    if args.allow_missing_files:
        cmd.append("--allow-missing-files")
    if args.timeout is not None:
        cmd += ["--timeout", str(args.timeout)]
    if args.sandbox:
        cmd += ["--sandbox", args.sandbox]
    if args.ask_for_approval:
        cmd += ["--ask-for-approval", args.ask_for_approval]
    if args.codex_arg:
        for item in args.codex_arg:
            cmd += ["--codex-arg", item]
    if args.dry_run:
        cmd.append("--dry-run")

    return cmd


def run_one(instance_slug: str, benchmark_json: Path, stage1a_mlw: Path, mode: str, out_dir: Path, args: argparse.Namespace) -> int:
    cmd = build_command(
        stage2_script=args.stage2_script,
        benchmark_json=benchmark_json,
        stage1a_mlw=stage1a_mlw,
        mode=mode,
        out_dir=out_dir,
        args=args,
    )

    print(f"[{instance_slug}] mode={mode}")
    print(f"  json: {benchmark_json}")
    print(f"  mlw:  {stage1a_mlw}")
    print(f"  out:  {out_dir}")
    print(f"  cmd: {shlex.join(cmd)}")

    started = time.perf_counter()
    result = subprocess.run(cmd)
    elapsed = time.perf_counter() - started
    print(f"  duration: {elapsed:.1f}s")
    print(f"  status: {'ok' if result.returncode == 0 else f'failed ({result.returncode})'}")
    return result.returncode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Stage 2A Codex array implementations over dataset-verified instances."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=None,
        help="Dataset root containing `array/` (default: dataset-verified in this directory).",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["imperative", "recursive"],
        default=["imperative"],
        help="Implementation modes to run. Default: imperative.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.4",
        help="Codex model passed to Stage 2A runner (default: gpt-5.4).",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "xhigh"],
        default="medium",
        help="reasoning.effort value for Codex.",
    )
    parser.add_argument(
        "--min-test-count",
        type=int,
        default=20,
        help="Minimum number of tests to include in Stage 2A runnable checks.",
    )
    parser.add_argument(
        "--max-repair-iterations",
        type=int,
        default=4,
        help="Repair iterations after the first generation in each run (default: 4).",
    )
    parser.add_argument(
        "--max-suspect-test-failures",
        type=int,
        default=2,
        help="Maximum suspicious failing tests considered for triage in Stage 2A runner (default: 2).",
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Pass --timestamp to each stage-2a run for unique run roots.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Shared output directory for all selected modes (optional).",
    )
    parser.add_argument(
        "--out-imperative",
        type=Path,
        default=None,
        help="Output directory for imperative mode (default: array-imperative).",
    )
    parser.add_argument(
        "--out-recursive",
        type=Path,
        default=None,
        help="Output directory for recursive mode (default: array-recursive).",
    )
    parser.add_argument(
        "--stage2-script",
        type=Path,
        default=None,
        help="Path to run_stage2a_array_codex.py (default: local artifact copy).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root passed to --repo-root in stage2 runner.",
    )
    parser.add_argument(
        "--skip-git-repo-check",
        action="store_true",
        help="Forward --skip-git-repo-check to stage2 runner.",
    )
    parser.add_argument(
        "--ask-for-approval",
        default="never",
        choices=["untrusted", "on-request", "never"],
        help="Forward --ask-for-approval to stage2 runner.",
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Forward --sandbox to stage2 runner.",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Pass --no-json to stage2 runner.",
    )
    parser.add_argument(
        "--allow-missing-files",
        action="store_true",
        help="Pass --allow-missing-files to stage2 runner.",
    )
    parser.add_argument(
        "--codex-arg",
        action="append",
        default=[],
        help="Extra --codex-arg value passed through to stage2 runner; can be repeated.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Per-run timeout in seconds passed to stage2 runner.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print all commands but do not invoke Codex.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop batch run after first failed instance/style.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="If set, skip instances when both expected mode outputs already exist for that slug.",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    args.dataset_root = resolve_in_script_root(args.dataset_root, DEFAULT_DATASET_ROOT).resolve()
    args.stage2_script = resolve_in_script_root(args.stage2_script, DEFAULT_STAGE2_SCRIPT).resolve()
    args.repo_root = resolve_in_script_root(args.repo_root, REPO_ROOT).resolve()

    if not args.dataset_root.exists():
        raise SystemExit(f"Dataset root not found: {args.dataset_root}")

    array_root = args.dataset_root / "array"
    if not array_root.is_dir():
        raise SystemExit(f"Expected array dataset dir: {array_root}")

    if not args.stage2_script.exists():
        raise SystemExit(f"Stage-2A script not found: {args.stage2_script}")

    if args.out_dir is not None:
        shared_out = resolve_in_script_root(args.out_dir, SCRIPT_DIR).resolve()
    else:
        shared_out = None

    out_imperative = resolve_in_script_root(args.out_imperative, SCRIPT_DIR / "array-imperative")
    out_recursive = resolve_in_script_root(args.out_recursive, SCRIPT_DIR / "array-recursive")

    if not shared_out is None:
        out_imperative = out_recursive = shared_out

    instances, skipped_discovery = discover_instances(array_root)

    if not instances:
        print(f"No processable instances found under {array_root}")
        return 1

    for slug, reason in skipped_discovery:
        print(f"skip: {slug} ({reason})")

    mode_outdir = {
        "imperative": out_imperative,
        "recursive": out_recursive,
    }

    total_steps = len(instances) * len(args.modes)
    total_runs = 0
    failures = 0
    executed = 0
    skipped_count = 0
    started = time.perf_counter()

    for instance_idx, (slug, benchmark_json, stage1a_mlw) in enumerate(instances, start=1):
        mode_outputs_missing = True
        for mode_idx, mode in enumerate(args.modes, start=1):
            step_idx = (instance_idx - 1) * len(args.modes) + mode_idx
            print(f"\n[{step_idx}/{total_steps}] ({(step_idx/total_steps)*100:.1f}%) slug={slug} mode={mode}")
            out_dir = mode_outdir[mode].resolve()

            if args.skip_existing and out_dir.exists():
                # Coarse skip check: only skip if the mode folder already has at least one run for this slug.
                marker = [
                    p
                    for p in out_dir.rglob(f"*{slug}*")
                    if p.is_file() and p.suffix in {".mlw", ".json"}
                ]
                if marker:
                    skipped_count += 1
                    print(f"[{slug}] skip {mode}: existing outputs found in {out_dir}")
                    continue

            total_runs += 1
            run_rc = run_one(
                instance_slug=slug,
                benchmark_json=benchmark_json,
                stage1a_mlw=stage1a_mlw,
                mode=mode,
                out_dir=out_dir,
                args=args,
            )
            mode_outputs_missing = False
            if run_rc != 0:
                failures += 1
                print(f"FAILED [{slug}] mode={mode} -> {run_rc}")
                if args.stop_on_error:
                    return 1
            else:
                executed += 1

        if args.skip_existing and mode_outputs_missing:
            print(f"[{slug}] nothing executed for selected modes")

    total_instances = len(instances)
    elapsed = time.perf_counter() - started
    print("\nBatch summary")
    print(f"instances discovered: {total_instances}")
    print(f"run modes: {len(instances) * len(args.modes)} planned")
    print(f"attempted: {total_runs}")
    print(f"succeeded: {executed}")
    print(f"failed: {failures}")
    print(f"skipped: {skipped_count}")
    print(f"overall elapsed: {elapsed:.1f}s")

    if skipped_discovery:
        print(f"skipped instances (discovery): {len(skipped_discovery)}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
