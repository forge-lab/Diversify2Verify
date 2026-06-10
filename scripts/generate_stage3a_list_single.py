#!/usr/bin/env python3
"""
Run Stage 3A Why3 list final-verification generation with Codex.

This script takes:

  1. one normalized Diversify2Verify `.list.json` benchmark,
  2. the corresponding Stage 1A Why3 list specification `.mlw`, and
  3. one Stage 2A Why3 list implementation `.mlw`,

and asks Codex to produce a final Stage 3A `.mlw` file that combines the
Stage 1A semantic specification with the Stage 2A implementation and adds only
what is needed for verification: contracts, loop invariants, variants,
intermediate assertions, and lemmas when genuinely necessary.

Design constraints enforced by the prompt:

  - do not change the Stage 1A semantic specification;
  - do not weaken or rewrite any Stage 1A target requires/ensures contract;
  - preserve Stage 1A semantic helper predicates/functions unless adding separate
    proved helper lemmas/facts;
  - do not change the implementation style from recursive to imperative or
    from imperative to recursive;
  - omit Stage 1A concrete test lemmas unless they are useful proof lemmas;
  - omit Stage 2A executable tests / `run_tests ()` from the final file;
  - use lemmas only when assertions/invariants/variants are not enough;
  - default to type-check only; full verification is handled externally/offline.

Example:

  python3 scripts/run_stage3a_list_codex.py \
    output/2200/foo/normalised/input/foo_list.list.json \
    output/2200/foo/generated/why3/list/foo_list.mlw \
    codex-runs/stage2a-list/foo/imperative/generated/why3/list/foo_list_imperative.mlw \
    --out-dir codex-runs/stage3a-list \
    --model gpt-5.5 \
    --reasoning-effort high

Expected output layout:

  <out-dir>/<input-stem>/
    prompt.md
    codex.stdout.jsonl
    codex.stderr.log
    codex.final.md
    generated/
      plans/list/<input-stem>.stage3.plan.md
      why3/list/<input-stem>_stage3.mlw
      reports/typecheck/<input-stem>_stage3.typecheck.txt
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Basic file / JSON helpers
# ---------------------------------------------------------------------------


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


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
        "target.module_name",
        "target.output_file",
        "target.signature.raw",
        "target.signature.function_name",
        "target.signature.parameters",
        "target.signature.return",
        "problem.description",
        "tests",
    ]
    for dotted in required_fields:
        require_dotted(data, dotted, path)

    if not isinstance(data.get("tests"), list):
        raise SystemExit(f"error: {path}: expected `tests` to be a list")


# ---------------------------------------------------------------------------
# Path / name helpers
# ---------------------------------------------------------------------------


def sanitize_stem(stem: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "stage3a_list"


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

    # Avoid accidental reuse of stale generated files.
    i = 1
    while True:
        candidate = out_dir / f"{input_stem}-{i:03d}"
        if not candidate.exists():
            return candidate
        i += 1


def derive_input_stem(stage1a_mlw: Path, stage2a_mlw: Path, repo_root: Path) -> str:
    def relish(path: Path) -> str:
        resolved = path.resolve()
        try:
            rel = resolved.relative_to(repo_root.resolve())
        except ValueError:
            rel = resolved
        return rel.with_suffix("").as_posix().replace("/", "_").replace("\\", "_")

    base = sanitize_stem(Path(stage1a_mlw).with_suffix("").name)
    if base in {"", "stage3a_list"}:
        base = sanitize_stem(relish(stage1a_mlw))

    digest_src = f"{relish(stage1a_mlw)}::{relish(stage2a_mlw)}"
    digest = hashlib.sha1(digest_src.encode("utf-8")).hexdigest()[:8]
    return f"{base}_stage3_{digest}"


# ---------------------------------------------------------------------------
# Lightweight Why3 source inspection
# ---------------------------------------------------------------------------


def extract_first_module_name(mlw_text: str) -> str | None:
    m = re.search(r"(?m)^\s*module\s+([A-Za-z_][A-Za-z0-9_']*)\b", mlw_text)
    return m.group(1) if m else None


def extract_val_names(mlw_text: str) -> list[str]:
    names = re.findall(r"(?m)^\s*val\s+([A-Za-z_][A-Za-z0-9_']*)\b", mlw_text)
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name not in seen:
            out.append(name)
            seen.add(name)
    return out


def extract_let_names(mlw_text: str) -> list[str]:
    names = re.findall(
        r"(?m)^\s*let\s+(?:rec\s+)?(?:function\s+)?([A-Za-z_][A-Za-z0-9_']*)\b",
        mlw_text,
    )
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name not in seen:
            out.append(name)
            seen.add(name)
    return out


def detect_implementation_style(mlw_text: str, target_function: str | None = None) -> str:
    """Best-effort classification used only to help Codex preserve style."""
    text = mlw_text
    target = re.escape(target_function) if target_function else r"[A-Za-z_][A-Za-z0-9_']*"

    if re.search(rf"(?m)^\s*let\s+rec\s+(?:function\s+)?{target}\b", text):
        return "recursive"

    imperative_markers = [
        r"\bwhile\b",
        r"\bfor\b",
        r"\bref\b",
        r":=",
    ]
    if any(re.search(p, text) for p in imperative_markers):
        return "imperative"

    # Non-recursive straight-line implementations are usually closer to the style
    # they came from than to either bucket. Codex still receives the source file.
    return "unknown"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_prompt(
    *,
    benchmark_json: Path,
    stage1a_mlw: Path,
    stage2a_mlw: Path,
    repo_root: Path,
    run_dir: Path,
    expected_plan: Path,
    expected_mlw: Path,
    typecheck_log: Path,
    data: dict[str, Any],
    stage3_skill: str,
    companion_array_skill: str,
    detected_stage1_module: str | None,
    detected_stage1_vals: list[str],
    detected_stage2_module: str | None,
    detected_stage2_lets: list[str],
    detected_style: str,
    max_repair_iterations: int,
) -> str:
    benchmark_for_prompt = rel_or_abs(benchmark_json, repo_root)
    stage1a_for_prompt = rel_or_abs(stage1a_mlw, repo_root)
    stage2a_for_prompt = rel_or_abs(stage2a_mlw, repo_root)
    run_for_prompt = rel_or_abs(run_dir, repo_root)
    plan_for_prompt = rel_or_abs(expected_plan, repo_root)
    mlw_for_prompt = rel_or_abs(expected_mlw, repo_root)
    typecheck_for_prompt = rel_or_abs(typecheck_log, repo_root)

    target = data.get("target", {}) if isinstance(data.get("target"), dict) else {}
    signature = target.get("signature", {}) if isinstance(target.get("signature"), dict) else {}
    task = data.get("task", {}) if isinstance(data.get("task"), dict) else {}
    tests = data.get("tests") if isinstance(data.get("tests"), list) else []

    target_function = signature.get("function_name", "<unknown>")
    target_signature = signature.get("raw", "<unknown>")
    target_module = target.get("module_name", "<unknown>")
    task_id = task.get("task_id", "<unknown>")
    question_id = task.get("question_id", "<unknown>")

    skill_path = f".agents/skills/{stage3_skill}/SKILL.md"
    skill_examples_path = f".agents/skills/{stage3_skill}/examples/"
    companion_array_skill_path = f".agents/skills/{companion_array_skill}/SKILL.md"
    stage1_vals = ", ".join(detected_stage1_vals) if detected_stage1_vals else "<not detected>"
    stage2_lets = ", ".join(detected_stage2_lets) if detected_stage2_lets else "<not detected>"

    return f"""You are generating a Diversify2Verify Stage 3A final Why3 list verification file.

