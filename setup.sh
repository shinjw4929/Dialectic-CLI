#!/usr/bin/env bash
# Dialectic-CLI installer — venv + editable install + CLI 점검
set -euo pipefail

cd "$(dirname "$0")"

echo "─── Dialectic-CLI 설치 ───"

# 1. Python 버전 점검 (3.10+ 필수)
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  echo "✗ Python 3.10+ 필요 (현재 $PY_VER)"
  exit 1
fi
echo "✓ Python $PY_VER"

# 2. venv (없으면 생성)
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "✓ venv 생성"
else
  echo "✓ venv 존재"
fi

# 3. Editable install
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -e .
echo "✓ pip install -e . 완료"

# 4. 외부 CLI 점검 (안내만, 실패해도 진행 — mock 모드로 동작 가능)
echo ""
echo "─── 외부 CLI 점검 (선택) ───"
if command -v codex >/dev/null 2>&1; then
  echo "codex CLI:  $(codex --version 2>&1 | head -1)"
else
  echo "codex CLI:  미설치 (실 호출 모드 제한, mock 모드 가능)"
fi
if command -v claude >/dev/null 2>&1; then
  echo "claude CLI: $(claude --version 2>&1 | head -1)"
else
  echo "claude CLI: 미설치 (실 호출 모드 제한, mock 모드 가능)"
fi

echo ""
echo "✓ 설치 완료. 다음을 시도해보세요:"
echo ""
echo "    source .venv/bin/activate"
echo "    dialectic run --task @tasks/wave_difficulty/task.md --mock tasks/wave_difficulty"
echo "    dialectic-skill sync-docs"
echo "    ./dialectic-skill sync-docs    # editable install 전에도 사용 가능"
echo ""
echo "  (실 호출은 \`claude login\` + \`codex login\` 1회 후 --mock 생략)"
echo ""
