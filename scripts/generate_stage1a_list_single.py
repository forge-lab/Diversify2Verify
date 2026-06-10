#!/usr/bin/env python3
"""
Run Stage 1A Why3 list contract generation with Codex.

This script takes one normalized Diversify2Verify `.list.json` benchmark,
builds a focused prompt for the `why3_list_contract_generation` skill, and
runs `codex exec` non-interactively.

Example:

  python3 scripts/run_stage1a_list_codex.py \
    benchmarks/lists/1385_find_the_distance_value_between_two_arrays.list.json \
    --out-dir codex-runs/stage1a-list \
    --model gpt-5.4 \
    --reasoning-effort medium

Expected output layout:

  <out-dir>/<run_id>/   (typically `<question_id>_<task_id>`)
    prompt.md
    codex.stdout.jsonl
    codex.stderr.log
    codex.final.md
    generated/
      plans/list/<task_id>.list.plan.md
      reports/typecheck/<task_id>.list.typecheck.txt
      why3/list/<file-from-target.output_file>

The generated Why3 file path is computed by prefixing the benchmark's
`target.output_file` with the per-task run directory.

Codex is asked to type-check and self-repair, but this driver also runs a final
authoritative `why3 prove --type-only` check after Codex exits, unless
`--skip-driver-typecheck` is used.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any


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


def require_dotted(data: dict[str, Any], dotted: str, path: Path) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise SystemExit(f"error: {path} is missing required field `{dotted}`")
        cur = cur[part]
    return cur


def require_list_benchmark(data: dict[str, Any], path: Path) -> None:
    target = data.get("target")
    if not isinstance(target, dict):
        raise SystemExit(f"error: {path} is missing object field `target`")

    if target.get("name") != "list":
        raise SystemExit(
            f"error: expected target.name == 'list' in {path}, "
            f"got {target.get('name')!r}"
        )

    if target.get("language") != "why3":
        raise SystemExit(
            f"error: expected target.language == 'why3' in {path}, "
            f"got {target.get('language')!r}"
        )

    required_fields = [
        "task.task_id",
        "task.question_id",
        "task.difficulty",
        "target.module_name",
        "target.output_file",
        "target.signature.raw",
        "target.signature.function_name",
        "target.signature.parameters",
        "target.signature.return",
        "problem.description",
        "tests",
        "normalization",
    ]

    for dotted in required_fields:
        require_dotted(data, dotted, path)

    if not isinstance(require_dotted(data, "task.task_id", path), str):
        raise SystemExit(f"error: {path}: expected `task.task_id` to be a string")

    if not isinstance(require_dotted(data, "target.module_name", path), str):
        raise SystemExit(f"error: {path}: expected `target.module_name` to be a string")

    if not isinstance(require_dotted(data, "target.output_file", path), str):
        raise SystemExit(f"error: {path}: expected `target.output_file` to be a string")

    if not isinstance(require_dotted(data, "target.signature.raw", path), str):
        raise SystemExit(f"error: {path}: expected `target.signature.raw` to be a string")

    if not isinstance(require_dotted(data, "target.signature.function_name", path), str):
        raise SystemExit(
            f"error: {path}: expected `target.signature.function_name` to be a string"
        )

    if not isinstance(require_dotted(data, "target.signature.parameters", path), list):
        raise SystemExit(
            f"error: {path}: expected `target.signature.parameters` to be a list"
        )

    if not isinstance(require_dotted(data, "target.signature.return", path), dict):
        raise SystemExit(
            f"error: {path}: expected `target.signature.return` to be an object"
        )

    if not isinstance(require_dotted(data, "problem.description", path), str):
        raise SystemExit(f"error: {path}: expected `problem.description` to be a string")

    if not isinstance(data.get("tests"), list):
        raise SystemExit(f"error: {path}: expected `tests` to be a list")

    if not isinstance(data.get("normalization"), dict):
        raise SystemExit(f"error: {path}: expected `normalization` to be an object")


def safe_task_id(data: dict[str, Any], json_path: Path) -> str:
    task = data.get("task", {})
    task_id = task.get("task_id") if isinstance(task, dict) else None
    if isinstance(task_id, str) and task_id.strip():
        return task_id.strip()
    return json_path.with_suffix("").name


def safe_run_id(data: dict[str, Any], json_path: Path) -> str:
    task = data.get("task", {})
    if not isinstance(task, dict):
        return safe_task_id(data, json_path)

    question_id = task.get("question_id")
    question_id_str = None
    if isinstance(question_id, str):
        question_id_str = question_id.strip()
    elif isinstance(question_id, int):
        question_id_str = str(question_id)

    task_id = task.get("task_id") if isinstance(task.get("task_id"), str) else None
    if isinstance(task_id, str):
        task_id = task_id.strip() or None

    if question_id_str and task_id:
        return f"{question_id_str}_{task_id}"
    if question_id_str:
        return question_id_str
    return task_id or safe_task_id(data, json_path)


def safe_path_component(value: str, *, fallback: str = "task") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or fallback


def safe_relative_path(raw: str, field_name: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        raise SystemExit(f"error: {field_name} must be relative, got absolute path: {raw}")
    if any(part == ".." for part in p.parts):
        raise SystemExit(f"error: {field_name} must not contain '..': {raw}")
    if str(p) in {"", "."}:
        raise SystemExit(f"error: {field_name} must name a file, got: {raw!r}")
    if p.suffix != ".mlw":
        raise SystemExit(f"error: {field_name} should end in .mlw, got: {raw}")
    return p


def make_run_dir(out_dir: Path, run_id: str, use_timestamp: bool) -> Path:
    if use_timestamp:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        return out_dir / f"{run_id}-{stamp}"
    return out_dir / run_id


def rel_or_abs(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())


def build_prompt(
    *,
    json_path: Path,
    repo_root: Path,
    run_dir: Path,
    data: dict[str, Any],
    expected_plan: Path,
    expected_mlw: Path,
    typecheck_log: Path,
    default_test_count: int,
) -> str:
    task_id = safe_task_id(data, json_path)
    target = data["target"]
    signature = target["signature"]
    normalization = data.get("normalization", {})
    tests = data.get("tests", [])

    # Use paths relative to repo root when possible; absolute paths are okay too.
    json_for_prompt = rel_or_abs(json_path, repo_root)
    run_for_prompt = rel_or_abs(run_dir, repo_root)
    plan_for_prompt = rel_or_abs(expected_plan, repo_root)
    mlw_for_prompt = rel_or_abs(expected_mlw, repo_root)
    typecheck_for_prompt = rel_or_abs(typecheck_log, repo_root)

    return f"""Use the `.agents/skills/why3_list_contract_generation` skill.

