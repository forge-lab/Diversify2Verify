#!/usr/bin/env python3
"""
Run Stage 2A Why3 array implementation generation with Codex.

This script takes one original normalized `.array.json` benchmark and the
corresponding Stage 1A Why3 array specification `.mlw` file and asks Codex
to generate executable Stage 2A implementations with runnable tests.

It supports two independent implementation modes:

  --recursive    Use the why3_array_recursive_implementation skill.
  --imperative   Use the why3_array_imperative_implementation skill.

You may pass either flag or both flags.

Examples:

  # Generate only the recursive implementation.
  python3 scripts/run_stage2a_array_codex.py \
    output/2200/foo/normalised/input/foo_array.array.json \
    output/2200/foo/generated/why3/array/foo_array.mlw \
    --recursive \
    --out-dir codex-runs/stage2a-array \
    --model gpt-5.5

  # Generate only the imperative implementation.
  python3 scripts/run_stage2a_array_codex.py \
    output/2200/foo/normalised/input/foo_array.array.json \
    output/2200/foo/generated/why3/array/foo_array.mlw \
    --imperative \
    --out-dir codex-runs/stage2a-array \
    --model gpt-5.5

  # Generate both implementations.
  python3 scripts/run_stage2a_array_codex.py \
    output/2200/foo/normalised/input/foo_array.array.json \
    output/2200/foo/generated/why3/array/foo_array.mlw \
    --recursive \
    --imperative \
    --out-dir codex-runs/stage2a-array \
    --model gpt-5.5

Expected output layout, for input `sorted_array.mlw`:

  <out-dir>/sorted_array/recursive/
    prompt.md
    codex.stdout.jsonl
    codex.stderr.log
    codex.final.md
    generated/
      plans/array/sorted_array.recursive.plan.md
      why3/array/sorted_array_recursive.mlw
      reports/typecheck/sorted_array_recursive.typecheck.txt
      reports/execute/sorted_array_recursive.execute.txt

  <out-dir>/sorted_array/imperative/
    prompt.md
    codex.stdout.jsonl
    codex.stderr.log
    codex.final.md
    generated/
      plans/array/sorted_array.imperative.plan.md
      why3/array/sorted_array_imperative.mlw
      reports/typecheck/sorted_array_imperative.typecheck.txt
      reports/execute/sorted_array_imperative.execute.txt

The generated implementation files should be executable Why3 files with a
`run_tests () : bool` function. The Codex prompt instructs the agent to run:

  why3 prove --type-only <generated-file>.mlw
  why3 execute <generated-file>.mlw --use=<ModuleName> 'run_tests ()'

and to repair syntax/type/test failures up to the skill's bounded repair budget.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


@dataclass(frozen=True)
class StyleConfig:
    style: str
    skill_name: str
    output_suffix: str
    plan_suffix: str
    prompt_label: str


STYLES: dict[str, StyleConfig] = {
    "recursive": StyleConfig(
        style="recursive",
        skill_name="why3_array_recursive_implementation",
        output_suffix="_recursive.mlw",
        plan_suffix=".recursive.plan.md",
        prompt_label="recursive",
    ),
    "imperative": StyleConfig(
        style="imperative",
        skill_name="why3_array_imperative_implementation",
        output_suffix="_imperative.mlw",
        plan_suffix=".imperative.plan.md",
        prompt_label="imperative",
    ),
}


def require_existing_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise SystemExit(f"error: {label} does not exist: {resolved}")
    if not resolved.is_file():
        raise SystemExit(f"error: {label} is not a file: {resolved}")
    return resolved


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise SystemExit(f"error: could not read {path} as UTF-8")


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"error: input JSON does not exist: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"error: invalid JSON in {path}: {e}") from e

    if not isinstance(data, dict):
        raise SystemExit(f"error: expected top-level JSON object in {path}")
    return data


def extract_json_test_count(data: dict[str, Any], path: Path) -> int:
    tests = data.get("tests")
    if not isinstance(tests, list):
        raise SystemExit(f"error: {path} is missing or has invalid top-level field `tests`")
    return len(tests)


def rel_or_abs(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def make_run_root(out_dir: Path, input_stem: str, use_timestamp: bool) -> Path:
    if use_timestamp:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        return out_dir / f"{input_stem}-{stamp}"
    base = out_dir / input_stem
    if not base.exists():
        return base
    # Avoid reusing a previous run root so stale artifacts from earlier runs are never
    # treated as current outputs.
    i = 1
    while True:
        candidate = out_dir / f"{input_stem}-{i:03d}"
        if not candidate.exists():
            return candidate
        i += 1
    return out_dir / input_stem


def sanitize_stem(stem: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "stage2a_array"


def derive_input_stem(stage1a_mlw: Path, repo_root: Path) -> str:
    resolved = stage1a_mlw.resolve()
    try:
        rel = resolved.relative_to(repo_root.resolve())
    except ValueError:
        rel = resolved
    stem_source = rel.with_suffix("").as_posix().replace("/", "_").replace("\\", "_")
    hashed = hashlib.sha1(str(rel).encode("utf-8")).hexdigest()[:8]
    base = sanitize_stem(stem_source)
    return f"{base}_{hashed}"


def extract_first_module_name(mlw_text: str) -> str | None:
    m = re.search(r"(?m)^\s*module\s+([A-Za-z_][A-Za-z0-9_']*)\b", mlw_text)
    return m.group(1) if m else None


def extract_val_names(mlw_text: str) -> list[str]:
    names = re.findall(r"(?m)^\s*val\s+([A-Za-z_][A-Za-z0-9_']*)\b", mlw_text)
    # Preserve order, remove duplicates.
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name not in seen:
            out.append(name)
            seen.add(name)
    return out


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_prompt(
    *,
    style_config: StyleConfig,
    benchmark_json: Path,
    stage1a_mlw: Path,
    repo_root: Path,
    run_dir: Path,
    expected_plan: Path,
    expected_mlw: Path,
    typecheck_log: Path,
    execute_log: Path,
    json_test_count: int,
    min_test_count: int,
    max_suspect_test_failures: int,
    max_repair_iterations: int,
) -> str:
    mlw_text = read_text(stage1a_mlw)
    module_name = extract_first_module_name(mlw_text)
    val_names = extract_val_names(mlw_text)

    benchmark_for_prompt = rel_or_abs(benchmark_json, repo_root)
    stage1a_for_prompt = rel_or_abs(stage1a_mlw, repo_root)
    run_for_prompt = rel_or_abs(run_dir, repo_root)
    plan_for_prompt = rel_or_abs(expected_plan, repo_root)
    mlw_for_prompt = rel_or_abs(expected_mlw, repo_root)
    typecheck_for_prompt = rel_or_abs(typecheck_log, repo_root)
    execute_for_prompt = rel_or_abs(execute_log, repo_root)

    discovered_module = module_name if module_name is not None else "<not detected>"
    discovered_vals = ", ".join(val_names) if val_names else "<not detected>"

    return f"""Use the `.agents/skills/{style_config.skill_name}` skill.

