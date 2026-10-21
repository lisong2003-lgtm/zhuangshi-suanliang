#!/usr/bin/env bash
# cad_measure_to_input 跨平台 CLI 入口（macOS / Linux；Windows 用 scripts/cad_measure_to_input.cmd 或 python scripts/cad_measure_to_input.py）。
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cad_measure_to_input.py" "$@"
