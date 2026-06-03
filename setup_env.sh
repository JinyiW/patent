#!/usr/bin/env bash
# 本地环境初始化脚本（macOS / 通用）
#
# 用途：在项目根目录创建 .venv 虚拟环境并安装全部依赖。
# 适配说明：本机默认 python3 为 /usr/bin/python3（Python 3.9，Xcode CLT），
# 且没有 `python` 命令，故统一使用 python3 + 项目本地 .venv，避免污染系统环境。
#
# 用法：
#   bash setup_env.sh        # 创建/更新 .venv 并安装 requirements.txt
#   source .venv/bin/activate  # 之后即可直接用 python tools/fill_template.py ...
set -euo pipefail

cd "$(dirname "$0")"

# 选择可用的 python3 解释器（优先 Homebrew 3.13，回退系统 3.9）
PY=""
for cand in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3 /usr/bin/python3 python3; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  echo "错误：未找到 python3 解释器" >&2; exit 1
fi
echo "使用解释器: $PY ($($PY --version 2>&1))"

# 创建虚拟环境
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
  echo "已创建 .venv"
fi

# 安装依赖
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
echo "依赖安装完成。"

# 自检
.venv/bin/python - <<'PYEOF'
import importlib.util
mods = ["lxml", "latex2mathml", "mathml2omml", "requests", "PIL", "matplotlib"]
miss = [m for m in mods if importlib.util.find_spec(m) is None]
if miss:
    raise SystemExit("缺少依赖: " + ", ".join(miss))
print("环境自检通过：所有依赖可用。")
PYEOF

echo ""
echo "完成。后续使用："
echo "  source .venv/bin/activate"
echo "  python tools/fill_template.py patent_04"
echo "或免激活直接调用："
echo "  .venv/bin/python tools/fill_template.py patent_04"
