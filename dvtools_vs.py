#!/usr/bin/env python3
"""
DVtools - VapourSynth Engine
-----------------------------
Optional processing backend built on top of VapourSynth instead of relying
only on ffmpeg's built-in "-vf" filters. VapourSynth gives access to much
stronger filters (motion-aware deinterlacers, spatio-temporal denoisers,
etc.) and lets third-party DVtools plugins hook directly into a VapourSynth
clip via the "modify_vs_clip" hook (see README_PLUGINS.md).

This module is 100% optional. DVtools works exactly as before if
VapourSynth is not installed; the "Use VapourSynth engine" checkbox in the
Advanced tab is simply disabled in that case.

--------------------------------------------------------------------------
Requirements (installed separately by the user, NOT bundled with DVtools):
  - VapourSynth itself:            https://www.vapoursynth.com/
  - The "vspipe" command line tool (ships with VapourSynth).
  - A source filter able to read the input container. Either one works:
      * bestsource  (core.bs.VideoSource)   -> recommended
      * ffms2       (core.ffms2.Source)
  - Optional, purely for better quality (DVtools degrades gracefully and
    falls back to a core VapourSynth filter if any of these are missing):
      * havsfunc + nnedi3   -> higher quality deinterlacing (QTGMC)
      * bwdif (vs-bwdif)    -> good, fast deinterlacer fallback
      * knlmeansCL          -> denoiser
      * mvtools             -> motion-based stabilization
      * cas (vs-cas)        -> contrast adaptive sharpening

DVtools never assumes a specific plugin set is installed: every optional
filter is wrapped in its own try/except so a missing plugin just means
"skip this particular enhancement", not a crash.
--------------------------------------------------------------------------
"""

import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

try:
    import vapoursynth as vs  # noqa: F401  (only used to confirm bindings exist)
    VAPOURSYNTH_AVAILABLE = True
except ImportError:
    vs = None
    VAPOURSYNTH_AVAILABLE = False


def is_available():
    """True if the VapourSynth Python bindings AND the vspipe executable
    are both present on this machine."""
    return VAPOURSYNTH_AVAILABLE and find_vspipe() is not None


def find_vspipe():
    """Locates the vspipe executable used to run a .vpy script and stream
    raw video frames into ffmpeg."""
    return shutil.which("vspipe") or shutil.which("vspipe.exe")


def _py_repr(path):
    """Safe literal representation of a filesystem path for embedding in a
    generated .vpy script."""
    return repr(str(path))


