#!/usr/bin/env bash
set -uo pipefail

# why3-verify.sh
#
# Usage:
#   ./why3-verify.sh file.mlw
#
# Optional environment variables:
#   PROVERS="Z3,4.8.6:Alt-Ergo,2.4.0:CVC4,1.8"
#   STAGE1_TIME=10
#   STAGE1_MEM=8192
#   STAGE2_TIME=10
#   STAGE2_MEM=8192
#   STAGE3_TIME=10
#   STAGE3_MEM=8192
#   OUTER_SLACK=20
#   KEEP_SESSION=1
#   KEEP_LOGS=1

PROVERS="${PROVERS:-Z3,4.8.6:Alt-Ergo,2.4.0:CVC4,1.8}"
STAGE1_TIME="${STAGE1_TIME:-10}"
STAGE1_MEM="${STAGE1_MEM:-8192}"
STAGE2_TIME="${STAGE2_TIME:-10}"
STAGE2_MEM="${STAGE2_MEM:-8192}"
STAGE3_TIME="${STAGE3_TIME:-$STAGE2_TIME}"
STAGE3_MEM="${STAGE3_MEM:-$STAGE2_MEM}"
OUTER_SLACK="${OUTER_SLACK:-20}"
KEEP_SESSION="${KEEP_SESSION:-0}"
KEEP_LOGS="${KEEP_LOGS:-0}"

BROKEN_PROVERS=()
ROOT_TOTAL="unknown"

emit_result() {
  local status="$1"      # SUCCESS | FAILURE | ERROR
  local reason="$2"
  local stage="$3"
  local total="${4:-unknown}"
  local proved="${5:-unknown}"
  local remaining="${6:-unknown}"

  echo "VERIFY_RESULT: $status" >&2
  echo "VERIFY_REASON: $reason" >&2
  echo "VERIFY_STAGE: $stage" >&2
  echo "VERIFY_ROOT_TOTAL: $total" >&2
  echo "VERIFY_ROOT_PROVED: $proved" >&2
  echo "VERIFY_ROOT_REMAINING: $remaining" >&2
}

usage_error() {
  echo "Usage: $0 <file.mlw>" >&2
  emit_result "ERROR" "invalid_input" "setup" "unknown" "unknown" "unknown"
  exit 2
}