Use the list verification skill:

`{skill_path}`

Open and follow that skill before generating. Also inspect its examples before
writing the final file, and choose the closest matching example(s) by proof shape
(structural recursion, imperative cursor traversal, counting, membership, max/min, sortedness,
accumulator helpers, etc.):

`{skill_examples_path}`

In the PLAN, briefly state which skill example(s) or example pattern(s) you used.

This is a list benchmark, so do not use the array verification skill for style
unless explicitly comparing repository conventions. The companion array skill is:

`{companion_array_skill_path}`

If the list verification skill file is missing, continue with the rules in this
prompt. Also follow `AGENTS.md` if present. If there is any conflict, this prompt
wins for this run.

Do not modify `.agents/`, `AGENTS.md`, scripts, benchmark JSON files, the Stage 1A
input file, or the Stage 2A input file.

Inputs:

- Benchmark JSON: `{benchmark_for_prompt}`
- Stage 1A specification `.mlw`: `{stage1a_for_prompt}`
- Stage 2A implementation `.mlw`: `{stage2a_for_prompt}`
- Task id: `{task_id}`
- Question id: `{question_id}`
- Target module from JSON: `{target_module}`
- Target function from JSON: `{target_function}`
- Target signature from JSON: `{target_signature}`
- Benchmark test count, for context only: `{len(tests)}`
- Detected Stage 1A module: `{detected_stage1_module or '<not detected>'}`
- Detected Stage 1A abstract val target(s): `{stage1_vals}`
- Detected Stage 2A module: `{detected_stage2_module or '<not detected>'}`
- Detected Stage 2A let target(s): `{stage2_lets}`
- Detected implementation style: `{detected_style}`

