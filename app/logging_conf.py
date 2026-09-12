import logging
import os
import sys


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
        
    stream = sys.stderr if sys.stderr is not None else sys.stdout
    if stream is not None and hasattr(stream, "write"):
        handler: logging.Handler = logging.StreamHandler(stream)
    else:
        log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "HADJAirTouch")
        os.makedirs(log_dir, exist_ok=True)
        handler = logging.FileHandler(os.path.join(log_dir, "app.log"), encoding="utf-8")

    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(handler)
    root.setLevel(level)