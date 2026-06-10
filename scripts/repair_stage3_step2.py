#!/usr/bin/env python3
"""
Run a Codex-assisted Stage 3 Why3 verification repair pass.

This script is for the Diversify2Verify final verification stage.  It takes a
failing Stage 3 `.mlw` file and the verifier log produced offline, then asks
Codex to repair the file by adding proof scaffolding only:

  - loop invariants,
  - variants for termination,
  - assertions for unfolding / quantifier instantiation,
  - helper contracts when needed for well-formedness,
  - small auxiliary lemmas only when necessary.

By default this script is conservative:

  - it does NOT allow semantic specification changes;
  - it does NOT allow recursive <-> imperative rewrites;
  - it does NOT ask Codex to run full verification;
  - it DOES ask Codex to type-check the repaired file when Why3 is available.

Typical use:

  python3 scripts/repair_stage3_why3_with_codex.py \
    output/.../stage3_verified.mlw \
    output/.../verify.log \
    --benchmark-json output/.../normalised/input/foo.array.json \
    --stage1a-mlw output/.../stage1a/foo_array.mlw \
    --stage2a-mlw output/.../stage2a/foo_array_imperative.mlw \
    --kind array \
    --repo-root /Users/rubenm/Desktop/Diversify2Verify \
    --model gpt-5.5 \
    --reasoning-effort high

Expected output layout:

  <out-dir>/<stage3-stem>/
    prompt.md
    codex.stdout.jsonl
    codex.stderr.log
    codex.final.md
    inputs/
      stage3_original.mlw
      verifier.log
      benchmark.json                 # if supplied
      stage1a_spec.mlw               # if supplied
      stage2a_impl.mlw               # if supplied
      context/...
    generated/
      why3/repaired.mlw
      reports/log_focus.md
      reports/source_audit.md
      reports/original.typecheck.txt
      reports/repaired.typecheck.txt
      reports/repair_report.md
      reports/repair_decision.json
      patches/repaired.diff
"""

from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import json
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
from typing import Any, NoReturn


KIND_CHOICES = ("auto", "array", "list")
CLASSIFICATION_CHOICES = [
    "missing_loop_invariant",
    "missing_variant_or_termination_argument",
    "missing_assertion_or_instantiation",
    "missing_auxiliary_lemma",
    "helper_contract_or_wellformedness_issue",
    "wrong_intermediate_assertion",
    "exception_or_loop_control_invariant_issue",
    "recursive_unfolding_issue",
    "type_or_syntax_error",
    "prover_timeout_or_resource_issue",
    "spec_suspected_wrong_but_not_changed",
    "mixed",
    "unknown",
]

SEMANTIC_CLUSTER_CHOICES = [
    "public_postcondition_bridge",
    "helper_model_correctness_bridge",
    "semantic_loop_invariant",
    "large_assertion_needs_decomposition",
    "sorting_or_order_helper",
    "counting_cardinality_occurrence",
    "optimization_optimality",
    "prefix_window_subarray_bridge",
    "array_bounds_or_index_arithmetic",
    "list_structural_induction",
    "precondition_wellformedness",
    "termination_variant",
    "wrong_intermediate_assertion",
    "type_or_syntax",
    "resource_or_timeout_only",
    "unknown",
]


def die(msg: str) -> NoReturn:
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
    src = src.resolve()
    if not src.exists():
        die(f"{what} does not exist: {src}")
    if not src.is_file():
        die(f"{what} is not a regular file: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst.resolve()


def slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip())
    slug = re.sub(r"-+", "-", slug).strip("-._")
    return slug or "stage3-repair"


def make_run_dir(out_dir: Path, mlw_path: Path, use_timestamp: bool) -> Path:
    base = slugify(mlw_path.with_suffix("").name)
    if use_timestamp:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"{base}-{stamp}"
    candidate = (out_dir / base).resolve()
    if not candidate.exists():
        return candidate
    i = 1
    while True:
        unique = (out_dir / f"{base}-{i:02d}").resolve()
        if not unique.exists():
            return unique
        i += 1


def rel_or_abs(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())


def infer_kind(mlw_path: Path, explicit: str) -> str:
    if explicit != "auto":
        return explicit
    name = mlw_path.name.lower()
    if "array" in name:
        return "array"
    if "list" in name:
        return "list"
    text = read_text(mlw_path, what="Stage 3 Why3 file")
    has_array = "array.Array" in text or "array int" in text or "array '" in text
    has_list = "list.List" in text or "list int" in text or "list '" in text
    if has_array and not has_list:
        return "array"
    if has_list and not has_array:
        return "list"
    # Prefer array only when clear; otherwise list is not guessed.
    die("could not infer --kind from the file; pass --kind array or --kind list")


def default_stage3_skill(kind: str) -> str:
    if kind == "array":
        return "why3_array_verification"
    if kind == "list":
        return "why3_list_verification"
    die(f"unsupported kind: {kind}")


def companion_skill(kind: str) -> str:
    return "why3_list_verification" if kind == "array" else "why3_array_verification"


def check_skill(repo_root: Path, skill: str, *, require: bool) -> tuple[bool, bool, Path, Path]:
    skill_dir = repo_root / ".agents" / "skills" / skill
    skill_md = skill_dir / "SKILL.md"
    examples_dir = skill_dir / "examples"
    skill_ok = skill_md.exists()
    examples_ok = examples_dir.exists()
    if require and not skill_ok:
        die(f"required skill missing: {skill_md}")
    return skill_ok, examples_ok, skill_md, examples_dir


def _why3_repair_hint(subgoal_kind: str, *, semantic_cluster: str = "unknown") -> str:
    kind = subgoal_kind.lower()
    if semantic_cluster == "public_postcondition_bridge":
        return (
            "prove the semantic bridge from the helper result to the public ensures; "
            "strengthen helper postconditions and add a small combine/bridge lemma instead of rewriting the algorithm."
        )
    if semantic_cluster == "optimization_optimality":
        return (
            "separate feasibility/existence from universal optimality; add the missing dominance, monotonicity, "
            "or exchange lemma for the algorithm."
        )
    if semantic_cluster == "sorting_or_order_helper":
        return (
            "prove sortedness, membership/permutation, length, and duplicate/positivity preservation separately; "
            "avoid one monolithic sorting assertion."
        )
    if semantic_cluster == "counting_cardinality_occurrence":
        return (
            "add induction lemmas for num_occ/mem/cardinal/length and expose finite-domain cases explicitly."
        )
    if semantic_cluster == "prefix_window_subarray_bridge":
        return (
            "connect the accumulator/helper to the processed prefix/window/subarray; prove shift/slice/index mapping lemmas."
        )
    if "array index bounds" in kind:
        return "prove `0 <= i < length a` at this access; add caller preconditions/invariants or branch-local assertions."
    if "precondition" in kind:
        return "prove the callee `requires` clause immediately before the call; add helper contracts only if they preserve the public spec."
    if "loop invariant init" in kind:
        return "weaken or initialize the invariant; add pre-loop assertions for bounds/accumulator facts."
    if "loop invariant preservation" in kind:
        return "strengthen the invariant so it survives the loop body mutation/update, especially the semantic accumulator-prefix relation."
    if "loop variant" in kind or "variant decrease" in kind:
        return "make the decreasing measure explicit with bounds and monotonicity assertions."
    if "assertion" in kind:
        return "replace one large assertion by smaller local assertions or a small proved lemma."
    if "postcondition" in kind:
        return "split the final correctness proof into branch-local assertions, helper postconditions, and bridge lemmas."
    return "repair the proof obligation at this exact source location before broad rewrites."