Before generating, open and follow:

`.agents/skills/why3_list_contract_generation/SKILL.md`

Also follow `AGENTS.md` if present. If there is any conflict:
1. the explicit paths in this prompt take precedence;
2. this Stage 1A prompt takes precedence over generic repository guidance;
3. the skill controls Why3 style and contract-generation details.

Do not modify `.agents/`, `AGENTS.md`, scripts, or benchmark JSON files.

Generate a Stage 1A Why3 list specification for this normalized benchmark JSON:

- Input JSON: `{json_for_prompt}`
- Task id: `{task_id}`
- Target module: `{target.get("module_name")}`
- Target function: `{signature.get("function_name")}`
- Target signature: `{signature.get("raw")}`
- Normalized test count: `{len(tests)}`
- Normalization test source: `{normalization.get("test_source")}`
- `allow_extra_tests`: `{normalization.get("allow_extra_tests")}`

Important output rule:

Use this run output root:

`{run_for_prompt}`

Do not write generated Stage 1A outputs outside that output root.

Create exactly these primary output files:

1. PLAN:
   `{plan_for_prompt}`

2. Why3 specification file:
   `{mlw_for_prompt}`

Also write the Why3 type-check output, if any, to:

`{typecheck_for_prompt}`

Generation requirements:

- Read the normalized JSON from the input path.
- Confirm `target.name = "list"` and `target.language = "why3"`.
- Read the Why3 references in `.agents/references/why3/`, especially:
  - `stdlib_policy.md`
  - `stdlib_int.md`
  - `stdlib_bool.md`
  - `stdlib_list.md`