def build_vs_script(input_path, width, height, info, options, vs_plugin_modules=None):
    """Builds a VapourSynth script (as Python source text) that mirrors the
    same processing steps as dvtools_core.build_filter_chain(), using
    VapourSynth filters where a higher quality equivalent is available.

    vs_plugin_modules: list of loaded DVtools plugin modules that expose
    modify_vs_clip(clip, options, info, vs_core) -> clip. Called last, same
    convention as the existing ffmpeg "modify_filters" plugin hook.

    Returns the script source as a string; the caller is responsible for
    writing it to a temp .vpy file.
    """
    lines = [
        "import vapoursynth as vs",
        "core = vs.core",
        "",
        "src_path = %s" % _py_repr(input_path),
        "",
        "# --- Source loading ---------------------------------------------",
        "# Try the best available source filter, in order of quality/speed.",
        "clip = None",
        "for _loader in (",
        "    lambda: core.bs.VideoSource(source=src_path),",
        "    lambda: core.ffms2.Source(source=src_path),",
        "):",
        "    try:",
        "        clip = _loader()",
        "        break",
        "    except AttributeError:",
        "        continue",
        "if clip is None:",
        "    raise RuntimeError(",
        "        'No VapourSynth source filter available. Install the "
        "\"bestsource\" or \"ffms2\" VapourSynth plugin.')",
        "",
        "clip = core.resize.Bicubic(clip, format=vs.YUV420P8, matrix_in_s='709')",
    ]

    # --- Auto-crop black borders / manual crop --------------------------
    # "autocrop_filter" is the ffmpeg-style string ("crop=W:H:X:Y") already
    # computed by dvtools_core.detect_black_borders(); we translate it into
    # VapourSynth's CropRel here so both engines apply the same detected
    # borders.
    autocrop_filter = options.get("autocrop_filter")
    autocrop_match = re.match(r"crop=(\d+):(\d+):(\d+):(\d+)", autocrop_filter or "")
    if autocrop_match:
        w, h, x, y = (int(g) for g in autocrop_match.groups())
        orig_w, orig_h = info.get("width", 0), info.get("height", 0)
        right = max(0, orig_w - w - x)
        bottom = max(0, orig_h - h - y)
        lines.append(f"clip = core.std.CropRel(clip, left={x}, right={right}, "
                      f"top={y}, bottom={bottom})")
    elif options.get("crop", False):
        px = int(options.get("crop_px", 8))
        lines.append(f"clip = core.std.CropRel(clip, left={px}, right={px}, "
                      f"top={px}, bottom={px})")

    # --- Chromatic aberration correction (best-effort) -------------------
    # Not something ffmpeg can do well (rgbashift only shifts channels by
    # whole pixels). Here it's done with sub-pixel precision using the
    # "fmtc" plugin (vs-fmtconv): R/G/B are separated, R and B are shifted
    # in opposite directions by a fraction of a pixel, and recombined.
    # If the fmtc plugin isn't installed, it's skipped without breaking
    # the rest of the pipeline (same pattern as the other optional
    # filters in this file).
    if options.get("chromatic_aberration", False):
        shift = float(options.get("chromatic_aberration_shift", 0.3))
        lines += [
            "",
            "# --- Chromatic aberration correction ------------------------------",
            "try:",
            "    _orig_format_id = clip.format.id",
            "    _rgb = core.resize.Bicubic(clip, format=vs.RGB24, matrix_in_s='709')",
            "    _r = core.std.ShufflePlanes(_rgb, planes=[0], colorfamily=vs.GRAY)",
            "    _g = core.std.ShufflePlanes(_rgb, planes=[1], colorfamily=vs.GRAY)",
            "    _b = core.std.ShufflePlanes(_rgb, planes=[2], colorfamily=vs.GRAY)",
            # FIXED: w=_r.width and h=_r.height are added to keep the exact size.
            f"    _r = core.fmtc.resample(_r, sx={shift}, sy={shift}, w=_r.width, h=_r.height)",
            f"    _b = core.fmtc.resample(_b, sx=-{shift}, sy=-{shift}, w=_b.width, h=_b.height)",
            "    _rgb = core.std.ShufflePlanes([_r, _g, _b], planes=[0, 0, 0], colorfamily=vs.RGB)",
            "    clip = core.resize.Bicubic(_rgb, format=_orig_format_id, matrix_s='709')",
            "except Exception:",  # A broad Exception is used to catch both AttributeError and VapourSynth-internal errors.
            "    print('[DVtools/VapourSynth] fmtc plugin not installed or error occurred: skipping '",
            "          'chromatic aberration correction. Install vs-fmtconv (fmtc) for this feature.')",
        ]

    # --- Deinterlace ------------------------------------------------------
    if options.get("deinterlace", True):
        lines += [
            "",
            "# --- Deinterlace -------------------------------------------------",
            "try:",
            "    import havsfunc as haf",
            "    clip = haf.QTGMC(clip, Preset='Medium', TFF=True, FPSDivisor=1)",
            "except ImportError:",
            "    try:",
            "        clip = core.bwdif.Bwdif(clip, field=3)",
            "    except AttributeError:",
            "        # Last-resort fallback available in every VapourSynth install.",
            "        clip = core.std.SeparateFields(clip, tff=True)",
            "        clip = core.std.DoubleWeave(clip, tff=True)",
            "        clip = clip[::2]",
        ]

    # --- Denoise ------------------------------------------------------
    if options.get("noise_reduction", False):
        lines += [
            "",
            "# --- Denoise -------------------------------------------------",
            "try:",
            "    clip = core.knlm.KNLMeansCL(clip, d=1, a=2, s=2, h=1.2, channels='YUV')",
            "except AttributeError:",
            "    try:",
            "        clip = core.dfttest.DFTTest(clip)",
            "    except AttributeError:",
            "        clip = core.std.Convolution(clip, matrix=[1, 2, 1, 2, 4, 2, 1, 2, 1])",
        ]

    # --- Stabilization (motion-based, deshake equivalent) -------------
    if options.get("stabilize", False):
        strength = int(options.get("stabilize_strength", 16))
        lines += [
            "",
            "# --- Stabilization -------------------------------------------------",
            "try:",
            "    import mvsfunc as mvf",
            "    import muvsfunc as muf",
            f"    clip = muf.GPS(clip, radius={strength})",
            "except ImportError:",
            "    print('[DVtools/VapourSynth] mvsfunc/muvsfunc not installed: '",
            "          'skipping VapourSynth stabilization, image left as-is. '",
            "          'Install mvtools + mvsfunc + muvsfunc for this feature, or '",
            "          'disable the VapourSynth engine to use ffmpeg deshake instead.')",
        ]

    # --- Color restoration ------------------------------------------------
    if options.get("color_restoration", False):
        lines += [
            "",
            "# --- Color restoration (simple levels-based white balance) -------",
            "clip = core.std.Levels(clip, planes=[0], min_in=0, max_in=235, "
            "min_out=0, max_out=255, gamma=0.98)",
        ]

    # --- Sharpening ------------------------------------------------------
    if options.get("sharpening", False):
        lines += [
            "",
            "# --- Sharpening -------------------------------------------------",
            "try:",
            "    clip = core.cas.CAS(clip, sharpness=0.4)",
            "except AttributeError:",
            "    clip = core.std.Convolution(clip, matrix=[-1, -1, -1, -1, 16, -1, -1, -1, -1], divisor=8)",
        ]

    # --- Final resize to the requested output resolution ----------------
    lines += [
        "",
        "# --- Final scale to requested output resolution -------------------",
        f"clip = core.resize.Lanczos(clip, width={int(width)}, height={int(height)})",
    ]

    # --- DVtools plugin hook: modify_vs_clip ------------------------------
    if vs_plugin_modules:
        lines += ["", "# --- DVtools plugins (modify_vs_clip hook) -------------------------"]
        for i, _ in enumerate(vs_plugin_modules):
            lines.append(f"clip = _dvtools_vs_plugins[{i}].modify_vs_clip(clip, _dvtools_options, _dvtools_info, core)")

    lines += ["", "clip.set_output()"]
    return "\n".join(lines)


