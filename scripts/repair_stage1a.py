#!/usr/bin/env python3
"""
Run a Codex-assisted Why3 repair/audit pass for a failing .mlw file.

The script is intended for the Diversify2Verify workflow after you have run
Why3 verification offline and saved the verifier output to a log file. It copies
all inputs into a reproducible run directory, builds a focused repair prompt,
and invokes `codex exec` non-interactively.

Typical use:

  python3 scripts/repair_why3_with_codex.py \
    output/2200/foo/generated/why3/array/foo.mlw \
    output/2200/foo/verify.log \
    --benchmark-json benchmarks/arrays/foo.array.json \
    --kind array \
    --out-dir codex-runs/why3-repair \
    --model gpt-5.5

Expected output layout:

  <out-dir>/<mlw-stem>/
    prompt.md
    codex.stdout.jsonl
    codex.stderr.log
    codex.final.md
    inputs/
      original.mlw
      verifier.log
      benchmark.json                 # if supplied
      context/...
    generated/
      why3/repaired.mlw
      reports/repair_report.md
      reports/repair_decision.json
      reports/repaired.typecheck.txt
      patches/repaired.diff

By default, Codex is asked to type-check only. It is not asked to run full
verification; you can verify the repaired .mlw offline with your usual script.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
from typing import Any


KIND_CHOICES = ("auto", "array", "list", "generic")


def die(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    raise SystemExit(f"error: {msg}")


def read_text(path: Path, *, what: str) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        die(f"{what} does not exist: {path}")
    except OSError as e:
        die(f"cannot read {what} {path}: {e}")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_file(src: Path, dst: Path, *, what: str) -> Path:
    if not src.exists():
        die(f"{what} does not exist: {src}")
    if not src.is_file():
        die(f"{what} is not a regular file: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip())
    slug = re.sub(r"-+", "-", slug).strip("-._")
    return slug or "why3-repair"


def make_run_dir(out_dir: Path, mlw_path: Path, use_timestamp: bool) -> Path:
    base = slugify(mlw_path.with_suffix("").name)
    if use_timestamp:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"{base}-{stamp}"
    return (out_dir / base).resolve()


def rel_or_abs(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())


def infer_kind(mlw_path: Path, explicit: str) -> str:
    if explicit != "auto":
        return explicit

    lower_name = mlw_path.name.lower()
    if ".array." in lower_name or lower_name.endswith("_array.mlw") or lower_name.endswith("-array.mlw"):
        return "array"
    if ".list." in lower_name or lower_name.endswith("_list.mlw") or lower_name.endswith("-list.mlw"):
        return "list"

    text = read_text(mlw_path, what="Why3 file")
    has_array = "use array.Array" in text or "use import array.Array" in text or "array int" in text
    has_list = "use list.List" in text or "use import list.List" in text or "list int" in text

    if has_array and not has_list:
        return "array"
    if has_list and not has_array:
        return "list"
    return "generic"


def kind_guidance(kind: str) -> str:
    if kind == "array":
        return """- Treat this as an array-oriented Why3 repair.
- Use `.agents/skills/why3_contract_audit_repair` if present.
- Also inspect `.agents/skills/why3_array_contract_generation` and `.agents/references/why3/stdlib_array.md` if present.
- Prefer array-specific proof scaffolding: `array.Array`, `array.Init`, explicit per-index assertions, finite-domain index enumeration for concrete tests, and small helper predicates/facts for quantified array properties.
- Preserve `length`, index bounds, and exact function signatures.
"""
    if kind == "list":
        return """- Treat this as a list-oriented Why3 repair.
- Use `.agents/skills/why3_contract_audit_repair` if present.
- Also inspect `.agents/skills/why3_list_contract_generation` and list-related Why3 references if present.
- Prefer list-specific proof scaffolding: structural recursion over `Nil`/`Cons`, explicit recursive unfolding assertions, helper lemmas for concrete lists, and variants over the list tail.
- Preserve list constructors and exact function signatures.
"""
    return """- Treat this as a generic Why3 repair.
