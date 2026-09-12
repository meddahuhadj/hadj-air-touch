"""System diagnostics report (``python main.py --doctor``).

Reports which optional/R runtime components are installed, enumerates
cameras and monitors best-effort, and exits non-zero when a required
component is missing so scripts can react.
"""
from __future__ import annotations

import platform
from typing import Callable

# name -> (pip package, role, critical)
COMPONENTS: dict[str, tuple[str, str, bool]] = {
    "PySide6": ("PySide6", "GUI", True),
    "cv2": ("opencv-python", "Camera", True),
    "mediapipe": ("mediapipe", "Hand tracking", True),
    "numpy": ("numpy", "Math", True),
    "onnxruntime": ("onnxruntime", "Optional AI", False),
    "vosk": ("vosk", "Voice (optional)", False),
}

Printer = Callable[[str], None]
Importer = Callable[[str], dict]


def probe_import(name: str) -> dict:
    """Import ``name`` and report presence + module version."""
    try:
        mod = __import__(name)
    except Exception:
        return {"present": False, "version": None}
    return {"present": True, "version": getattr(mod, "__version__", None)}


def check_components(importer: Importer | None = None,
                     names: list[str] | None = None) -> dict[str, dict]:
    importer = importer or probe_import
    names = names or list(COMPONENTS)
    out: dict[str, dict] = {}
    for name in names:
        r = importer(name)
        pip_name, role, critical = COMPONENTS[name]
        out[name] = {
            "present": r["present"],
            "version": r["version"],
            "pip": pip_name,
            "role": role,
            "critical": critical,
        }
    return out


def _camera_diag() -> dict:
    try:
        from app.camera.manager import CameraManager  # noqa: PLC0415
        cams = CameraManager().cameras
        detail = ", ".join(f"{c.index}: {c.name}" for c in cams)
        return {"ok": True, "count": len(cams), "detail": detail or "none"}
    except Exception as exc:
        return {"ok": False, "count": 0, "detail": str(exc)}


def _monitor_diag() -> dict:
    try:
        from app.windows_input.screen import ScreenManager  # noqa: PLC0415
        mons = ScreenManager().monitors
        detail = ", ".join(
            f"{m.name} {m.width}x{m.height}{' (primary)' if m.primary else ''}"
            for m in mons
        )
        return {"ok": True, "count": len(mons), "detail": detail or "none"}
    except Exception as exc:
        return {"ok": False, "count": 0, "detail": str(exc)}


def build_report(importer: Importer | None = None,
                 python_note: str | None = None) -> list[str]:
    lines = ["HADJ AIR TOUCH - system diagnostics", ""]
    if python_note is None:
        python_note = (
            f"Python {platform.python_version()} "
            f"({platform.system().lower()}, {platform.machine()})"
        )
    lines.append(python_note)
    for name, r in check_components(importer=importer).items():
        status = "OK" if r["present"] else "MISSING"
        ver = f" ({r['version']})" if r["version"] else ""
        need = "required" if r["critical"] else "optional"
        lines.append(
            f"[{status:<7}] {name:<12} {r['role']:<15} "
            f"({need}) pip install {r['pip']}{ver}"
        )
    lines.append("")
    cam = _camera_diag()
    lines.append(f"[{'OK' if cam['ok'] else 'ERR':<7}] camera  : {cam['detail']}")
    mon = _monitor_diag()
    lines.append(f"[{'OK' if mon['ok'] else 'ERR':<7}] monitor : {mon['detail']}")
    return lines


def run_doctor(importer: Importer | None = None, printer: Printer | None = None) -> int:
    printer = printer or print
    results = check_components(importer=importer)
    missing_critical = [
        name for name, r in results.items()
        if r["critical"] and not r["present"]
    ]
    for line in build_report(importer=importer):
        printer(line)
    printer("")
    if missing_critical:
        printer("Required components are missing. See README 'Offline / "
                "restricted networks'.")
        return 1
    printer("All required components present.")
    return 0