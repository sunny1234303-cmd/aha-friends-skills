---
name: claude-usage-statusline
description: Claude Code 터미널 하단 상태줄에 컨텍스트 사용량, 5시간/주간 사용 한도, Claude 서비스 상태를 색상 게이지 바로 표시. "상태줄", "게이지 바", "토큰 사용량 확인", "컨텍스트 얼마나 남았어", "statusline" 등을 언급하면 자동 실행. Pro/Max 등 구독 플랜 무관하게 동작.
allowed-tools: Bash, Read, Write
---

# Claude Usage Statusline Skill

Claude Code의 `statusLine` 기능을 이용해, 터미널 하단에 **컨텍스트 창 사용량**과 **요금제 사용 한도(5시간/주간)**를 항상 볼 수 있게 만드는 Skill입니다.

## 🎯 표시되는 내용

설치하면 상태줄에 최대 4줄이 표시됩니다 (해당 데이터가 없으면 그 줄은 자동 생략):

```
[Sonnet 5] 📁 imi-workspace | ● Claude 정상
Context [███████░░░░░] 63%·37%남음 (↓45K ↑8K)
5h    [██░░░░░░░░] 24% (~08/03 04:46 리셋)
주간   [████░░░░░░] 41% (~08/10 03:26 리셋)
```

| 줄 | 내용 | 비고 |
|---|---|---|
| 1 | 모델명 · 현재 폴더 · Claude 서비스 상태 | status.claude.com API, 2분 캐시로 논블로킹 조회 |
| 2 | **컨텍스트 게이지** — 이번 대화창이 얼마나 찼는지 | `context_window.used_percentage` 기반, 70%↑ 노랑 경고, 90%↑ 빨강 경고 |
| 3 | **5시간 한도 게이지** — 롤링 5시간 사용률 | `rate_limits.five_hour`, 리셋 시각 함께 표시 |
| 4 | **주간 한도 게이지** — 7일 사용률 | `rate_limits.seven_day`, 리셋 시각 함께 표시 |

3~4번째 줄(rate_limits)은 **Claude.ai Pro/Max 구독자만** 첫 API 응답 이후에 채워집니다. Console/API 키 사용자는 해당 데이터가 없어 자동으로 생략됩니다.

## ⚙️ 동작 원리 (왜 Pro/Max 상관없이 동작하는가)

Claude Code가 상태줄 스크립트에 `rate_limits.five_hour.used_percentage`, `rate_limits.seven_day.used_percentage`를 **이미 사용자 플랜의 한도 대비 %로 계산해서** 내려줍니다. 이 스크립트는 그 %값을 게이지로 그리기만 할 뿐 절대 토큰 수나 플랜 이름을 하드코딩하지 않습니다 — 그래서 Pro든 Max든 코드 수정 없이 동일하게 동작합니다.

## 📦 설치 방법

**1단계: 스크립트 설치**
```bash
mkdir -p ~/.claude
cp "$(pwd)/.claude/skills/claude-usage-statusline/scripts/statusline-command.sh" ~/.claude/statusline-command.sh
chmod +x ~/.claude/statusline-command.sh
```

**2단계: 설정 등록** (`~/.claude/settings.json`에 `statusLine` 필드 병합 — 기존 설정 보존)
```bash
jq '.statusLine = {"type": "command", "command": "~/.claude/statusline-command.sh"}' \
  ~/.claude/settings.json > /tmp/claude-settings-merged.json \
  && mv /tmp/claude-settings-merged.json ~/.claude/settings.json
```

`~/.claude/settings.json`이 아직 없다면:
```bash
echo '{"statusLine": {"type": "command", "command": "~/.claude/statusline-command.sh"}}' > ~/.claude/settings.json
```

**3단계: 확인**
- 새 Claude Code 세션(또는 새 탭)을 열면 하단에 상태줄이 나타납니다.
- 상태줄은 새 assistant 메시지가 도착할 때마다 자동 갱신됩니다 (수동 새로고침 불필요).

## 🧪 테스트 (모의 입력으로 동작 확인)

실제 세션 없이도 스크립트 자체를 검증할 수 있습니다:
```bash
echo '{"model":{"display_name":"Sonnet 5"},"workspace":{"current_dir":"/Users/you/project"},"context_window":{"total_input_tokens":45000,"total_output_tokens":8000,"used_percentage":63,"remaining_percentage":37},"rate_limits":{"five_hour":{"used_percentage":23.5,"resets_at":1785700000},"seven_day":{"used_percentage":41.2,"resets_at":1786300000}},"session_id":"test"}' | ~/.claude/statusline-command.sh
```

실제 세션에서 `rate_limits`가 제대로 들어오는지 확인하려면:
```bash
cat ~/.claude/status/_last_raw.json | jq '.rate_limits'
```
이 파일은 Claude Code가 스크립트에 보낸 가장 최근 원본 JSON을 그대로 담고 있어, "왜 5h/주간 줄이 안 보이지?" 같은 문제를 바로 진단할 수 있습니다.

## 🎨 커스터마이징

`~/.claude/statusline-command.sh`를 직접 수정하세요:

- **임계치 색상 (70%/90%)**: `make_gauge()` 함수 안의 `-ge 90`, `-ge 70` 숫자 변경
- **게이지 폭**: `make_gauge "$used_pct_int" 12` 등 호출부의 마지막 숫자(칸 수) 변경
- **서비스 상태 캐시 주기**: `STATUS_CACHE_MAX_AGE=120` (초 단위)
- **줄 순서**: 창이 좁으면 뒤쪽부터 잘리므로, 가장 중요한 정보(컨텍스트 게이지)를 상단 줄에 유지할 것

## 🔧 트러블슈팅

**상태줄이 아예 안 보임**
- `chmod +x ~/.claude/statusline-command.sh` 확인
- 현재 폴더의 workspace trust를 아직 수락하지 않았으면 상태줄이 비어 있음 — Claude Code 재시작 후 trust 다이얼로그 수락
- `claude --debug`로 첫 상태줄 실행의 종료 코드/stderr 확인

**5h/주간 줄이 안 보임**
- Console/API 키 사용자는 `rate_limits`가 애초에 내려오지 않음 (정상 동작)
- Pro/Max 사용자인데 안 보이면 세션의 첫 API 응답 전이라 그럴 수 있음 — 메시지 한 번 주고받은 후 확인
- `cat ~/.claude/status/_last_raw.json | jq '.rate_limits'`로 실제 원본 값 확인

**창을 좁히면 뒷부분이 잘림**
- 각 줄이 터미널 폭보다 길면 잘림 — 게이지 폭을 줄이거나(커스터마이징 참고) 폰트 크기를 조정

## 📚 참고 자료

- 공식 문서: https://code.claude.com/docs/en/statusline
- Claude 서비스 상태 API: https://status.claude.com/api/v2/status.json