def _source_snippet(source_lines: list[str], line_no: int, *, radius: int = 3) -> list[str]:
    if line_no <= 0 or line_no > len(source_lines):
        return []
    lo = max(1, line_no - radius)
    hi = min(len(source_lines), line_no + radius)
    out: list[str] = []
    for i in range(lo, hi + 1):
        mark = ">>>" if i == line_no else "   "
        out.append(f"{mark} {i:5d}: {source_lines[i - 1]}")
    return out


def _obs_key(obs: dict[str, object]) -> tuple[object, ...]:
    """Key used to decide if the same leaf subgoal was eventually proved."""
    return (
        obs.get("stage"),
        obs.get("file"),
        obs.get("src_line"),
        obs.get("char_start"),
        obs.get("char_end"),
        obs.get("subgoal_kind"),
        obs.get("root_goal"),
    )


def _function_at_line(source_lines: list[str], line_no: int) -> str:
    """Return the nearest enclosing WhyML declaration before line_no."""
    for i in range(min(line_no, len(source_lines)), 0, -1):
        line = source_lines[i - 1].strip()
        m = re.match(r"let\s+(?:rec\s+)?(?:function\s+|lemma\s+)?([A-Za-z_][A-Za-z0-9_']*)\b", line)
        if m:
            return m.group(1)
        m = re.match(r"val\s+([A-Za-z_][A-Za-z0-9_']*)\b", line)
        if m:
            return m.group(1)
    return "<unknown>"


def _source_window_text(source_lines: list[str], line_no: int, *, radius: int = 8) -> str:
    if line_no <= 0 or line_no > len(source_lines):
        return ""
    lo = max(1, line_no - radius)
    hi = min(len(source_lines), line_no + radius)
    return "\n".join(source_lines[lo - 1:hi])


def _infer_semantic_cluster(
    *,
    unproved_items: list[dict[str, object]],
    valid_items: list[dict[str, object]],
    still_unproved_text: str,
    source_lines: list[str],
) -> tuple[str, str, list[str], list[str]]:
    """Return (cluster, diagnosis, do_focus, avoid_focus)."""
    text_bits: list[str] = [still_unproved_text.lower()]
    for item in unproved_items:
        for k in ("root_goal", "subgoal_kind", "theory"):
            text_bits.append(str(item.get(k, "")).lower())
        src_line = int(item.get("src_line") or 0)
        text_bits.append(_source_window_text(source_lines, src_line, radius=8).lower())
    blob = "\n".join(text_bits)

    only_one = len(unproved_items) == 1
    first = unproved_items[0] if unproved_items else {}
    first_kind = str(first.get("subgoal_kind", "")).lower()
    first_line = int(first.get("src_line") or 0)
    first_window = _source_window_text(source_lines, first_line, radius=4).lower()
    valid_preconditions = [x for x in valid_items if "precondition" in str(x.get("subgoal_kind", "")).lower()]

    if only_one and "postcondition" in first_kind and "ensures" in first_window:
        return (
            "public_postcondition_bridge",
            "Only a public postcondition remains. Helper-call preconditions appear discharged; the repair should expose a semantic bridge from helper/model result to the public ensures.",
            [
                "Strengthen the helper/model postcondition so it states the semantic property needed by the public wrapper.",
                "Add a small bridge/combine lemma that follows the implementation recursion/loop structure.",
                "Split the public postcondition into existence/feasibility and universal optimality/upper-bound parts when applicable.",
                "Use local assertions to instantiate the bridge lemma immediately before the final result.",
            ],
            [
                "Do not rewrite the algorithm or switch recursive/imperative style.",
                "Do not add a final assertion equivalent to the full public ensures unless helper facts already prove it.",
                "Do not spend effort on call preconditions that are already Valid in the focused log.",
            ],
        )

    if "insert_sorted" in blob or "insertion_sort" in blob or "sorted" in blob or "sort" in blob:
        return (
            "sorting_or_order_helper",
            "The remaining goals involve sorting/order preservation helpers. These usually need separate preservation lemmas rather than one large proof jump.",
            [
                "Prove sortedness preservation separately from membership/permutation preservation.",
                "Prove length and no-duplicate/positivity preservation in their own helper lemmas if used by the spec.",
                "Instantiate the insertion/sorting lemma at the exact call site before the public result proof.",
            ],
            ["Do not rederive all sorting facts in one assertion.", "Do not replace the sorting helper with a different algorithm."],
        )

    if any(w in blob for w in ["num_occ", "occurrence", "cardinal", "mem ", "length", "count", "frequency"]):
        return (
            "counting_cardinality_occurrence",
            "The remaining goals mention counting, membership, cardinality, or length. These usually need structural induction/finite-domain facts.",
            [
                "Add small induction lemmas for num_occ/mem/cardinal/length over the same list or index structure.",
                "Expose finite cases explicitly with per-index or per-constructor assertions.",
                "Keep arithmetic/cardinality facts separate from semantic optimality facts.",
            ],
            ["Do not expect SMT to infer quantified finite-domain cases automatically."],
        )

    if any(w in blob for w in ["max_", "maximum", "min_", "minimum", "best", "optimal", "upper_bound", "lower_bound", "sum", "cost", "largest", "smallest"]):
        return (
            "optimization_optimality",
            "The remaining goals look like an optimization/optimality proof. The hard part is usually the universal bound, not computing the candidate.",
            [
                "Separate candidate existence/feasibility from universal optimality.",
                "Add the missing monotonicity, dominance, exchange, or max/min-combine lemma.",
                "For recursive helpers, split competitors into current-case versus recursive-tail cases.",
            ],
            ["Do not collapse the whole optimality proof into a single assertion."],
        )

    if any(w in blob for w in ["prefix", "suffix", "subarray", "window", "slice", "drop", "take", "range"]):
        return (
            "prefix_window_subarray_bridge",
            "The remaining goals involve prefix/suffix/window/subarray reasoning. The proof likely needs an explicit index/slice mapping lemma.",
            [
                "State the accumulator/helper meaning over the processed prefix/window/range.",
                "Add shift lemmas for mapping original indices to suffix/window indices and back.",
                "Use branch-local assertions for boundary cases such as empty window, i = 0, or i > 0.",
            ],
            ["Do not rely on the prover to infer index-shift arithmetic across slices/suffixes."],
        )

    if any("loop invariant" in str(x.get("subgoal_kind", "")).lower() for x in unproved_items):
        return (
            "semantic_loop_invariant",
            "A loop invariant does not initialize or preserve. Bounds-only invariants are probably insufficient.",
            [
                "Add the semantic relation between each accumulator and the processed prefix/range.",
                "Add mutation-frame facts showing unchanged array/list portions still satisfy needed properties.",
                "Add post-loop assertions that convert the invariant plus exit condition into the final postcondition.",
            ],
            ["Do not only add index bounds unless the failing goal is purely an array-bounds VC."],
        )

    if any("assertion" in str(x.get("subgoal_kind", "")).lower() for x in unproved_items):
        return (
            "large_assertion_needs_decomposition",
            "An assertion remains unproved. It is probably too large or missing explicit instantiations.",
            [
                "Break the assertion into local facts that mirror the constructors/branches/indices involved.",
                "Add a small proved lemma if the assertion expresses a reusable induction fact.",
                "Instantiate quantified predicates/functions with concrete indices or constructors before the assertion.",
            ],
            ["Do not move the same assertion elsewhere without proving its prerequisites."],
        )

    if any("precondition" in str(x.get("subgoal_kind", "")).lower() for x in unproved_items):
        return (
            "precondition_wellformedness",
            "A call precondition remains unproved. The caller needs local facts before the call, not a changed public spec.",
            [
                "Add assertions immediately before the call proving the callee requires clauses.",
                "Strengthen caller/helper contracts only with facts derivable from existing preconditions.",
                "For array/list accesses, prove bounds/non-empty/non-negative facts before the call.",
            ],
            ["Do not weaken the public precondition or hide the obligation in an assume/axiom."],
        )

    return (
        "unknown",
        "No specific semantic cluster was detected. Use the focused leaf subgoals and source snippets as the primary repair target.",
        ["Repair the earliest remaining leaf subgoal first.", "Prefer small assertions/lemmas over broad rewrites."],
        ["Do not change Stage 1A semantic specification or Stage 2A algorithmic strategy."],
    )


