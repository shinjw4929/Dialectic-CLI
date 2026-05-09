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

# 4. PATH 등록 — ~/.local/bin이 PATH에 있으면 symlink 자동 생성 (어디서나 `dialectic` 호출).
#    venv activate 없이도 동작 (shim이 python3 -m src.cli 호출, 외부 의존성 0이라 system python OK).
#    안전: 기존 동명 파일/symlink가 있으면 본 repo 외부 자산 침해 차단 — 다른 target이거나
#    실파일이면 경고만 출력하고 skip (사용자 자산 우선).
LOCAL_BIN="$HOME/.local/bin"
REPO_DIR="$(pwd)"
link_if_safe() {
  local name="$1"
  local target="$REPO_DIR/$name"
  local link="$LOCAL_BIN/$name"
  if [ -L "$link" ]; then
    local existing
    existing="$(readlink "$link")"
    if [ "$existing" = "$target" ]; then
      return 0  # 이미 본 repo 가리킴 — no-op
    fi
    echo "⚠ $link → $existing 존재 (다른 target). skip — 수동 확인 권장"
    return 0
  fi
  if [ -e "$link" ]; then
    echo "⚠ $link 동명 실파일 존재. skip — 수동 확인 권장"
    return 0
  fi
  ln -s "$target" "$link"
  echo "✓ symlink: $link → $target"
}

mkdir -p "$LOCAL_BIN"
link_if_safe dialectic
link_if_safe dialectic-skill

if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
  echo "ℹ ~/.local/bin이 PATH에 없음 — 다음을 ~/.bashrc 또는 ~/.zshrc에 추가하면 어디서나 호출 가능 (symlink는 이미 생성됨):"
  echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# 5. 외부 CLI 점검 (안내만, 실패해도 진행 — 사용 시점에 인증 필요)
echo ""
echo "─── 외부 CLI 점검 (필수) ───"
if command -v codex >/dev/null 2>&1; then
  echo "codex CLI:  $(codex --version 2>&1 | head -1)"
else
  echo "codex CLI:  미설치 — 사용 전 설치 + 인증 필요 (\`codex login\` 또는 OPENAI_API_KEY)"
fi
if command -v claude >/dev/null 2>&1; then
  echo "claude CLI: $(claude --version 2>&1 | head -1)"
else
  echo "claude CLI: 미설치 — 사용 전 설치 + 인증 필요 (\`claude /login\` 또는 ANTHROPIC_API_KEY)"
fi

echo ""
echo "✓ 설치 완료. 다음을 시도해보세요:"
echo ""
echo "    dialectic doctor                                    # claude/codex --version + auth 점검 (비용 0)"
echo "    dialectic                                           # default 메뉴 진입 (어디서나, activate 불필요)"
echo "    dialectic run --task \"JSON 파싱 함수 작성\" --max-turns 3"
echo "    dialectic-skill sync-docs"
echo ""
echo "  데모 시나리오: tasks/implement-dijkstra/task.md (1차 task 본문 paste 후 critical 모드)"
echo "  (symlink 생성 실패 fallback: cd 후 \`./dialectic\` 또는 \`source .venv/bin/activate\`)"
echo ""
