#!/bin/bash
# Claude Code 상태줄: 컨텍스트 게이지 + 5시간/주간 한도 게이지 + 서비스 상태
# Pro/Max 등 구독 플랜에 관계없이 동작 (rate_limits는 Claude Code가 이미
# 각자의 플랜 한도 대비 %로 계산해서 내려주므로, 이 스크립트는 플랜을
# 하드코딩하지 않고 percentage 값만 그대로 게이지로 그린다).

input=$(cat)

# 디버그용: Claude Code가 실제로 보내는 원본 JSON을 항상 최신 1건만 보존
# (rate_limits 등 필드가 실제로 채워지는지 확인할 때 사용: cat ~/.claude/status/_last_raw.json)
mkdir -p "$HOME/.claude/status" 2>/dev/null
echo "$input" > "$HOME/.claude/status/_last_raw.json" 2>/dev/null

cwd=$(echo "$input" | jq -r '.workspace.current_dir')
model=$(echo "$input" | jq -r '.model.display_name')
total_in=$(echo "$input" | jq -r '.context_window.total_input_tokens')
total_out=$(echo "$input" | jq -r '.context_window.total_output_tokens')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
remain_pct=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')
five_h_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
five_h_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
seven_d_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
seven_d_reset=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // empty')

# 상태 대시보드(00-system/status-dashboard)용 상태 저장 + 검증용 rate_limits 원본 보존
session_id=$(echo "$input" | jq -r '.session_id // .session.id // .sessionId // empty')
if [ -n "$session_id" ]; then
    status_dir="$HOME/.claude/status"
    mkdir -p "$status_dir"
    jq -n \
        --arg cwd "$cwd" \
        --arg model "$model" \
        --argjson total_in "${total_in:-0}" \
        --argjson total_out "${total_out:-0}" \
        --arg used_pct "${used_pct:-0}" \
        --arg five_h_pct "${five_h_pct:-null}" \
        --arg seven_d_pct "${seven_d_pct:-null}" \
        --argjson updated_at "$(date +%s)" \
        '{cwd: $cwd, model: $model, total_in: $total_in, total_out: $total_out,
          used_pct: ($used_pct | tonumber),
          five_h_pct: (if $five_h_pct == "null" then null else ($five_h_pct | tonumber) end),
          seven_d_pct: (if $seven_d_pct == "null" then null else ($seven_d_pct | tonumber) end),
          updated_at: $updated_at}' \
        > "$status_dir/$session_id.json" 2>/dev/null
fi

# ANSI colors
C_GREEN=$'\033[32m'
C_YELLOW=$'\033[33m'
C_RED=$'\033[1;31m'
C_CYAN=$'\033[36m'
C_DIM=$'\033[2m'
C_RESET=$'\033[0m'

format_tokens() {
    local tokens=$1
    if [ "$tokens" -ge 1000 ]; then
        echo "$((tokens / 1000))K"
    else
        echo "$tokens"
    fi
}

# args: pct width -> colored gauge bar (초록<70 / 노랑70-89 / 빨강90+)
# 절대 수치가 아닌 %만 받으므로 Pro든 Max든 각자의 플랜 한도 대비 값을 그대로 표시한다.
make_gauge() {
    local pct=$1
    local width=$2
    [ "$pct" -gt 100 ] && pct=100
    [ "$pct" -lt 0 ] && pct=0
    local filled=$((pct * width / 100))
    local empty=$((width - filled))

    local color=$C_GREEN
    if [ "$pct" -ge 90 ]; then
        color=$C_RED
    elif [ "$pct" -ge 70 ]; then
        color=$C_YELLOW
    fi

    local bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done

    echo "${color}${bar}${C_RESET}"
}

fmt_reset() {
    local epoch=$1
    [ -z "$epoch" ] && return
    date -r "$epoch" "+%m/%d %H:%M" 2>/dev/null
}

cwd_short=$(basename "$cwd")
total_in_fmt=$(format_tokens "${total_in:-0}")
total_out_fmt=$(format_tokens "${total_out:-0}")

