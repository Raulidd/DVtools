#!/usr/bin/env python3
"""
DVtools — macOS launcher
-------------------------------
All the real logic lives in dvtools_core.py (shared with the Windows and
Linux builds), so plugins work exactly the same way on all three
platforms: you just need to copy the same plugin file into the
"plugins/" folder next to dvtools_core.py, or into ~/.dvtools/plugins
(the per-user folder, on macOS
/Users/<user>/.dvtools/plugins).

This file only adds macOS-specific details:
  - Uses the name "DVtools" in the menu bar instead of "Python" or
    "python3" (which is what shows up by default when running a bare
    .py script on macOS).
  - Packaging note: if you're going to distribute this as a real .app
    bundle (with py2app or PyInstaller --windowed), this file is the
    one that should be used as the entry-point script.
"""

import sys
import platform


def _configure_macos_app_name():
    if platform.system() != "Darwin":
        return
    try:
        from Foundation import NSBundle
        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info is not None:
            info["CFBundleName"] = "DVtools"
    except Exception:
        # pyobjc isn't installed or isn't available; not critical, the
        # app still works, it just shows "Python" in the menu bar.
        pass


if __name__ == "__main__":
    _configure_macos_app_name()
    import dvtools_core as dvtools

    if len(sys.argv) > 1:
        dvtools.run_cli_mode()
    else:
        dvtools.App().mainloop()