if [[ $# -ne 1 ]]; then
  usage_error
fi

INPUT="$1"
if [[ ! -f "$INPUT" ]]; then
  echo "Error: file not found: $INPUT" >&2
  emit_result "ERROR" "file_not_found" "setup" "unknown" "unknown" "unknown"
  exit 2
fi

FILE_DIR="$(cd "$(dirname "$INPUT")" && pwd)"
FILE_BASE="$(basename "$INPUT")"
BASE_NO_EXT="${FILE_BASE%.mlw}"

SESSION_ROOT="$FILE_DIR/.why3_sessions"
SESSION1="$SESSION_ROOT/${BASE_NO_EXT}_stage1"
LOG_DIR="$SESSION_ROOT/${BASE_NO_EXT}_logs"

mkdir -p "$SESSION_ROOT" "$LOG_DIR"

cleanup() {
  if [[ "$KEEP_SESSION" != "1" ]]; then
    rm -rf "$SESSION1"
  else
    echo "Keeping session directory: $SESSION1" >&2
  fi

  if [[ "$KEEP_LOGS" != "1" ]]; then
    rm -rf "$LOG_DIR"
  else
    echo "Keeping logs in: $LOG_DIR" >&2
  fi
}
trap cleanup EXIT

split_provers() {
  local IFS=':'
  read -r -a PROVER_ARRAY <<< "$PROVERS"
  printf '%s\n' "${PROVER_ARRAY[@]}"
}

safe_name() {
  printf '%s' "$1" | sed 's/[^A-Za-z0-9._-]/_/g'
}

run_with_timeout() {
  local secs="$1"
  shift

  if command -v gtimeout >/dev/null 2>&1; then
    gtimeout -k 5s "${secs}s" "$@"
  elif command -v timeout >/dev/null 2>&1; then
    timeout -k 5s "${secs}s" "$@"
  else
    "$@"
  fi
}

is_broken_prover() {
  local p="$1"
  local x
  for x in "${BROKEN_PROVERS[@]}"; do
    [[ "$x" == "$p" ]] && return 0
  done
  return 1
}

mark_broken_prover() {
  local p="$1"
  is_broken_prover "$p" || BROKEN_PROVERS+=("$p")
}

is_infra_output() {
  local out="$1"
  printf '%s\n' "$out" | grep -Eqi \
    'why3server|socket|connection (failed|refused|reset)|broken pipe|internalfailure|highfailure'
}

classify_attempt() {
  local rc="$1"
  local out="$2"

  if [[ $rc -eq 124 || $rc -eq 137 ]]; then
    echo "infra"
    return
  fi

  if is_infra_output "$out"; then
    echo "infra"
    return
  fi

  local result_lines
  result_lines="$(printf '%s\n' "$out" | grep 'Prover result is:' || true)"

  # No explicit prover results. Nonzero exit means infrastructure issue.
  if [[ -z "$result_lines" ]]; then
    if [[ $rc -ne 0 ]]; then
      echo "infra"
    else
      echo "fail"
    fi
    return
  fi

  # Infrastructure-level prover failures.
  if printf '%s\n' "$result_lines" | grep -Eq 'Prover result is: HighFailure\b'; then
    echo "infra"
    return
  fi

  # Any negative result on any subgoal means the whole attempt is not proved.
  if printf '%s\n' "$result_lines" | grep -Eq \
    'Prover result is: (Unknown|Timeout|OutOfMemory|StepLimitExceeded|Failure|Invalid)\b'; then
    echo "fail"
    return
  fi

  # Success only if every reported result is Valid.
  if printf '%s\n' "$result_lines" | grep -Eqv 'Prover result is: Valid\b'; then
    echo "fail"
    return
  fi

  echo "proved"
}

session_stats() {
  why3 session info --session-stats "$SESSION1"
}

extract_unproved_root_goals_from_text() {
  awk '
    /== Goals not proved ==/ { in_unproved=1; next }
    /^== / && in_unproved { in_unproved=0 }
    !in_unproved { next }

    /^[[:space:]]+\+-- theory / {
      theory=$0
      sub(/^[[:space:]]+\+-- theory /, "", theory)
      next
    }

    /^[[:space:]]+\+-- goal / {
      goal=$0
      sub(/^[[:space:]]+\+-- goal /, "", goal)
      sub(/:.*/, "", goal)
      if (theory != "" && goal != "") {
        print theory "\t" goal
      }
      next
    }
  '
}

extract_root_total_from_stats() {
  awk '
    /== Number of root goals ==/ {
      getline
      if (match($0, /total: [0-9]+/)) {
        s = substr($0, RSTART, RLENGTH)
        sub(/total: /, "", s)
        print s
        exit
      }
    }
  '
}

prove_goal_with_one_prover() {
  local theory="$1"
  local goal="$2"
  local prover="$3"
  local stage="$4"
  shift 4
  local transforms=("$@")

  local tl ml outer
  case "$stage" in
    stage1)
      tl="$STAGE1_TIME"
      ml="$STAGE1_MEM"
      ;;
    stage2)
      tl="$STAGE2_TIME"
      ml="$STAGE2_MEM"
      ;;
    stage3)
      tl="$STAGE3_TIME"
      ml="$STAGE3_MEM"
      ;;
    *)
      tl="$STAGE2_TIME"
      ml="$STAGE2_MEM"
      ;;
  esac
  outer=$((tl + OUTER_SLACK))

  local transform_tag="plain"
  if [[ ${#transforms[@]} -gt 0 ]]; then
    transform_tag="$(printf '%s__' "${transforms[@]}")"
    transform_tag="${transform_tag%__}"
  fi

  local logfile
  logfile="$LOG_DIR/${stage}__${transform_tag}__$(safe_name "$prover")__$(safe_name "$theory")__$(safe_name "$goal").log"

  local -a cmd
  cmd=(
    why3 prove
    "$FILE_BASE"
    -T "$theory"
    -G "$goal"
  )

  local tr
  for tr in "${transforms[@]}"; do
    cmd+=(-a "$tr")
  done

  cmd+=(
    -P "$prover"
    --timelimit="$tl"
    --memlimit="$ml"
  )

  local out rc status
  out="$(
    cd "$FILE_DIR" && \
    run_with_timeout "$outer" "${cmd[@]}" 2>&1
  )"
  rc=$?

  printf '%s\n' "$out" > "$logfile"

  echo "---- $stage | prover: $prover | theory: $theory | goal: $goal ----" >&2
  if [[ ${#transforms[@]} -gt 0 ]]; then
    echo "Transforms: ${transforms[*]}" >&2
  fi
  echo "$out" >&2

  status="$(classify_attempt "$rc" "$out")"
  case "$status" in
    proved)
      return 0
      ;;
    infra)
      mark_broken_prover "$prover"
      return 2
      ;;
    *)
      return 1
      ;;
  esac
}

run_stage1_first_prover() {
  local first_prover="$1"

  rm -rf "$SESSION1"

  (
    cd "$FILE_DIR"
    echo "== Stage 1: first prover on whole file ==" >&2
    echo "Running in $FILE_DIR: why3 session create -o $SESSION1 -P $first_prover -t $STAGE1_TIME -m $STAGE1_MEM $FILE_BASE" >&2
    why3 session create -o "$SESSION1" -P "$first_prover" -t "$STAGE1_TIME" -m "$STAGE1_MEM" "$FILE_BASE"
  )
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "Stage 1 session creation failed." >&2
    return 3
  fi

  local out
  out="$(
    cd "$FILE_DIR" && \
    echo "Running in $FILE_DIR: why3 bench $SESSION1" >&2 && \
    run_with_timeout $((STAGE1_TIME + OUTER_SLACK)) why3 bench "$SESSION1" 2>&1
  )"
  rc=$?

  printf '%s\n' "$out" > "$LOG_DIR/stage1__bench__$(safe_name "$first_prover").log"
  echo "$out" >&2

  if [[ $rc -ne 0 ]] || is_infra_output "$out"; then
    echo "Stage 1 infrastructure issue; skipping the rest of stage 1 and continuing." >&2
    mark_broken_prover "$first_prover"
    return 2
  fi

  return 0
}