- Use `.agents/skills/why3_contract_audit_repair` if present.
- Inspect any relevant `.agents/skills/why3_*` skills and `.agents/references/why3/` references if present.
- Infer whether the file is array-, list-, arithmetic-, or predicate-heavy from the source.
"""


def build_prompt(
    *,
    repo_root: Path,
    run_dir: Path,
    kind: str,
    original_mlw: Path,
    verifier_log: Path,
    benchmark_json: Path | None,
    copied_context_files: list[Path],
    repaired_mlw: Path,
    repair_report: Path,
    decision_json: Path,
    typecheck_log: Path,
    patch_path: Path,
    allow_spec_changes: bool,
    allow_full_verify: bool,
    verify_command: str | None,
    extra_instructions: str | None,
) -> str:
    original_for_prompt = rel_or_abs(original_mlw, repo_root)
    log_for_prompt = rel_or_abs(verifier_log, repo_root)
    repaired_for_prompt = rel_or_abs(repaired_mlw, repo_root)
    report_for_prompt = rel_or_abs(repair_report, repo_root)
    decision_for_prompt = rel_or_abs(decision_json, repo_root)
    typecheck_for_prompt = rel_or_abs(typecheck_log, repo_root)
    patch_for_prompt = rel_or_abs(patch_path, repo_root)
    run_for_prompt = rel_or_abs(run_dir, repo_root)

    if benchmark_json is None:
        benchmark_line = "- Benchmark JSON: not provided"
    else:
        benchmark_line = f"- Benchmark JSON: `{rel_or_abs(benchmark_json, repo_root)}`"

    if copied_context_files:
        context_lines = "\n".join(
            f"  - `{rel_or_abs(path, repo_root)}`" for path in copied_context_files
        )
    else:
        context_lines = "  - none"

    spec_policy = (
        "Spec changes are allowed only when the verifier log and source make a strong case "
        "that the existing specification is inconsistent, too strong, or semantically wrong."
        if allow_spec_changes
        else
        "Do not change the semantic specification. Treat the likely failure causes as proof scaffolding, intermediate assertions, missing assertions, or helper lemmas. If you believe the spec is wrong, explain it in the report but keep the repaired .mlw conservative."
    )

    verify_policy = (
        f"You may run full verification if useful. Prefer this command when appropriate: `{verify_command}`"
        if allow_full_verify and verify_command
        else (
            "You may run full verification if useful, but keep it bounded and record exactly what you ran."
            if allow_full_verify
            else "Do not run full verification. Type-check only with `why3 prove --type-only` if Why3 is available. The user will run full verification offline."
        )
    )

    extra = f"\nAdditional user instructions:\n{extra_instructions.strip()}\n" if extra_instructions else ""

    return f"""Use the Diversify2Verify Why3 repair/audit workflow.

Goal: analyze a failed Why3 verification run and produce a repaired `.mlw` candidate plus a concise diagnosis.

Run output root:
`{run_for_prompt}`

Inputs:
- Failing Why3 file: `{original_for_prompt}`
- Verifier output log: `{log_for_prompt}`
{benchmark_line}
- Additional context files:
{context_lines}

Detected target kind: `{kind}`

Kind-specific guidance:
{kind_guidance(kind)}

Primary outputs to create exactly:

1. Repaired Why3 file:
   `{repaired_for_prompt}`

2. Human-readable repair report:
   `{report_for_prompt}`

3. Machine-readable decision summary JSON:
   `{decision_for_prompt}`

4. Type-check output, if any:
   `{typecheck_for_prompt}`

5. Unified diff from original to repaired file:
   `{patch_for_prompt}`

Repair policy:
- First, read the verifier log and identify the earliest/root failures rather than only the final cascading failures.
- In this workflow, a common cause is a wrong intermediate `assert`; treat that as the default hypothesis before changing the semantic specification.
- Other common causes to check: missing recursive unfolding assertions, missing finite-domain facts for concrete tests, quantifier-instantiation failures, overly strong/weak loop invariants, missing variants, type/syntax errors, and solver timeouts.
- {spec_policy}
- Preserve the module name and public function signatures unless the log shows the file does not type-check because of a syntactic signature issue.
- Preserve normalized test inputs and expected outputs. Do not invent new benchmark tests.
- Prefer small local changes: remove or weaken bad intermediate assertions, add helper assertions/lemmas, split hard goals, and make quantifier triggers easier through explicit facts.
- If you change the spec, explicitly mark this in the report and decision JSON with evidence.
- {verify_policy}

