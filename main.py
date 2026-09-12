"""HADJ AIR TOUCH - AI-powered virtual touch interface for Windows 11.

Turns a normal (non-touch) PC into an air-touch computer using a webcam and
AI hand/finger tracking. All processing happens locally.
"""


import io
import os
import sys
import traceback

# Prevent PyInstaller --windowed NoneType stdout/stderr crashes
class NullStream(io.TextIOBase):
    def write(self, s):
        return len(s) if s else 0
    def flush(self):
        pass

if sys.stdout is None:
    sys.stdout = NullStream()
if sys.stderr is None:
    sys.stderr = NullStream()

# Handle PyInstaller frozen environment
if getattr(sys, 'frozen', False):
    bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)

# Top-level Exception Handler for Windows PyInstaller executable
def _gui_excepthook(exc_type, exc_value, exc_traceback):
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(err_msg, file=sys.stderr)
    
    # Save error to crash.log
    try:
        log_path = os.path.join(os.path.expanduser("~"), "HADJ_Air_Touch_crash.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(err_msg)
    except Exception:
        pass

    # Display error dialog box so user sees exact cause on target PC
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"An error occurred while launching HADJ AIR TOUCH:\n\n{exc_value}\n\n"
            f"Full traceback saved to: {os.path.expanduser('~')}\\HADJ_Air_Touch_crash.log",
            "HADJ AIR TOUCH - Error",
            0x10 | 0x0
        )
    except Exception:
        pass

sys.excepthook = _gui_excepthook


def main() -> int:
    """Entry point. Delegates to the Qt bootstrap unless --headless is set."""
    import argparse

    from app.cli import build_parser, run_cli

    parser = build_parser()
    args = parser.parse_args()

    if args.headless or args.self_test or args.doctor:
        return run_cli(args)

    # GUI path (PySide6). Imported lazily so --headless works without Qt.
    from app.gui import run_gui  # noqa: PLC0415

    return run_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())