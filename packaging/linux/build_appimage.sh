#!/usr/bin/env bash
# build_appimage.sh
# ------------------
# Wraps the Nuitka standalone build (build/dvtools_linux.dist/) into a
# single portable AppImage. Run from the repo root:
#
#   bash packaging/linux/build_appimage.sh
#
# Requires: appimagetool on PATH (the CI workflow downloads it
# automatically; for local builds get it from
# https://github.com/AppImage/AppImageKit/releases).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="$ROOT_DIR/build/dvtools_linux.dist"
APPDIR="$ROOT_DIR/build/DVtools.AppDir"
OUT_DIR="$ROOT_DIR/dist"

if [ ! -d "$DIST_DIR" ]; then
    echo "Error: $DIST_DIR not found. Build with Nuitka first:"
    echo "  python -m nuitka --standalone --output-dir=build dvtools_linux.py"
    exit 1
fi

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$OUT_DIR"

# Copy the whole standalone folder (app + embedded Python + fonts +
# plugins) so BASE_PATH-relative lookups keep working unmodified.
cp -r "$DIST_DIR"/* "$APPDIR/usr/bin/"

# AppRun is the AppImage entry point.
cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "$HERE/usr/bin/dvtools_linux" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cp "$ROOT_DIR/packaging/linux/dvtools.desktop" "$APPDIR/dvtools.desktop"

if [ -f "$ROOT_DIR/packaging/icons/icon.png" ]; then
    cp "$ROOT_DIR/packaging/icons/icon.png" "$APPDIR/dvtools.png"
else
    # appimagetool requires *some* icon to exist; fall back to a blank
    # placeholder rather than failing the whole build.
    echo "Warning: no packaging/icons/icon.png found, using a blank icon."
    python3 - "$APPDIR/dvtools.png" <<'PYEOF'
import sys
from pathlib import Path
Path(sys.argv[1]).write_bytes(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000a49444154789c6360000002000100beb7e9d90000000049454e"
    "44ae426082"
))
PYEOF
fi

appimagetool "$APPDIR" "$OUT_DIR/DVtools-Linux-x86_64.AppImage"
echo "Built: $OUT_DIR/DVtools-Linux-x86_64.AppImage"