# ── Anthropic 서비스 상태 (2분 캐시, 논블로킹 백그라운드 갱신) ──
STATUS_CACHE="/tmp/claude-service-status.cache"
STATUS_CACHE_MAX_AGE=120
cache_age=999999
if [ -f "$STATUS_CACHE" ]; then
    cache_age=$(( $(date +%s) - $(stat -f %m "$STATUS_CACHE" 2>/dev/null || stat -c %Y "$STATUS_CACHE" 2>/dev/null || echo 0) ))
fi
if [ "$cache_age" -gt "$STATUS_CACHE_MAX_AGE" ]; then
    ( curl -sL -m 4 https://status.claude.com/api/v2/status.json > "${STATUS_CACHE}.tmp" 2>/dev/null \
      && mv "${STATUS_CACHE}.tmp" "$STATUS_CACHE" ) & disown
fi
svc_indicator=""
[ -f "$STATUS_CACHE" ] && svc_indicator=$(jq -r '.status.indicator // empty' "$STATUS_CACHE" 2>/dev/null)
svc_line=""
case "$svc_indicator" in
    none)     svc_line="${C_GREEN}● Claude 정상${C_RESET}" ;;
    minor)    svc_line="${C_YELLOW}● Claude 부분 장애${C_RESET}" ;;
    major|critical) svc_line="${C_RED}● Claude 장애 발생${C_RESET}" ;;
esac

# ── 1줄: 모델 · 경로 · 서비스 상태 ──
line1="${C_CYAN}[$model]${C_RESET} 📁 ${cwd_short}"
[ -n "$svc_line" ] && line1="$line1 | $svc_line"

# ── 2줄: 컨텍스트 게이지 (이번 대화창이 얼마나 찼는지) ──
line2=""
if [ -n "$used_pct" ]; then
    used_pct_int=$(printf "%.0f" "$used_pct")
    if [ -n "$remain_pct" ]; then
        remain_pct_int=$(printf "%.0f" "$remain_pct")
    else
        remain_pct_int=$((100 - used_pct_int))
    fi
    gauge=$(make_gauge "$used_pct_int" 12)

    warn=""
    if [ "$used_pct_int" -ge 90 ]; then
        warn=" ${C_RED}⚠ 컨텍스트 한도 임박${C_RESET}"
    elif [ "$used_pct_int" -ge 70 ]; then
        warn=" ${C_YELLOW}⚠ 컨텍스트 주의${C_RESET}"
    fi

    line2="Context [${gauge}] ${used_pct_int}%·${remain_pct_int}%남음 ${C_DIM}(↓${total_in_fmt} ↑${total_out_fmt})${C_RESET}${warn}"
fi

# ── 3/4줄: 요금제 사용 한도 (5시간 롤링 / 주간) — Pro·Max 공통, %만 사용 ──
line3=""
if [ -n "$five_h_pct" ]; then
    fh_int=$(printf "%.0f" "$five_h_pct")
    fh_gauge=$(make_gauge "$fh_int" 10)
    fh_reset_fmt=$(fmt_reset "$five_h_reset")
    line3="5h    [${fh_gauge}] ${fh_int}%$( [ -n "$fh_reset_fmt" ] && echo " ${C_DIM}(~${fh_reset_fmt} 리셋)${C_RESET}")"
fi

line4=""
if [ -n "$seven_d_pct" ]; then
    sd_int=$(printf "%.0f" "$seven_d_pct")
    sd_gauge=$(make_gauge "$sd_int" 10)
    sd_reset_fmt=$(fmt_reset "$seven_d_reset")
    line4="주간   [${sd_gauge}] ${sd_int}%$( [ -n "$sd_reset_fmt" ] && echo " ${C_DIM}(~${sd_reset_fmt} 리셋)${C_RESET}")"
fi

echo "$line1"
[ -n "$line2" ] && echo "$line2"
[ -n "$line3" ] && echo "$line3"
[ -n "$line4" ] && echo "$line4"
