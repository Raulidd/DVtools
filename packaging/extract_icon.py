#!/usr/bin/env python3
"""
extract_icon.py
----------------
DVtools already carries its logo embedded as a base64 PNG string
(LOGO_B64 in dvtools_core.py) so the app never depends on an external
image file at runtime. For PACKAGING, though, Windows/macOS installers
want a real .ico / .icns file. This script pulls LOGO_B64 out with a
regex (no need to import dvtools_core, which would drag in tkinter),
decodes it, and uses Pillow to produce every format the CI workflow
needs.

Usage: python packaging/extract_icon.py
Produces (next to this script, in packaging/icons/):
  icon.png   - source image
  icon.ico   - Windows
  icon.icns  - macOS (only built if run on macOS/with iconutil,
               otherwise Pillow's multi-size .ico-like fallback is used)

If anything goes wrong (Pillow missing, logo not found, etc.) this
script exits 0 without producing icons -- packaging still works, it
will just fall back to the default OS icon. This is intentional so a
missing icon never breaks a CI build.
"""
import base64
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = Path(__file__).resolve().parent / "icons"


def extract_logo_png(core_path: Path) -> bytes | None:
    text = core_path.read_text(encoding="utf-8")
    match = re.search(r'LOGO_B64\s*=\s*\(([\s\S]*?)\)\s*\n', text)
    if not match:
        match = re.search(r'LOGO_B64\s*=\s*"([^"]+)"', text)
        if not match:
            return None
        b64_data = match.group(1)
    else:
        # Concatenated string literals across multiple lines.
        pieces = re.findall(r'"([^"]*)"', match.group(1))
        b64_data = "".join(pieces)
    b64_data = b64_data.strip()
    try:
        return base64.b64decode(b64_data)
    except Exception:
        return None


def main() -> int:
    core_path = ROOT / "dvtools_core.py"
    if not core_path.exists():
        print("dvtools_core.py not found, skipping icon extraction.")
        return 0

    png_bytes = extract_logo_png(core_path)
    if not png_bytes:
        print("Could not extract LOGO_B64, skipping icon extraction.")
        return 0

    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    png_path = ICONS_DIR / "icon.png"
    png_path.write_bytes(png_bytes)
    print(f"Wrote {png_path}")

    try:
        from PIL import Image
    except ImportError:
        print("Pillow not installed, skipping .ico/.icns generation "
              "(icon.png alone is still available).")
        return 0

    img = Image.open(png_path).convert("RGBA")

    # --- Windows .ico (multi-resolution) ---
    ico_path = ICONS_DIR / "icon.ico"
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format="ICO", sizes=sizes)
    print(f"Wrote {ico_path}")

    # --- macOS .icns ---
    # iconutil (macOS-only) needs an .iconset folder of specific sizes.
    if sys.platform == "darwin":
        iconset_dir = ICONS_DIR / "icon.iconset"
        iconset_dir.mkdir(exist_ok=True)
        icns_sizes = [16, 32, 128, 256, 512]
        for s in icns_sizes:
            img.resize((s, s), Image.LANCZOS).save(iconset_dir / f"icon_{s}x{s}.png")
            img.resize((s * 2, s * 2), Image.LANCZOS).save(iconset_dir / f"icon_{s}x{s}@2x.png")
        icns_path = ICONS_DIR / "icon.icns"
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
            check=True,
        )
        print(f"Wrote {icns_path}")
    else:
        print("Not running on macOS: skipping .icns (only needed for the macOS build job).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
