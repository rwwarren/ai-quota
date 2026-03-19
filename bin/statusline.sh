#!/usr/bin/env bash
# statusline-command.sh — Claude Code status line
# Outputs: hostname | repo:branch | ctx: 42% | [████░░░░] 42% | week: 22% | Extra usage: 32%

input=$(cat)

# Colors
RST='\033[0m'
DIM='\033[2m'
BLUE='\033[94m'
CYAN='\033[36m'
MAGENTA='\033[35m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'

# Color a percentage based on value: green < 50, yellow < 80, red >= 80
color_pct() {
  local pct=$1
  if (( pct >= 80 )); then   printf "${RED}%d%%${RST}" "$pct"
  elif (( pct >= 50 )); then printf "${YELLOW}%d%%${RST}" "$pct"
  else                       printf "${GREEN}%d%%${RST}" "$pct"
  fi
}

# Computer name
host=$(hostname -s)

# Git repo + branch from cwd in JSON input
cwd=$(echo "$input" | jq -r '.workspace.current_dir // empty')
repo_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)
if [[ -n "$repo_root" ]]; then
  repo_name=$(basename "$repo_root")
  branch=$(git -C "$repo_root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  [[ -n "$branch" ]] && repo_part="${CYAN}${repo_name}${DIM}:${RST}${MAGENTA}${branch}${RST}" || repo_part="${CYAN}${repo_name}${RST}"
else
  repo_part="${DIM}no repo${RST}"
fi

# Context window usage from JSON input (live, per-session)
ctx_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty' 2>/dev/null)
ctx_pct=${ctx_pct%.*}  # truncate to integer if float

# Usage data from JSON cache (refreshed by launchd every 15 min)
USAGE_CACHE="/tmp/cc-usage-pct.cache"
session_pct=""
week_pct=""
extra_pct=""
if [[ -f "$USAGE_CACHE" ]]; then
  if command -v jq &>/dev/null; then
    session_pct=$(jq -r '.entries[] | select(.label | test("[Ss]ession")) | .percent // empty' "$USAGE_CACHE" 2>/dev/null | head -1)
    session_reset_ts=$(jq -r '.entries[] | select(.label | test("[Ss]ession")) | .reset_ts // empty' "$USAGE_CACHE" 2>/dev/null | head -1)
    week_pct=$(jq -r '.entries[] | select(.label | test("week|Weekly"; "i")) | .percent // empty' "$USAGE_CACHE" 2>/dev/null | head -1)
    week_reset_ts=$(jq -r '.entries[] | select(.label | test("week|Weekly"; "i")) | .reset_ts // empty' "$USAGE_CACHE" 2>/dev/null | head -1)
    extra_pct=$(jq -r '.entries[] | select(.label | test("[Ee]xtra")) | .percent // empty' "$USAGE_CACHE" 2>/dev/null | head -1)
    extra_reset_ts=$(jq -r '.entries[] | select(.label | test("[Ee]xtra")) | .reset_ts // empty' "$USAGE_CACHE" 2>/dev/null | head -1)
  else
    week_pct=$(grep -oE 'week: [0-9]+%' "$USAGE_CACHE" 2>/dev/null | grep -oE '[0-9]+')
    extra_pct=$(grep -oE 'Extra usage: [0-9]+%' "$USAGE_CACHE" 2>/dev/null | grep -oE '[0-9]+')
  fi
  # Format an ISO timestamp into a compact reset string.
  # <24h: "1h 43m (11:00 PM)"  ≥24h: "5d 0h (Mar 19 10:00 PM)"
  _fmt_reset() {
    local ts="$1"
    [[ -z "$ts" || "$ts" == "null" ]] && return
    # macOS date: parse ISO timestamp to epoch
    local target_epoch now_epoch delta_s
    target_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$ts" +%s 2>/dev/null) || return
    now_epoch=$(date +%s)
    delta_s=$(( target_epoch - now_epoch ))
    (( delta_s < 0 )) && delta_s=0
    local total_min=$(( delta_s / 60 ))
    local hours=$(( total_min / 60 ))
    local mins=$(( total_min % 60 ))
    # 12-hour time
    local time_12
    time_12=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$ts" "+%l:%M %p" 2>/dev/null | sed 's/^ //') || return
    if (( hours >= 24 )); then
      local days=$(( hours / 24 ))
      hours=$(( hours % 24 ))
      local date_part
      date_part=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$ts" "+%b %-d" 2>/dev/null) || return
      echo "${days}d ${hours}h (${date_part} ${time_12})"
    elif (( hours > 0 )); then
      echo "${hours}h ${mins}m (${time_12})"
    else
      echo "${mins}m (${time_12})"
    fi
  }
  session_reset_short=$(_fmt_reset "${session_reset_ts:-}")
  week_reset_short=$(_fmt_reset "${week_reset_ts:-}")
  extra_reset_short=$(_fmt_reset "${extra_reset_ts:-}")
fi

# Session usage bar
ctx_bar=""
if [[ -n "$session_pct" ]]; then
  filled=$(( session_pct * 10 / 100 ))
  empty=$(( 10 - filled ))
  bar=""
  if (( session_pct >= 80 )); then   bar_color="$RED"
  elif (( session_pct >= 50 )); then bar_color="$YELLOW"
  else                               bar_color="$GREEN"
  fi
  for ((i=0; i<filled; i++)); do bar+="█"; done
  bar_empty=""
  for ((i=0; i<empty; i++)); do bar_empty+="░"; done
  ctx_bar="${DIM}[${RST}${bar_color}${bar}${DIM}${bar_empty}${RST}${DIM}]${RST} $(color_pct "$session_pct")"
  [[ -n "$session_reset_short" ]] && ctx_bar+=" ${DIM}${session_reset_short}${RST}"
fi

# Context window usage bar
ctx_window_part=""
if [[ -n "$ctx_pct" && "$ctx_pct" =~ ^[0-9]+$ ]]; then
  filled=$(( ctx_pct * 10 / 100 ))
  empty=$(( 10 - filled ))
  if (( ctx_pct >= 80 )); then   bar_color="$RED"
  elif (( ctx_pct >= 50 )); then bar_color="$YELLOW"
  else                           bar_color="$GREEN"
  fi
  bar=""; for ((i=0; i<filled; i++)); do bar+="█"; done
  bar_empty=""; for ((i=0; i<empty; i++)); do bar_empty+="░"; done
  ctx_window_part="${DIM}[${RST}${bar_color}${bar}${DIM}${bar_empty}${RST}${DIM}]${RST} $(color_pct "$ctx_pct") context"
fi

# Assemble
SEP="${DIM} | ${RST}"
output="${BLUE}${host}${RST}${SEP}${repo_part}"
[[ -n "$ctx_window_part" ]] && output+="${SEP}${ctx_window_part}"
[[ -n "$ctx_bar" ]] && output+="${SEP}${ctx_bar}"
week_part=""
[[ -n "$week_pct" ]] && week_part="${DIM}week:${RST} $(color_pct "$week_pct")"
[[ -n "$week_pct" && -n "$week_reset_short" ]] && week_part+=" ${DIM}${week_reset_short}${RST}"
[[ -n "$week_part" ]] && output+="${SEP}${week_part}"
extra_part=""
[[ -n "$extra_pct" ]] && extra_part="${DIM}extra:${RST} $(color_pct "$extra_pct")"
[[ -n "$extra_pct" && -n "$extra_reset_short" ]] && extra_part+=" ${DIM}${extra_reset_short}${RST}"
[[ -n "$extra_part" ]] && output+="${SEP}${extra_part}"

printf '%b\n' "$output"