def write_vs_script(script_text, vs_plugin_modules, options, info):
    """Writes the generated script to a temp .vpy file. Plugin modules and
    the options/info dicts are injected as pickled globals via a small
    Python preamble so plugins can access them exactly like they do in the
    ffmpeg "modify_filters" hook."""
    tmp_dir = Path(tempfile.gettempdir()) / "dvtools_vs"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    script_path = tmp_dir / f"dvtools_pipeline_{uuid.uuid4().hex}.vpy"

    preamble = ""
    if vs_plugin_modules:
        # vspipe runs the .vpy file as a brand-new process, so we cannot
        # simply pass Python objects in memory. Instead we re-import each
        # plugin module fresh (they are stateless filter functions) using
        # the same loader DVtools' core uses.
        preamble += "import importlib.util as _u, sys as _s\n"
        preamble += "_dvtools_vs_plugins = []\n"
        for module in vs_plugin_modules:
            preamble += (
                f"_spec = _u.spec_from_file_location({_py_repr(module.__name__)}, "
                f"{_py_repr(module.__file__)})\n"
                f"_mod = _u.module_from_spec(_spec)\n"
                f"_spec.loader.exec_module(_mod)\n"
                f"_dvtools_vs_plugins.append(_mod)\n"
            )
        preamble += f"_dvtools_options = {options!r}\n"
        preamble += f"_dvtools_info = {info!r}\n"

    script_path.write_text(preamble + "\n" + script_text, encoding="utf-8")
    return script_path