Generate a Stage 2A Why3 array {style_config.prompt_label} implementation from this Stage 1A Why3 specification file:

- Input benchmark JSON: `{benchmark_for_prompt}`
- Input Stage 1A `.mlw`: `{stage1a_for_prompt}`
- Detected input module: `{discovered_module}`
- Detected abstract `val` target(s): `{discovered_vals}`
- Declared benchmark test count: `{json_test_count}`
- Minimum Stage 2A test count: `{min_test_count}`
- Suspect failing tests tolerated for triage: `{max_suspect_test_failures}`

Important output rule:

Use this run output root:

`{run_for_prompt}`

Do not write generated Stage 2A outputs outside that output root.

Create exactly these primary output files:

1. PLAN:
   `{plan_for_prompt}`

2. Why3 Stage 2A implementation file:
   `{mlw_for_prompt}`

Also write command outputs to:

3. Type-check log:
   `{typecheck_for_prompt}`

4. Executable test log:
   `{execute_for_prompt}`

Generation requirements:

- Read the benchmark JSON from the input path and Stage 1A Why3 from its input path.
- Use at least `{min_test_count}` concrete test cases from the benchmark JSON `tests` list to drive
  executable coverage in `run_tests ()` when enough tests exist.
- If the JSON has fewer than `{min_test_count}` tests, use all available tests and
  note that all available tests were already consumed.
- Do not invent tests or alter expected outputs.
- Extract the target function name, argument types, return type, intended behavior, and examples from the Stage 1A file.
- Generate a {style_config.prompt_label} implementation.
- Replace the abstract `val` declaration for the target function with an executable `let`.
- Do not copy proof artifacts from Stage 1A into the implementation. Specifically omit `lemma`, `axiom`, and `goal` declarations unless one is strictly needed for executable compilation.
- Do not add full correctness `ensures` contracts unless they are already necessary for type checking.
- Keep or adapt useful predicates only if they help preserve context; executable tests must be ordinary `let` functions returning `bool`, not lemmas.
- Add a `run_tests () : bool` function.
- Convert concrete examples from proof-style lemma tests into executable tests.
- Do not use `init 0 [||]`; use `make 0 0` for empty arrays.
- For Boolean-returning functions, avoid tests of the form `f a = true` or `f a = false`; use `f a` and `not (f a)`.
- For non-Boolean-returning functions, bind the result before comparing, e.g. `let r = f a x in r = expected`.
- Use examples in `.agents/skills/{style_config.skill_name}/examples/` as style references if available.