- Inspect the examples in `.agents/skills/why3_list_contract_generation/examples/` if available.
- Generate a semantic Why3 specification from the problem description, not from the tests.
- Use the exact module name and function signature from the normalized JSON.
- Select 5 to 10 normalized tests; default to {default_test_count}.
- Do not invent tests.
- Do not parse any raw Python test string.
- Do not change expected outputs.
- Concrete test lemmas should primarily validate the generated specification predicates/functions.
- Use `let lemma` for concrete tests.
- Use intermediate `assert` statements to help recursive unfolding and quantifier instantiation.
- Prefer Why3 standard-library functions/predicates when available.
- Prefer `use` over `use import` unless importing names is necessary.
- For list traversal specs, prefer structural recursive definitions over array-style indexing.
- For occurrence-counting list specs, prefer `list.NumOcc.num_occ` when it is documented in `.agents/references/why3/stdlib_list.md` or already used in local examples. Otherwise use a transparent structural recursive helper.
- Keep recursive list definitions structurally decreasing and include variants when needed.
- Avoid using logical predicates as executable `if` guards.
- Avoid quantified formulas directly inside executable `if` guards.
- Type-check only with:

  `why3 prove --type-only {mlw_for_prompt}`

- If `why3` is unavailable, record that fact in `{typecheck_for_prompt}` and still produce the files.
- Do not run full verification.
- Do not call `scripts/why3-verify.sh` unless explicitly asked; this run is type-check only.

The Python driver will perform a final authoritative type-check after Codex exits, but you should still type-check and self-repair before finishing when `why3` is available.

