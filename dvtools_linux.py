#!/usr/bin/env python3
"""
DVtools — Linux launcher
--------------------------------
All the real logic lives in dvtools_core.py (shared with the Windows and
macOS builds), so plugins work exactly the same way on all three
platforms: you just need to copy the same plugin file into the
"plugins/" folder next to dvtools_core.py, or into ~/.dvtools/plugins
(the per-user folder, on Linux
/home/<user>/.dvtools/plugins).

This file only adds Linux-specific details:
  - Sets the window's WM_CLASS to "dvtools" so the window
    manager/taskbar correctly groups the app and can associate it with
    its own icon via a .desktop file.
"""

import sys


if __name__ == "__main__":
    import dvtools_core as dvtools

    if len(sys.argv) > 1:
        dvtools.run_cli_mode()
    else:
        # className sets the WM_CLASS that Linux window managers
        # (X11/Wayland) use to identify the application.
        app = dvtools.App(className="dvtools")
        app.mainloop()