def extract_log_focus(
    log_text: str,
    *,
    source_text: str | None = None,
    max_matches: int = 120,
    context_radius: int = 2,
) -> str:
    """Extract a compact, diagnosis-oriented verifier-log summary for repair.

    The output intentionally avoids a large generic keyword dump.  It focuses on
    leaf subgoals that remain unproved in the latest stage, removes exact leaf
    goals that were proved by another prover in that same stage, and emits a
    semantic repair playbook for the most likely failure cluster.
    """
    lines = log_text.splitlines()
    source_lines = source_text.splitlines() if source_text is not None else []

    stage_rx = re.compile(
        r"^---- (?P<stage>stage\d+) \| prover: (?P<prover>[^|]+) \| theory: (?P<theory>[^|]+) \| goal: (?P<goal>.+?) ----"
    )
    file_rx = re.compile(
        r'^File "(?P<file>[^"]+)", line (?P<line>\d+), characters (?P<start>\d+)-(?P<end>\d+):'
    )
    subgoal_rx = re.compile(r"^Sub-goal (?P<kind>.+?) of goal (?P<goal>.+)\.$")
    subgoal_header_rx = re.compile(r"^Sub-goal (?P<kind>.+?) of goal$")
    result_rx = re.compile(r"^Prover result is: (?P<result>.+)$")

    current_stage = ""
    current_prover = ""
    current_theory = ""
    current_goal = ""
    pending: dict[str, object] | None = None
    observations: list[dict[str, object]] = []

    summary_lines: list[tuple[int, str]] = []
    for idx, line in enumerate(lines, start=1):
        if (
            line.startswith("VERIFY_")
            or line.startswith("== Final summary ==")
            or line.startswith("Remaining failures")
            or line.startswith("Unproved root goals")
        ):
            summary_lines.append((idx, line.rstrip()))

        m = stage_rx.match(line)
        if m:
            current_stage = m.group("stage")
            current_prover = m.group("prover").strip()
            current_theory = m.group("theory").strip()
            current_goal = m.group("goal").strip()
            pending = None
            continue

        m = file_rx.match(line)
        if m:
            pending = {
                "log_line": idx,
                "file": m.group("file"),
                "src_line": int(m.group("line")),
                "char_start": int(m.group("start")),
                "char_end": int(m.group("end")),
                "stage": current_stage,
                "prover": current_prover,
                "theory": current_theory,
                "root_goal": current_goal,
                "subgoal_kind": "<unknown>",
            }
            continue

        if pending is not None:
            stripped = line.strip()
            if pending.get("_awaiting_subgoal_goal"):
                if stripped and not stripped.startswith("Prover result is:"):
                    pending["root_goal"] = stripped.rstrip(".")
                    pending.pop("_awaiting_subgoal_goal", None)
                    continue

            m = subgoal_rx.match(stripped)
            if m:
                pending["subgoal_kind"] = m.group("kind").strip()
                pending["root_goal"] = m.group("goal").strip()
                continue

            m = subgoal_header_rx.match(stripped)
            if m:
                pending["subgoal_kind"] = m.group("kind").strip()
                pending["_awaiting_subgoal_goal"] = True
                continue

            m = result_rx.match(stripped)
            if m:
                obs = {k: v for k, v in pending.items() if not str(k).startswith("_")}
                obs["result"] = m.group("result").strip().rstrip(".")
                obs["result_log_line"] = idx
                observations.append(obs)
                pending = None
                continue

    available_stages = {str(obs.get("stage")) for obs in observations if obs.get("stage")}
    if "stage3" in available_stages:
        focus_stage = "stage3"
    elif "stage2" in available_stages:
        focus_stage = "stage2"
    elif "stage1" in available_stages:
        focus_stage = "stage1"
    else:
        focus_stage = ""

    stage_obs = [obs for obs in observations if not focus_stage or obs.get("stage") == focus_stage]
    valid_keys = {
        _obs_key(obs)
        for obs in stage_obs
        if str(obs.get("result", "")).lower().startswith("valid")
    }
    valid_items = [obs for obs in stage_obs if str(obs.get("result", "")).lower().startswith("valid")]
    candidate_obs = [
        obs for obs in stage_obs
        if not str(obs.get("result", "")).lower().startswith("valid")
        and _obs_key(obs) not in valid_keys
    ]

    grouped: dict[tuple[object, ...], dict[str, object]] = {}
    for obs in candidate_obs:
        key = (
            obs.get("file"), obs.get("src_line"), obs.get("char_start"), obs.get("char_end"),
            obs.get("subgoal_kind"), obs.get("root_goal"),
        )
        item = grouped.setdefault(key, {
            "file": obs.get("file"),
            "src_line": obs.get("src_line"),
            "char_start": obs.get("char_start"),
            "char_end": obs.get("char_end"),
            "subgoal_kind": obs.get("subgoal_kind"),
            "root_goal": obs.get("root_goal"),
            "theory": obs.get("theory"),
            "function": _function_at_line(source_lines, int(obs.get("src_line") or 0)) if source_lines else "<unknown>",
            "log_lines": [],
            "results": [],
        })
        item["log_lines"].append(obs.get("log_line"))
        item["results"].append(f"{obs.get('stage')}/{obs.get('prover')}: {obs.get('result')}")

    unproved = list(grouped.values())

    priority_order = {
        "array index bounds": 0,
        "precondition": 1,
        "loop invariant init": 2,
        "loop invariant preservation": 3,
        "loop variant decrease": 4,
        "variant decrease": 5,
        "assertion": 6,
        "postcondition": 7,
    }

    def priority(item: dict[str, object]) -> tuple[int, int, str]:
        kind = str(item.get("subgoal_kind", "")).lower()
        p = 99
        for needle, value in priority_order.items():
            if needle in kind:
                p = value
                break
        return (p, int(item.get("src_line") or 0), str(item.get("root_goal") or ""))

    unproved.sort(key=priority)

    still_unproved: list[tuple[int, str]] = []
    in_still = False
    for idx, line in enumerate(lines, start=1):
        if line.strip() == "Still unproved goals:":
            in_still = True
            still_unproved.append((idx, line.rstrip()))
            continue
        if in_still:
            if line.startswith("VERIFY_") or line.startswith("=="):
                in_still = False
                continue
            if line.strip():
                still_unproved.append((idx, line.rstrip()))

    still_text = "\n".join(line for _, line in still_unproved)
    cluster, diagnosis, do_focus, avoid_focus = _infer_semantic_cluster(
        unproved_items=unproved,
        valid_items=valid_items,
        still_unproved_text=still_text,
        source_lines=source_lines,
    )

    out: list[str] = ["# Focused verifier-log extract", ""]

    out.extend(["## Repair diagnosis", f"- Semantic cluster: `{cluster}`", f"- Diagnosis: {diagnosis}"])
    out.extend(["", "### Focus repair on"])
    out.extend(f"- {x}" for x in do_focus)
    out.extend(["", "### Avoid wasting repair effort on"])
    out.extend(f"- {x}" for x in avoid_focus)

    out.extend(["", "## Verification summary"])
    if summary_lines:
        for idx, line in summary_lines[-16:]:
            out.append(f"- L{idx}: {line}")
    else:
        out.append("- No final VERIFY_* summary lines found.")

    out.extend(["", "## Still unproved root goals"])
    if still_unproved:
        for idx, line in still_unproved[:max_matches]:
            out.append(f"- L{idx}: {line}")
    else:
        out.append("- No `Still unproved goals:` block found.")

    out.extend(["", "## Final unproved leaf subgoals to repair first"])
    if unproved:
        for item in unproved[:max_matches]:
            src_line = item.get("src_line")
            chars = f"{item.get('char_start')}-{item.get('char_end')}"
            log_lines = ", ".join(f"L{x}" for x in item.get("log_lines", [])[:6])
            if len(item.get("log_lines", [])) > 6:
                log_lines += ", ..."
            results = "; ".join(str(x) for x in item.get("results", [])[:6])
            if len(item.get("results", [])) > 6:
                results += "; ..."
            kind = str(item.get("subgoal_kind"))
            out.append(
                f"- source L{src_line}:{chars}; function `{item.get('function')}`; log {log_lines}; "
                f"goal `{item.get('root_goal')}`; subgoal `{kind}`; results: {results}. "
                f"Repair hint: {_why3_repair_hint(kind, semantic_cluster=cluster)}"
            )
        if len(unproved) > max_matches:
            out.append(f"- ... {len(unproved) - max_matches} more unproved leaf subgoals omitted")
    else:
        out.append("- No leaf subgoal remained unproved after aggregating exact prover results; use root-goal summary and full log.")

    if valid_items:
        out.extend(["", "## Facts already discharged in the focused stage"])
        grouped_valid: dict[tuple[object, object, object], int] = {}
        for obs in valid_items:
            key = (obs.get("src_line"), obs.get("subgoal_kind"), obs.get("root_goal"))
            grouped_valid[key] = grouped_valid.get(key, 0) + 1
        for (src_line, kind, root_goal), count in sorted(grouped_valid.items(), key=lambda x: (int(x[0][0] or 0), str(x[0][1])) )[:80]:
            out.append(f"- source L{src_line}; `{kind}` for `{root_goal}`: Valid in {count} prover attempt(s)")
        if len(grouped_valid) > 80:
            out.append(f"- ... {len(grouped_valid) - 80} more Valid leaf locations omitted")

    if source_lines and unproved:
        out.extend(["", "## Source snippets at unproved locations"])
        seen_lines: set[int] = set()
        for item in unproved[:30]:
            src_line = int(item.get("src_line") or 0)
            if src_line in seen_lines:
                continue
            seen_lines.add(src_line)
            out.append(f"\n### Source line {src_line}: {item.get('subgoal_kind')} / {item.get('root_goal')}")
            snippet = _source_snippet(source_lines, src_line, radius=5)
            if snippet:
                out.extend(snippet)
            else:
                out.append("- source line outside copied file; inspect full log path/file name")

    important_log_lines: set[int] = set()
    for item in unproved[:max_matches]:
        for x in item.get("log_lines", []):
            if isinstance(x, int):
                important_log_lines.add(x)
    for idx, _ in still_unproved:
        important_log_lines.add(idx)

    if important_log_lines:
        out.extend(["", "## Context around final unproved log lines"])
        context: dict[int, str] = {}
        for idx in sorted(important_log_lines):
            for j in range(max(1, idx - context_radius), min(len(lines), idx + context_radius) + 1):
                context[j] = lines[j - 1].rstrip()
        for idx in sorted(context)[: max_matches * 5]:
            out.append(f"L{idx}: {context[idx]}")

    fallback_rx = re.compile(
        r"\b(syntax error|type error|Cannot|Error|Failure|Warning)\b",
        re.IGNORECASE,
    )
    selected = [(idx, line.rstrip()) for idx, line in enumerate(lines, start=1) if fallback_rx.search(line)]
    out.extend(["", "## Parser fallback / non-proof issues only"])
    if selected:
        for idx, line in selected[:40]:
            out.append(f"- L{idx}: {line}")
        if len(selected) > 40:
            out.append(f"- ... {len(selected) - 40} more fallback lines omitted")
    else:
        out.append("- No syntax/type/error lines found. Treat this as a proof-obligation repair, not a parser/type repair.")

    return "\n".join(out) + "\n"