Important output rule:

Use this run output root:

`{run_for_prompt}`

Do not write generated Stage 3A outputs outside that output root.

Create exactly these primary output files:

1. PLAN:
   `{plan_for_prompt}`

2. Why3 Stage 3A final verification file:
   `{mlw_for_prompt}`

Also write command outputs to:

3. Type-check log:
   `{typecheck_for_prompt}`


4. Final verification is intentionally out-of-band in this pipeline run; run your preferred
verification command externally.

Core Stage 3A task:

- Read the benchmark JSON only for names/context. The semantic contract comes from Stage 1A.
- Read the Stage 1A file and identify the semantic specification: helper predicates,
  recursive logical functions, the target `requires` clauses, and the target
  `ensures` clauses.
- Read the Stage 2A file and identify the executable implementation.
- Produce a single `.mlw` file that combines the Stage 1A semantic specification with
  the Stage 2A implementation.
- Replace the Stage 1A abstract `val {target_function}` with an executable `let` / `let rec`
  implementation from Stage 2A, carrying the complete Stage 1A target contract
  (`requires` and `ensures`) on that implementation.
- Add exactly the proof scaffolding needed for verification: `requires`, `ensures`,
  loop invariants, loop variants, recursive variants, intermediate `assert` statements,
  local ghost facts, and lemmas only when necessary.

Non-negotiable constraints:

- Do not change the Stage 1A semantic specification. Prefer copying semantic helper
  predicates/functions verbatim from Stage 1A.
- Do not weaken, delete, or rewrite any Stage 1A target `requires` or `ensures` clause.
- Do not change Stage 1A helper predicates/functions to make the proof easier; add
  separately proved helper lemmas/assertions instead.
- Do not change the target function signature.
- Do not change a recursive implementation into an imperative implementation.
- Do not change an imperative implementation into a recursive implementation.
- Do not replace the implementation with a fresh algorithm just because it is easier to prove.
- Do not keep Stage 1A concrete test lemmas unless they are genuinely useful as proof lemmas.
- Do not keep Stage 2A executable test functions or `run_tests ()` in the final Stage 3A file.
- Do not introduce unproved axioms to force verification.
- Do not use `false`, impossible preconditions, vacuous contracts, or ghost-only replacements
  to make the proof pass.
- Do not add `diverges` to avoid proving termination unless the Stage 2A implementation was
  explicitly partial in a way required by the original problem, which should be rare.
- If you believe the Stage 1A spec is wrong, do not silently modify it. Leave the spec intact,
  make the best proof attempt, and report the suspected spec issue in the final summary.

Proof strategy guidance:

- Start from the closest example(s) in `.agents/skills/{stage3_skill}/examples/` and
  adapt the proof pattern rather than inventing a new proof architecture.
- First try to prove the Stage 2A implementation against the Stage 1A spec with direct
  assertions, variants, and loop invariants.
- For recursive implementations, preserve the recursive structure and add variants and
  assertions that expose recursive unfolding facts.
- For imperative implementations, preserve loops and add invariants strong enough to bridge
  the loop state to the Stage 1A semantic helper functions.
- For imperative list loops, invariants should usually relate the cursor/suffix already remaining and any accumulator to the corresponding recursive/counting/search predicate from the Stage 1A spec.
- If the Stage 2A implementation uses a cursor `cur`, prefer invariants over `!cur`, `length !cur`, and accumulators; introduce a processed-prefix relation only when necessary.
- Use small helper lemmas only when solvers need induction, monotonicity, extensionality,
  sortedness propagation, counting decomposition, or range-splitting facts that assertions
  alone cannot establish.
- Every helper lemma must be proved. Keep lemmas general enough to be reusable but no more
  general than necessary.