Failure triage rule:

1. If executable tests fail with only a small number of bad concrete examples (at most
   `{max_suspect_test_failures}` failing cases), assume test noise is possible.
2. Re-examine each failing example against the benchmark JSON and Stage 1A spec for internal consistency.
3. If a failing case looks incorrect or ambiguous, replace it with an unused benchmark example.
4. Keep coverage at least `{min_test_count}` tests, unless the benchmark has fewer tests available.
5. If all failing examples are correct, repair the implementation/tests as normal.

Required validation loop:

1. Run syntax/type checking first:

   `why3 prove --type-only {mlw_for_prompt}`

   Save output to `{typecheck_for_prompt}`.

2. Only if type checking succeeds, run executable tests:

   `why3 execute {mlw_for_prompt} --use=<GeneratedModuleName> 'run_tests ()'`

   Save output to `{execute_for_prompt}`.

3. If type checking fails, repair the file and retry.
4. If executable tests fail or `run_tests ()` does not evaluate to `true`, repair the implementation or tests and retry.
5. Use one initial generation plus {max_repair_iterations} repair iterations, for {max_repair_iterations + 1} total attempts.
6. Stop as soon as both commands succeed.
7. If no valid implementation is found within the repair budget, stop and report the failure clearly.

Do not run full verification.
Do not call `scripts/why3-verify.sh` unless explicitly asked; this Stage 2A run is type-check plus executable tests only.

