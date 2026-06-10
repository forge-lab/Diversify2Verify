#!/usr/bin/env python3
"""Run Stage 3A array final-verification across benchmark instances.

This script discovers array instances from a dataset root and invokes
`run_stage3a_array_codex.py` for each requested mode.
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
DEFAULT_DATASET_ROOT = SCRIPT_DIR / "dataset-final"
DEFAULT_STAGE3_SCRIPT = SCRIPT_DIR / "run_stage3a_array_codex.py"


def resolve_in_script_root(path: Path | None, default: Path | None = None) -> Path | None:
    if path is None:
        return default
    p = Path(path)
    return p if p.is_absolute() else (SCRIPT_DIR / p)


def discover_instances(instance_root: Path):
    instances = []
    skipped = []

    for slug_dir in sorted((p for p in instance_root.iterdir() if p.is_dir()), key=lambda p: p.name):
        stage1_root = slug_dir / "stage1" / "array"
        if not stage1_root.is_dir():
            skipped.append((slug_dir.name, "missing stage1/array directory"))
            continue

        json_files = sorted(stage1_root.glob("*.array.json"))
        if not json_files:
            skipped.append((slug_dir.name, "missing *.array.json"))
            continue
        if len(json_files) > 1:
            skipped.append((slug_dir.name, f"multiple *.array.json files: {[p.name for p in json_files]}"))
            continue

        mlw_files = sorted(stage1_root.glob("*_array.mlw"))
        if not mlw_files:
            skipped.append((slug_dir.name, "missing *_array.mlw"))
            continue
        if len(mlw_files) > 1:
            skipped.append((slug_dir.name, f"multiple array Stage 1A mlw files: {[p.name for p in mlw_files]}"))
            continue

        stage2a_root = slug_dir / "stage2a"
        if not stage2a_root.is_dir():
            skipped.append((slug_dir.name, "missing stage2a directory"))
            continue

        mode_map = {}
        for mode in ("imperative", "recursive"):
            impl_dir = stage2a_root / f"array-{mode}"
            impl_mlw = impl_dir / f"array-{mode}.mlw"
            if impl_mlw.exists():
                mode_map[mode] = impl_mlw.resolve()
            else:
                mode_map[mode] = None

        if not any(mode_map.values()):
            skipped.append((slug_dir.name, "missing Stage 3A Stage 2A implementation for both modes"))
            continue

        instances.append(
            (
                slug_dir.name,
                slug_dir,
                json_files[0].resolve(),
                mlw_files[0].resolve(),
                mode_map,
            )
        )

    return instances, skipped


def build_command(
    *,
    stage3_script: Path,
    benchmark_json: Path,
    stage1a_mlw: Path,
    stage2a_mlw: Path,
    mode: str,
    out_dir: Path,
    args: argparse.Namespace,
) -> list[str]:
    cmd: list[str] = [
        sys.executable,
        str(stage3_script.resolve()),
        str(benchmark_json),
        str(stage1a_mlw),
        str(stage2a_mlw),
        "--out-dir",
        str(out_dir),
        "--repo-root",
        str(args.repo_root),
        "--model",
        args.model,
    ]

    if args.reasoning_effort:
        cmd += ["--reasoning-effort", args.reasoning_effort]
    if args.max_repair_iterations is not None:
        cmd += ["--max-repair-iterations", str(args.max_repair_iterations)]
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
    if args.driver_verify_timeout is not None:
        cmd += ["--driver-verify-timeout", str(args.driver_verify_timeout)]
    if args.skip_driver_verify:
        cmd.append("--skip-driver-verify")
    if args.allow_verify_unavailable:
        cmd.append("--allow-verify-unavailable")
    if args.stage3_skill != "why3_array_verification":
        cmd += ["--stage3-skill", args.stage3_skill]
    if args.codex_bin != "codex":
        cmd += ["--codex-bin", args.codex_bin]
    if args.why3_bin != "why3":
        cmd += ["--why3-bin", args.why3_bin]
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


def run_one(instance_slug: str, benchmark_json: Path, stage1a_mlw: Path, stage2a_mlw: Path, mode: str, out_dir: Path, args: argparse.Namespace) -> int:
    cmd = build_command(
        stage3_script=args.stage3_script,
        benchmark_json=benchmark_json,
        stage1a_mlw=stage1a_mlw,
        stage2a_mlw=stage2a_mlw,
        mode=mode,
        out_dir=out_dir,
        args=args,
    )

    print(f"[{instance_slug}] mode={mode}")
    print(f"  json: {benchmark_json}")
    print(f"  mlw:  {stage1a_mlw}")
    print(f"  impl: {stage2a_mlw}")
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
        description="Run Stage 3A array Codex final-verification over dataset instances."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=None,
        help="Dataset root containing per-instance dirs (default: dataset-final in this directory).",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["imperative", "recursive"],
        default=["imperative", "recursive"],
        help="Output modes to run. Default: imperative recursive.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.5",
        help="Codex model passed to Stage 3A runner (default: gpt-5.5).",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "xhigh"],
        default="high",
        help="reasoning.effort value for Codex.",
    )
    parser.add_argument(
        "--reasoning-level",
        choices=["low", "medium", "high", "xhigh"],
        default=None,
        help="Alias for --reasoning-effort.",
    )
    parser.add_argument(
        "--max-repair-iterations",
        type=int,
        default=6,
        help="Repair iterations after the first generation in each run (default: 6).",
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Pass --timestamp to each Stage 3A run for unique run roots.",
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
        help="Output directory for imperative mode (default: <instance>/stage3a/array-imperative).",
    )
    parser.add_argument(
        "--out-recursive",
        type=Path,
        default=None,
        help="Output directory for recursive mode (default: <instance>/stage3a/array-recursive).",
    )
    parser.add_argument(
        "--stage3-script",
        type=Path,
        default=None,
        help="Path to run_stage3a_array_codex.py (default: local artifact copy).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root passed to `--repo-root` in Stage 3A runner.",
    )
    parser.add_argument(
        "--stage3-skill",
        default="why3_array_verification",
        help="Stage3 skill under .agents/skills (default: why3_array_verification).",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable used by Stage 3A runner.",
    )
    parser.add_argument(
        "--why3-bin",
        default="why3",
        help="Why3 executable used by Stage 3A runner.",
    )
    parser.add_argument(
        "--skip-git-repo-check",
        action="store_true",
        help="Pass --skip-git-repo-check to Stage 3A runner.",
    )
    parser.add_argument(
        "--ask-for-approval",
        default="never",
        choices=["untrusted", "on-request", "never"],
        help="Approval policy passed to Stage 3A runner.",
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Sandbox mode passed to Stage 3A runner.",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Pass --no-json to Stage 3A runner.",
    )
    parser.add_argument(
        "--allow-missing-files",
        action="store_true",
        help="Pass --allow-missing-files to Stage 3A runner.",
    )
    parser.add_argument(
        "--skip-driver-verify",
        action="store_true",
        help="Pass --skip-driver-verify to Stage 3A runner.",
    )
    parser.add_argument(
        "--allow-verify-unavailable",
        action="store_true",
        help="Pass --allow-verify-unavailable to Stage 3A runner.",
    )
    parser.add_argument(
        "--codex-arg",
        action="append",
        default=[],
        help="Extra --codex-arg value passed through to Stage 3A runner; can be repeated.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Per-run timeout in seconds for Stage 3A runner.",
    )
    parser.add_argument(
        "--driver-verify-timeout",
        type=int,
        default=None,
        help="Per-run timeout in seconds for driver-side why3 type-check.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands but do not invoke Codex.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop batch run after first failed instance/mode.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="If set, skip mode if a prior run for this instance+mode appears to exist.",
    )

    return parser.parse_args(argv)


def select_instance_root(dataset_root: Path) -> Path:
    if (dataset_root / "array").is_dir():
        return dataset_root / "array"
    return dataset_root


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    args.dataset_root = resolve_in_script_root(args.dataset_root, DEFAULT_DATASET_ROOT)
    if args.dataset_root is None:
        raise SystemExit("failed to resolve dataset root")
    args.dataset_root = args.dataset_root.resolve()

    args.stage3_script = resolve_in_script_root(args.stage3_script, DEFAULT_STAGE3_SCRIPT)
    if args.stage3_script is None:
        raise SystemExit("failed to resolve stage3 script")
    args.stage3_script = args.stage3_script.resolve()

    args.repo_root = resolve_in_script_root(args.repo_root, REPO_ROOT)
    if args.repo_root is None:
        raise SystemExit("failed to resolve repo root")
    args.repo_root = args.repo_root.resolve()

    if not args.dataset_root.exists():
        raise SystemExit(f"Dataset root not found: {args.dataset_root}")

    if not args.stage3_script.exists():
        raise SystemExit(f"Stage-3A script not found: {args.stage3_script}")

    instance_root = select_instance_root(args.dataset_root)
    if not instance_root.is_dir():
        raise SystemExit(f"Expected array dataset dir: {instance_root}")

    if args.reasoning_level is not None and args.reasoning_level != args.reasoning_effort:
        args.reasoning_effort = args.reasoning_level

    if args.out_dir is not None:
        shared_out = resolve_in_script_root(args.out_dir, SCRIPT_DIR)
        if shared_out is None:
            raise SystemExit("failed to resolve shared out directory")
        shared_out = shared_out.resolve()
    else:
        shared_out = None

    out_imperative = resolve_in_script_root(args.out_imperative, None)
    out_recursive = resolve_in_script_root(args.out_recursive, None)
    if out_imperative is not None:
        out_imperative = out_imperative.resolve()
    if out_recursive is not None:
        out_recursive = out_recursive.resolve()

    instances, skipped_discovery = discover_instances(instance_root)

    if not instances:
        print(f"No processable instances found under {instance_root}")
        return 1

    for slug, reason in skipped_discovery:
        print(f"skip: {slug} ({reason})")

    total_steps = len(instances) * len(args.modes)
    total_runs = 0
    failures = 0
    executed = 0
    skipped_count = 0
    started = time.perf_counter()

    for step_idx, (slug, slug_dir, benchmark_json, stage1a_mlw, mode_paths) in enumerate(instances, start=1):
        all_mode_missing = True
        for mode_idx, mode in enumerate(args.modes, start=1):
            global_step = (step_idx - 1) * len(args.modes) + mode_idx
            mode_progress = (global_step / total_steps) * 100
            print(f"\n[{global_step}/{total_steps}] ({mode_progress:.1f}%) slug={slug} mode={mode}")

            if shared_out is not None:
                out_dir = shared_out
            elif mode == "imperative" and out_imperative is not None:
                out_dir = out_imperative
            elif mode == "recursive" and out_recursive is not None:
                out_dir = out_recursive
            else:
                out_dir = slug_dir / "stage3a" / f"array-{mode}"

            out_dir = out_dir.resolve()

            impl_path = mode_paths.get(mode)
            if impl_path is None:
                skipped_count += 1
                print(f"[{slug}] skip {mode}: missing stage2a implementation file")
                continue

            if args.skip_existing and out_dir.exists():
                marker_stem = stage1a_mlw.with_suffix("").name
                marker = [
                    p
                    for p in out_dir.rglob("*.mlw")
                    if p.name.endswith("_stage3.mlw") and marker_stem in p.name
                ]
                if marker:
                    skipped_count += 1
                    print(f"[{slug}] skip {mode}: existing Stage 3A output found in {out_dir}")
                    continue

            total_runs += 1
            run_rc = run_one(
                instance_slug=slug,
                benchmark_json=benchmark_json,
                stage1a_mlw=stage1a_mlw,
                stage2a_mlw=impl_path,
                mode=mode,
                out_dir=out_dir,
                args=args,
            )
            all_mode_missing = False
            if run_rc != 0:
                failures += 1
                print(f"FAILED [{slug}] mode={mode} -> {run_rc}")
                if args.stop_on_error:
                    return 1
            else:
                executed += 1

        if args.skip_existing and all_mode_missing:
            print(f"[{slug}] nothing executed for selected modes")

    total_instances = len(instances)
    elapsed = time.perf_counter() - started
    print("\nBatch summary")
    print(f"instances discovered: {total_instances}")
    print(f"run modes: {total_instances * len(args.modes)} planned")
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