- Prefer constructor-level assertions and suffix/length facts before invoking quantified or membership facts over lists.
- Prefer Why3 standard-library theories already used by Stage 1A/Stage 2A, and add imports
  only when needed.
- Use examples from `{skill_examples_path}` as the primary style references for how
  Stage 3 list files should combine specifications, implementations, invariants,
  assertions, and helper lemmas.

Common repair moves to prefer, in this order:

1. Add branch-local assertions exposing constructors, suffix relationships, lengths, and recursive unfolding facts.
2. Strengthen loop invariants to connect the processed prefix, remaining suffix/cursor, and accumulator with the
   Stage 1A semantic helper function or predicate.
3. Add post-loop assertions that instantiate the loop invariant when the cursor reaches `Nil`.
4. Add accumulator invariants for counting, sums, extrema, membership, or witness tracking.
5. Add small proved lemmas only when the VC needs induction, range decomposition,
   monotonicity, membership reasoning, or quantified list instantiation that assertions cannot provide.

Validation loop:

1. Type-check the generated Stage 3A file first:

   `why3 prove --type-only {mlw_for_prompt}`

   Save stdout/stderr to `{typecheck_for_prompt}`.

2. If type-checking fails, inspect the log and repair the generated file.
3. Use one initial generation plus {max_repair_iterations} repair iterations,
   for {max_repair_iterations + 1} total attempts.
4. Stop as soon as type-checking succeeds.
5. If type-checking remains impossible within the repair budget, stop and clearly report:
   the failing type-check condition/log summary, whether the problem appears to be an
   implementation-proof gap or a suspected Stage 1A specification issue, and what you tried.

At the end, provide a short final summary with:

