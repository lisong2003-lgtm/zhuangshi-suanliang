#!/usr/bin/env bash
# decor_qty 跨平台 CLI 入口（macOS / Linux；Windows 用 scripts/decor_qty.cmd 或 python scripts/decor_qty.py）。
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/decor_qty.py" "$@"