def build_vs_pipeline_commands(input_path, output_path, width, height, info,
                                options, ffmpeg_path, video_encoder_args,
                                audio_filters, audio_args, metadata_args,
                                vs_plugin_modules=None, extra_output_args=None):
    """Builds the two commands needed to run the VapourSynth pipeline:
      1. vspipe: renders the .vpy script and streams raw y4m frames.
      2. ffmpeg: reads y4m from stdin for video, re-reads the ORIGINAL file
         for audio (VapourSynth here only touches video), encodes, and muxes.

    video_encoder_args: the full "-c:v <encoder> ..." argument list, exactly
    as produced by dvtools_core.build_video_encoder_args() -- shared with
    the plain ffmpeg pipeline so both engines always use the same codec
    settings.

    extra_output_args: additional raw ffmpeg output arguments appended right
    before the output path (e.g. ["-timecode", "00:00:00:00"] for the
    timecode-repair feature), so both engines stay in sync feature-wise.

    Returns (vspipe_cmd, ffmpeg_cmd, script_path).
    """
    script_text = build_vs_script(input_path, width, height, info, options,
                                   vs_plugin_modules)
    script_path = write_vs_script(script_text, vs_plugin_modules, options, info)

    vspipe_cmd = [find_vspipe(), str(script_path), "-", "-c", "y4m"]

    ffmpeg_cmd = [ffmpeg_path, "-y", "-i", "-", "-i", str(input_path)]
    ffmpeg_cmd += ["-map", "0:v:0", "-map", "1:a:0?"]
    ffmpeg_cmd += list(video_encoder_args)
    if audio_filters:
        ffmpeg_cmd += ["-af", ",".join(audio_filters)]
    ffmpeg_cmd += list(audio_args)
    ffmpeg_cmd += list(metadata_args)
    ffmpeg_cmd += list(extra_output_args or [])
    ffmpeg_cmd += ["-progress", "pipe:1", "-nostats", str(output_path)]

    return vspipe_cmd, ffmpeg_cmd, script_path


def run_pipeline(vspipe_cmd, ffmpeg_cmd, log_path):
    """Runs vspipe piped directly into ffmpeg. Returns the ffmpeg Popen
    object (whose .stdout carries the "-progress pipe:1" lines DVtools
    already knows how to parse) so the calling code in dvtools_core can
    reuse the exact same progress-bar logic used for the ffmpeg-only path.
    """
    vspipe_proc = subprocess.Popen(vspipe_cmd, stdout=subprocess.PIPE)
    with open(log_path, "w", encoding="utf-8", errors="replace") as log_f:
        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd, stdin=vspipe_proc.stdout, stdout=subprocess.PIPE,
            stderr=log_f, text=True)
    # Allow vspipe to receive SIGPIPE if ffmpeg exits early, instead of
    # hanging forever waiting for a reader that will never come back.
    vspipe_proc.stdout.close()
    return vspipe_proc, ffmpeg_proc


def run_pipeline_sync(vspipe_cmd, ffmpeg_cmd):
    """Blocking variant of run_pipeline(), used by batch/CLI mode where
    DVtools already runs each file synchronously with subprocess.run(). 

    Returns an object exposing .returncode and .stderr, mirroring the
    subset of subprocess.CompletedProcess that the batch/CLI code paths
    already use for the plain-ffmpeg pipeline.
    """
    class _Result:
        pass

    vspipe_proc = subprocess.Popen(vspipe_cmd, stdout=subprocess.PIPE)
    ffmpeg_proc = subprocess.Popen(
        ffmpeg_cmd, stdin=vspipe_proc.stdout, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True)
    vspipe_proc.stdout.close()
    _, ffmpeg_stderr = ffmpeg_proc.communicate()
    vspipe_proc.wait()

    result = _Result()
    result.returncode = ffmpeg_proc.returncode
    result.stderr = ffmpeg_stderr
    return result