- generated Stage 3A Why3 file path,
- type-check command and status,
- whether repair was needed,
- whether any helper lemmas were added,
- if type-check failed, the final blocker and whether the Stage 1A spec was preserved.
"""


# ---------------------------------------------------------------------------
# Codex invocation
# ---------------------------------------------------------------------------


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
    cmd.extend(["--cd", str(repo_root), "--sandbox", sandbox])

    for add_dir in add_dirs:
        cmd.extend(["--add-dir", str(add_dir)])

    cmd.extend(["--output-last-message", str(final_path)])

    if json_events:
        cmd.append("--json")

    if skip_git_repo_check:
        cmd.append("--skip-git-repo-check")

    cmd.extend(extra_args)
    cmd.append("-")  # prompt from stdin

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


# ---------------------------------------------------------------------------
# Driver-side validation
# ---------------------------------------------------------------------------


def command_display(cmd: list[str]) -> str:
    return shlex.join(cmd)


def run_command_to_log(
    *,
    cmd: list[str],
    log_path: Path,
    cwd: Path | None = None,
    timeout: int | None = None,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    header = "Command:\n  " + command_display(cmd) + "\n\n"

    exe = cmd[0]
    if os.sep in exe:
        exe_path = Path(exe)
        if not exe_path.is_absolute():
            base_dir = Path(cwd) if cwd is not None else Path.cwd()
            exe_path = base_dir / exe_path

        if not exe_path.exists():
            log_path.write_text(
                header
                + f"executable unavailable: {exe} (checked: {exe_path})\n",
                encoding="utf-8",
            )
            return 127
    if os.sep not in exe and shutil.which(exe) is None:
        log_path.write_text(header + f"executable unavailable on PATH: {exe}\n", encoding="utf-8")
        return 127

    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        log_path.write_text(
            header
            + (e.stdout or "")
            + f"\nTimed out after {timeout} seconds.\nExit code: 124\n",
            encoding="utf-8",
        )
        return 124

    log_path.write_text(
        header + (proc.stdout or "") + f"\nExit code: {proc.returncode}\n",
        encoding="utf-8",
    )
    return proc.returncode


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Codex Stage 3A list Why3 final verification generation."
    )
    parser.add_argument(
        "benchmark_json",
        type=Path,
        help="Path to the original normalized .list.json benchmark.",
    )
    parser.add_argument(
        "stage1a_mlw",
        type=Path,
        help="Path to the Stage 1A Why3 list specification .mlw file.",
    )
    parser.add_argument(
        "stage2a_mlw",
        type=Path,
        help="Path to one Stage 2A Why3 list implementation .mlw file.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("codex-runs/stage3a-list"),
        help="Directory where prompt, logs, and generated outputs are written.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
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
        default="high",
        help="Reasoning effort level passed as `reasoning.effort`.",
    )
    parser.add_argument(
        "--reasoning-level",
        choices=["low", "medium", "high", "xhigh"],
        default=None,
        help="Alias for --reasoning-effort.",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable name/path.",
    )
    parser.add_argument(
        "--why3-bin",
        default="why3",
        help="Why3 executable used for driver-side type-check.",
    )
    parser.add_argument(
        "--stage3-skill",
        default="why3_list_verification",
        help="Name of the Stage 3 list verification skill under .agents/skills/.",
    )
    parser.add_argument(
        "--companion-array-skill",
        default="why3_array_verification",
        help=(
            "Name of the companion Stage 3 array verification skill. This is included "
            "in the prompt only to prevent confusing the list/array skill names."
        ),
    )
    parser.add_argument(
        "--require-stage3-skill",
        action="store_true",
        help=(
            "Fail before invoking Codex if .agents/skills/<stage3-skill>/SKILL.md "
            "does not exist under --repo-root. By default the prompt still tells "
            "Codex to continue with the embedded rules if the skill is missing."
        ),
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
        default=6,
        help="Number of repair iterations after the initial generation. Default: 6.",
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Create a timestamped run directory instead of auto-incrementing.",
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
        help="Optional wall-clock timeout in seconds for Codex.",
    )
    parser.add_argument(
        "--driver-verify-timeout",
        type=int,
        default=None,
        help="Optional wall-clock timeout in seconds for driver-side type-check.",
    )
    parser.add_argument(
        "--codex-arg",
        action="append",
        default=[],
        help=(
            "Extra raw argument to append to `codex exec`. Repeat for flags and values, "
            "e.g. --codex-arg -c --codex-arg reasoning.effort='xhigh'."
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
        "--skip-driver-verify",
        action="store_true",
        help=(
            "Do not run driver-side type-check after Codex exits. "
            "Full verification is intentionally offline in this stage."
        ),
    )
    parser.add_argument(
        "--allow-verify-unavailable",
        action="store_true",
        help="If driver-side Why3 is unavailable, record it but do not fail.",
    )

    args = parser.parse_args(argv)

    if args.reasoning_level is not None:
        if args.reasoning_effort != "high" and args.reasoning_effort != args.reasoning_level:
            raise SystemExit(
                "error: --reasoning-effort and --reasoning-level disagree. "
                f"Got {args.reasoning_effort} vs {args.reasoning_level}."
            )
        args.reasoning_effort = args.reasoning_level

    if args.max_repair_iterations < 0:
        raise SystemExit("error: --max-repair-iterations must be non-negative")

    benchmark_json = require_existing_file(args.benchmark_json, "Benchmark .json file")
    stage1a_mlw = require_existing_file(args.stage1a_mlw, "Stage 1A .mlw file")
    stage2a_mlw = require_existing_file(args.stage2a_mlw, "Stage 2A .mlw file")
    repo_root = args.repo_root.resolve()
    out_dir = args.out_dir.resolve()

    if not repo_root.exists() or not repo_root.is_dir():
        raise SystemExit(f"error: repo root does not exist or is not a directory: {repo_root}")

    stage3_skill_file = repo_root / ".agents" / "skills" / args.stage3_skill / "SKILL.md"
    stage3_examples_dir = repo_root / ".agents" / "skills" / args.stage3_skill / "examples"
    if args.require_stage3_skill and not stage3_skill_file.exists():
        raise SystemExit(f"error: Stage 3 skill file not found: {stage3_skill_file}")
    if not stage3_skill_file.exists():
        print(f"warning: Stage 3 skill file not found under repo root: {stage3_skill_file}", file=sys.stderr)
    elif not stage3_examples_dir.exists():
        print(f"warning: Stage 3 skill examples directory not found: {stage3_examples_dir}", file=sys.stderr)

    data = load_json(benchmark_json)
    require_list_benchmark(data, benchmark_json)

    stage1_text = read_text(stage1a_mlw)
    stage2_text = read_text(stage2a_mlw)
    target_function = require_dotted(data, "target.signature.function_name", benchmark_json)
    target_function = target_function if isinstance(target_function, str) else None

    detected_stage1_module = extract_first_module_name(stage1_text)
    detected_stage1_vals = extract_val_names(stage1_text)
    detected_stage2_module = extract_first_module_name(stage2_text)
    detected_stage2_lets = extract_let_names(stage2_text)
    detected_style = detect_implementation_style(stage2_text, target_function)

    input_stem = derive_input_stem(stage1a_mlw, stage2a_mlw, repo_root)
    run_dir = make_run_root(out_dir, input_stem, args.timestamp).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    expected_mlw = run_dir / "generated" / "why3" / "list" / f"{input_stem}_stage3.mlw"
    expected_plan = run_dir / "generated" / "plans" / "list" / f"{input_stem}.stage3.plan.md"
    typecheck_log = run_dir / "generated" / "reports" / "typecheck" / f"{input_stem}_stage3.typecheck.txt"

    prompt_path = run_dir / "prompt.md"
    final_path = run_dir / "codex.final.md"
    stdout_path = run_dir / ("codex.stdout.jsonl" if not args.no_json else "codex.stdout.log")
    stderr_path = run_dir / "codex.stderr.log"

    typecheck_cmd = [args.why3_bin, "prove", "--type-only", str(expected_mlw)]

    prompt = build_prompt(
        benchmark_json=benchmark_json,
        stage1a_mlw=stage1a_mlw,
        stage2a_mlw=stage2a_mlw,
        repo_root=repo_root,
        run_dir=run_dir,
        expected_plan=expected_plan,
        expected_mlw=expected_mlw,
        typecheck_log=typecheck_log,
        data=data,
        stage3_skill=args.stage3_skill,
        companion_array_skill=args.companion_array_skill,
        detected_stage1_module=detected_stage1_module,
        detected_stage1_vals=detected_stage1_vals,
        detected_stage2_module=detected_stage2_module,
        detected_stage2_lets=detected_stage2_lets,
        detected_style=detected_style,
        max_repair_iterations=args.max_repair_iterations,
    )
    write_text(prompt_path, prompt)

    add_dirs = [run_dir]
    if not is_relative_to(stage1a_mlw, repo_root):
        add_dirs.append(stage1a_mlw.parent)
    if not is_relative_to(stage2a_mlw, repo_root):
        add_dirs.append(stage2a_mlw.parent)
    if not is_relative_to(benchmark_json, repo_root):
        add_dirs.append(benchmark_json.parent)

    # Include repo-local scripts directory as a writable/readable additional dir only when
    # the repo itself is not the current Codex workspace. Usually --cd repo_root is enough.
    deduped_add_dirs: list[Path] = []
    seen: set[Path] = set()
    for p in add_dirs:
        rp = p.resolve()
        if rp not in seen:
            deduped_add_dirs.append(rp)
            seen.add(rp)

    print("Stage 3 skill:")
    print(f"  {stage3_skill_file} [{'ok' if stage3_skill_file.exists() else 'missing'}]")
    print(f"  examples: {stage3_examples_dir} [{'ok' if stage3_examples_dir.exists() else 'missing'}]")

    model = args.model if args.model.strip() else None

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

    if rc != 0:
        print(f"\nCodex exited with code {rc}. See logs in {run_dir}.", file=sys.stderr)
        return rc

    if args.dry_run:
        return 0

    if not args.allow_missing_files:
        missing = [p for p in [expected_plan, expected_mlw] if not p.exists()]
        if missing:
            print("\nerror: Codex completed but expected files are missing:", file=sys.stderr)
            for p in missing:
                print(f"  {p}", file=sys.stderr)
            print("Use --allow-missing-files to ignore this check.", file=sys.stderr)
            return 2

    if args.skip_driver_verify:
        print("\nDriver-side type-check skipped by --skip-driver-verify.")
        return 0

    if not expected_mlw.exists():
        print(
            "\nwarning: skipping driver-side type-check because the expected MLW file is missing.",
            file=sys.stderr,
        )
        return 0 if args.allow_missing_files else 2

    print("\nDriver-side type-check:")
    print("  " + command_display(typecheck_cmd))
    type_rc = run_command_to_log(
        cmd=typecheck_cmd,
        log_path=typecheck_log,
        cwd=repo_root,
        timeout=args.driver_verify_timeout,
    )
    print(f"  log: {typecheck_log}")
    print(f"  exit code: {type_rc}")

    if type_rc == 127 and args.allow_verify_unavailable:
        print("warning: Why3 unavailable; continuing because --allow-verify-unavailable was set.")
        return 0
    if type_rc != 0:
        print(f"\nerror: driver-side type-check failed. See {typecheck_log}", file=sys.stderr)
        return type_rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
