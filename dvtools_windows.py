#!/usr/bin/env python3
"""
DVtools — Windows launcher
--------------------------------
All the real logic lives in dvtools_core.py (shared with the macOS and
Linux builds), so plugins work exactly the same way on all three
platforms: you just need to copy the same plugin file into the
"plugins/" folder next to dvtools_core.py, or into ~/.dvtools/plugins
(the per-user folder, which on Windows is
C:\\Users\\<user>\\.dvtools\\plugins).

This file only adds Windows-specific details:
  - Declares the app "DPI aware" so it doesn't look blurry on
    high-resolution screens with scaling (125%, 150%, etc.).
"""

import sys
import ctypes
import platform


def _enable_dpi_awareness():
    if platform.system() != "Windows":
        return
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2 (Windows 8.1+)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            # Fallback for older Windows versions.
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


if __name__ == "__main__":
    _enable_dpi_awareness()
    import dvtools_core as dvtools

    if len(sys.argv) > 1:
        dvtools.run_cli_mode()
    else:
        dvtools.App().mainloop()
