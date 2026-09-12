"""Tests for the system diagnostics report (--doctor)."""
from __future__ import annotations

import unittest

from app.diagnostics import (
    COMPONENTS,
    build_report,
    check_components,
    probe_import,
    run_doctor,
)


def _importer(present: dict[str, bool], versions: dict[str, str] | None = None):
    versions = versions or {}

    def imp(name: str) -> dict:
        ok = present.get(name, False)
        return {"present": ok, "version": versions.get(name) if ok else None}

    return imp


class TestProbeImport(unittest.TestCase):
    def test_builtin_present(self):
        self.assertTrue(probe_import("sys")["present"])

    def test_missing_module_absent(self):
        r = probe_import("definitely_not_a_real_module_hslkghj")
        self.assertFalse(r["present"])
        self.assertIsNone(r["version"])


class TestCheckComponents(unittest.TestCase):
    def test_injected_importer_drives_result(self):
        imp = _importer(present={"PySide6": True, "cv2": False})
        res = check_components(importer=imp)
        self.assertTrue(res["PySide6"]["present"])
        self.assertFalse(res["cv2"]["present"])
        self.assertEqual(res["cv2"]["pip"], "opencv-python")
        self.assertEqual(res["cv2"]["role"], "Camera")
        self.assertTrue(res["cv2"]["critical"])
        self.assertTrue(res["numpy"]["critical"])
        self.assertFalse(res["vosk"]["critical"])

    def test_real_importer_present_is_consistent(self):
        res = check_components()
        self.assertEqual(set(res), set(COMPONENTS))
        for r in res.values():
            self.assertIn("present", r)
            self.assertIn("pip", r)
            self.assertIn("role", r)
            self.assertIn("critical", r)


class TestBuildReport(unittest.TestCase):
    def test_report_contains_status_rows(self):
        imp = _importer(present={"PySide6": True, "cv2": False},
                        versions={"PySide6": "6.7.0"})
        lines = build_report(importer=imp, python_note="Python 3.13.10")
        text = "\n".join(lines)
        self.assertIn("Python 3.13.10", text)
        self.assertIn("[OK     ] PySide6", text)
        self.assertIn("(6.7.0)", text)
        self.assertIn("[MISSING] cv2", text)
        self.assertIn("camera  :", text)
        self.assertIn("monitor :", text)

    def test_report_deterministic_order(self):
        imp = _importer(present={n: True for n in COMPONENTS})
        l1 = build_report(importer=imp, python_note="note")
        l2 = build_report(importer=imp, python_note="note")
        self.assertEqual(l1, l2)


class TestRunDoctor(unittest.TestCase):
    def test_exit_zero_when_all_present(self):
        imp = _importer(present={n: True for n in COMPONENTS})
        lines: list[str] = []
        code = run_doctor(importer=imp, printer=lines.append)
        self.assertEqual(code, 0)
        self.assertTrue(any("All required components present" in l for l in lines))

    def test_exit_nonzero_when_critical_missing(self):
        imp = _importer(present={"PySide6": True, "cv2": True,
                                 "mediapipe": True, "numpy": False,
                                 "onnxruntime": True, "vosk": True})
        lines: list[str] = []
        code = run_doctor(importer=imp, printer=lines.append)
        self.assertEqual(code, 1)
        self.assertTrue(any("Required components are missing" in l for l in lines))

    def test_optional_missing_does_not_fail(self):
        imp = _importer(present={"PySide6": True, "cv2": True,
                                 "mediapipe": True, "numpy": True,
                                 "onnxruntime": False, "vosk": False})
        lines: list[str] = []
        code = run_doctor(importer=imp, printer=lines.append)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()