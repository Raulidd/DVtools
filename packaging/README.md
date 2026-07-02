# Empaquetado y distribución de DVtools

## La estrategia en una frase

**El instalador no incluye ffmpeg.** DVtools es 100% librería estándar de
Python + Tkinter, así que el paquete de la app pesa poco (~15-25 MB por
plataforma). Si al abrir la app no encuentra `ffmpeg`/`ffprobe` (ni junto
al ejecutable ni en el PATH del sistema), ofrece descargarlos
automáticamente en segundo plano (ver `download_ffmpeg()` en
`dvtools_core.py`). Así:

- El instalador que la gente descarga es chico y rápido.
- Quien ya tiene ffmpeg instalado (muy común en Linux/macOS) no descarga
  nada de más.
- Quien no lo tiene, lo consigue con un clic, sin salir de la app.

## Qué genera cada plataforma

| Plataforma | Herramienta | Resultado |
|---|---|---|
| Windows | Nuitka (standalone) + Inno Setup | `DVtools-Setup-Windows.exe` (instalador) + `.zip` portable |
| macOS | Nuitka (`--macos-create-app-bundle`) + `create-dmg` | `DVtools-macOS.dmg` |
| Linux | Nuitka (standalone) + `appimagetool` | `DVtools-Linux-x86_64.AppImage` (un solo archivo, sin instalación) |

Se usa **Nuitka** en vez de PyInstaller porque compila a binario nativo:
el resultado pesa menos y arranca más rápido, ya que no carga un
intérprete Python empaquetado con un bootloader como hace PyInstaller.

## Cómo se generan (CI automático)

`.github/workflows/build.yml` compila las 3 plataformas en sus propios
runners de GitHub Actions (Windows no puede compilar el `.exe` de macOS
ni viceversa — cada SO se compila en su propia máquina, algo que Nuitka
y PyInstaller comparten como limitación). Se dispara:

- Automáticamente al crear un tag de versión: `git tag v1.0.0 && git push --tags`
- Manualmente desde la pestaña **Actions** del repo ("Run workflow")

Al final, si el trigger fue un tag, los 3 instaladores se adjuntan
automáticamente a una GitHub Release.

## Compilar localmente (para probar antes de un release)

```bash
pip install nuitka pillow

# Windows (desde Windows):
python -m nuitka --standalone --enable-plugin=tk-inter \
  --windows-console-mode=disable --include-data-dir=fonts=fonts \
  --include-data-dir=plugins=plugins --output-dir=build dvtools_windows.py

# macOS (desde macOS):
python -m nuitka --standalone --enable-plugin=tk-inter \
  --macos-create-app-bundle --include-data-dir=fonts=fonts \
  --include-data-dir=plugins=plugins --output-dir=build dvtools_macos.py

# Linux (desde Linux):
python -m nuitka --standalone --enable-plugin=tk-inter \
  --include-data-dir=fonts=fonts --include-data-dir=plugins=plugins \
  --output-dir=build dvtools_linux.py
bash packaging/linux/build_appimage.sh
```

## Sobre la firma de código (importante, léelo antes de publicar)

- **macOS**: sin una cuenta de Apple Developer ($99/año) para firmar y
  notarizar, Gatekeeper mostrará "app dañada / no verificada" la
  primera vez. Es normal en apps indie sin firmar; se resuelve
  haciendo clic derecho → Abrir. Vale la pena ponerlo en el README
  del repo para que no espante a nadie.
- **Windows**: sin certificado de firma de código, SmartScreen puede
  mostrar una advertencia ("Windows protegió tu PC"). El usuario puede
  igual hacer clic en "Más información" → "Ejecutar de todas formas".
  Con el tiempo, mientras más gente lo descargue y ejecute sin
  reportarlo como malware, la reputación del binario mejora en
  SmartScreen.

Ninguna de las dos cosas es un bloqueador para distribuir — solo hay
que avisarle a la gente en el README principal para que no se asusten.

## Icono de la app

`packaging/extract_icon.py` saca el logo que ya vive embebido en
`dvtools_core.py` (la constante `LOGO_B64`) y genera `icon.ico` /
`icon.icns` / `icon.png` en `packaging/icons/`. El workflow de CI lo
corre automáticamente antes de cada build; si algo falla (por ejemplo
Pillow no disponible), el build sigue igual, solo que sin ícono
personalizado.