At the end, provide a short final summary with:
- PLAN path
- Why3 file path
- type-check status
- selected test ids
"""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_codex(
    *,
    codex_bin: str,
    repo_root: Path,
    run_dir: Path,
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
            "--add-dir",
            str(run_dir),
            "--output-last-message",
            str(final_path),
        ]
    )

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


def run_typecheck(why3_bin: str, mlw_path: Path, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [why3_bin, "prove", "--type-only", str(mlw_path)]
    header = "Command:\n  " + shlex.join(cmd) + "\n\n"

    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except FileNotFoundError:
        log_path.write_text(
            header + f"why3 unavailable: could not find executable {why3_bin!r}\n",
            encoding="utf-8",
        )
        return 127

    body = proc.stdout or ""
    footer = f"\nExit code: {proc.returncode}\n"
    log_path.write_text(header + body + footer, encoding="utf-8")
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Codex Stage 1A list Why3 contract generation for one normalized .list.json benchmark."
    )
    parser.add_argument(
        "benchmark_json",
        type=Path,
        help="Path to one normalized .list.json benchmark.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("codex-runs/stage1a-list"),
        help="Directory where prompt, logs, and generated outputs are written.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root passed to `codex exec --cd`.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.4",
        help="Codex model passed via `--model`. Use empty string to rely on Codex config.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "xhigh"],
        default="medium",
        help="Reasoning effort level passed as `reasoning.effort`.",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable name/path.",
    )
    parser.add_argument(
        "--why3-bin",
        default="why3",
        help="Why3 executable used for final driver-side type-checking.",
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
        "--default-test-count",
        type=int,
        default=7,
        help="Default number of normalized tests to ask Codex to select; must be between 5 and 10.",
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
    help="Create a timestamped run directory instead of reusing <out-dir>/<run_id>.",
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
        help="Optional wall-clock timeout in seconds for the Codex process.",
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
        help="Write the prompt and print the Codex command, but do not run Codex.",
    )
    parser.add_argument(
        "--allow-missing-files",
        action="store_true",
        help="Do not fail if expected PLAN/Why3 files are missing after Codex exits.",
    )
    parser.add_argument(
        "--skip-driver-typecheck",
        action="store_true",
        help="Do not run the final driver-side `why3 prove --type-only` check.",
    )
    parser.add_argument(
        "--allow-why3-unavailable",
        action="store_true",
        help=(
            "If the final driver-side type-check cannot find Why3, record that in the "
            "type-check log but do not fail the script."
        ),
    )

    args = parser.parse_args(argv)

    if not (5 <= args.default_test_count <= 10):
        raise SystemExit("error: --default-test-count must be between 5 and 10")

    json_path = args.benchmark_json.resolve()
    repo_root = args.repo_root.resolve()
    out_dir = args.out_dir.resolve()

    data = load_json(json_path)
    require_list_benchmark(data, json_path)

    task_id = safe_task_id(data, json_path)
    run_id = safe_run_id(data, json_path)
    run_id_for_paths = safe_path_component(run_id)
    task_id_for_paths = safe_path_component(task_id)
    run_dir = make_run_dir(out_dir, run_id_for_paths, args.timestamp).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    target_output = safe_relative_path(data["target"]["output_file"], "target.output_file")
    expected_mlw = run_dir / target_output
    expected_plan = run_dir / "generated" / "plans" / "list" / f"{task_id_for_paths}.list.plan.md"
    typecheck_log = (
        run_dir
        / "generated"
        / "reports"
        / "typecheck"
        / f"{task_id_for_paths}.list.typecheck.txt"
    )

    prompt_path = run_dir / "prompt.md"
    final_path = run_dir / "codex.final.md"
    stdout_path = run_dir / ("codex.stdout.jsonl" if not args.no_json else "codex.stdout.log")
    stderr_path = run_dir / "codex.stderr.log"

    prompt = build_prompt(
        json_path=json_path,
        repo_root=repo_root,
        run_dir=run_dir,
        data=data,
        expected_plan=expected_plan,
        expected_mlw=expected_mlw,
        typecheck_log=typecheck_log,
        default_test_count=args.default_test_count,
    )
    write_text(prompt_path, prompt)

    model = args.model if args.model.strip() else None

    rc = run_codex(
        codex_bin=args.codex_bin,
        repo_root=repo_root,
        run_dir=run_dir,
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

    if rc != 0:
        print(f"\nCodex exited with code {rc}. See logs in {run_dir}.", file=sys.stderr)
        return rc

    if args.dry_run:
        return 0

    missing = [p for p in [expected_plan, expected_mlw] if not p.exists()]
    if missing and not args.allow_missing_files:
        print("\nerror: Codex completed but expected files are missing:", file=sys.stderr)
        for p in missing:
            print(f"  {p}", file=sys.stderr)
        print("Use --allow-missing-files to ignore this check.", file=sys.stderr)
        return 2

    if not args.skip_driver_typecheck:
        if not expected_mlw.exists():
            print(
                "\nwarning: skipping driver-side type-check because the expected MLW file is missing.",
                file=sys.stderr,
            )
        else:
            typecheck_rc = run_typecheck(args.why3_bin, expected_mlw, typecheck_log)
            print(f"\nDriver-side type-check log:")
            print(f"  {typecheck_log}")
            print(f"Driver-side type-check exit code: {typecheck_rc}")

            if typecheck_rc == 127 and args.allow_why3_unavailable:
                print("warning: Why3 unavailable; continuing because --allow-why3-unavailable was set.")
            elif typecheck_rc != 0:
                print(
                    f"\nerror: driver-side Why3 type-check failed. See {typecheck_log}",
                    file=sys.stderr,
                )
                return typecheck_rc
    else:
        print("\nDriver-side type-check skipped by --skip-driver-typecheck.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
