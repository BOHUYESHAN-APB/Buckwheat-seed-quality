"""Lightweight test to initialize the CTk App without entering mainloop.
This helps check imports and Detector init without opening a blocking GUI.
"""
import traceback
import sys
from pathlib import Path

# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from app.main import App
    print("Imported App")
    # Create and immediately destroy the app to avoid opening a window loop.
    app = App()
    print("App instance created OK")
    # check detector state if available
    det = getattr(app, "detector", None)
    if det is None:
        print("Detector: None")
    else:
        print("Detector present. is_ready=", getattr(det, "is_ready", None))
        print("Detector last_error=", getattr(det, "last_error", None))
        # If detector has sample boxes from fallback, print count
        print("Detector last_boxes count=", len(getattr(det, "last_boxes", [])))
    # Clean up
    try:
        app.destroy()
        print("App destroyed OK")
    except Exception:
        print("App destroy failed (non-fatal)")
except Exception:
    traceback.print_exc()
    raise
