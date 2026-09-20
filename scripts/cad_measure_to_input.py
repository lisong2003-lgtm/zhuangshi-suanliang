#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 cad-file-reader 测量候选转成装饰算量输入表草稿。

CAD 导入行只作待核对输入：做法编号保持为空，需核对固定为“是”。
面积/长度换算、扣减、做法映射、损耗和材料台账仍由 zhuangshi-suanliang 处理。
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

HEADERS = [
    "楼层", "区域", "房间", "部位类型", "做法编号", "做法名称", "做法类型",
    "节点编号", "节点详图", "长_m", "宽_m", "高_m", "周长_m",
    "门窗洞口面积_m2", "洞口侧壁增加_m2", "扣减长度_m", "直接面积_m2",
    "直接长度_m", "防水上翻高度_m", "附加层面积_m2", "附加层长度_m",
    "附加层宽度_m", "搭接宽度_mm", "卷材幅宽_mm", "涂膜厚度_mm",
    "防水道数", "间数", "说明", "依据", "需核对",
]


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def room_name(row: dict[str, Any]) -> str:
    rooms = row.get("rooms")
    if isinstance(rooms, list) and rooms:
        return "、".join(str(value) for value in rooms if value)
    return str(row.get("source_id") or "CAD识图候选")


def measurement_row(row: dict[str, Any], floor: str, zone: str) -> dict[str, str] | None:
    kind = str(row.get("kind") or "")
    if kind not in {"length", "area"}:
        return None
    value = row.get("value")
    if value is None:
        detail = (
            f"未换算：图面值 {fmt(row.get('value_drawing_units'))} {row.get('drawing_unit') or ''}；"
            f"{row.get('review_reason') or '缺比例或单位'}"
        )
    else:
        detail = f"{row.get('formula') or ''}；{row.get('review_reason') or ''}".strip("；")
    output = {header: "" for header in HEADERS}
    output.update({
        "楼层": floor,
        "区域": zone,
        "房间": room_name(row),
        "部位类型": "待确认-面积" if kind == "area" else "待确认-长度",
        "做法名称": "CAD识图测量候选（需绑定做法）",
        "做法类型": "通用",
        "间数": "1",
        "说明": f"{detail}；final_quantity=false",
        "依据": f"cad-file-reader:{row.get('source_schema') or ''}:{row.get('source_id') or ''}",
        "需核对": "是",
    })
    if kind == "area" and value is not None:
        output["直接面积_m2"] = fmt(value)
    elif kind == "length" and value is not None:
        output["直接长度_m"] = fmt(value)
    return output


def convert(payload: dict[str, Any], floor: str, zone: str) -> tuple[list[dict[str, str]], int]:
    measurements = payload.get("measurements")
    if not isinstance(measurements, list):
        raise ValueError("输入 JSON 缺少 measurements 数组")
    rows: list[dict[str, str]] = []
    skipped = 0
    for item in measurements:
        if not isinstance(item, dict):
            skipped += 1
            continue
        row = measurement_row(item, floor, zone)
        if row is None:
            skipped += 1
            continue
        rows.append(row)
    return rows, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="cad-file-reader 测量候选 → 装饰算量输入表草稿（全部需核对）")
    parser.add_argument("--measurements", required=True, help="cad-measurement-candidates.json")
    parser.add_argument("--out", required=True, help="输出 CSV")
    parser.add_argument("--floor", default="", help="统一填写楼层")
    parser.add_argument("--zone", default="CAD识图候选", help="区域名称")
    args = parser.parse_args()

    source = Path(args.measurements).expanduser().resolve()
    target = Path(args.out).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    rows, skipped = convert(payload, args.floor, args.zone)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({
        "source": str(source),
        "output": str(target),
        "rows": len(rows),
        "skipped": skipped,
        "review_required": True,
        "note": "做法编号保持为空；面积/长度、扣减、损耗和材料量仍由装饰算量技能处理",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
