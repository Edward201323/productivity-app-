#!/bin/zsh
set -eu
cd -- "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install 'uv>=0.12,<0.13'
export UV_PYTHON_INSTALL_DIR="$PWD/.runtime"
export UV_CACHE_DIR="$PWD/build/uv-cache"
.venv/bin/uv python install --no-bin 3.13
if [[ ! -x .app-venv/bin/python ]]; then
    .venv/bin/uv venv --python 3.13 --managed-python .app-venv
fi
.venv/bin/uv pip install --python .app-venv/bin/python -r requirements.txt
export PYINSTALLER_CONFIG_DIR="$PWD/build/pyinstaller-cache"
.app-venv/bin/pyinstaller --noconfirm Calendar.spec
print "Built $PWD/dist/lock in no gooning.app"
