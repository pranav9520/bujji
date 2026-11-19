#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock -e '.[test]'
.venv/bin/python scripts/init_config.py
npm --prefix frontend ci
npm --prefix frontend run build
printf '%s\n' 'Setup complete. Configure .env locally, then start the localhost backend. Windows controls require Windows.'