def extract_module_name(source: str) -> str | None:
    m = re.search(r"(?m)^\s*module\s+([A-Za-z_][A-Za-z0-9_']*)\b", source)
    return m.group(1) if m else None


def source_stats_and_audit(source: str, *, kind: str) -> str:
    lines = source.splitlines()
    module_name = extract_module_name(source) or "<not detected>"
    use_lines = [(i, l.strip()) for i, l in enumerate(lines, 1) if l.strip().startswith("use ")]
    val_lines = [(i, l.strip()) for i, l in enumerate(lines, 1) if re.match(r"\s*val\s+", l)]
    let_lines = [(i, l.strip()) for i, l in enumerate(lines, 1) if re.match(r"\s*let\b", l)]
    invariant_lines = [(i, l.strip()) for i, l in enumerate(lines, 1) if "invariant" in l]
    variant_lines = [(i, l.strip()) for i, l in enumerate(lines, 1) if "variant" in l]
    assert_lines = [(i, l.strip()) for i, l in enumerate(lines, 1) if "assert" in l]
    lemma_lines = [(i, l.strip()) for i, l in enumerate(lines, 1) if re.search(r"\blet\s+(rec\s+)?lemma\b|\blemma\b", l)]
    while_lines = [(i, l.strip()) for i, l in enumerate(lines, 1) if re.search(r"\bwhile\b", l)]
    raises_or_exceptions = [(i, l.strip()) for i, l in enumerate(lines, 1) if re.search(r"\bexception\b|\braise\b|\bwith\b", l)]
    array_reads = [(i, l.strip()) for i, l in enumerate(lines, 1) if re.search(r"\w+\s*\[[^\]]+\]", l)]
    list_matches = [(i, l.strip()) for i, l in enumerate(lines, 1) if "Cons" in l or "Nil" in l or "match" in l]

    suspicious: list[str] = []
    if while_lines and not invariant_lines:
        suspicious.append("- The file has `while` loops but no invariants; likely root cause is missing loop invariants.")
    if while_lines and not variant_lines:
        suspicious.append("- The file has `while` loops but no variants; termination may fail.")
    if re.search(r"\blet\s+rec\b", source) and not variant_lines:
        suspicious.append("- The file has recursive definitions but few/no variants; termination may fail.")
    if kind == "array" and array_reads and "0 <=" not in source:
        suspicious.append("- Array reads appear but no obvious lower-bound facts; array-bounds preconditions/assertions may be missing.")
    if kind == "list" and while_lines and "length !cur" not in source and "variant" not in source:
        suspicious.append("- List cursor loop appears without a `length !cur`-style variant.")
    if "run_tests" in source:
        suspicious.append("- `run_tests` is present. Stage 3 final files usually do not need executable tests; remove only if they are not part of the verified target.")

    out = ["# Lightweight Stage 3 source audit", ""]
    out.append(f"Detected kind: `{kind}`")
    out.append(f"Module: `{module_name}`")
    out.append(f"Lines: {len(lines)}")
    out.append(f"Use clauses: {len(use_lines)}")
    out.append(f"Public `val` declarations: {len(val_lines)}")
    out.append(f"`let` declarations: {len(let_lines)}")
    out.append(f"While loops: {len(while_lines)}")
    out.append(f"Invariants: {len(invariant_lines)}")
    out.append(f"Variants: {len(variant_lines)}")
    out.append(f"Assertions: {len(assert_lines)}")
    out.append(f"Lemmas: {len(lemma_lines)}")

    def add_section(title: str, items: list[tuple[int, str]], limit: int) -> None:
        out.extend(["", f"## {title}"])
        if not items:
            out.append("- none found")
            return
        for i, line in items[:limit]:
            out.append(f"- L{i}: `{line}`")
        if len(items) > limit:
            out.append(f"- ... {len(items) - limit} more omitted")

    add_section("Use clauses", use_lines, 30)
    add_section("Public declarations", val_lines, 30)
    add_section("Loops", while_lines, 40)
    add_section("Invariants", invariant_lines, 80)
    add_section("Variants", variant_lines, 80)
    add_section("Assertions", assert_lines, 120)
    add_section("Lemma declarations", lemma_lines, 80)
    if kind == "array":
        add_section("Array reads / updates to inspect for bounds facts", array_reads, 120)
    if kind == "list":
        add_section("List pattern/cursor facts to inspect", list_matches, 120)
    add_section("Exception/control-flow facts", raises_or_exceptions, 80)

    out.extend(["", "## Suspicious proof-repair targets"])
    out.extend(suspicious or ["- none from lightweight heuristics; use verifier log and skill examples."])
    return "\n".join(out) + "\n"


