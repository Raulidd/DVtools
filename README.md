# DVtools
A light-weight cross-platform tool to digitize, restore, and upscale MiniDV and legacy video tapes using FFmpeg, VapourSynth, and an extensible plugin system.

============================================================================================
## Requirements

### Minimum requirements
- **OS**: Windows 10 (64-bit), macOS 11 (Big Sur), or a modern 64-bit Linux distribution
- **CPU**: Any 64-bit dual-core CPU (software encoding will be slow but functional)
- **RAM**: 4 GB
- **Disk space**: ~50 MB for the app itself, plus free space for FFmpeg and your output files (high-resolution exports of long tapes can require several GB)
- **FFmpeg + FFprobe**: required — see [Dependencies](#-dependencies) below

### Recommended requirements
- **OS**: Windows 11, macOS 13+, or a recent Linux distro
- **CPU**: Quad-core or better (for reasonable software-encoding speed on H.265/AV1)
- **RAM**: 8 GB or more
- **GPU**: An NVIDIA (NVENC), AMD (AMF), or Intel (QuickSync) GPU for hardware-accelerated encoding — dramatically faster exports
- **Storage**: SSD, for smoother scrubbing/preview and faster batch processing
- **Disk space**: 10+ GB free when batch-processing multiple tapes at high resolution

============================================================================================

## Dependencies

DVtools itself is built entirely on the Python standard library + Tkinter, so the app download is small. Everything else is either bundled at build time or offered as an optional one-click download the first time you run it:

 **FFmpeg / FFprobe** Are Required.  They're not bundled in the installer to keep it lightweight. If not found on your system (checked next to the executable and in your system `PATH`), DVtools offers to download official static builds automatically in the background. Can also be installed manually: `winget`/[gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/) on Windows, `brew install ffmpeg` on macOS, `sudo apt install ffmpeg` (or your distro's package manager) on Linux.

 **VapourSynth + vspipe**  Optional  Enables the higher-quality VapourSynth processing engine (better deinterlacing, denoising, and stabilization) and the chromatic aberration correction filter. If not installed, DVtools automatically uses its built-in FFmpeg pipeline instead. Get it from [vapoursynth.com](https://www.vapoursynth.com/).

 **vs-fmtconv (`fmtc`)**  Optional  Needed specifically for the chromatic aberration correction filter, on top of VapourSynth. Silently skipped if not installed. 

 **VLC**  Is optional,  only needed if you use the "Open with VLC" button instead of the built-in preview. 

 **A GPU driver supporting NVENC / AMF / QuickSync**  Optional,  Only needed for hardware-accelerated encoding; DVtools falls back to CPU/software encoding automatically if unavailable. |

> **Note on code signing**: Prebuilt binaries in this release are not code-signed (no Apple Developer or Windows code-signing certificate). On macOS you may need to right-click → Open the first time to bypass Gatekeeper; on Windows, SmartScreen may show a warning — click "More info" → "Run anyway". This is normal for unsigned indie software and not a sign of malware.

============================================================================================
## Installation

Download the build for your platform from the assets below:
- **Windows**: `DVtools-Setup-Windows.exe` (installer) or the portable `.zip`
- **macOS**: `DVtools-macOS.dmg`
- **Linux**: `DVtools-Linux-x86_64.AppImage` (single file, no installation needed)

That's all! an easy installation

============================================================================================