At the end, provide a short final summary with:
- generated Why3 file path,
- type-check command and status,
- execute command and status,
- whether repair was needed,
- if repair budget was exhausted, the final failing command and error.
"""


def run_codex(
    *,
    codex_bin: str,
    repo_root: Path,
    add_dirs: list[Path],
    prompt_path: Path,
    final_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    model: str | None,
    sandbox: str,
    ask_for_approval: str,
    json_events: bool,
    reasoning_effort: str | None,
    skip_git_repo_check: bool,
    extra_args: list[str],
    timeout: int | None,
    dry_run: bool,
) -> int:
    cmd: list[str] = [codex_bin]

    if model:
        cmd.extend(["--model", model])

    if ask_for_approval:
        cmd.extend(["--ask-for-approval", ask_for_approval])

    if reasoning_effort:
        cmd.extend(["-c", f"reasoning.effort={reasoning_effort}"])

    cmd.append("exec")

    cmd.extend(
        [
            "--cd",
            str(repo_root),
            "--sandbox",
            sandbox,
        ]
    )

    for add_dir in add_dirs:
        cmd.extend(["--add-dir", str(add_dir)])

    cmd.extend(["--output-last-message", str(final_path)])

    if json_events:
        cmd.append("--json")

    if skip_git_repo_check:
        cmd.append("--skip-git-repo-check")

    cmd.extend(extra_args)
    cmd.append("-")  # read prompt from stdin

    print("Codex command:")
    print("  " + shlex.join(cmd))
    print(f"Prompt: {prompt_path}")
    print(f"stdout log: {stdout_path}")
    print(f"stderr log: {stderr_path}")
    print(f"final message: {final_path}")

    if dry_run:
        print("\nDry run: not invoking Codex.")
        return 0

    prompt = prompt_path.read_text(encoding="utf-8")

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        raise SystemExit(
            f"error: could not find Codex executable {codex_bin!r}. "
            "Install Codex or pass --codex-bin."
        )
    except subprocess.TimeoutExpired as e:
        stdout_path.write_text(e.stdout or "", encoding="utf-8")
        stderr_path.write_text(e.stderr or "", encoding="utf-8")
        print(f"error: Codex timed out after {timeout} seconds", file=sys.stderr)
        return 124

    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")

    return proc.returncode


def run_one_style(
    *,
    style_config: StyleConfig,
    benchmark_json: Path,
    stage1a_mlw: Path,
    repo_root: Path,
    run_root: Path,
    input_stem: str,
    json_test_count: int,
    args: argparse.Namespace,
) -> int:
    run_dir = (run_root / style_config.style).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    expected_mlw = run_dir / "generated" / "why3" / "array" / f"{input_stem}{style_config.output_suffix}"
    expected_plan = run_dir / "generated" / "plans" / "array" / f"{input_stem}{style_config.plan_suffix}"
    typecheck_log = run_dir / "generated" / "reports" / "typecheck" / f"{input_stem}{style_config.output_suffix.removesuffix('.mlw')}.typecheck.txt"
    execute_log = run_dir / "generated" / "reports" / "execute" / f"{input_stem}{style_config.output_suffix.removesuffix('.mlw')}.execute.txt"

    prompt_path = run_dir / "prompt.md"
    final_path = run_dir / "codex.final.md"
    stdout_path = run_dir / ("codex.stdout.jsonl" if not args.no_json else "codex.stdout.log")
    stderr_path = run_dir / "codex.stderr.log"

    prompt = build_prompt(
        style_config=style_config,
        benchmark_json=benchmark_json,
        stage1a_mlw=stage1a_mlw,
        repo_root=repo_root,
        run_dir=run_dir,
        expected_plan=expected_plan,
        expected_mlw=expected_mlw,
        typecheck_log=typecheck_log,
        execute_log=execute_log,
        json_test_count=json_test_count,
        min_test_count=args.min_test_count,
        max_suspect_test_failures=args.max_suspect_test_failures,
        max_repair_iterations=args.max_repair_iterations,
    )
    write_text(prompt_path, prompt)

    add_dirs = [run_dir]
    if not is_relative_to(stage1a_mlw, repo_root):
        add_dirs.append(stage1a_mlw.parent)
    if not is_relative_to(benchmark_json, repo_root):
        add_dirs.append(benchmark_json.parent)

    # Deduplicate while preserving order.
    deduped_add_dirs: list[Path] = []
    seen: set[Path] = set()
    for p in add_dirs:
        rp = p.resolve()
        if rp not in seen:
            deduped_add_dirs.append(rp)
            seen.add(rp)

    model = args.model if args.model.strip() else None

    print(f"\n=== Running Stage 2A {style_config.style} implementation ===")

    rc = run_codex(
        codex_bin=args.codex_bin,
        repo_root=repo_root,
        add_dirs=deduped_add_dirs,
        prompt_path=prompt_path,
        final_path=final_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        model=model,
        sandbox=args.sandbox,
        ask_for_approval=args.ask_for_approval,
        json_events=not args.no_json,
        reasoning_effort=args.reasoning_effort,
        skip_git_repo_check=args.skip_git_repo_check,
        extra_args=args.codex_arg,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )

    print("\nRun directory:")
    print(f"  {run_dir}")
    print("Expected generated files:")
    print(f"  PLAN: {expected_plan} [{'ok' if expected_plan.exists() else 'missing'}]")
    print(f"  MLW : {expected_mlw} [{'ok' if expected_mlw.exists() else 'missing'}]")
    print(f"  TYPE: {typecheck_log} [{'ok' if typecheck_log.exists() else 'missing'}]")
    print(f"  EXEC: {execute_log} [{'ok' if execute_log.exists() else 'missing'}]")

    if rc != 0:
        print(f"\nCodex exited with code {rc}. See logs in {run_dir}.", file=sys.stderr)
        return rc

    if not args.dry_run and not args.allow_missing_files:
        missing = [p for p in [expected_plan, expected_mlw] if not p.exists()]
        if missing:
            print("\nerror: Codex completed but expected files are missing:", file=sys.stderr)
            for p in missing:
                print(f"  {p}", file=sys.stderr)
            print("Use --allow-missing-files to ignore this check.", file=sys.stderr)
            return 2

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Codex Stage 2A array Why3 implementation generation from one Stage 1A .mlw spec."
    )
    parser.add_argument(
        "benchmark_json",
        type=Path,
        help="Path to the original normalized .array.json benchmark.",
    )
    parser.add_argument(
        "stage1a_mlw",
        type=Path,
        help="Path to one Stage 1A Why3 array specification .mlw file.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Generate a recursive Stage 2A implementation using the why3_array_recursive_implementation skill.",
    )
    parser.add_argument(
        "--imperative",
        action="store_true",
        help="Generate an imperative Stage 2A implementation using the why3_array_imperative_implementation skill.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("codex-runs/stage2a-array"),
        help="Directory where prompts, logs, and generated outputs are written.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root passed to `codex exec --cd`.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.5",
        help="Codex model passed via `--model`. Use empty string to rely on Codex config.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "xhigh"],
        default=None,
        help=(
            "Reasoning effort level passed as `reasoning.effort`. "
            "Default uses Codex configuration."
        ),
    )
    parser.add_argument(
        "--reasoning-level",
        choices=["low", "medium", "high", "xhigh"],
        default=None,
        help=(
            "Alias for --reasoning-effort. Sets the Codex reasoning effort level."
        ),
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable name/path.",
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Codex sandbox mode.",
    )
    parser.add_argument(
        "--ask-for-approval",
        default="never",
        choices=["untrusted", "on-request", "never"],
        help="Approval policy for Codex commands.",
    )
    parser.add_argument(
        "--max-repair-iterations",
        type=int,
        default=4,
        help="Number of repair iterations after the initial generation. Default: 4, for 5 total attempts.",
    )
    parser.add_argument(
        "--max-suspect-test-failures",
        type=int,
        default=2,
        help=(
            "When executable tests fail, automatically triage at most this many failing examples as "
            "potentially incorrect benchmark tests and consider replacing them with unused cases."
        ),
    )
    parser.add_argument(
        "--default-test-count",
        "--min-test-count",
        dest="min_test_count",
        type=int,
        default=20,
        help="Minimum number of JSON tests to use in Stage 2A executable coverage. Default: 20. "
        "Use all available tests if fewer are provided.",
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Create a timestamped run directory instead of reusing <out-dir>/<input-stem>.",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Do not pass --json to Codex; stdout will be formatted text instead of JSONL.",
    )
    parser.add_argument(
        "--skip-git-repo-check",
        action="store_true",
        help="Pass --skip-git-repo-check to Codex.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Optional wall-clock timeout in seconds for each Codex process.",
    )
    parser.add_argument(
        "--codex-arg",
        action="append",
        default=[],
        help=(
            "Extra raw argument to append to `codex exec`. "
            "Repeat for flags and values, e.g. --codex-arg -c --codex-arg reasoning.effort='high'."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write prompts and print Codex commands, but do not run Codex.",
    )
    parser.add_argument(
        "--allow-missing-files",
        action="store_true",
        help="Do not fail if expected PLAN/Why3 files are missing after Codex exits.",
    )

    args = parser.parse_args(argv)

    if not args.recursive and not args.imperative:
        raise SystemExit("error: select at least one implementation mode: --recursive and/or --imperative")

    if args.max_repair_iterations < 0:
        raise SystemExit("error: --max-repair-iterations must be non-negative")
    if args.min_test_count <= 0:
        raise SystemExit("error: --min-test-count must be positive")
    if args.max_suspect_test_failures < 0:
        raise SystemExit("error: --max-suspect-test-failures must be non-negative")

    if args.reasoning_effort is not None and args.reasoning_level is not None:
        if args.reasoning_effort != args.reasoning_level:
            raise SystemExit(
                "error: --reasoning-effort and --reasoning-level disagree. "
                f"Got {args.reasoning_effort} vs {args.reasoning_level}."
            )

    benchmark_json = require_existing_file(args.benchmark_json, "Benchmark .json file")
    stage1a_mlw = require_existing_file(args.stage1a_mlw, "Stage 1A .mlw file")
    repo_root = args.repo_root.resolve()
    out_dir = args.out_dir.resolve()

    benchmark_data = load_json(benchmark_json)
    json_test_count = extract_json_test_count(benchmark_data, benchmark_json)

    if not repo_root.exists() or not repo_root.is_dir():
        raise SystemExit(f"error: repo root does not exist or is not a directory: {repo_root}")

    input_stem = derive_input_stem(stage1a_mlw, repo_root)

    # Prefer explicit reasoning-level alias over default behavior when provided.
    if args.reasoning_level is not None and args.reasoning_effort is None:
        args.reasoning_effort = args.reasoning_level
    run_root = make_run_root(out_dir, input_stem, args.timestamp).resolve()
    run_root.mkdir(parents=True, exist_ok=True)

    selected_styles: list[StyleConfig] = []
    if args.recursive:
        selected_styles.append(STYLES["recursive"])
    if args.imperative:
        selected_styles.append(STYLES["imperative"])

    exit_code = 0
    for style_config in selected_styles:
        rc = run_one_style(
            style_config=style_config,
            benchmark_json=benchmark_json,
            stage1a_mlw=stage1a_mlw,
            repo_root=repo_root,
            run_root=run_root,
            input_stem=input_stem,
            json_test_count=json_test_count,
            args=args,
        )
        if rc != 0 and exit_code == 0:
            exit_code = rc

    print("\nStage 2A run root:")
    print(f"  {run_root}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
