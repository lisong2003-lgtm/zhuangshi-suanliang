#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "cad_measure_to_input.py"


class CadMeasureToInputTest(unittest.TestCase):
    def test_converts_area_and_length_but_marks_review(self):
        payload = {
            "schema": "cad-measurement-candidates/v1",
            "measurements": [
                {"kind": "area", "value": 12.5, "unit": "m2", "formula": "50000000 mm² = 50 m2", "basis": "polygon", "method": "shoelace", "status": "candidate", "review_reason": "", "source_schema": "cad-descriptive-geometry/v7", "source_id": "room-1", "rooms": ["办公室"]},
                {"kind": "length", "value": None, "unit": "m", "value_drawing_units": 3000, "drawing_unit": "mm", "review_reason": "缺比例或单位", "basis": "wall_segment", "method": "segment_sum", "status": "review", "source_schema": "cad-descriptive-geometry/v7", "source_id": "wall-1"},
                {"kind": "volume", "value": 3.0, "unit": "m3", "basis": "area_x_thickness", "method": "area_times_explicit_parameter", "status": "review", "source_schema": "cad-descriptive-geometry/v7", "source_id": "v-1"},
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src = root / "measure.json"
            out = root / "decor.csv"
            src.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(SCRIPT), "--measurements", str(src), "--out", str(out), "--floor", "二层"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with out.open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(row["需核对"] == "是" for row in rows))
            self.assertTrue(all(row["做法编号"] == "" for row in rows))
            self.assertEqual(rows[0]["直接面积_m2"], "12.5")
            self.assertEqual(rows[1]["直接长度_m"], "")
            self.assertIn("图面值 3000 mm", rows[1]["说明"])


if __name__ == "__main__":
    unittest.main()
