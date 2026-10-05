#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 cad-file-reader 测量候选 / 装饰识图中间数据转成装饰算量输入表草稿。

CAD 导入行只作待核对输入：做法编号保持为空，需核对固定为“是”。
面积/长度换算、扣减、做法映射、损耗和材料台账仍由 zhuangshi-suanliang 处理。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
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


def blank() -> dict[str, str]:
    return {header: "" for header in HEADERS}


def cad_validate(input_path: Path) -> dict[str, Any] | None:
    """用 cad-file-reader 的 cad_validate.sh 校验交接 JSON；找不到底座时返回 None。"""
    base = os.environ.get("CAD_SKILL_DIR")
    if not base:
        for d in (Path.home() / ".codex/skills/cad-file-reader",
                  Path.home() / ".claude/skills/cad-file-reader"):
            if d.is_dir():
                base = str(d)
                break
    if not base:
        return None
    validator = Path(base) / "scripts" / "cad_validate.sh"
    if not validator.exists():
        return None
    try:
        r = subprocess.run(
            [str(validator), str(input_path)],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as exc:
        return {"ok": False, "errors": [f"{type(exc).__name__}: {exc}"], "skipped": True}
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    errors: list[str] = []
    for ln in lines:
        try:
            rec = json.loads(ln)
            errors.extend(rec.get("errors") or [])
        except Exception:
            continue
    return {"ok": r.returncode == 0 and not errors, "errors": errors[:20],
            "exit": r.returncode}


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
    output = blank()
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


def descriptive_rows(payload: dict[str, Any], floor: str, zone: str) -> list[dict[str, str]]:
    """把 cad-descriptive-geometry 中间数据转成待核对输入行。

    房间/墙段/吊顶/洞口/做法索引只作装饰算量前的地图与草表，不直接出量；
    做法编号尽量从做法/节点详情带出，但必须先人工核对。
    """
    rows: list[dict[str, str]] = []

    def sid(item: dict[str, Any]) -> str:
        return str(item.get("source_id") or item.get("id") or "CAD装饰候选")

    def review_reason(item: dict[str, Any]) -> str:
        return str(item.get("review_reason") or "")

    for item in payload.get("room_boundaries") or []:
        if not isinstance(item, dict):
            continue
        row = blank()
        row.update({
            "楼层": floor, "区域": zone, "房间": room_name(item),
            "部位类型": "待确认-房间",
            "做法名称": "CAD房间边界（待核对/绑定做法）", "做法类型": "通用",
            "间数": "1",
            "说明": f"闭合房间边界；bbox={item.get('bbox') or ''}；{review_reason(item)}".rstrip("；"),
            "依据": f"cad-file-reader:cad-descriptive-geometry:{sid(item)}",
            "需核对": "是",
        })
        rows.append(row)

    for item in payload.get("wall_segments") or []:
        if not isinstance(item, dict):
            continue
        seg = item.get("segment") or ()
        row = blank()
        seg_kind = item.get("segment_kind") or item.get("status") or "待确认"
        row.update({
            "楼层": floor, "区域": zone,
            "房间": "、".join(str(v) for v in item.get("rooms") or []) or room_name(item),
            "部位类型": "待确认-墙面" if seg_kind == "clear" else "待确认-墙面洞口",
            "做法名称": "CAD墙段（clear/opening）", "做法类型": "通用",
            "门窗洞口面积_m2": "", "扣减长度_m": fmt(item.get("opening_width_mm")),
            "直接长度_m": "",
            "高_m": fmt(item.get("height_m")),
            "说明": f"墙段={list(seg)}；{review_reason(item)}".rstrip("；"),
            "依据": f"cad-file-reader:cad-descriptive-geometry:{sid(item)}",
            "需核对": "是",
        })
        rows.append(row)

    for item in payload.get("ceiling_zones") or []:
        if not isinstance(item, dict):
            continue
        row = blank()
        zone_kind = item.get("zone_kind") or "吊顶"
        row.update({
            "楼层": floor, "区域": zone, "房间": room_name(item),
            "部位类型": "待确认-顶棚",
            "做法名称": f"CAD吊顶分区({zone_kind})", "做法类型": "通用",
            "间数": "1",
            "说明": f"吊顶标高={fmt(item.get('elevation_m'))}m；{review_reason(item)}".rstrip("；"),
            "依据": f"cad-file-reader:cad-descriptive-geometry:{sid(item)}",
            "需核对": "是",
        })
        rows.append(row)

    for item in payload.get("openings") or []:
        if not isinstance(item, dict):
            continue
        geo = item.get("geometry") or {}
        row = blank()
        row.update({
            "楼层": floor, "区域": zone,
            "房间": "、".join(str(v) for v in item.get("rooms") or geo.get("room_candidates") or []) or old_rooms(item),
            "部位类型": "待确认-门窗洞口",
            "做法名称": "CAD门窗洞口（需核对尺寸/扣减）", "做法类型": "通用",
            "门窗洞口面积_m2": "",
            "说明": f"洞口编号={item.get('code') or item.get('door_code') or ''}；{review_reason(item)}".rstrip("；"),
            "依据": f"cad-file-reader:cad-descriptive-geometry:{sid(item)}",
            "需核对": "是",
        })
        rows.append(row)

    for item in payload.get("node_detail_index") or []:
        if not isinstance(item, dict):
            continue
        row = blank()
        codes = "、".join(str(v) for v in (item.get("practice_codes") or []))
        nodes = "、".join(str(v) for v in (item.get("node_codes") or []))
        row.update({
            "楼层": floor, "区域": zone, "房间": room_name(item),
            "部位类型": "待确认-做法",
            "做法编号": codes, "做法名称": "CAD做法→节点索引", "做法类型": "通用",
            "节点编号": nodes, "节点详图": str(geo_file(item) or ""),
            "说明": f"做法编号={codes or '未识别'}；{review_reason(item)}".rstrip("；"),
            "依据": f"cad-file-reader:cad-descriptive-geometry:{sid(item)}",
            "需核对": "是",
        })
        rows.append(row)
    return rows


def old_rooms(item: dict[str, Any]) -> str:
    return str(item.get("source_id") or "CAD门窗候选")


def geo_file(item: dict[str, Any]) -> Any:
    return item.get("file") or item.get("file_name")


def convert(payload: dict[str, Any], floor: str, zone: str,
            descriptive: dict[str, Any] | None = None) -> tuple[list[dict[str, str]], int]:
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
    if descriptive:
        rows.extend(descriptive_rows(descriptive, floor, zone))
    return rows, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="cad-file-reader 识别/测量候选 → 装饰算量输入表草稿（全部需核对）")
    parser.add_argument("--measurements", required=True, help="cad-measurement-candidates.json")
    parser.add_argument("--out", required=True, help="输出 CSV")
    parser.add_argument("--floor", default="", help="统一填写楼层")
    parser.add_argument("--zone", default="CAD识图候选", help="区域名称")
    parser.add_argument("--descriptive", default=None,
                        help="可选：cad-descriptive-geometry 中间数据 JSON（房间/墙段/吊顶/洞口/做法索引）")
    parser.add_argument("--validate", "--no-validate", dest="validate", action=argparse.BooleanOptionalAction,
                        default=True, help="导入前用 cad-file-reader 校验交接 JSON（缺底座时静默跳过）")
    args = parser.parse_args()

    source = Path(args.measurements).expanduser().resolve()
    target = Path(args.out).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    descriptive = None
    if args.descriptive:
        descriptive = json.loads(Path(args.descriptive).expanduser().resolve().read_text(encoding="utf-8"))
    rows, skipped = convert(payload, args.floor, args.zone, descriptive)

    validation: dict[str, Any] | None = None
    if args.validate:
        validation = cad_validate(source)
        if validation is not None and not validation.get("ok"):
            for row in rows:
                row["需核对"] = "是"
                row["说明"] = ("CAD交接校验未通过：" + "；".join(validation.get("errors") or []) + "。 " + row["说明"])

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({
        "source": str(source),
        "descriptive": args.descriptive,
        "output": str(target),
        "rows": len(rows),
        "skipped": skipped,
        "review_required": True,
        "validation": validation,
        "note": "做法编号保持为空或仅作待核对候选；面积/长度、扣减、损耗和材料量仍由装饰算量技能处理",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