Decision JSON schema:
Create a JSON object with these fields:
- `classification`: one of `wrong_intermediate_assertion`, `missing_assertion_or_instantiation`, `recursive_unfolding_issue`, `loop_invariant_issue`, `termination_or_variant_issue`, `type_or_syntax_error`, `spec_likely_wrong`, `prover_timeout_or_resource_issue`, `mixed`, `unknown`
- `confidence`: number from 0.0 to 1.0
- `changed_spec`: boolean
- `changed_tests`: boolean
- `changed_public_signature`: boolean
- `root_cause_summary`: string
- `key_log_locations`: array of strings
- `key_source_locations`: array of strings
- `repair_summary`: array of strings
- `offline_verification_command`: string

Report requirements:
- Start with the suspected root cause.
- Explain why the failure is likely proof scaffolding vs. spec error.
- List the important changes made to the repaired file.
- Include the exact offline verification command the user should run next.
- Keep the report practical and concise.

At the end, provide a short final message with paths to the repaired file, report, decision JSON, diff, and type-check status.
{extra}"""


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
    cmd.extend([
        "--cd",
        str(repo_root),
        "--sandbox",
        sandbox,
        "--add-dir",
        str(run_dir),
        "--output-last-message",
        str(final_path),
    ])

    if json_events:
        cmd.append("--json")

    if skip_git_repo_check:
        cmd.append("--skip-git-repo-check")

    cmd.extend(extra_args)
    cmd.append("-")

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
        die(f"could not find Codex executable {codex_bin!r}; install Codex or pass --codex-bin")
    except subprocess.TimeoutExpired as e:
        stdout_path.write_text(e.stdout or "", encoding="utf-8")
        stderr_path.write_text(e.stderr or "", encoding="utf-8")
        print(f"error: Codex timed out after {timeout} seconds", file=sys.stderr)
        return 124

    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Codex to diagnose and repair a failing Why3 .mlw file from a verifier log."
    )
    parser.add_argument("mlw_file", type=Path, help="Failing .mlw file.")
    parser.add_argument("verifier_log", type=Path, help="Verifier output log from the failed run.")
    parser.add_argument(
        "--benchmark-json",
        type=Path,
        default=None,
        help="Optional normalized benchmark JSON; useful when deciding whether a spec is wrong.",
    )
    parser.add_argument(
        "--context-file",
        type=Path,
        action="append",
        default=[],
        help="Optional extra context file to copy into the run directory. Repeat as needed.",
    )
    parser.add_argument(
        "--kind",
        choices=KIND_CHOICES,
        default="auto",
        help="Repair kind. Use auto unless you know this is array or list.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("codex-runs/why3-repair"),
        help="Directory where prompts, logs, and generated repair outputs are written.",
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
        default="medium",
        help="Reasoning effort passed as `reasoning.effort`.",
    )
    parser.add_argument("--codex-bin", default="codex", help="Codex executable name/path.")
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
        "--timestamp",
        action="store_true",
        help="Create a timestamped run directory instead of reusing <out-dir>/<mlw-stem>.",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Do not pass --json to Codex; stdout will be formatted text instead of JSONL.",
    )
    parser.add_argument("--skip-git-repo-check", action="store_true", help="Pass --skip-git-repo-check to Codex.")
    parser.add_argument("--timeout", type=int, default=None, help="Optional wall-clock timeout in seconds for Codex.")
    parser.add_argument(
        "--codex-arg",
        action="append",
        default=[],
        help="Extra raw argument appended to `codex exec`. Repeat for flags and values.",
    )
    parser.add_argument(
        "--allow-spec-changes",
        action="store_true",
        help="Allow Codex to change semantic specification if it finds strong evidence the spec is wrong.",
    )
    parser.add_argument(
        "--allow-full-verify",
        action="store_true",
        help="Allow Codex to run full verification. By default it is asked to type-check only.",
    )
    parser.add_argument(
        "--verify-command",
        default=None,
        help="Optional verification command to suggest in the prompt, e.g. scripts/why3-verify.sh {repaired_mlw}.",
    )
    parser.add_argument(
        "--extra-instructions",
        default=None,
        help="Additional text appended to the Codex prompt.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Write prompt and print command without invoking Codex.")
    parser.add_argument(
        "--allow-missing-files",
        action="store_true",
        help="Do not fail if expected repaired/report files are missing after Codex exits.",
    )

    args = parser.parse_args(argv)

    mlw_path = args.mlw_file.resolve()
    log_path = args.verifier_log.resolve()
    repo_root = args.repo_root.resolve()
    out_dir = args.out_dir.resolve()

    if mlw_path.suffix != ".mlw":
        print(f"warning: input does not end in .mlw: {mlw_path}", file=sys.stderr)

    kind = infer_kind(mlw_path, args.kind)

    run_dir = make_run_dir(out_dir, mlw_path, args.timestamp)
    run_dir.mkdir(parents=True, exist_ok=True)

    inputs_dir = run_dir / "inputs"
    copied_mlw = copy_file(mlw_path, inputs_dir / "original.mlw", what="Why3 file")
    copied_log = copy_file(log_path, inputs_dir / "verifier.log", what="verifier log")

    copied_benchmark: Path | None = None
    if args.benchmark_json is not None:
        copied_benchmark = copy_file(args.benchmark_json.resolve(), inputs_dir / "benchmark.json", what="benchmark JSON")

    copied_context_files: list[Path] = []
    for i, src in enumerate(args.context_file):
        src_resolved = src.resolve()
        dst_name = f"{i:02d}_{slugify(src_resolved.name)}"
        copied_context_files.append(copy_file(src_resolved, inputs_dir / "context" / dst_name, what="context file"))

    repaired_mlw = run_dir / "generated" / "why3" / "repaired.mlw"
    repair_report = run_dir / "generated" / "reports" / "repair_report.md"
    decision_json = run_dir / "generated" / "reports" / "repair_decision.json"
    typecheck_log = run_dir / "generated" / "reports" / "repaired.typecheck.txt"
    patch_path = run_dir / "generated" / "patches" / "repaired.diff"

    prompt_path = run_dir / "prompt.md"
    final_path = run_dir / "codex.final.md"
    stdout_path = run_dir / ("codex.stdout.jsonl" if not args.no_json else "codex.stdout.log")
    stderr_path = run_dir / "codex.stderr.log"

    prompt = build_prompt(
        repo_root=repo_root,
        run_dir=run_dir,
        kind=kind,
        original_mlw=copied_mlw,
        verifier_log=copied_log,
        benchmark_json=copied_benchmark,
        copied_context_files=copied_context_files,
        repaired_mlw=repaired_mlw,
        repair_report=repair_report,
        decision_json=decision_json,
        typecheck_log=typecheck_log,
        patch_path=patch_path,
        allow_spec_changes=args.allow_spec_changes,
        allow_full_verify=args.allow_full_verify,
        verify_command=args.verify_command,
        extra_instructions=args.extra_instructions,
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
    print(f"Detected kind: {kind}")
    print("Expected generated files:")
    for label, path in [
        ("REPAIRED", repaired_mlw),
        ("REPORT  ", repair_report),
        ("DECISION", decision_json),
        ("TYPECHK ", typecheck_log),
        ("DIFF    ", patch_path),
    ]:
        print(f"  {label}: {path} [{'ok' if path.exists() else 'missing'}]")

    if rc != 0:
        print(f"\nCodex exited with code {rc}. See logs in {run_dir}.", file=sys.stderr)
        return rc

    if not args.dry_run and not args.allow_missing_files:
        missing = [p for p in [repaired_mlw, repair_report, decision_json] if not p.exists()]
        if missing:
            print("\nerror: Codex completed but expected files are missing:", file=sys.stderr)
            for p in missing:
                print(f"  {p}", file=sys.stderr)
            print("Use --allow-missing-files to ignore this check.", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