def run_command_to_file(cmd: list[str], *, cwd: Path, output_path: Path, timeout: int | None) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = "Command:\n  " + shlex.join(cmd) + "\n\n"
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        output_path.write_text(header + f"command not found: {cmd[0]}\n", encoding="utf-8")
        return 127
    except subprocess.TimeoutExpired as e:
        output_path.write_text(header + (e.stdout or "") + f"\nTIMEOUT after {timeout} seconds\n", encoding="utf-8")
        return 124
    output_path.write_text(header + (proc.stdout or "") + f"\nExit code: {proc.returncode}\n", encoding="utf-8")
    return proc.returncode


def default_verify_command(repo_root: Path, repaired_mlw: Path) -> str:
    script = repo_root / "scripts" / "why3-verify.sh"
    repaired = rel_or_abs(repaired_mlw, repo_root)
    if script.exists():
        return f"scripts/why3-verify.sh {shlex.quote(repaired)}"
    return f"why3 prove {shlex.quote(repaired)}"


def expand_verify_command(template: str | None, *, repaired_mlw: Path, repo_root: Path) -> str:
    if not template:
        return default_verify_command(repo_root, repaired_mlw)
    repaired_rel = rel_or_abs(repaired_mlw, repo_root)
    try:
        return template.format(
            repaired_mlw=repaired_rel,
            repaired=repaired_rel,
            file=repaired_rel,
        )
    except KeyError:
        return template


def stage3_kind_guidance(kind: str) -> str:
    if kind == "array":
        return """- This is an array Stage 3 final verification repair.
- Use array proof patterns: explicit bounds facts, `0 <= i < length a`, post-loop index facts, accumulator/index coupling invariants, and finite-domain assertions when needed.
- Do not replace array traversal by a different algorithm.
- Do not change `array` parameters into lists or vice versa.
"""
    return """- This is a list Stage 3 final verification repair.
- Use list proof patterns: structural unfolding over `Nil`/`Cons`, cursor-loop invariants relating `!cur` to the processed prefix/suffix, `length !cur` variants, accumulator invariants, and post-loop `!cur = Nil` assertions.
- For exception-based implementations, preserve the exception/control-flow shape and prove the catch result with invariants/assertions.
- Do not replace list cursor loops by a new recursive algorithm unless the Stage 2A implementation was already recursive.
"""