main() {
  mapfile -t PROVER_LIST < <(split_provers)

  if [[ ${#PROVER_LIST[@]} -eq 0 ]]; then
    echo "No provers configured." >&2
    emit_result "ERROR" "no_provers_configured" "setup" "unknown" "unknown" "unknown"
    exit 2
  fi

  local first_prover="${PROVER_LIST[0]}"
  local stage1_broken=0
  local rc

  run_stage1_first_prover "$first_prover"
  rc=$?
  if [[ $rc -eq 3 ]]; then
    emit_result "ERROR" "stage1_session_creation_failed" "stage1" "unknown" "unknown" "unknown"
    exit 2
  elif [[ $rc -eq 2 ]]; then
    stage1_broken=1
  fi

  local stats_text
  stats_text="$(session_stats 2>&1)"
  rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "Could not read session stats." >&2
    echo "$stats_text" >&2
    emit_result "ERROR" "session_stats_unavailable" "stage1" "unknown" "unknown" "unknown"
    exit 2
  fi

  echo "== Stage 1 stats ==" >&2
  printf '%s\n' "$stats_text" >&2

  ROOT_TOTAL="$(printf '%s\n' "$stats_text" | extract_root_total_from_stats)"
  if [[ -z "$ROOT_TOTAL" ]]; then
    ROOT_TOTAL="unknown"
  fi

  local -a REMAINING
  mapfile -t REMAINING < <(printf '%s\n' "$stats_text" | extract_unproved_root_goals_from_text)

  if [[ ${#REMAINING[@]} -eq 0 ]]; then
    echo "All stage-1 goals are proved. No need to continue." >&2
    emit_result "SUCCESS" "proved_in_stage1" "stage1" "$ROOT_TOTAL" "$ROOT_TOTAL" "0"
    exit 0
  fi

  echo "== Unproved root goals after first prover ==" >&2
  printf '%s\n' "${REMAINING[@]}" >&2

  if [[ $stage1_broken -eq 0 ]]; then
    local i j entry theory goal prover
    for (( i=1; i<${#PROVER_LIST[@]}; i++ )); do
      prover="${PROVER_LIST[$i]}"
      [[ ${#REMAINING[@]} -eq 0 ]] && break
      is_broken_prover "$prover" && continue

      echo "== Stage 1: trying remaining goals with prover $prover ==" >&2

      local -a NEXT_REMAINING=()
      for (( j=0; j<${#REMAINING[@]}; j++ )); do
        entry="${REMAINING[$j]}"
        theory="${entry%%$'\t'*}"
        goal="${entry#*$'\t'}"

        prove_goal_with_one_prover "$theory" "$goal" "$prover" "stage1"
        rc=$?

        if [[ $rc -eq 0 ]]; then
          echo "Solved in stage 1 using prover: $prover" >&2
        elif [[ $rc -eq 1 ]]; then
          NEXT_REMAINING+=("$entry")
        else
          echo "Infrastructure issue in stage 1 with prover $prover; aborting rest of stage 1." >&2
          NEXT_REMAINING+=("$entry")
          for (( j=j+1; j<${#REMAINING[@]}; j++ )); do
            NEXT_REMAINING+=("${REMAINING[$j]}")
          done
          stage1_broken=1
          break
        fi
      done

      REMAINING=("${NEXT_REMAINING[@]}")
      echo "Remaining after prover $prover: ${#REMAINING[@]}" >&2
      [[ $stage1_broken -eq 1 ]] && break
    done
  fi

  if [[ ${#REMAINING[@]} -eq 0 ]]; then
    echo "All goals proved after sequential stage 1. No need to continue." >&2
    emit_result "SUCCESS" "proved_after_stage1" "stage1" "$ROOT_TOTAL" "$ROOT_TOTAL" "0"
    exit 0
  fi

  echo "== Goals still unproved after stage 1 ==" >&2
  printf '%s\n' "${REMAINING[@]}" >&2

  local -a AFTER_SPLIT_REMAINING=()
  local stage2_broken=0
  local solved
  local j entry theory goal prover
  for (( j=0; j<${#REMAINING[@]}; j++ )); do
    entry="${REMAINING[$j]}"
    theory="${entry%%$'\t'*}"
    goal="${entry#*$'\t'}"
    solved=0

    echo "== Stage 2: split_vc on unproved goal ==" >&2
    echo "Target theory: $theory" >&2
    echo "Target goal  : $goal" >&2

    for prover in "${PROVER_LIST[@]}"; do
      is_broken_prover "$prover" && continue

      prove_goal_with_one_prover "$theory" "$goal" "$prover" "stage2" "split_vc"
      rc=$?

      if [[ $rc -eq 0 ]]; then
        echo "Solved with split_vc using prover: $prover" >&2
        solved=1
        break
      elif [[ $rc -eq 2 ]]; then
        echo "Infrastructure issue in stage 2 with prover $prover; aborting rest of stage 2." >&2
        stage2_broken=1
        break
      fi
    done

    [[ $solved -eq 0 ]] && AFTER_SPLIT_REMAINING+=("$entry")

    if [[ $stage2_broken -eq 1 ]]; then
      for (( j=j+1; j<${#REMAINING[@]}; j++ )); do
        AFTER_SPLIT_REMAINING+=("${REMAINING[$j]}")
      done
      break
    fi
  done

  if [[ ${#AFTER_SPLIT_REMAINING[@]} -eq 0 ]]; then
    echo "== Final summary ==" >&2
    echo "Unproved root goals after first prover : ${#REMAINING[@]}" >&2
    echo "Remaining failures after split_vc      : 0" >&2
    echo "Remaining failures after stage 3       : 0" >&2
    echo "Detailed logs stored in                : $LOG_DIR" >&2
    emit_result "SUCCESS" "proved_after_stage2" "stage2" "$ROOT_TOTAL" "$ROOT_TOTAL" "0"
    exit 0
  fi

  echo "== Goals still unproved after stage 2 (split_vc) ==" >&2
  printf '%s\n' "${AFTER_SPLIT_REMAINING[@]}" >&2

  local -a FINAL_REMAINING=()
  local stage3_broken=0
  for (( j=0; j<${#AFTER_SPLIT_REMAINING[@]}; j++ )); do
    entry="${AFTER_SPLIT_REMAINING[$j]}"
    theory="${entry%%$'\t'*}"
    goal="${entry#*$'\t'}"
    solved=0

    echo "== Stage 3: split_vc + inline_all on still-unproved goal ==" >&2
    echo "Target theory: $theory" >&2
    echo "Target goal  : $goal" >&2

    for prover in "${PROVER_LIST[@]}"; do
      is_broken_prover "$prover" && continue

      prove_goal_with_one_prover "$theory" "$goal" "$prover" "stage3" "split_vc" "inline_all"
      rc=$?

      if [[ $rc -eq 0 ]]; then
        echo "Solved with split_vc + inline_all using prover: $prover" >&2
        solved=1
        break
      elif [[ $rc -eq 2 ]]; then
        echo "Infrastructure issue in stage 3 with prover $prover; aborting rest of stage 3." >&2
        stage3_broken=1
        break
      fi
    done

    [[ $solved -eq 0 ]] && FINAL_REMAINING+=("$entry")

    if [[ $stage3_broken -eq 1 ]]; then
      for (( j=j+1; j<${#AFTER_SPLIT_REMAINING[@]}; j++ )); do
        FINAL_REMAINING+=("${AFTER_SPLIT_REMAINING[$j]}")
      done
      break
    fi
  done

  echo "== Final summary ==" >&2
  echo "Unproved root goals after first prover : ${#REMAINING[@]}" >&2
  echo "Remaining failures after split_vc      : ${#AFTER_SPLIT_REMAINING[@]}" >&2
  echo "Remaining failures after stage 3       : ${#FINAL_REMAINING[@]}" >&2
  echo "Detailed logs stored in                : $LOG_DIR" >&2

  if [[ ${#FINAL_REMAINING[@]} -eq 0 ]]; then
    emit_result "SUCCESS" "proved_after_stage3" "stage3" "$ROOT_TOTAL" "$ROOT_TOTAL" "0"
    exit 0
  else
    echo "Still unproved goals:" >&2
    printf '%s\n' "${FINAL_REMAINING[@]}" >&2
    local proved_count="unknown"
    if [[ "$ROOT_TOTAL" =~ ^[0-9]+$ ]]; then
      proved_count=$((ROOT_TOTAL - ${#FINAL_REMAINING[@]}))
    fi
    emit_result "FAILURE" "unproved_goals_remain" "stage3" "$ROOT_TOTAL" "$proved_count" "${#FINAL_REMAINING[@]}"
    exit 1
  fi
}

main
