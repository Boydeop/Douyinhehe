"""PyInstaller/Nuitka entry point for the desktop application.

Windowed EXEs can hide Python tracebacks, so explicit UI smoke checks write
failures beside their requested success marker. No user data or API keys are
included in normal startup logs.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

from douyinhehe.__main__ import main


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if "--ui-smoke-file" in sys.argv:
            try:
                pos = sys.argv.index("--ui-smoke-file") + 1
                if pos < len(sys.argv):
                    Path(sys.argv[pos] + ".error.txt").write_text(
                        traceback.format_exc(), encoding="utf-8"
                    )
            except OSError:
                pass
        raise