def build_prompt(
    *,
    repo_root: Path,
    run_dir: Path,
    kind: str,
    stage3_skill: str,
    companion: str,
    skill_md: Path,
    examples_dir: Path,
    skill_ok: bool,
    examples_ok: bool,
    original_mlw: Path,
    verifier_log: Path,
    benchmark_json: Path | None,
    stage1a_mlw: Path | None,
    stage2a_mlw: Path | None,
    copied_context_files: list[Path],
    source_audit: Path,
    log_focus: Path,
    original_typecheck: Path,
    repaired_mlw: Path,
    repair_report: Path,
    decision_json: Path,
    typecheck_log: Path,
    patch_path: Path,
    offline_verify_command: str,
    allow_full_verify: bool,
    allow_spec_changes: bool,
    max_repair_iterations: int,
    extra_instructions: str | None,
) -> str:
    def maybe_line(label: str, path: Path | None) -> str:
        if path is None:
            return f"- {label}: not provided"
        return f"- {label}: `{rel_or_abs(path, repo_root)}`"

    context_lines = "\n".join(
        f"  - `{rel_or_abs(p, repo_root)}`" for p in copied_context_files
    ) or "  - none"

    skill_line = (
        f"Open and follow `{rel_or_abs(skill_md, repo_root)}`."
        if skill_ok else
        f"The expected skill `{rel_or_abs(skill_md, repo_root)}` was not found; use the instructions in this prompt as the source of truth."
    )
    examples_line = (
        f"Inspect examples in `{rel_or_abs(examples_dir, repo_root)}` and choose the closest proof pattern."
        if examples_ok else
        f"No examples directory was found at `{rel_or_abs(examples_dir, repo_root)}`; rely on the prompt guidance."
    )

    spec_policy = (
        "Spec changes are allowed only because `--allow-spec-changes` was set. Even then, change Stage 1A semantic specification only with explicit evidence from the benchmark and log; mark `changed_spec=true`."
        if allow_spec_changes else
        "Do not change the Stage 1A semantic specification or public contract. If you suspect a spec bug, report it, set classification to `spec_suspected_wrong_but_not_changed`, and keep the repaired file conservative."
    )
    verify_policy = (
        "Run `why3 prove --type-only` first. If it type-checks, you may run the full offline "
        f"verification command `{offline_verify_command}` because `--allow-full-verify` was set. "
        "If full verification fails, read the new log and do another focused repair iteration."
        if allow_full_verify else
        "Do not run full verification in this wrapper. "
        "Run `why3 prove --type-only` on the repaired file when Why3 is available. "
        "Run full verification separately in your offline workflow."
    )
    extra = f"\nAdditional user instructions:\n{extra_instructions.strip()}\n" if extra_instructions else ""

    return f"""Use the Diversify2Verify Stage 3 Why3 verification repair workflow.

Goal: repair a failing final-verification `.mlw` file using the offline verifier log. The expected cause is missing proof scaffolding: invariants, assertions, variants, helper contracts, or small auxiliary lemmas.

Stage 3 skill:
- Primary skill: `{stage3_skill}`
- Companion skill for the other data structure: `{companion}`. Do not use it unless it clarifies an analogous proof pattern.
- {skill_line}
- {examples_line}

Run output root:
`{rel_or_abs(run_dir, repo_root)}`

Inputs:
- Failing Stage 3 Why3 file: `{rel_or_abs(original_mlw, repo_root)}`
- Offline verifier log: `{rel_or_abs(verifier_log, repo_root)}`
{maybe_line('Benchmark JSON', benchmark_json)}
{maybe_line('Stage 1A spec reference', stage1a_mlw)}
{maybe_line('Stage 2A implementation reference', stage2a_mlw)}
- Focused verifier-log extract: `{rel_or_abs(log_focus, repo_root)}`
- Lightweight source audit: `{rel_or_abs(source_audit, repo_root)}`
- Original type-check log: `{rel_or_abs(original_typecheck, repo_root)}`
- Additional context files:
{context_lines}

Detected target kind: `{kind}`

Kind-specific guidance:
{stage3_kind_guidance(kind)}

Failure-cluster repair playbook:

- `public_postcondition_bridge`:
  - Treat this as a semantic bridge failure from a helper/model result to the public `ensures` clause.
  - Do not rewrite the algorithm and do not focus on call preconditions that `log_focus.md` says are already Valid.
  - Strengthen helper/model postconditions so they expose the exact semantic predicate needed by the public wrapper.
  - Add a small bridge/combine lemma that follows the implementation structure, for example current case vs recursive tail, processed prefix vs remaining suffix, or loop accumulator vs final result.
  - Split the final property into existence/feasibility and universal optimality/upper-bound facts when the spec is an optimization predicate.

- `large_assertion_needs_decomposition`:
  - Treat the assertion as too large. Replace it with smaller local facts, explicit quantifier instantiations, or a proved helper lemma.
  - Do not move the same assertion elsewhere without proving its prerequisites.

- `semantic_loop_invariant`:
  - Bounds-only invariants are insufficient for final verification.
  - Every accumulator/ref/cursor should have an invariant relating it to the processed prefix/range/window and the original input.
  - Add post-loop assertions converting the invariant plus the loop exit condition into the public postcondition.

- `optimization_optimality`:
  - Separate candidate construction from universal optimality.
  - Add monotonicity, dominance, exchange, or max/min-combine lemmas as needed.
  - For recursive algorithms, split competitors into the current branch and recursive subproblem.

- `sorting_or_order_helper`:
  - Prove sortedness, membership/permutation, length, and no-duplicate/positivity preservation separately.
  - Prefer reusable insertion/sorting lemmas over ad hoc monolithic assertions.

- `counting_cardinality_occurrence`:
  - Add structural induction lemmas for `mem`, `num_occ`, `cardinal`, `length`, and append/prefix facts.
  - Enumerate finite domains explicitly when proving quantified facts over concrete arrays/lists.

- `prefix_window_subarray_bridge`:
  - Add explicit shift/slice/drop/take lemmas mapping original indices to suffix/window indices.
  - Split boundary cases such as empty/non-empty, `i = 0` vs `i > 0`, or current window vs recursive suffix.

Primary outputs to create exactly:

1. Repaired Why3 file:
   `{rel_or_abs(repaired_mlw, repo_root)}`

2. Human-readable repair report:
   `{rel_or_abs(repair_report, repo_root)}`

3. Machine-readable decision summary JSON:
   `{rel_or_abs(decision_json, repo_root)}`

4. Type-check output for the repaired file, if Why3 is available:
   `{rel_or_abs(typecheck_log, repo_root)}`

5. Unified diff from original to repaired file:
   `{rel_or_abs(patch_path, repo_root)}`

Non-negotiable preservation rules:

- {spec_policy}
- Preserve the implementation strategy from Stage 2A:
  - recursive implementations must remain recursive;
  - imperative implementations must remain imperative;
  - do not replace a loop with a recursive helper or recursive code with refs/loops;
  - do not redesign the algorithm just because another proof would be easier.
- Preserve module-level intent, public function names, public signatures, and contracts.
- Preserve Stage 1A helper predicates/functions unless `--allow-spec-changes` was set and the evidence is strong.
- Stage 3 does not need Stage 1A concrete lemma tests or Stage 2A executable `run_tests`. Remove/omit tests only when they are clearly not part of the final verified target.
- Do not add axioms. Use lemmas only when necessary and prove them.

Mandatory repair workflow:

0. Read the verifier log and `log_focus.md`; identify the earliest/root verification failures before fixing cascading errors.
   Treat `Final unproved leaf subgoals to repair first` and `Source snippets at unproved locations` in `log_focus.md` as the primary repair targets. Ignore early Timeout/Unknown observations that later have a Valid result.
1. Compare the Stage 3 file with the Stage 1A spec reference, when provided. Ensure the semantic spec and public contract are preserved.
2. Compare the Stage 3 file with the Stage 2A implementation reference, when provided. Ensure the implementation style and algorithm are preserved.
3. Classify both the proof-failure kind and the semantic cluster. Prefer the semantic cluster from `log_focus.md` unless you find stronger evidence.
4. Repair in the smallest useful way:
   - strengthen loop invariants;
   - add variants;
   - add branch-local and post-loop assertions;
   - strengthen helper postconditions when the public proof needs semantic facts;
   - add helper preconditions only for well-formedness/proof obligations, not to weaken the public spec;
   - add small proved lemmas only when assertions/invariants/helper contracts are not enough.
5. Prefer the closest example pattern from `{stage3_skill}/examples/`; state the chosen pattern in the PLAN/report.
6. Use one initial repair plus up to `{max_repair_iterations}` additional repair iterations inside Codex if type-checking fails or, when full verification is enabled, if the refreshed full-verification log still has remaining goals.

Validation policy:

- {verify_policy}
- If Why3 is available, run exactly:
  `why3 prove --type-only {shlex.quote(rel_or_abs(repaired_mlw, repo_root))}`
  and save combined stdout/stderr to `{rel_or_abs(typecheck_log, repo_root)}`.
- Always create the unified diff at `{rel_or_abs(patch_path, repo_root)}`.
- The user will run full verification offline with:
  `{offline_verify_command}`

Decision JSON schema:
Create a JSON object with these fields:
- `classification`: one of {json.dumps(CLASSIFICATION_CHOICES)}
- `semantic_cluster`: one of {json.dumps(SEMANTIC_CLUSTER_CHOICES)}
- `confidence`: number from 0.0 to 1.0
- `changed_spec`: boolean
- `changed_public_signature`: boolean
- `changed_implementation_strategy`: boolean
- `removed_tests_only`: boolean
- `added_invariants`: array of strings
- `added_variants`: array of strings
- `added_assertions`: array of strings
- `added_lemmas`: array of strings
- `changed_helper_contracts`: array of strings
- `root_cause_summary`: string
- `skill_example_pattern_used`: string or null
- `key_log_locations`: array of strings
- `key_source_locations`: array of strings
- `repair_summary`: array of strings
- `typecheck_command`: string
- `typecheck_exit_code`: integer or null
- `offline_verification_command`: string, exactly `{offline_verify_command}` unless you have a better project-specific command
- `remaining_risks`: array of strings

Report requirements:
- Start with the suspected root cause.
- State whether the Stage 1A spec was preserved.
- State whether the Stage 2A implementation strategy was preserved.
- State which skill example pattern was used, if any.
- List the proof scaffolding added: invariants, variants, assertions, helper contracts, lemmas.
- Include the exact offline verification command:
  `{offline_verify_command}`
- Keep the report concise and practical.

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
        "--cd", str(repo_root),
        "--sandbox", sandbox,
        "--add-dir", str(run_dir),
        "--output-last-message", str(final_path),
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


def validate_decision_json(path: Path, *, enforce_no_spec_changes: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return False, f"invalid JSON: {e}"
    if not isinstance(data, dict):
        return False, "JSON root is not an object"
    required = [
        "classification", "semantic_cluster", "confidence", "changed_spec",
        "changed_public_signature", "changed_implementation_strategy",
        "root_cause_summary", "repair_summary", "offline_verification_command",
    ]
    missing = [k for k in required if k not in data]
    if missing:
        return False, "missing keys: " + ", ".join(missing)
    if data.get("classification") not in CLASSIFICATION_CHOICES:
        return False, f"unknown classification: {data.get('classification')!r}"
    if data.get("semantic_cluster") not in SEMANTIC_CLUSTER_CHOICES:
        return False, f"unknown semantic_cluster: {data.get('semantic_cluster')!r}"
    if enforce_no_spec_changes and data.get("changed_spec"):
        return False, "changed_spec=true is disallowed by default Stage 3 policy; pass --allow-spec-changes if needed"
    return True, "ok"


def write_diff(original: Path, repaired: Path, diff_path: Path) -> None:
    if not repaired.exists():
        return
    original_lines = original.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    repaired_lines = repaired.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines,
        repaired_lines,
        fromfile=str(original),
        tofile=str(repaired),
    )
    write_text(diff_path, "".join(diff))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Codex to repair a failing Stage 3 Why3 final-verification file from an offline verifier log."
    )
    parser.add_argument("stage3_mlw", type=Path, help="Failing Stage 3 .mlw file.")
    parser.add_argument("verifier_log", type=Path, help="Offline verifier output log from the failed run.")
    parser.add_argument("--benchmark-json", type=Path, default=None, help="Optional normalized benchmark JSON.")
    parser.add_argument("--stage1a-mlw", type=Path, default=None, help="Optional Stage 1A spec .mlw reference.")
    parser.add_argument("--stage2a-mlw", type=Path, default=None, help="Optional Stage 2A implementation .mlw reference.")
    parser.add_argument("--context-file", type=Path, action="append", default=[], help="Optional extra context file. Repeat as needed.")
    parser.add_argument("--kind", choices=KIND_CHOICES, default="auto", help="Repair kind: array or list. Auto infers from file.")
    parser.add_argument("--stage3-skill", default=None, help="Override Stage 3 skill name. Defaults to why3_array_verification or why3_list_verification.")
    parser.add_argument("--require-stage3-skill", action="store_true", help="Fail early if the selected Stage 3 skill is missing.")
    parser.add_argument("--out-dir", type=Path, default=Path("codex-runs/stage3-repair"), help="Run output directory.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root passed to `codex exec --cd`.")
    parser.add_argument("--model", default="gpt-5.5", help="Codex model. Use empty string to rely on Codex config.")
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high", "xhigh"], default="high", help="Codex reasoning effort.")
    parser.add_argument("--codex-bin", default="codex", help="Codex executable name/path.")
    parser.add_argument("--sandbox", default="workspace-write", choices=["read-only", "workspace-write", "danger-full-access"], help="Codex sandbox mode.")
    parser.add_argument("--ask-for-approval", default="never", choices=["untrusted", "on-request", "never"], help="Codex approval policy.")
    parser.add_argument("--max-repair-iterations", type=int, default=4, help="Repair iterations requested inside the Codex prompt.")
    parser.add_argument("--timestamp", action="store_true", help="Create a timestamped run directory.")
    parser.add_argument("--no-json", action="store_true", help="Do not pass --json to Codex.")
    parser.add_argument("--skip-git-repo-check", action="store_true", help="Pass --skip-git-repo-check to Codex.")
    parser.add_argument("--timeout", type=int, default=None, help="Wall-clock timeout in seconds for Codex.")
    parser.add_argument("--preflight-timeout", type=int, default=30, help="Timeout for original type-only preflight.")
    parser.add_argument("--no-preflight-typecheck", action="store_true", help="Skip local `why3 prove --type-only` on the copied original file.")
    parser.add_argument("--codex-arg", action="append", default=[], help="Extra raw argument appended to `codex exec`. Repeat as needed.")
    parser.add_argument("--allow-full-verify", action="store_true", help="Allow Codex to run full verification. Default: type-check only.")
    parser.add_argument(
        "--allow-spec-changes",
        action="store_true",
        help="Allow semantic spec changes. Default: disallowed for Stage 3 repair.",
    )
    parser.add_argument("--verify-command", default=None, help="Offline verification command template, e.g. 'scripts/why3-verify.sh {repaired_mlw}'.")
    parser.add_argument("--extra-instructions", default=None, help="Additional text appended to the Codex prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Write prompt and print command without invoking Codex.")
    parser.add_argument("--allow-missing-files", action="store_true", help="Do not fail if expected output files are missing after Codex exits.")

    args = parser.parse_args(argv)
    if args.max_repair_iterations < 0:
        die("--max-repair-iterations must be non-negative")

    stage3_path = args.stage3_mlw.resolve()
    log_path = args.verifier_log.resolve()
    repo_root = args.repo_root.resolve()
    out_dir = args.out_dir.resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        die(f"repo root does not exist or is not a directory: {repo_root}")
    if stage3_path.suffix != ".mlw":
        print(f"warning: input does not end in .mlw: {stage3_path}", file=sys.stderr)

    kind = infer_kind(stage3_path, args.kind)
    stage3_skill = args.stage3_skill or default_stage3_skill(kind)
    companion = companion_skill(kind)
    skill_ok, examples_ok, skill_md, examples_dir = check_skill(repo_root, stage3_skill, require=args.require_stage3_skill)

    run_dir = make_run_dir(out_dir, stage3_path, args.timestamp)
    run_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir = run_dir / "inputs"

    copied_stage3 = copy_file(stage3_path, inputs_dir / "stage3_original.mlw", what="Stage 3 Why3 file")
    copied_log = copy_file(log_path, inputs_dir / "verifier.log", what="verifier log")
    copied_benchmark = copy_file(args.benchmark_json, inputs_dir / "benchmark.json", what="benchmark JSON") if args.benchmark_json else None
    copied_stage1a = copy_file(args.stage1a_mlw, inputs_dir / "stage1a_spec.mlw", what="Stage 1A spec") if args.stage1a_mlw else None
    copied_stage2a = copy_file(args.stage2a_mlw, inputs_dir / "stage2a_impl.mlw", what="Stage 2A implementation") if args.stage2a_mlw else None

    copied_context_files: list[Path] = []
    for i, src in enumerate(args.context_file):
        dst_name = f"{i:02d}_{slugify(src.resolve().name)}"
        copied_context_files.append(copy_file(src, inputs_dir / "context" / dst_name, what="context file"))

    reports_dir = run_dir / "generated" / "reports"
    repaired_mlw = run_dir / "generated" / "why3" / "repaired.mlw"
    repair_report = reports_dir / "repair_report.md"
    decision_json = reports_dir / "repair_decision.json"
    original_typecheck = reports_dir / "original.typecheck.txt"
    repaired_typecheck = reports_dir / "repaired.typecheck.txt"
    source_audit = reports_dir / "source_audit.md"
    log_focus = reports_dir / "log_focus.md"
    patch_path = run_dir / "generated" / "patches" / "repaired.diff"

    prompt_path = run_dir / "prompt.md"
    final_path = run_dir / "codex.final.md"
    stdout_path = run_dir / ("codex.stdout.jsonl" if not args.no_json else "codex.stdout.log")
    stderr_path = run_dir / "codex.stderr.log"

    source_text = read_text(copied_stage3, what="copied Stage 3 Why3 file")
    log_text = read_text(copied_log, what="copied verifier log")
    write_text(source_audit, source_stats_and_audit(source_text, kind=kind))
    write_text(log_focus, extract_log_focus(log_text, source_text=source_text))

    if args.no_preflight_typecheck:
        write_text(original_typecheck, "skipped by --no-preflight-typecheck\n")
    else:
        why3 = shutil.which("why3")
        if why3 is None:
            write_text(original_typecheck, "why3 not found on PATH; skipped local preflight type-check\n")
        else:
            run_command_to_file(
                [why3, "prove", "--type-only", str(copied_stage3)],
                cwd=repo_root,
                output_path=original_typecheck,
                timeout=args.preflight_timeout,
            )

    offline_verify_command = expand_verify_command(args.verify_command, repaired_mlw=repaired_mlw, repo_root=repo_root)

    prompt = build_prompt(
        repo_root=repo_root,
        run_dir=run_dir,
        kind=kind,
        stage3_skill=stage3_skill,
        companion=companion,
        skill_md=skill_md,
        examples_dir=examples_dir,
        skill_ok=skill_ok,
        examples_ok=examples_ok,
        original_mlw=copied_stage3,
        verifier_log=copied_log,
        benchmark_json=copied_benchmark,
        stage1a_mlw=copied_stage1a,
        stage2a_mlw=copied_stage2a,
        copied_context_files=copied_context_files,
        source_audit=source_audit,
        log_focus=log_focus,
        original_typecheck=original_typecheck,
        repaired_mlw=repaired_mlw,
        repair_report=repair_report,
        decision_json=decision_json,
        typecheck_log=repaired_typecheck,
        patch_path=patch_path,
        offline_verify_command=offline_verify_command,
        allow_full_verify=args.allow_full_verify,
        allow_spec_changes=args.allow_spec_changes,
        max_repair_iterations=args.max_repair_iterations,
        extra_instructions=args.extra_instructions,
    )
    write_text(prompt_path, prompt)

    model = args.model if args.model.strip() else None
    codex_rc = run_codex(
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

    if repaired_mlw.exists() and not patch_path.exists():
        write_diff(copied_stage3, repaired_mlw, patch_path)

    typecheck_rc: int | None = None
    why3 = shutil.which("why3")
    if not repaired_mlw.exists():
        write_text(repaired_typecheck, "repaired Why3 file missing; skipped repaired type-check\n")
    elif why3 is None:
        write_text(repaired_typecheck, "why3 not found on PATH; skipped repaired type-check\n")
    else:
        typecheck_rc = run_command_to_file(
            [why3, "prove", "--type-only", str(repaired_mlw)],
            cwd=repo_root,
            output_path=repaired_typecheck,
            timeout=args.preflight_timeout,
        )
        with repaired_typecheck.open("a", encoding="utf-8") as f:
            f.write(f"\n[typecheck_exit_code={typecheck_rc}]\n")

    decision_ok, decision_status = validate_decision_json(
        decision_json,
        enforce_no_spec_changes=(not args.allow_spec_changes),
    )

    print("\nRun directory:")
    print(f"  {run_dir}")
    print(f"Detected kind: {kind}")
    print(f"Stage 3 skill: {stage3_skill} [{'ok' if skill_ok else 'missing'}]")
    print(f"Skill examples: {examples_dir} [{'ok' if examples_ok else 'missing'}]")
    print("Generated wrapper evidence:")
    for label, path in [
        ("SOURCE_AUDIT", source_audit),
        ("LOG_FOCUS   ", log_focus),
        ("ORIG_TYPECHK", original_typecheck),
    ]:
        print(f"  {label}: {path} [{'ok' if path.exists() else 'missing'}]")
    print("Expected generated files:")
    for label, path in [
        ("REPAIRED", repaired_mlw),
        ("REPORT  ", repair_report),
        ("DECISION", decision_json),
        ("TYPECHK ", repaired_typecheck),
        ("DIFF    ", patch_path),
    ]:
        print(f"  {label}: {path} [{'ok' if path.exists() else 'missing'}]")
    print(f"Decision JSON: {decision_status}")
    print(f"Offline verification command: {offline_verify_command}")

    if codex_rc != 0:
        print(f"\nCodex exited with code {codex_rc}. See logs in {run_dir}.", file=sys.stderr)
        return codex_rc

    if typecheck_rc not in (None, 0):
        print(f"\nRepaired file failed Why3 type-check with code {typecheck_rc}. See {repaired_typecheck}.", file=sys.stderr)
        return typecheck_rc

    if not args.dry_run and not args.allow_missing_files:
        missing = [p for p in [repaired_mlw, repair_report, decision_json] if not p.exists()]
        if missing:
            print("\nerror: Codex completed but expected files are missing:", file=sys.stderr)
            for p in missing:
                print(f"  {p}", file=sys.stderr)
            print("Use --allow-missing-files to ignore this check.", file=sys.stderr)
            return 2
        if not decision_ok:
            print(f"\nerror: decision JSON validation failed: {decision_status}", file=sys.stderr)
            print("Use --allow-missing-files to ignore this check.", file=sys.stderr)
            return 3

    if not args.dry_run and not args.allow_missing_files and not repaired_typecheck.exists():
        print(f"\nwarning: repaired type-check log is missing: {repaired_typecheck}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
