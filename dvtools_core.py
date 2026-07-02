#!/usr/bin/env python3
"""
DVtools
-------
Welcome to the DVtools Source Code! This is a Python application that allows you to process MiniDV video files
and upscale them to high resolution. It provides a graphical user interface (GUI) for easy interaction.

Note: This code is provided as-is and may require additional dependencies to run correctly.
"""

import base64
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import tkinter as tk
import importlib.util
import urllib.request
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
import ctypes

# Optional VapourSynth processing engine (see dvtools_vs.py). Import is
# always safe: the module itself falls back to VAPOURSYNTH_AVAILABLE=False
# if the "vapoursynth" package is not installed on this machine.
import dvtools_vs

# BASE_PATH points to the script's folder both in development mode and
# when the app is packaged with PyInstaller/py2app/py2exe (sys.frozen).
# FIXED BUG: previously Path(__file__) was used without checking "frozen"
# mode, which broke font and plugin lookup once packaged into an
# executable.
BASE_PATH = Path(sys.executable).parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent

# FIXED BUG: the previous version called os.add_dll_directory()
# unconditionally on module import, pointing to a .lnk (shortcut) file
# instead of a real folder. On a standard VLC install via the Start Menu
# that path DOES exist, so on most Windows machines with VLC installed
# the app failed to start with "NotADirectoryError". Now it's done
# lazily, only on Windows, only if the real folder exists, and inside a
# try/except so it can never bring down app startup.
def _prepare_vlc_dll_windows():
    if platform.system() != "Windows":
        return
    for folder in (
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC",
    ):
        if os.path.isdir(folder):
            try:
                os.add_dll_directory(folder)
            except (OSError, AttributeError):
                pass


_prepare_vlc_dll_windows()

_DYNAMIC_FONT_LOADED = False


def load_dynamic_font(font_path):
    """Loads a font file (.ttf or .otf) into memory so Tkinter can use it,
    without installing it system-wide.

    FIXED BUG: the previous version only worked on Windows (via ctypes)
    and every other platform silently ended up with no custom font at
    all. On macOS it now tries to register the font in the user's font
    folder (~/Library/Fonts) if it isn't installed yet; on Linux it does
    the same with fontconfig (~/.local/share/fonts). If anything fails,
    the app simply falls back to the system's default font: this must
    never break startup.
    """
    global _DYNAMIC_FONT_LOADED
    font_path = Path(font_path)
    if not font_path.exists():
        return False

    system = platform.system()
    try:
        if system == "Windows":
            # FR_PRIVATE: only available to this process, not installed
            # permanently system-wide.
            result = ctypes.windll.gdi32.AddFontResourceExW(str(font_path), 0x10, 0)
            if result:
                _DYNAMIC_FONT_LOADED = True
                return True
        elif system == "Darwin":
            destination = Path.home() / "Library" / "Fonts" / font_path.name
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(font_path.read_bytes())
            _DYNAMIC_FONT_LOADED = True
            return True
        else:
            destination = Path.home() / ".local" / "share" / "fonts" / font_path.name
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(font_path.read_bytes())
                try:
                    subprocess.run(["fc-cache", "-f", str(destination.parent)],
                                    capture_output=True, timeout=10)
                except (OSError, subprocess.SubprocessError):
                    pass
            _DYNAMIC_FONT_LOADED = True
            return True
    except Exception as e:
        print(f"[dvtools] Could not load the custom font: {e}")
    return False

def change_windows_title_bar(window, dark_mode: bool):
    """
    Changes the native title bar color in Windows 10/11 without consuming extra resources.
    """
    if platform.system() != "Windows":
        return

    try:
        # Force window refresh to obtain the correct handle (HWND)
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        
        # DWMWA_USE_IMMERSIVE_DARK_MODE attribute
        # In older Win10 builds it was 19, in newer versions and Win11 it is 20
        dwm_attr = 20
        
        # Configure the value (1 for dark, 0 for light)
        value = ctypes.c_int(1 if dark_mode else 0)
        
        # Call the Windows API
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 
            dwm_attr, 
            ctypes.byref(value), 
            ctypes.sizeof(value)
        )
    except Exception as e:
        # If the system does not support it (e.g. Windows 7 or Linux), fail silently without breaking the app
        print(f"Could not change title bar color: {e}")

# ----------------------------------------------------------------------
# Embedded Logo (Small PNG, avoiding external file dependencies)
# ----------------------------------------------------------------------

LOGO_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAADwUlEQVRYCd1WT0iUQRR/K2tQLRHrBlEEoa5iRSBrx0UsMAmsW4lFhwi9SHjpIEVK1w4JefHSwcBDxz0EGSXmoYMuRodMd7UQjKB16bAmUfm1v/ftm2bG2fVT6NKD75t5f+b9fvPmzbdL9B+JV9wLnh1JaEfR5YO9XPgoe2O/ViUqUO5AQZKxwqgISIxGBKayOGUdkijAuAXcXlMi48SqsoP/hV46Hmd/OFntgETQ3dspFW7Y8jhZWjGBVb0P4vE4r8tkMsZ6xaRoZXAJRFRTU5MRfLWry9DPXb9t6LZy40KC5ufn2by4uEgNDQ08L5FgbKmAAT46Okq9vb3U3Nxs5FxZXaVEImHYRHk59oCnOqn+/n62tbW18Sh5ZQ1GqYAnO0cQBAQg3d3dPI6Pj/M8EomwjpdNZnh4mB4/Sys/Ju8mntDU1JSynWhspCt+TsY2bkFPTw8HAjx8soPy+bxaiAlIFAoFfqCn0z6YDvDozk24lOg+GO8ODiofJgYBGGTnP6MxqDQyMsKjVIIV7aWTwHmDpC6tra0kj+1DnPQAr8HuIF7yGu0/1kiZXI5iMZ8I7KhIpthMkHixoeQ4hoaGaHJyku02iGwITQjRGxC6UQFJXp3PwUcdr3ngHfgzH1jmchwAt0stMW8+ficBF5s+GgTEkf/whULhalp5eEtMvPO+vj7WsXtdAD43N8cP7HYfgKBUSF+HuXEE4jzw+y39SB8mEIEMDAxQXW2tKv+lzk56v7CgABGTTCa5OeXewyaCPpHjFZuMxjWMRqMM9HxigsKHztKvr684rr6+fsuNgAMfKgDjOspdl4/NiyWPIlUbvB4Vkd6we8CogFw7AGazPjgyZLNZToTX+fZ2mpmdVd8H5dAmZ1paiJZmqLC5V7NubUA4hUCoyMyrqalx7hSEXCK3QK6iKwY27N7eucTqTRhaW1sj/UGQXw2/AugDW+RsK5EoB45cOgHo6Al5oHP5QQLgKL1LdBLoi8L6uivMabMJGEGohsjS8jKhSUXwzRBg2DCfnp4Wd+BRbkGlBdwbeh+gWbnRSqv0HadSKUrREfacrtpHxzf5+MriSBNWIoDe8GT3GGUuR4KyA3g3UpaZI5n6ydZ9pQaDCbm8Mapj90HaoIv0Wexsc72CVEDW8VUVRRudm/hG5jdAizemFZvQiPQVgNmPhHn3qYk+0R7RA41O9oFW/g3iv3MA1+Ue8X/BbfNvG6AnteYMfJn8f7vwnSp9WIOCY81uCXg6MBJBnpL6yx04b+BAH8J4cwUMyy429AfbJnKUYelzTQAAAABJRU5ErkJggg=="
)
# ----------------------------------------------------------------------
#Animation (Base64 Frames)
# ----------------------------------------------------------------------

FRAME_1_B64 = "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAxklEQVRYCe1UAQoCMQw7xf9/WQlnjrbY6HZuE+zg2LVNk6yMbVutmsC/T+AycQB3o3Xo3kwSvxYUSqdDiqYaKKTF0/Ke4NC5PvNM0KWHD4xoABLTxSFqDSCevpYb4Il5BxiP3J3W8gmUgeUT4GVzF4PJAbvUkcUvmHnJH1+/CIr1Xh/gbeaKZnrEwSF5lCvbqHCZMfb39DpOErmkCIDnJ2B76VN3NKHwxIBZ4d6aygDZqbJ8xuPyrU7tKUnUysG+2msCvzGBB7CnHwbXuUNMAAAAAElFTkSuQmCC"
FRAME_2_B64 = "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAADo0lEQVRYCe1WPUgcURCeDWIwwRQ5BAP5KfSQSxUOziKNaJpUdkng7GMTUsteiBLYrYQQsLEPJ2oRsI9GCBZ3cDYhiT9F/gpFrJRIRNjMN/fm5e3enbcSSBMH3r73ZubNfO+b2b0jOpdzBv53Brx/SEDk5LJ5Oxwllq5TwvTXW00ay6FKN7nVjY6OxpyXlpasbb5cFtujYvFUncKOoshfWVkJR0ZGNJec08OayFteXoaDv7q6GmLGRqW7u5vy+bxuaXh42K4X5uYCbHp6e0tWaRbqxwBofHw82NragqUBgDc9PY0EkvTJqzfhgztX4Sj7crkcFIvFEkCouGCg29vZCT9ubPgKtFarCWC+jB6h2wMDAbOGvQC4oBYkZ9EbN9ze+IUHBweEAUECiCbg5LKHHTbMahMDP55NTupSZgvA0YaPX7+n40wPTU1NQQ0whNtjTkoSBNvFX0EODQ2RDrCYPG8B4AAGkrP4l25kZZ6ZmdH+INROhyaAE4AiCYsyiDWAhKg5hvaBW384WQAauHN/jzAg9+ul80xwymazMsTIDwWN5kpQLSxwL/izs7Olzc3Npuwhjv0OVKtVKhQKtL+xK/GvFTrp+8untLi4KHsAZAByQwBxxSSXpEZvmdASGT0azzIKnQVgDKV7+Q56WzsJj6vvfICZmJiAH/X39wv9WDMAJEMSmxS3NWWxOuzxRmhDGvoRwooLwNve3vY5kX/rypfwa72hbTA+4a4RQPZIjNdRawwD90TIDRehcbVXTAMmY8R7AEEZBGLEbqd6x6Y+lmooIGNjY2DK53KWmtwY9Mv7L878UAakNpVKxRscHBSUu58XiNfq15AIBtALSdRZdHigV/TVM2BiyeFj3wJeK4iIgQCpNotlA32QFKW4GYj19fUgl8tp7zQkRyxlQOO6TgBCmUwm6OvrkyZkJ7DTwIbbbIeHh4glHxz+8cIa4sata8zTZSBmMBtlgVB/NCn0oBNDbw+dWYcmqZcmOc61RAajkYhZIGbB/ZiEpkzq02puGz9ZgqaBBn5eprVKJeCmRECwIEy8oFxT/+f0SfUNXa8GndsiZMfobtdN8V87+iYzgICBVgA0OGYDpmWedj3gxiIAwVD6nZvG/M6ySQVAb66BlRHsTwPR7vY4n6YHQJ99G3AI8pDiP0h17Z9nmuTwTsUAHJMs/Oj6BbXIBzrR5Znnls3RIpIw4Zbg+tFFWiD5k0nalGlvjxxnBaC4kiVJlil13N/S25WRIsydPQAAAABJRU5ErkJggg=="
FRAME_3_B64 = "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAADw0lEQVRYCe1WzUtUURQ/T8bCECodSfoi/GRCAtEQhOahm/oPgiFa6qqdLoRIbevGhRu3QTOmO/8A5b1FIGm0G5hRCaFF+FELQaL0dX/He27njeM4ErTJA/fdc8/H/f3uOfcOQ3QhFxX43yvg/cMCRArL4SaUEaoOKnH99VJAYxhidODt7e0OKZVKOR3K4uKii3+XzfJGTzOZEzbEvp2bw0T5fJ7nQqEQLi8v+4ODg1gjl/MkmTcT8NnZ2XB4eDidyWRCzraf+vp66unpcaaBgQGnz+dyaSyamptjObBJnCFA2LdYLMIcJ6DB4UUgZiGRzWaZEEiIaDKwTU9Pp7u7u0Mhak6bXlpaCoMgkBS639mZNlXDmgnUOI9RhoaGmD3AE12Pw729Pe2G7u/v7xMGZG1tjWcNAAP8AN9J3OKZg+zn5fi4XlKMADxy8p/XmzhwZmYmVolYtlloErbf/uTkJIMjFiSw9n2fUMXSfP0KPMOcaxU9ehbW3+mk4s5OmEwmXVKxUHD57R0dJO2YmJgg9NdIaMBcjFbkHuj+w+8q8LC3lwSg9ts25z7hhpAH9hCAYohIOwCu2hDh1Fqw9jzPHUT7HIEPq6vOvpv/SpSopa3pF7SwsMB2S44rpEnAacHB8pgpZ5T98MXTHt2CyDj4zFcPP6V/fLwRgsjY2BjHt7a0uAoZAgACGQdo2hGMjo663nOS+qAKyWIRGDFxFYB1Y3OTTCv49nMVFIBxA0wGwhkcwKZFwcjICGznlhgB8+zSINHW1hYebi+lzYjW19exqQ87hhFug51F5x6X9h7BWsr5pQWeuZ1RY2MjNTQ08MlsYmTIQHVAekN5BfIUta9a3SsJjPQahFANYwOpAPcAIncABPAShAjuAAeYjz5t8tcXMWOOYcZaYJ0IkCDPtACbCriujjEfC0hApqamQJZz94/q2KY+el9nLiXgHFB2d3ddRewdCGDHk8QQYNisXpYg/KeJnPQ0P+x8N2wrJM437WAyMNiW4CcXy2iRbmKm/sTx9rYFZbHKGjn7zyfqr7tL7w+2qK+vD/EBXPY+8ImzuRxMrlpC4EHNFbp3xK/oVBx5BdigojCJlZXIkuDYEmCARG+olb4b5RodnAmOTU5lBqcVroAsMKMaSvQeTEB8z2kDqvaLy80VL6GN8koACdUQnyhmjl5Tij7TJWU6W62GQKVd0HceABcBiWpOj/iK5ZEN7XyiFbcPLsdCuuj4Sr0i/iNa1d5VBSkUvumqBaRJzBP/2UR41ftWHahIQHVPrsR+7v1+A96PZBQhjpV0AAAAAElFTkSuQmCC"
FRAME_4_B64 = "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAADyklEQVRYCe1Vz0tUURQ+T6ZCkyh/gP2k1JkYkCemLQoGsShc9QdItQrdSLsWIoS2aB3kxm3BiC5nEeQiMaEWOplvM+BMFkIRNE4txiQwX/e7vnO5983zzRNx14E7595zzz3f98459w7RfzncDLjVwtdUczjAvluMncXxUBLWAQDCjjK49Gna/godiBVoDIscYc8AZ/+9SBxmCRhbaq0cRkn8BLB5oOEBGeC8iMfjPFVaL4Fkpjslk0nlmMlkdF+aTqeNL2HHm/cf8TRQi1IgDs7KeBzUAJ+cnHSGhobsgYEBR49SX19P3d3dytTX16fmM1NTdjVwz9kSJBSBGEfgLwc429LptE6is1wur2SzWd42dHNLC87ZhjF4YWTO6IHBwUEJjq+PdfQ7pVJJhRBkXBASJAgDwmTm5+fJvn0vCrg8pzUkGQSwC3Do7VNNUDQxMSHX/nLITfHDJHgN/Xz0gYOh25zZl861S3WEoYtBgL+MUned4+cvU7FYNIIgI/nVVTmUr4g2NjZGAAAoAywvLxsZ8frFyufzpL8JBgEEh8R+FqXufysV9fb27k7EbzyRUHMux9zcHKEMLH5wtgPcE25+Uk3IO9Cl3Hc6feUIrT97qMwgNzw8LDOik4ADwHXQrq6u3cy9yqosgGSQBBI48fej/edDiwMikJGREWprbZWpx1oQ6BRqRYxOASy7OpVKOchILpdToPBl0TPENmhOhYtr2NDQ4ADo9eysHWu+4Wz/eCODtbe340YYgUVTWgAHMN4GfhMSiYTye//5t8Qq79TSrTaLRAmAB8KMa94CgHxaWyMAMjgiFAoFGw2IcbWnhxtzRaUaTprAR/PTdkxwbHAJ0J3IgmIm9mRqhbYEIaS7QvAyQoKuot/Za0A9vnRhAlhIEvrBxsZGBpc1R3n8grqDCEjoz7Tfb6+1cQ2FExjywBlkQYEvLi2p+mKThd8EkMAfWHlz0346vWij9hgXdwpwrfh6GP0EYFOysbGB+stSoDfQpLyJa8nAsGG+sLAQSJDPBOlAVj5HV5RCNibb0ax6k+Fa8nUUf9uUoTPS1a6pC/16OOk9wPH92hKZcMXXy69DFjgTKIkgYo2Pj/vPRF5HyQAHk28FL1j7nlf3BbXJrZO0RXfoG+ahGFEywFgVt8TbCAT4RbV8LlSHNqHvJL8LMAOUB7u5TyhJX+goryPpQPYBJ93rtReU+d3WuprzBOC6PKYcllXjV3XQghokYD+3dUzbJurwejoqOA7vhwD8ZRn0bOgkZqjy/x6HwmS/BDiW3g9sg953vH/X+ZCZDHn+hAAAAABJRU5ErkJggg=="
FRAME_5_B64 = "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAADwElEQVRYCd1Wz0tUURQ+I2OQDRHjBNEPKHWUqXCjLVoMYoG5sXYl9mMVupF2LaRI6R9IyI2bFgUuWs4iyCAxFy10MFpkOqNFUATNDC3GJLJe850353Le9fnmKbTpwJ177rnn3u8755575xH9Z+JU4kELLZHQnrUdnUL0CHslNj+jD7V3Xe19d+5RJSLZCMxIKJYhKJjo/XyDMvJPMmCTUBmxp8Kd05ZVXkNg9Nq1mgmYTOaNUnUMPC+9mdal+LRNdAFNJpNsyuVy6A2uUSpGBhdHeKVSKXRGrvb3G12U8zdui+rbnz3RwPaVlRVqbW1lXZMQAh7wyclJGhoaooGBAc+msViMOjo6jK27u5uK9UfN2FbeTj9hE/wgMzMzvK8vAYkc4BAQgAiJqakp1kFCBGTae67zEGDj4+P06FlWpo19dnbW2E62tdEVNzAO3nMLBgcH2RHg0VO9VCqVzEIoIFEul7lhnM1mCcAP79zEkEXrMGhwjO+OjqIz4iEAq0T+K55gp4mJCe4lEzxQPyABAdDS0hKTVNPU1dVlGgKwJaoNiA7ipK/RvmNtlCsUKJFwicCOjOQqxQRJVgpKjmNsbIzPF3YbRAJCEUL0+WPsyYBsXl8qYI56X3HHEbiaCyy6HAeKy061+Lz+8IMEXGy69xCQidL7rxSJ1tOnB7fExJEPDw/zGNFrAfji4iI32O06AEE0P/EcgTjs//2GfmYPEYhARkZGqLmpyaT/Ul8fvVteNoDwSafTXJyoA1tQJ3K89px5B3AN4/E4Az2fnqbowXO0+e0l+7e0tGy5EZjAQwVgXEe56/LYvFh1KFa3weuREakNuwY8GZBrB8B83gXHDvl8njfCz4WeHppfWDDvg5lQypnOTqLVeSr/2ausWwsQk0IgUmHmNDY2+kYKQn4it0Cuop8PbIjejlx8dRFGisUi6QYnNxtuBlAHtsjZBpHYDhx7aQIYoyakYczpBwmAI/V+okmgLsrr635uvjabgMcJ2RBZXVvjIpUx3gwBhg363NycTIfu5RYELeDa0HWAYuVCq67SEWcyGcrQYZ5pr2ug43/4+LbFkSIMIoDacHBFIehFlyNB2gG8G9mWmc9mjvxl67lqgcGEvZzH1MzTB2iDLtIXsbPN7ydMBmQdX1UZqN43iO/kfQOUv0cNLEKPpzsAmN3EzblPKfpIe2QcqvdlH2ql68SfclABruUe8X9Czf1rOuhNlc7Al8n90hX76erDGhYc63ZDwLGBhcBT4k/uHe27GwIAMKkX8Gq/4/3+ArFWdai23HxgAAAAAElFTkSuQmCC"
FRAME_6_B64 = "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAADwUlEQVRYCd1WT0iUQRR/K2tQLRHrBlEEoa5iRSBrx0UsMAmsW4lFhwi9SHjpIEVK1w4JefHSwcBDxz0EGSXmoYMuRodMd7UQjKB16bAmUfm1v/ftm2bG2fVT6NKD75t5f+b9fvPmzbdL9B+JV9wLnh1JaEfR5YO9XPgoe2O/ViUqUO5AQZKxwqgISIxGBKayOGUdkijAuAXcXlMi48SqsoP/hV46Hmd/OFntgETQ3dspFW7Y8jhZWjGBVb0P4vE4r8tkMsZ6xaRoZXAJRFRTU5MRfLWry9DPXb9t6LZy40KC5ufn2by4uEgNDQ08L5FgbKmAAT46Okq9vb3U3Nxs5FxZXaVEImHYRHk59oCnOqn+/n62tbW18Sh5ZQ1GqYAnO0cQBAQg3d3dPI6Pj/M8EomwjpdNZnh4mB4/Sys/Ju8mntDU1JSynWhspCt+TsY2bkFPTw8HAjx8soPy+bxaiAlIFAoFfqCn0z6YDvDozk24lOg+GO8ODiofJgYBGGTnP6MxqDQyMsKjVIIV7aWTwHmDpC6tra0kj+1DnPQAr8HuIF7yGu0/1kiZXI5iMZ8I7KhIpthMkHixoeQ4hoaGaHJyku02iGwITQjRGxC6UQFJXp3PwUcdr3ngHfgzH1jmchwAt0stMW8+ficBF5s+GgTEkf/whULhalp5eEtMvPO+vj7WsXtdAD43N8cP7HYfgKBUSF+HuXEE4jzw+y39SB8mEIEMDAxQXW2tKv+lzk56v7CgABGTTCa5OeXewyaCPpHjFZuMxjWMRqMM9HxigsKHztKvr684rr6+fsuNgAMfKgDjOspdl4/NiyWPIlUbvB4Vkd6we8CogFw7AGazPjgyZLNZToTX+fZ2mpmdVd8H5dAmZ1paiJZmqLC5V7NubUA4hUCoyMyrqalx7hSEXCK3QK6iKwY27N7eucTqTRhaW1sj/UGQXw2/AugDW+RsK5EoB45cOgHo6Al5oHP5QQLgKL1LdBLoi8L6uivMabMJGEGohsjS8jKhSUXwzRBg2DCfnp4Wd+BRbkGlBdwbeh+gWbnRSqv0HadSKUrREfacrtpHxzf5+MriSBNWIoDe8GT3GGUuR4KyA3g3UpaZI5n6ydZ9pQaDCbm8Mapj90HaoIv0Wexsc72CVEDW8VUVRRudm/hG5jdAizemFZvQiPQVgNmPhHn3qYk+0R7RA41O9oFW/g3iv3MA1+Ue8X/BbfNvG6AnteYMfJn8f7vwnSp9WIOCY81uCXg6MBJBnpL6yx04b+BAH8J4cwUMyy429AfbJnKUYelzTQAAAABJRU5ErkJggg=="

ALL_FRAMES_B64 = [FRAME_1_B64, FRAME_2_B64, FRAME_3_B64, FRAME_4_B64, FRAME_5_B64, FRAME_6_B64]

def load_animation_frames():
    frames = []
    try:
        import base64
        import tempfile
        from pathlib import Path
        
        for b64_data in ALL_FRAMES_B64:
            tmp_path = Path(tempfile.gettempdir()) / f"dvtools_frame_{len(frames)}.png"
            tmp_path.write_bytes(base64.b64decode(b64_data))
            frames.append(tk.PhotoImage(file=str(tmp_path)))
    except Exception:
        pass
    return frames


# ----------------------------------------------------------------------
# Languages (English as default, Spanish, French)
# ----------------------------------------------------------------------

TEXTS = {
    "en": {
        "theme_label": "Theme:",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "theme_auto": "Auto (Hour)",
        "title": "DVtools — MiniDV to high-resolution scanner",
        "tab_file": "File",
        "tab_correction": "Correction",
        "tab_format": "Format and Codec",
        "tab_advanced": "Advanced",
        "tab_batch": "Batch Processing",
        "tab_plugins": "Plugins",
        "file_label": ".dv file (exact path):",
        "browse": "Browse...",
        "detected_data": "Detected data:",
        "no_data": "—",
        "open_vlc": "Open with VLC",
        "built_in_preview": "Built-in Preview",
        "process": "Process to High Resolution",
        "target_height": "Target height (px):",
        "auto_width": "(width is calculated automatically, keeping the real aspect ratio)",
        "force_aspect": "Force aspect ratio:",
        "aspect_auto": "Automatic (detected)",
        "aspect_4_3": "4:3 (standard)",
        "aspect_16_9": "16:9 (widescreen)",
        "pixel_correction": "Non-square DV pixel correction (PAL 720x576 / NTSC 720x480)",
        "crop_edges": "Crop edges with head-switching noise",
        "px_per_side": "pixels per side:",
        "noise_reduction": "Analog noise reduction (light temporal degrain-like filter)",
        "color_restoration": "Automatic color restoration (white balance)",
        "deinterlace": "Deinterlace (recommended for YouTube)",
        "sharpening": "Light sharpening",
        "output_format": "Output format (container):",
        "video_codec": "Video codec:",
        "hw_accel": "Hardware acceleration:",
        "accel_cpu": "Automatic (CPU / software)",
        "accel_nvenc": "NVIDIA (NVENC)",
        "accel_amf": "AMD (AMF)",
        "accel_qsv": "Intel (QuickSync)",
        "metadata_check": "Copy original recording date/time to the output file",
        "scenes_check": "Detect scene changes and split into separate files",
        "scenes_note": ("Note: based on visual changes between frames; it does not read "
                        "the DV's internal timecode, so it may not exactly match the "
                        "actual recording pauses."),
        "save_as": "Save processed video as...",
        "ready": "Ready.",
        "processing": "Processing to {width}x{height}...",
        "processing_pct": "Processing... {pct:.0f}%",
        "done_title": "Done",
        "done_msg": "Video saved to:\n{path}",
        "error_path": "Select a valid .dv file.",
        "error_read": "Error reading the video",
        "error_height": "Target height must be a number.",
        "missing_software_title": "Missing software",
        "folder_label": "Folder with .dv files:",
        "choose_folder": "Choose folder...",
        "add_queue": "Add to queue",
        "process_queue": "Process queue",
        "clear_queue": "Clear queue",
        "queue_empty": "The queue is empty. Add files first.",
        "queue_processing": "Processing {current} of {total}: {name}",
        "queue_done": "Batch finished: {total} file(s) processed.",
        "lang_label": "Language:",
        "preview_title": "Preview — {name}",
        "preview_close": "Close",
        "col_file": "File",
        "col_status": "Status",
        "status_pending": "Pending",
        "status_done": "Done",
        "status_error": "Error",
        "plugins_detected": "Plugins detected in the /plugins folder:",
        "col_plugin_enabled": "Enabled",
        "col_plugin_name": "Plugin Name",
        "col_plugin_type": "Type",
        "col_plugin_author": "Author / Version",
        "no_plugins": "No plugins detected",
        "plugin_frame_title": "Selected Plugin Options",
        "tab_audio": "Audio",
        "tab_metadata": "Metadata",
        "stabilize_check": "Stabilize image (reduce hand-held shake)",
        "stabilize_strength_label": "Stabilization strength (search range px):",
        "autocrop_black_check": "Auto-detect and crop black borders",
        "autocrop_black_note": ("Analyzes a few frames of the video before processing to find "
                                 "black bars/edges and crops them automatically. If nothing "
                                 "significant is found, no crop is applied."),
        "audio_declick_check": "Remove clicks and pops (magnetic head noise)",
        "audio_denoise_check": "Reduce background audio noise (hiss/hum)",
        "audio_denoise_strength_label": "Noise reduction strength (1-97):",
        "audio_loudnorm_check": "Normalize loudness (even volume across scenes)",
        "audio_loudnorm_note": ("Uses the EBU R128 standard (-16 LUFS) so all your clips end up "
                                 "at a similar, comfortable volume."),
        "metadata_intro": ("Review and edit the metadata that will be written to the output "
                            "file. Leave a field empty to keep the original value (or none)."),
        "metadata_date_label": "Recording date/time:",
        "metadata_title_label": "Title:",
        "metadata_author_label": "Author / Camera:",
        "metadata_comment_label": "Comment / Notes:",
        "autocrop_analyzing": "Analyzing frames to detect black borders...",
        "vs_engine_check": "Use VapourSynth engine (experimental)",
        "vs_engine_note": ("Routes video processing through VapourSynth instead of ffmpeg's "
                            "built-in filters for higher-quality deinterlacing, denoising and "
                            "stabilization. Requires VapourSynth + vspipe installed separately."),
        "vs_engine_unavailable": ("Not available: VapourSynth (and/or vspipe) was not found on "
                                   "this system. Install it from vapoursynth.com to enable this "
                                   "option."),
        "vs_engine_error": "VapourSynth engine error",
        "audio_denoise_floor_label": "Noise floor (dB, -80 to -20):",
        "audio_highpass_check": "Remove low-frequency hum (highpass filter)",
        "audio_highpass_hz_label": "Cutoff frequency (Hz):",
        "chromatic_aberration_check": "Correct chromatic aberration (color fringing)",
        "chromatic_aberration_shift_label": "Correction strength (px):",
        "chromatic_aberration_note": ("Best-effort, sub-pixel correction that shifts the red and "
                                       "blue channels in opposite directions. Requires the "
                                       "VapourSynth engine plus the \"fmtc\" (vs-fmtconv) plugin; "
                                       "if fmtc isn't installed, this step is silently skipped."),
        "tab_tape": "Tape",
        "dropout_section_title": "Dropout Detector",
        "dropout_note": ("Scans the whole file for possible tape dropouts (frozen/green "
                          "blocks typical of a dirty or damaged MiniDV head/tape), using "
                          "ffmpeg's temporal-outlier detector. This is a HEURISTIC, advisory "
                          "scan, not a perfect detector: fast motion or heavy camera noise "
                          "can also trigger it. Use it as a guide of where to look, not as "
                          "absolute truth."),
        "dropout_scan_btn": "Scan for dropouts",
        "dropout_scanning": "Scanning the whole file for dropouts... this can take a while.",
        "dropout_none_found": "No likely dropouts found.",
        "dropout_error": "Could not complete the scan: {error}",
        "dropout_event": "Possible dropout: {start} – {end}  (severity ~{severity}%)",
        "timecode_section_title": "Timecode Repair",
        "timecode_repair_check": "Regenerate a clean, sequential timecode on export",
        "timecode_start_label": "Start timecode (HH:MM:SS:FF):",
        "timecode_repair_note": ("Only applies to MOV/MP4 output: writes a fresh, sequential "
                                  "timecode track into the exported file's container so editing "
                                  "software reads it correctly. Note: this rewrites the "
                                  "CONTAINER-level timecode, not the raw DV subcode embedded in "
                                  "the original tape data."),
        "queue_drag_note": "Drag a row to reorder the queue's processing priority.",
        "schedule_section_title": "Scheduled / overnight processing",
        "idle_wait_check": "Wait until the computer is idle before starting",
        "idle_wait_unavailable": ("Not available: this OS/machine doesn't expose an idle-time "
                                   "API DVtools recognizes."),
        "idle_minutes_label": "Idle minutes required:",
        "scheduled_start_check": "Start at a specific time",
        "scheduled_time_label": "Start time (HH:MM):",
        "schedule_note": ("If both are enabled, DVtools waits for the scheduled time first, "
                           "then also waits for the idle condition before processing the queue. "
                           "The app must stay open for this to work."),
        "queue_waiting_schedule": "Waiting for the scheduled time ({time})...",
        "queue_waiting_idle": "Waiting for the computer to be idle for {minutes} min..."
    },
    "es": {
        "theme_label": "Tema:",
        "theme_light": "Claro",
        "theme_dark": "Oscuro",
        "theme_auto": "Automático (Hora)",
        "title": "DVtools — Escáner MiniDV a alta resolución",
        "tab_file": "Archivo",
        "tab_correction": "Corrección",
        "tab_format": "Formato y codec",
        "tab_advanced": "Avanzado",
        "tab_batch": "Procesar por lotes",
        "tab_plugins": "Plugins",
        "file_label": "Archivo .dv (ruta exacta):",
        "browse": "Examinar...",
        "detected_data": "Datos detectados:",
        "no_data": "—",
        "open_vlc": "Abrir con VLC",
        "built_in_preview": "Vista previa propia",
        "process": "Procesar a alta resolución",
        "target_height": "Alto destino (px):",
        "auto_width": "(el ancho se calcula solo, respetando el aspecto real)",
        "force_aspect": "Forzar relación de aspecto:",
        "aspect_auto": "Automático (detectado)",
        "aspect_4_3": "4:3 (estándar)",
        "aspect_16_9": "16:9 (panorámico)",
        "pixel_correction": "Corrección de píxel no cuadrado del DV (PAL 720x576 / NTSC 720x480)",
        "crop_edges": "Recortar bordes con ruido de cabezal (head-switching noise)",
        "px_per_side": "píxeles por lado:",
        "noise_reduction": "Reducción de ruido analógico (filtro temporal, tipo degrain leve)",
        "color_restoration": "Restauración de color automática (balance de blancos)",
        "deinterlace": "Desentrelazar (recomendado para YouTube)",
        "sharpening": "Realce de nitidez leve",
        "output_format": "Formato de salida (contenedor):",
        "video_codec": "Códec de video:",
        "hw_accel": "Aceleración por hardware:",
        "accel_cpu": "Automático (CPU / software)",
        "accel_nvenc": "NVIDIA (NVENC)",
        "accel_amf": "AMD (AMF)",
        "accel_qsv": "Intel (QuickSync)",
        "metadata_check": "Copiar fecha/hora original de grabación al archivo de salida",
        "scenes_check": "Detectar cambios de escena y dividir en archivos separados",
        "scenes_note": ("Nota: se basa en cambios visuales entre fotogramas; no lee el "
                        "código de tiempo interno del DV, por lo que puede no coincidir "
                        "exactamente con las pausas de grabación reales."),
        "save_as": "Guardar video procesado como...",
        "ready": "Listo.",
        "processing": "Procesando a {width}x{height}...",
        "processing_pct": "Procesando... {pct:.0f}%",
        "done_title": "Terminado",
        "done_msg": "Video guardado en:\n{path}",
        "error_path": "Selecciona un archivo .dv válido.",
        "error_read": "Error al leer el video",
        "error_height": "El alto destino debe ser un número.",
        "missing_software_title": "Falta software",
        "folder_label": "Carpeta con archivos .dv:",
        "choose_folder": "Elegir carpeta...",
        "add_queue": "Agregar a la cola",
        "process_queue": "Procesar cola",
        "clear_queue": "Limpiar cola",
        "queue_empty": "La cola está vacía. Agrega archivos primero.",
        "queue_processing": "Procesando {current} de {total}: {name}",
        "queue_done": "Lote terminado: {total} archivo(s) procesados.",
        "lang_label": "Idioma:",
        "preview_title": "Vista previa — {name}",
        "preview_close": "Cerrar",
        "col_file": "Archivo",
        "col_status": "Estado",
        "status_pending": "Pendiente",
        "status_done": "Hecho",
        "status_error": "Error",
        "plugins_detected": "Plugins detectados en la carpeta /plugins:",
        "col_plugin_enabled": "Activo",
        "col_plugin_name": "Nombre del Plugin",
        "col_plugin_type": "Tipo",
        "col_plugin_author": "Autor / Version",
        "no_plugins": "No se detectaron plugins",
        "plugin_frame_title": "Opciones del Plugin Seleccionado",
        "tab_audio": "Audio",
        "tab_metadata": "Metadatos",
        "stabilize_check": "Estabilizar imagen (reducir temblor de cámara en mano)",
        "stabilize_strength_label": "Intensidad de estabilización (rango de búsqueda, px):",
        "autocrop_black_check": "Detectar y recortar bordes negros automáticamente",
        "autocrop_black_note": ("Analiza varios fotogramas del video antes de procesar para "
                                 "encontrar franjas/bordes negros y recortarlos solo. Si no "
                                 "encuentra nada significativo, no aplica ningún recorte."),
        "audio_declick_check": "Quitar chasquidos y clics (ruido del cabezal magnético)",
        "audio_denoise_check": "Reducir ruido de fondo del audio (siseo/zumbido)",
        "audio_denoise_strength_label": "Intensidad de reducción de ruido (1-97):",
        "audio_loudnorm_check": "Normalizar volumen (parejo entre escenas)",
        "audio_loudnorm_note": ("Usa el estándar EBU R128 (-16 LUFS) para que todos tus clips "
                                 "terminen con un volumen parecido y cómodo de escuchar."),
        "metadata_intro": ("Revisa y edita los metadatos que se escribirán en el archivo de "
                            "salida. Deja un campo vacío para mantener el valor original (o "
                            "ninguno)."),
        "metadata_date_label": "Fecha/hora de grabación:",
        "metadata_title_label": "Título:",
        "metadata_author_label": "Autor / Cámara:",
        "metadata_comment_label": "Comentario / Notas:",
        "autocrop_analyzing": "Analizando fotogramas para detectar bordes negros...",
        "vs_engine_check": "Usar motor VapourSynth (experimental)",
        "vs_engine_note": ("Procesa el video con VapourSynth en lugar de los filtros nativos "
                            "de ffmpeg, para desentrelazado, reducción de ruido y "
                            "estabilización de mayor calidad. Requiere tener VapourSynth y "
                            "vspipe instalados por separado."),
        "vs_engine_unavailable": ("No disponible: no se encontró VapourSynth (o vspipe) en "
                                   "este equipo. Instalalo desde vapoursynth.com para activar "
                                   "esta opción."),
        "vs_engine_error": "Error del motor VapourSynth",
        "audio_denoise_floor_label": "Piso de ruido (dB, -80 a -20):",
        "audio_highpass_check": "Quitar zumbido de graves (filtro highpass)",
        "audio_highpass_hz_label": "Frecuencia de corte (Hz):",
        "chromatic_aberration_check": "Corregir aberración cromática (bordes de color)",
        "chromatic_aberration_shift_label": "Intensidad de corrección (px):",
        "chromatic_aberration_note": ("Corrección subpíxel best-effort que desplaza los canales "
                                       "rojo y azul en direcciones opuestas. Requiere el motor "
                                       "VapourSynth más el plugin \"fmtc\" (vs-fmtconv); si fmtc "
                                       "no está instalado, este paso se omite en silencio."),
        "tab_tape": "Cinta",
        "dropout_section_title": "Detector de dropouts",
        "dropout_note": ("Escanea el archivo completo buscando posibles dropouts de cinta "
                          "(bloques congelados/verdes típicos de un cabezal o cinta MiniDV "
                          "sucia o dañada), usando el detector de outliers temporales de "
                          "ffmpeg. Es un análisis HEURÍSTICO y orientativo, no un detector "
                          "perfecto: movimiento rápido o mucho ruido de la propia cámara "
                          "también pueden activarlo. Úsalo como guía de dónde mirar, no como "
                          "verdad absoluta."),
        "dropout_scan_btn": "Escanear dropouts",
        "dropout_scanning": "Escaneando el archivo completo en busca de dropouts... puede tardar.",
        "dropout_none_found": "No se encontraron dropouts probables.",
        "dropout_error": "No se pudo completar el escaneo: {error}",
        "dropout_event": "Posible dropout: {start} – {end}  (severidad ~{severity}%)",
        "timecode_section_title": "Reparación de timecode",
        "timecode_repair_check": "Regenerar timecode limpio y secuencial al exportar",
        "timecode_start_label": "Timecode inicial (HH:MM:SS:FF):",
        "timecode_repair_note": ("Solo aplica a salida MOV/MP4: escribe una pista de timecode "
                                  "nueva y secuencial en el contenedor del archivo exportado, "
                                  "para que los programas de edición lo lean correctamente. "
                                  "Nota: esto reescribe el timecode a nivel de CONTENEDOR, no "
                                  "el subcode DV crudo embebido en los datos originales de la "
                                  "cinta."),
        "queue_drag_note": "Arrastra una fila para reordenar la prioridad de procesamiento de la cola.",
        "schedule_section_title": "Procesamiento programado / nocturno",
        "idle_wait_check": "Esperar a que el PC esté inactivo antes de empezar",
        "idle_wait_unavailable": ("No disponible: este sistema operativo/equipo no expone una "
                                   "API de tiempo de inactividad que DVtools reconozca."),
        "idle_minutes_label": "Minutos de inactividad requeridos:",
        "scheduled_start_check": "Empezar a una hora específica",
        "scheduled_time_label": "Hora de inicio (HH:MM):",
        "schedule_note": ("Si activas ambas opciones, DVtools primero espera la hora "
                           "programada y luego también espera la inactividad antes de procesar "
                           "la cola. La aplicación debe permanecer abierta para que esto "
                           "funcione."),
        "queue_waiting_schedule": "Esperando la hora programada ({time})...",
        "queue_waiting_idle": "Esperando {minutes} min de inactividad del sistema..."
    },
    "fr": {
        "theme_label": "Thème:",
        "theme_light": "Clair",
        "theme_dark": "Sombre",
        "theme_auto": "Automatique (Heure)",
        "title": "DVtools — Scanner MiniDV haute résolution",
        "tab_file": "Fichier",
        "tab_correction": "Correction",
        "tab_format": "Format et codec",
        "tab_advanced": "Avancé",
        "tab_batch": "Traitement par lots",
        "tab_plugins": "Plugins",
        "file_label": "Fichier .dv (chemin exact):",
        "browse": "Parcourir...",
        "detected_data": "Données détectées :",
        "no_data": "—",
        "open_vlc": "Ouvrir avec VLC",
        "built_in_preview": "Aperçu intégré",
        "process": "Traiter en haute résolution",
        "target_height": "Hauteur cible (px):",
        "auto_width": "(la largeur est calculée automatiquement pour conserver le format)",
        "force_aspect": "Forcer le rapport d'aspect :",
        "aspect_auto": "Automatique (détecté)",
        "aspect_4_3": "4:3 (standard)",
        "aspect_16_9": "16:9 (grand écran)",
        "pixel_correction": "Correction des pixels non carrés DV (PAL 720x576 / NTSC 720x480)",
        "crop_edges": "Recadrer les bords (bruit de commutation des têtes)",
        "px_per_side": "pixels par côté :",
        "noise_reduction": "Réduction du bruit analogique (léger filtre temporel)",
        "color_restoration": "Restauration automatique des couleurs (balance des blancs)",
        "deinterlace": "Désentrelacer (recommandé pour YouTube)",
        "sharpening": "Léger renforcement de la netteté",
        "output_format": "Format de sortie (conteneur) :",
        "video_codec": "Codec vidéo :",
        "hw_accel": "Accélération matérielle :",
        "accel_cpu": "Automatique (CPU / logiciel)",
        "accel_nvenc": "NVIDIA (NVENC)",
        "accel_amf": "AMD (AMF)",
        "accel_qsv": "Intel (QuickSync)",
        "metadata_check": "Copier la date/heure d'enregistrement d'origine",
        "scenes_check": "Détecter les changements de scène et diviser les fichiers",
        "scenes_note": ("Remarque : basé sur les changements visuels entre les images ; "
                        "il ne lit pas le code temporel interne du DV."),
        "save_as": "Enregistrer la vidéo sous...",
        "ready": "Prêt.",
        "processing": "Traitement vers {width}x{height}...",
        "processing_pct": "Traitement... {pct:.0f}%",
        "done_title": "Terminé",
        "done_msg": "Vidéo enregistrée dans :\n{path}",
        "error_path": "Sélectionnez un fichier .dv valide.",
        "error_read": "Erreur lors de la lecture de la vidéo",
        "error_height": "La hauteur cible doit être un nombre.",
        "missing_software_title": "Logiciel manquant",
        "folder_label": "Dossier contenant des fichiers .dv :",
        "choose_folder": "Choisir le dossier...",
        "add_queue": "Ajouter à la file",
        "process_queue": "Traiter la file",
        "clear_queue": "Vider la file",
        "queue_empty": "La file d'attente est vide. Ajoutez d'abord des fichiers.",
        "queue_processing": "Traitement de {current} sur {total} : {name}",
        "queue_done": "Lot terminé : {total} fichier(s) traité(s).",
        "lang_label": "Langue :",
        "preview_title": "Aperçu — {name}",
        "preview_close": "Fermer",
        "col_file": "Fichier",
        "col_status": "Statut",
        "status_pending": "En attente",
        "status_done": "Terminé",
        "status_error": "Erreur",
        "plugins_detected": "Plugins détectés dans le dossier /plugins :",
        "col_plugin_enabled": "Actif",
        "col_plugin_name": "Nom du Plugin",
        "col_plugin_type": "Type",
        "col_plugin_author": "Auteur / Version",
        "no_plugins": "Aucun plugin détecté",
        "plugin_frame_title": "Opciones du Plugin Sélectionné",
        "tab_audio": "Audio",
        "tab_metadata": "Métadonnées",
        "stabilize_check": "Stabiliser l'image (réduire les tremblements de caméra)",
        "stabilize_strength_label": "Intensité de stabilisation (plage de recherche, px):",
        "autocrop_black_check": "Détecter et recadrer automatiquement les bords noirs",
        "autocrop_black_note": ("Analyse plusieurs images de la vidéo avant le traitement pour "
                                 "trouver des bandes/bords noirs et les recadrer automatiquement. "
                                 "Si rien de significatif n'est trouvé, aucun recadrage n'est "
                                 "appliqué."),
        "audio_declick_check": "Supprimer les clics et crépitements (bruit de tête magnétique)",
        "audio_denoise_check": "Réduire le bruit de fond audio (souffle/bourdonnement)",
        "audio_denoise_strength_label": "Intensité de réduction du bruit (1-97):",
        "audio_loudnorm_check": "Normaliser le volume (uniforme entre les scènes)",
        "audio_loudnorm_note": ("Utilise la norme EBU R128 (-16 LUFS) pour que tous vos clips "
                                 "aient un volume similaire et confortable."),
        "metadata_intro": ("Vérifiez et modifiez les métadonnées qui seront écrites dans le "
                            "fichier de sortie. Laissez un champ vide pour conserver la valeur "
                            "d'origine (ou aucune)."),
        "metadata_date_label": "Date/heure d'enregistrement:",
        "metadata_title_label": "Titre:",
        "metadata_author_label": "Auteur / Caméra:",
        "metadata_comment_label": "Commentaire / Notes:",
        "autocrop_analyzing": "Analyse des images pour détecter les bords noirs...",
        "vs_engine_check": "Utiliser le moteur VapourSynth (expérimental)",
        "vs_engine_note": ("Traite la vidéo avec VapourSynth au lieu des filtres intégrés "
                            "de ffmpeg, pour un désentrelacement, un débruitage et une "
                            "stabilisation de meilleure qualité. Nécessite VapourSynth et "
                            "vspipe installés séparément."),
        "vs_engine_unavailable": ("Non disponible : VapourSynth (ou vspipe) est introuvable sur "
                                   "cet ordinateur. Installez-le depuis vapoursynth.com pour "
                                   "activer cette option."),
        "vs_engine_error": "Erreur du moteur VapourSynth",
        "audio_denoise_floor_label": "Seuil de bruit (dB, -80 à -20):",
        "audio_highpass_check": "Supprimer le bourdonnement grave (filtre passe-haut)",
        "audio_highpass_hz_label": "Fréquence de coupure (Hz):",
        "chromatic_aberration_check": "Corriger l'aberration chromatique (franges colorées)",
        "chromatic_aberration_shift_label": "Intensité de correction (px):",
        "chromatic_aberration_note": ("Correction subpixel best-effort qui décale les canaux "
                                       "rouge et bleu dans des directions opposées. Nécessite "
                                       "le moteur VapourSynth et le plugin \"fmtc\" "
                                       "(vs-fmtconv) ; si fmtc n'est pas installé, cette étape "
                                       "est ignorée silencieusement."),
        "tab_tape": "Bande",
        "dropout_section_title": "Détecteur de dropouts",
        "dropout_note": ("Analyse tout le fichier à la recherche de dropouts de bande "
                          "possibles (blocs figés/verts typiques d'une tête ou bande MiniDV "
                          "sale ou endommagée), avec le détecteur d'anomalies temporelles de "
                          "ffmpeg. C'est une analyse HEURISTIQUE et indicative, pas une "
                          "détection parfaite : un mouvement rapide ou beaucoup de bruit de "
                          "la caméra peuvent aussi la déclencher. Utilisez-la comme guide, pas "
                          "comme vérité absolue."),
        "dropout_scan_btn": "Analyser les dropouts",
        "dropout_scanning": "Analyse du fichier complet à la recherche de dropouts... patientez.",
        "dropout_none_found": "Aucun dropout probable trouvé.",
        "dropout_error": "Impossible de terminer l'analyse : {error}",
        "dropout_event": "Dropout possible : {start} – {end}  (sévérité ~{severity}%)",
        "timecode_section_title": "Réparation du timecode",
        "timecode_repair_check": "Régénérer un timecode propre et séquentiel à l'export",
        "timecode_start_label": "Timecode de départ (HH:MM:SS:FF):",
        "timecode_repair_note": ("S'applique uniquement aux sorties MOV/MP4 : écrit une "
                                  "nouvelle piste de timecode séquentielle dans le conteneur "
                                  "du fichier exporté, pour que les logiciels de montage la "
                                  "lisent correctement. Remarque : ceci réécrit le timecode au "
                                  "niveau du CONTENEUR, pas le sous-code DV brut intégré aux "
                                  "données d'origine de la bande."),
        "queue_drag_note": "Faites glisser une ligne pour réordonner la priorité de traitement de la file.",
        "schedule_section_title": "Traitement programmé / nocturne",
        "idle_wait_check": "Attendre que l'ordinateur soit inactif avant de commencer",
        "idle_wait_unavailable": ("Non disponible : ce système/cette machine n'expose pas d'API "
                                   "de temps d'inactivité reconnue par DVtools."),
        "idle_minutes_label": "Minutes d'inactivité requises:",
        "scheduled_start_check": "Démarrer à une heure précise",
        "scheduled_time_label": "Heure de démarrage (HH:MM):",
        "schedule_note": ("Si les deux sont activées, DVtools attend d'abord l'heure "
                           "programmée puis attend aussi l'inactivité avant de traiter la "
                           "file. L'application doit rester ouverte pour que cela fonctionne."),
        "queue_waiting_schedule": "En attente de l'heure programmée ({time})...",
        "queue_waiting_idle": "En attente de {minutes} min d'inactivité du système..."
    }
}

CURRENT_LANGUAGE = {"code": "en"}


def t(key, **kwargs):
    text = TEXTS.get(CURRENT_LANGUAGE["code"], TEXTS["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text

# ----------------------------------------------------------------------
# Persistent configuration (config.txt)
# ----------------------------------------------------------------------
# Stores every user-adjustable setting (checkboxes, dropdowns, language,
# theme, and which plugins are enabled/disabled) so DVtools remembers how
# it was left the last time it was closed. Stored as JSON for robustness,
# in a file literally named "config.txt" as requested, under the same
# per-user folder already used for user plugins (~/.dvtools).
CONFIG_PATH = Path.home() / ".dvtools" / "config.txt"

# Attribute names (all Tk *Var instances ending in "_var") that are
# session-only state -- the currently loaded file, its per-file metadata,
# status text, etc. -- and therefore should NOT be written to config.txt,
# even though App._save_config() auto-discovers every other "*_var"
# attribute generically.
CONFIG_EXCLUDED_VARS = {
    "status_var", "path_var", "info_var", "folder_var",
    "title_var", "lang_label_var", "theme_label_var",
    "meta_title_var", "meta_author_var", "meta_date_var", "timecode_start_var",
}


def load_config_file():
    """Reads config.txt and returns its contents as a dict, or an empty
    dict if the file doesn't exist yet or can't be parsed (first run,
    corrupted file, etc. -- this must never crash startup)."""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[dvtools] Could not read config file ({CONFIG_PATH}): {e}")
    return {}


def save_config_file(data):
    """Writes 'data' to config.txt as JSON. Never raises: a failed save
    (e.g. read-only filesystem) should not interrupt closing the app."""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[dvtools] Could not save config file ({CONFIG_PATH}): {e}")


# ----------------------------------------------------------------------
# Plugin System
# ----------------------------------------------------------------------

# Whether each plugin is currently enabled, keyed by plugin id (the
# plugin's filename without extension). Populated from config.txt at
# startup (see load_plugins()) and updated live from the Plugins tab
# without needing to restart the app -- every hook-invocation site below
# checks this dict via is_plugin_enabled() before calling into a plugin.
_saved_config_for_plugins = load_config_file()
PLUGIN_ENABLED = dict(_saved_config_for_plugins.get("plugins", {}))


def is_plugin_enabled(module):
    """True unless the user explicitly disabled this plugin from the
    Plugins tab (or via a previously saved config.txt). Defaults to
    enabled for any plugin id not present in PLUGIN_ENABLED yet."""
    plugin_id = getattr(module, "_dvtools_plugin_id", None)
    return PLUGIN_ENABLED.get(plugin_id, True)


ACTIVE_PLUGINS = {
    "video_filter": [],
    "post_process": [],
    "ffmpeg_modifier": [],
    "event_listener": [],
    "vs_filter": [],
    "extension_provider": [],
    "info_list": []
}

# Folders where plugins are looked up. The second one is a per-user
# folder (~/.dvtools/plugins) that exists the same way on Windows, macOS
# and Linux thanks to pathlib, so the same plugin works unchanged across
# all three OS builds of the app as long as they share this same core
# module.
USER_PLUGINS_PATH = Path.home() / ".dvtools" / "plugins"


def load_plugins():
    plugins_path = BASE_PATH / "plugins"
    candidate_paths = []
    for folder in (plugins_path, USER_PLUGINS_PATH):
        if not folder.exists():
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except Exception:
                continue
        candidate_paths.extend(sorted(folder.glob("*.py")))

    for file_path in candidate_paths:
        if file_path.stem == "__init__":
            continue
        try:
            module_name = f"plugin_{file_path.stem}"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Stable id used to remember this plugin's enabled/disabled
            # state across restarts (see PLUGIN_ENABLED / config.txt) and
            # to identify its row when toggled from the Plugins tab.
            module._dvtools_plugin_id = file_path.stem
            PLUGIN_ENABLED.setdefault(file_path.stem, True)

            if hasattr(module, "register_plugin"):
                info = module.register_plugin()

                # FIXED BUG: previously a plugin was only registered under
                # "video_filter" or "post_process" if its register_plugin()
                # explicitly declared info["type"] == that exact name. The
                # example plugin (efecto_vhs_pro.py) never declares
                # "type", so even though it defines valid functions they
                # were never called. Plugins are now detected by
                # duck-typing (hasattr), the same way "ffmpeg_modifier" and
                # "event_listener" already were, so any combination of
                # hooks works without needing to declare an exact "type".
                if hasattr(module, "modify_filters"):
                    ACTIVE_PLUGINS["video_filter"].append(module)
                if hasattr(module, "execute_post"):
                    ACTIVE_PLUGINS["post_process"].append(module)
                if hasattr(module, "modify_command"):
                    ACTIVE_PLUGINS["ffmpeg_modifier"].append(module)
                if hasattr(module, "on_file_loaded") or hasattr(module, "on_event"):
                    ACTIVE_PLUGINS["event_listener"].append(module)
                # modify_vs_clip(clip, options, info, vs_core) -> clip lets a
                # plugin add a filter directly to the VapourSynth pipeline,
                # the equivalent of "modify_filters" but for the optional
                # VapourSynth engine (dvtools_vs.py).
                if hasattr(module, "modify_vs_clip"):
                    ACTIVE_PLUGINS["vs_filter"].append(module)
                if hasattr(module, "register_extensions"):
                    ACTIVE_PLUGINS["extension_provider"].append(module)

                info.setdefault("type", info.get("type", "General"))
                info["module"] = module
                info["id"] = file_path.stem
                ACTIVE_PLUGINS["info_list"].append(info)

        except Exception as e:
            print(f"Error loading plugin {file_path.name}: {e}")

def get_all_supported_extensions():
    """Collects every supported extension: the DV core's own plus
    whatever enabled plugins register."""
    extensions = [".dv", ".dif"]  # Core's base support
    for plugin in ACTIVE_PLUGINS.get("extension_provider", []):
        if not is_plugin_enabled(plugin):
            continue
        if hasattr(plugin, "register_extensions"):
            try:
                extensions.extend(plugin.register_extensions())
            except Exception:
                pass
    return sorted(set(extensions))

def dispatch_event(event_name, data):
    """Notifies plugins of an app lifecycle event.

    Two plugin styles are supported so both keep working without having
    to rewrite either one:
      - Specific hooks, e.g. on_file_loaded(info, path).
      - A generic on_event(event_name, data) router, as used by
        efecto_vhs_pro.py.
    """
    for plugin in ACTIVE_PLUGINS.get("event_listener", []):
        if not is_plugin_enabled(plugin):
            continue
        if event_name == "on_file_loaded" and hasattr(plugin, "on_file_loaded"):
            try:
                plugin.on_file_loaded(data.get("info"), data.get("path"))
            except Exception as e:
                print(f"Error executing on_file_loaded hook: {e}")
        if hasattr(plugin, "on_event"):
            try:
                plugin.on_event(event_name, data)
            except Exception as e:
                print(f"Error executing on_event({event_name}) hook: {e}")


def notify_post_process(output, original_path, options):
    for plugin in ACTIVE_PLUGINS.get("post_process", []):
        if not is_plugin_enabled(plugin):
            continue
        if hasattr(plugin, "execute_post"):
            try:
                plugin.execute_post(output, original_path, options)
            except Exception as e:
                print(f"Error in post-process context: {e}")
    dispatch_event("on_process_complete", {
        "output": output, "input": original_path, "options": options,
    })


load_plugins()

# ----------------------------------------------------------------------
# External Software Detection
# ----------------------------------------------------------------------

# Detects FFMPEG and FFPROBE first (near the top of the file).

def get_executable_path(name):
    """Looks for `name` next to the app first (BASE_PATH), then on PATH.

    `name` should be given WITHOUT a platform suffix (e.g. "ffmpeg", not
    "ffmpeg.exe"); the ".exe" suffix is added automatically on Windows.
    FIXED BUG: the previous version hardcoded the ".exe" suffix
    regardless of platform.system(), so on macOS/Linux a binary placed
    next to the app (e.g. by the auto-downloader below) was never found
    via BASE_PATH -- only shutil.which() ever had a chance to succeed,
    and only for binaries already on the user's PATH.
    """
    exe_name = name + ".exe" if platform.system() == "Windows" else name
    local_path = BASE_PATH / exe_name
    if local_path.exists():
        return str(local_path)
    return shutil.which(exe_name)

FFMPEG = get_executable_path("ffmpeg")
FFPROBE = get_executable_path("ffprobe")
VLC = get_executable_path("vlc")

if not VLC:
    # FIXED BUG: the original path had "x86" misspelled
    # (r"...\Files\x86\..." instead of "...\Files (x86)\..."),
    # so it never found 32-bit VLC on a 64-bit Windows machine.
    # The typical macOS and Linux paths are also added now, since
    # previously only Windows was searched.
    if platform.system() == "Windows":
        candidates = (
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        )
    elif platform.system() == "Darwin":
        candidates = (
            "/Applications/VLC.app/Contents/MacOS/VLC",
            str(Path.home() / "Applications" / "VLC.app" / "Contents" / "MacOS" / "VLC"),
        )
    else:
        candidates = (
            "/usr/bin/vlc",
            "/usr/local/bin/vlc",
            "/snap/bin/vlc",
            "/var/lib/flatpak/exports/bin/org.videolan.VLC",
            str(Path.home() / ".local/share/flatpak/exports/bin/org.videolan.VLC"),
        )
    for candidate in candidates:
        if os.path.exists(candidate):
            VLC = candidate
            break

_AVAILABLE_ENCODERS = None


def get_available_encoders():
    """Queries ffmpeg once to see which hardware encoders are available."""
    global _AVAILABLE_ENCODERS
    if _AVAILABLE_ENCODERS is not None:
        return _AVAILABLE_ENCODERS
    available = set()
    if FFMPEG:
        try:
            output = subprocess.run([FFMPEG, "-hide_banner", "-encoders"],
                                     capture_output=True, text=True, timeout=10)
            text = output.stdout
            for name in ("h264_nvenc", "hevc_nvenc", "av1_nvenc",
                            "h264_amf", "hevc_amf", "av1_amf",
                            "h264_qsv", "hevc_qsv", "av1_qsv"):
                if name in text:
                    available.add(name)
        except Exception:
            pass
    _AVAILABLE_ENCODERS = available
    return available


def check_dependencies():
    missing = []
    if not FFMPEG:
        missing.append("ffmpeg")
    if not FFPROBE:
        missing.append("ffprobe")
    if missing:
        return (
            "Missing components required: " + ", ".join(missing) +
            "\n\nWindows: https://www.gyan.dev/ffmpeg/builds/ (Add to PATH)"
            "\nmacOS: brew install ffmpeg"
            "\nLinux: sudo apt install ffmpeg"
        )
    return None


# ----------------------------------------------------------------------
# Automatic ffmpeg/ffprobe download
# ----------------------------------------------------------------------
# The installer intentionally does NOT bundle ffmpeg (it would add
# ~80-100 MB to every single download). Instead, if ffmpeg/ffprobe are
# not found (system-wide install OR a copy sitting next to the app --
# see get_executable_path()), the user is offered a one-click download
# of official static builds. The binaries are saved into BASE_PATH, so
# get_executable_path() picks them up on the next check without any
# extra configuration, and they survive app updates (they're not part
# of the packaged app itself).
#
# Sources (official static builds, no installer/wizard involved):
#   Windows: gyan.dev "essentials" build (zip)
#   macOS:   evermeet.cx per-binary zips (ffmpeg and ffprobe separately)
#   Linux:   johnvansickle.com static build (tar.xz)

FFMPEG_DOWNLOAD_URLS = {
    "Windows": {
        "ffmpeg_bundle": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    },
    "Darwin": {
        "ffmpeg": "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
        "ffprobe": "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip",
    },
    "Linux": {
        "ffmpeg_bundle": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
    },
}


def _download_with_progress(url, dest_path, progress_callback=None):
    """Downloads `url` to `dest_path`, calling progress_callback(pct) as
    it goes (pct is 0-100, or -1 if the server didn't report a size)."""
    def _hook(block_count, block_size, total_size):
        if progress_callback is None:
            return
        if total_size > 0:
            pct = min(100, int(block_count * block_size * 100 / total_size))
            progress_callback(pct)
        else:
            progress_callback(-1)
    urllib.request.urlretrieve(url, dest_path, reporthook=_hook)


def download_ffmpeg(progress_callback=None, status_callback=None):
    """Downloads and installs ffmpeg + ffprobe into BASE_PATH for the
    current platform. Meant to be called from a worker thread (it
    blocks on network I/O); use progress_callback/status_callback to
    update a GUI safely via `App.after(0, ...)`.

    Returns True on success. Raises on failure (network error, unknown
    platform, unexpected archive layout) so the caller can show the
    real error message to the user.
    """
    system = platform.system()
    urls = FFMPEG_DOWNLOAD_URLS.get(system)
    if not urls:
        raise RuntimeError(f"No automatic ffmpeg download is available for {system}.")

    BASE_PATH.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dvtools_ffmpeg_") as tmp:
        tmp = Path(tmp)

        if system == "Windows":
            if status_callback:
                status_callback("Downloading ffmpeg...")
            archive = tmp / "ffmpeg.zip"
            _download_with_progress(urls["ffmpeg_bundle"], archive, progress_callback)
            if status_callback:
                status_callback("Extracting...")
            with zipfile.ZipFile(archive) as zf:
                for member in zf.namelist():
                    base = os.path.basename(member)
                    if base in ("ffmpeg.exe", "ffprobe.exe"):
                        with zf.open(member) as src, open(BASE_PATH / base, "wb") as dst:
                            shutil.copyfileobj(src, dst)

        elif system == "Darwin":
            for name, url in urls.items():
                if status_callback:
                    status_callback(f"Downloading {name}...")
                archive = tmp / f"{name}.zip"
                _download_with_progress(url, archive, progress_callback)
                with zipfile.ZipFile(archive) as zf:
                    zf.extractall(tmp)
                extracted = tmp / name
                if extracted.exists():
                    dest = BASE_PATH / name
                    shutil.copyfile(extracted, dest)
                    dest.chmod(0o755)

        elif system == "Linux":
            if status_callback:
                status_callback("Downloading ffmpeg...")
            archive = tmp / "ffmpeg.tar.xz"
            _download_with_progress(urls["ffmpeg_bundle"], archive, progress_callback)
            if status_callback:
                status_callback("Extracting...")
            with tarfile.open(archive, "r:xz") as tf:
                for member in tf.getmembers():
                    base = os.path.basename(member.name)
                    if base in ("ffmpeg", "ffprobe") and member.isfile():
                        with tf.extractfile(member) as src, open(BASE_PATH / base, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        (BASE_PATH / base).chmod(0o755)

        else:
            raise RuntimeError(f"No automatic ffmpeg download is available for {system}.")

    global FFMPEG, FFPROBE
    FFMPEG = get_executable_path("ffmpeg")
    FFPROBE = get_executable_path("ffprobe")
    if not FFMPEG or not FFPROBE:
        raise RuntimeError("Download finished but ffmpeg/ffprobe were not found afterwards.")
    return True


def offer_ffmpeg_download(parent):
    """Shows a small modal with a progress bar and downloads ffmpeg in a
    background thread, so the GUI never freezes. `parent` is the Tk
    root/toplevel to attach the dialog to."""
    win = tk.Toplevel(parent)
    win.title("DVtools")
    win.geometry("380x120")
    win.resizable(False, False)
    win.transient(parent)
    win.grab_set()

    label_var = tk.StringVar(value="Preparing download...")
    ttk.Label(win, textvariable=label_var).pack(pady=(18, 8), padx=16)
    progress = ttk.Progressbar(win, mode="determinate", maximum=100, length=340)
    progress.pack(pady=6, padx=16)

    def set_progress(pct):
        if pct < 0:
            progress.configure(mode="indeterminate")
            progress.start(12)
        else:
            progress.configure(mode="determinate")
            progress.stop()
            progress["value"] = pct

    def set_status(text):
        label_var.set(text)

    def worker():
        try:
            download_ffmpeg(
                progress_callback=lambda p: parent.after(0, set_progress, p),
                status_callback=lambda s: parent.after(0, set_status, s),
            )
            parent.after(0, on_success)
        except Exception as e:
            parent.after(0, on_error, str(e))

    def on_success():
        win.destroy()
        messagebox.showinfo("DVtools", "ffmpeg was installed successfully.")

    def on_error(msg):
        win.destroy()
        messagebox.showerror(
            "DVtools",
            "The automatic download failed:\n" + msg +
            "\n\nPlease install ffmpeg manually (see the previous message)."
        )

    threading.Thread(target=worker, daemon=True).start()


# ----------------------------------------------------------------------
# Formats and Codecs
# ----------------------------------------------------------------------

CONTAINERS = {
    "MP4": (".mp4", ["h264", "h265", "av1"]),
    "MOV": (".mov", ["h264", "h265", "prores"]),
    "MKV": (".mkv", ["h264", "h265", "av1"]),
    "AVI": (".avi", ["h264"]),
    "WebM": (".webm", ["vp9", "av1"]),
}

CODEC_NAMES = {
    "h264": "H.264 (Max compatibility)",
    "h265": "H.265 / HEVC (Half size, same quality)",
    "av1": "AV1 (Most efficient, slowest to encode)",
    "prores": "ProRes (Master file, visually lossless)",
    "vp9": "VP9 (Native WebM)",
}


def get_encoder_for(codec, accel):
    """Returns (ffmpeg_encoder_name, extra_args) based on codec and acceleration mode."""
    hw_map = {
        "nvenc": {"h264": "h264_nvenc", "h265": "hevc_nvenc", "av1": "av1_nvenc"},
        "amf": {"h264": "h264_amf", "h265": "hevc_amf", "av1": "av1_amf"},
        "qsv": {"h264": "h264_qsv", "h265": "hevc_qsv", "av1": "av1_qsv"},
    }
    if accel in hw_map and codec in hw_map[accel]:
        candidate = hw_map[accel][codec]
        if candidate in get_available_encoders():
            return candidate, []
    
    sw_map = {
        "h264": "libx264",
        "h265": "libx265",
        "av1": "libsvtav1",
        "prores": "prores_ks",
        "vp9": "libvpx-vp9",
    }
    return sw_map[codec], []


def get_audio_for_container(container):
    if container == "AVI":
        return ["-c:a", "mp3", "-b:a", "256k"]
    if container == "WebM":
        return ["-c:a", "libopus", "-b:a", "192k"]
    if container == "MOV":
        return ["-c:a", "pcm_s16le"]
    return ["-c:a", "aac", "-b:a", "320k"]


# ----------------------------------------------------------------------
# Video Logic
# ----------------------------------------------------------------------

def get_video_info(path):
    cmd = [FFPROBE, "-v", "quiet", "-print_format", "json",
           "-show_streams", "-show_format", str(path)]
    output = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(output.stdout)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")

    width = int(video["width"])
    height = int(video["height"])

    if height in (576, 288):
        system = "PAL"
    elif height in (480, 240):
        system = "NTSC"
    else:
        system = "unknown"

    dar_str = video.get("display_aspect_ratio")
    if dar_str and ":" in dar_str and "0:1" not in dar_str:
        a, b = dar_str.split(":")
        dar = float(a) / float(b)
    else:
        dar = 4 / 3 

    fps_str = video.get("r_frame_rate", "25/1")
    n, d = fps_str.split("/")
    fps = float(n) / float(d) if float(d) else float(n)

    duration = float(data.get("format", {}).get("duration", 0) or 0)

    format_tags = data.get("format", {}).get("tags", {}) or {}
    stream_tags = video.get("tags", {}) or {}
    recording_date = format_tags.get("creation_time") or stream_tags.get("creation_time")

    return {
        "width": width, "height": height, "dar": dar, "fps": fps,
        "duration": duration, "system": system, "date": recording_date,
    }


def get_metadata_tags(path):
    """Reads a file's metadata tags (format + video) to display them in the
    metadata editor. Returns a plain text dict, never raises an exception
    outward (if anything fails, an empty dict is returned).
    """
    try:
        cmd = [FFPROBE, "-v", "quiet", "-print_format", "json",
               "-show_format", "-show_streams", str(path)]
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        data = json.loads(output.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
        return {}

    tags = dict(data.get("format", {}).get("tags", {}) or {})
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            for k, v in (stream.get("tags", {}) or {}).items():
                tags.setdefault(k, v)
            break
    return tags


def calculate_target_resolution(info, target_height, force_aspect="auto"):
    if force_aspect == "4:3":
        dar = 4 / 3
    elif force_aspect == "16:9":
        dar = 16 / 9
    else:
        dar = info["dar"]
    height = int(round(target_height / 2) * 2)
    width = int(round((height * dar) / 2) * 2)
    return width, height


def play_with_vlc(path):
    path = str(path)
    if not VLC:
        messagebox.showerror("Error", "VLC is not installed or not found on the system.")
        return
    subprocess.Popen([VLC, path])


def extract_frame(path, second, output_png, width=None, height=None):
    """Extracts a frame, automatically scaling it to target preview aspect settings via FFMPEG."""
    if width and height and width > 10 and height > 10:
        cmd = [FFMPEG, "-y", "-ss", str(second), "-i", str(path),
               "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease",
               "-frames:v", "1", "-q:v", "2", str(output_png)]
    else:
        cmd = [FFMPEG, "-y", "-ss", str(second), "-i", str(path),
               "-frames:v", "1", "-q:v", "2", str(output_png)]
    subprocess.run(cmd, capture_output=True)


def detect_black_borders(path, info):
    """Analyzes several frames spread across the video to detect black
    borders (letterboxing / edge noise) and returns a 'crop=W:H:X:Y'
    filter in the file's ORIGINAL resolution, ready to be placed before
    scaling. Returns None if nothing is found or the detected crop is
    negligible.
    """
    duration = info.get("duration", 0) or 0
    if duration > 4:
        sample_points = [duration * frac for frac in (0.15, 0.4, 0.65, 0.85)]
    else:
        sample_points = [max(0.0, duration / 2)]

    crops_found = []
    for ts in sample_points:
        cmd = [FFMPEG, "-ss", str(ts), "-i", str(path), "-t", "1",
               "-vf", "cropdetect=24:2:0", "-f", "null", "-"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            continue
        matches = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", result.stderr)
        if matches:
            w, h, x, y = matches[-1]
            crops_found.append((int(w), int(h), int(x), int(y)))

    if not crops_found:
        return None

    # We use the most conservative crop (the smallest one detected) so we
    # don't over-crop if some frame happened to have a very dark scene.
    w = min(c[0] for c in crops_found)
    h = min(c[1] for c in crops_found)
    x = max(c[2] for c in crops_found)
    y = max(c[3] for c in crops_found)

    orig_w, orig_h = info.get("width", 0), info.get("height", 0)
    if orig_w and orig_h and (orig_w - w) < 4 and (orig_h - h) < 4:
        return None
    if w <= 0 or h <= 0:
        return None

    return f"crop={w}:{h}:{x}:{y}"


def _seconds_to_mmss(seconds):
    seconds = max(0, seconds)
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def detect_dropouts(path, info, tout_threshold=0.12, min_gap=1.0):
    """Scans the ENTIRE video looking for possible tape dropouts (the
    green/frozen blocks typical of MiniDV head errors or damaged tape),
    using the "temporal outliers" (TOUT) detector built into ffmpeg's
    'signalstats' filter: it flags pixels whose value sharply differs from
    the temporal average of their neighbors, which is exactly a dropout's
    signature.

    IMPORTANT: this is a HEURISTIC / indicative analysis, not perfect
    detection. Scenes with very abrupt motion or strong camera noise can
    produce false positives; use it as a guide for "where to start
    looking", not as absolute truth.

    Returns (events, error). 'events' is a list of dicts
    {"start": sec, "end": sec, "severity": 0..1} sorted by time, with
    nearby detections merged into a single event. 'error' is None if
    everything went fine, or an error message string if the analysis
    failed.
    """
    cmd = [FFMPEG, "-i", str(path),
           "-vf", ("signalstats=stat=tout,"
                   f"metadata=select:key=lavfi.signalstats.TOUT:value={tout_threshold}:function=greater,"
                   "metadata=print:file=-"),
           "-f", "null", "-"]
    duration = info.get("duration", 0) or 0
    timeout = max(120, int(duration) * 4)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return [], str(e)

    hits = []
    current_time = None
    for line in (result.stdout or "").splitlines():
        m = re.search(r"pts_time:(\d+\.?\d*)", line)
        if m:
            current_time = float(m.group(1))
            continue
        m2 = re.search(r"lavfi\.signalstats\.TOUT=(\d+\.?\d*)", line)
        if m2 and current_time is not None:
            hits.append((current_time, float(m2.group(1))))

    if not hits:
        return [], None

    hits.sort(key=lambda h: h[0])
    events = []
    start_t = last_t = hits[0][0]
    max_sev = hits[0][1]
    for ts, sev in hits[1:]:
        if ts - last_t > min_gap:
            events.append({"start": start_t, "end": last_t, "severity": max_sev})
            start_t, max_sev = ts, sev
        else:
            max_sev = max(max_sev, sev)
        last_t = ts
    events.append({"start": start_t, "end": last_t, "severity": max_sev})
    return events, None


def build_timecode_args(options):
    """Returns the '-timecode HH:MM:SS:FF' arguments to regenerate a
    CLEAN, SEQUENTIAL timecode in the output container.

    Honest note: this rewrites the timecode at the CONTAINER level (the
    'tmcd' track of MOV/MP4), which is what editing software reads. It
    does not rewrite the SMPTE subcode embedded inside the raw DV stream
    itself (ffmpeg doesn't expose that level of granularity); in practice,
    however, this fixes the actual problem most people run into: a
    broken/erratic timecode that confuses the NLE on import. Only applies
    to containers that support a timecode track (MOV/MP4).
    """
    if not options.get("timecode_repair"):
        return []
    if options.get("container") not in ("MOV", "MP4"):
        return []
    start = (options.get("timecode_start") or "00:00:00:00").strip()
    if not re.match(r"^\d{2}:\d{2}:\d{2}[:;]\d{2}$", start):
        start = "00:00:00:00"
    return ["-timecode", start]


def get_system_idle_seconds():
    """Returns, in seconds, how long the system has gone without
    keyboard/mouse input. This is "best-effort" cross-platform: it uses
    the native API on Windows, 'ioreg' on macOS, and 'xprintidle' on
    Linux (if installed). Returns None if it couldn't be determined on
    this machine, in which case the calling function should treat that as
    "not available" rather than assuming the system is idle.
    """
    system = platform.system()
    try:
        if system == "Windows":
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
                millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
                return millis / 1000.0
        elif system == "Darwin":
            result = subprocess.run(["ioreg", "-c", "IOHIDSystem"],
                                     capture_output=True, text=True, timeout=5)
            m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', result.stdout)
            if m:
                return int(m.group(1)) / 1_000_000_000.0
        else:
            if shutil.which("xprintidle"):
                result = subprocess.run(["xprintidle"], capture_output=True,
                                         text=True, timeout=5)
                return int(result.stdout.strip()) / 1000.0
    except Exception:
        pass
    return None


def is_system_idle_available():
    """True if this machine/OS supports measuring idle time (needed for
    the 'process when the PC is idle' mode)."""
    return get_system_idle_seconds() is not None


def build_audio_filter_chain(options):
    """Builds the AUDIO filter chain (-af) from the active options. The
    order is tailored for MiniDV tapes: first remove individual clicks,
    then the low-frequency hum (highpass), then reduce continuous
    background noise, and finally normalize volume (so normalization
    measures the already-cleaned audio).
    """
    afilters = []
    if options.get("audio_declick", False):
        afilters.append("adeclick")
    if options.get("audio_highpass", False):
        hz = int(options.get("audio_highpass_hz", 100))
        afilters.append(f"highpass=f={hz}")
    if options.get("audio_denoise", False):
        nr = options.get("audio_denoise_strength", 12)
        nf = options.get("audio_denoise_floor", -50)
        afilters.append(f"afftdn=nr={nr}:nf={nf}")
    if options.get("audio_loudnorm", False):
        afilters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    return afilters


def build_filter_chain(info, width, height, options):
    filters = []

    # 0. Auto-crop black borders (if one was detected before calling this
    #    function). Must go BEFORE scaling because the coordinates are
    #    calculated against the file's original resolution.
    autocrop_filter = options.get("autocrop_filter")
    if autocrop_filter:
        filters.append(autocrop_filter)

    # 0.5 Image stabilization (deshake). Applied at the original
    #     resolution, before scaling, so motion estimation is more
    #     accurate. Uses ffmpeg's built-in "deshake" filter (unlike
    #     vidstab, it doesn't depend on an external library that might
    #     not be compiled into the user's ffmpeg binary).
    if options.get("stabilize", False):
        strength = int(options.get("stabilize_strength", 16))
        filters.append(f"deshake=rx={strength}:ry={strength}:edge=mirror")

    # 1. FIRST compute the scale filter string.
    scale_filter = f"scale={width}:{height}:flags=lanczos"
    if options.get("codec") == "prores":
        scale_filter += ":format=yuv422p10le"

    # 2. THEN add it to the filter list.
    filters.append(scale_filter)

    # 3. The rest of the base filters are added after.
    if options.get("crop", False):
        px = int(options.get("crop_px", 8))
        filters.append(f"crop=in_w-{2*px}:in_h-{2*px}:{px}:{px}")

    if options.get("deinterlace", True):
        filters.append("yadif=0:-1:0")

    if options.get("noise_reduction", False):
        filters.append("hqdn3d=3:2.5:4:3")

    if options.get("pixel_correction", True):
        filters.append("setsar=1")

    if options.get("color_restoration", False):
        filters.append("eq=contrast=1.05:saturation=1.15:brightness=0.01")
        filters.append("colorbalance=rs=0.02:gs=0.0:bs=-0.02:rm=0.02:gm=0.0:bm=-0.02")

    if options.get("sharpening", False):
        filters.append("unsharp=5:5:0.4:5:5:0.0")

    # 4. FINALLY call the plugins (they receive the already-built list)
    for plugin in ACTIVE_PLUGINS["video_filter"]:
        if not is_plugin_enabled(plugin):
            continue
        if hasattr(plugin, "modify_filters"):
            filters = plugin.modify_filters(filters, options, info)

    return ",".join(filters)


def build_video_encoder_args(codec, accel):
    """Returns (encoder_name, args) where args is the full "-c:v <encoder> ..."
    argument list for the given codec/accel combo. Shared by the plain
    ffmpeg pipeline (build_ffmpeg_command) and the optional VapourSynth
    pipeline (dvtools_vs.build_vs_pipeline_commands) so both engines always
    produce output with identical codec settings.
    """
    encoder, extra_args = get_encoder_for(codec, accel)
    args = ["-c:v", encoder]

    if codec == "prores":
        # pix_fmt is already fixed by the scale filter (see build_filter_chain).
        args += ["-profile:v", "3", "-vendor", "apl0"]
    elif codec in ("h264", "h265"):
        if "nvenc" in encoder or "amf" in encoder or "qsv" in encoder:
            args += ["-b:v", "0", "-cq", "18"] if "nvenc" in encoder else ["-qp", "20"]
        else:
            args += ["-crf", "16", "-preset", "slow"]
        args += ["-pix_fmt", "yuv420p"]
    elif codec == "av1":
        if encoder == "libsvtav1":
            args += ["-crf", "26", "-preset", "6"]
        args += ["-pix_fmt", "yuv420p"]
    elif codec == "vp9":
        args += ["-crf", "24", "-b:v", "0", "-pix_fmt", "yuv420p"]

    args += extra_args
    return encoder, args


def build_metadata_args(options):
    """Builds the -map_metadata / -metadata argument list shared by both
    the ffmpeg-only and the VapourSynth pipelines."""
    args = []
    if options.get("copy_metadata", True):
        args += ["-map_metadata", "0"]
        date = options.get("recording_date")
        if date:
            args += ["-metadata", f"creation_time={date}"]

    # Custom metadata from the metadata editor tab is appended AFTER
    # -map_metadata 0 so it overrides anything copied from the original
    # file if the user edited a field by hand.
    custom_metadata = options.get("custom_metadata") or {}
    for key, value in custom_metadata.items():
        if value:
            args += ["-metadata", f"{key}={value}"]
    return args


def build_ffmpeg_command(input_path, output_path, width, height, info, options):
    video_filter = build_filter_chain(info, width, height, options)

    cmd = [FFMPEG, "-y", "-i", str(input_path), "-vf", video_filter]

    codec = options["codec"]
    accel = options.get("accel", "auto")
    _, video_encoder_args = build_video_encoder_args(codec, accel)
    cmd += video_encoder_args

    audio_filters = build_audio_filter_chain(options)
    if audio_filters:
        cmd += ["-af", ",".join(audio_filters)]

    cmd += get_audio_for_container(options["container"])
    cmd += build_metadata_args(options)
    cmd += build_timecode_args(options)
    cmd += ["-progress", "pipe:1", "-nostats", str(output_path)]

    for plugin in ACTIVE_PLUGINS.get("ffmpeg_modifier", []):
        if not is_plugin_enabled(plugin):
            continue
        if hasattr(plugin, "modify_command"):
            cmd = plugin.modify_command(cmd, options)

    return cmd


def build_vapoursynth_command(input_path, output_path, width, height, info, options):
    """Equivalent of build_ffmpeg_command() but routes video through the
    optional VapourSynth engine (dvtools_vs.py). Returns
    (vspipe_cmd, ffmpeg_cmd, script_path); run both with
    dvtools_vs.run_pipeline().
    """
    codec = options["codec"]
    accel = options.get("accel", "auto")
    _, video_encoder_args = build_video_encoder_args(codec, accel)

    audio_filters = build_audio_filter_chain(options)
    audio_args = get_audio_for_container(options["container"])
    metadata_args = build_metadata_args(options)
    extra_output_args = build_timecode_args(options)

    return dvtools_vs.build_vs_pipeline_commands(
        input_path, output_path, width, height, info, options,
        FFMPEG, video_encoder_args, audio_filters, audio_args, metadata_args,
        vs_plugin_modules=[p for p in ACTIVE_PLUGINS.get("vs_filter", []) if is_plugin_enabled(p)],
        extra_output_args=extra_output_args)


def detect_scene_changes(path, threshold=0.35):
    cmd = [FFMPEG, "-i", str(path), "-vf", f"select='gt(scene,{threshold})',showinfo",
           "-f", "null", "-"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    times = [0.0]
    for line in result.stderr.splitlines():
        m = re.search(r"pts_time:(\d+\.?\d*)", line)
        if m:
            times.append(float(m.group(1)))
    return sorted(set(round(x, 2) for x in times))


def split_by_scenes(input_path, output_folder, times, total_duration, options):
    """Splits the already-processed video into segments at the detected
    timestamps.

    FIXED BUG: the previous version used "-c copy", which can only cut on
    keyframes. Since the input file here is already an MP4/MOV/etc. with
    long GOPs, a cut landing in the middle of a GOP produced freezes or
    blocky artifacts at the start of each scene. It now re-encodes on
    every cut so it's accurate to the millisecond.
    """
    generated_paths = []
    limits = times + [total_duration]
    codec = options.get("codec", "h264")
    encoder, _ = get_encoder_for(codec, options.get("accel", "auto"))
    for i in range(len(limits) - 1):
        start, end = limits[i], limits[i + 1]
        duration = end - start
        if duration < 1.0:
            continue
        name = f"Scene_{i+1:02d}{Path(input_path).suffix}"
        output = Path(output_folder) / name
        cmd = [FFMPEG, "-y", "-ss", str(start), "-i", str(input_path),
               "-t", str(duration), "-c:v", encoder]
        if codec in ("h264", "h265") and not any(
                x in encoder for x in ("nvenc", "amf", "qsv")):
            cmd += ["-crf", "16", "-preset", "slow"]
        cmd += ["-c:a", "copy", str(output)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            generated_paths.append(str(output))
    return generated_paths


# ----------------------------------------------------------------------
# Graphical User Interface
# ----------------------------------------------------------------------

import time

# FIXED BUG: this block of VLC DLL imports/setup used to be tripled
# (copy-pasted 3 times in a row), which didn't break anything but was
# pure dead code. It's now left in a single place, and reuses
# _prepare_vlc_dll_windows() (defined above) instead of repeating the
# VLC folder lookup.
_prepare_vlc_dll_windows()

try:
    import vlc
except ImportError:
    vlc = None


class PreviewWindow(tk.Toplevel):
    """Preview window with real playback (VLC engine).

    BUGS FIXED compared to the previous version:
      - There was no visible Play/Pause button: it only worked with the
        Space key. There's now a real button.
      - Fullscreen mode hid the control bar and relied on the window's
        native decoration (which disappears in fullscreen) to be able to
        close it; if the user didn't know Escape got them back out, the
        window got "stuck" in fullscreen. Fullscreen mode was removed
        entirely and a Close button that never depends on window
        decoration, and is always visible, was added instead.
    """

    def __init__(self, master, path, duration):
        super().__init__(master)
        self.master = master
        self.path = path
        self.duration = max(duration, 1)  # Duration in seconds

        self.title(f"Live Preview (VLC Engine) — {Path(path).name}")
        self.geometry("800x580")
        self.resizable(True, True)
        self.minsize(500, 420)
        self.configure(bg="#2d2d2d")
        self.protocol("WM_DELETE_WINDOW", self._on_close_window)

        if vlc is None:
            lbl = ttk.Label(
                self,
                text="Please execute in your terminal:\npip install python-vlc\nto activate the integrated previewer.",
                foreground="red", font=("Arial", 12, "bold"), anchor="center", justify="center"
            )
            lbl.pack(expand=True, fill="both", padx=20, pady=20)
            close_btn = ttk.Button(self, text="Close", command=self.destroy)
            close_btn.pack(pady=(0, 15))
            return

        self.info_label = ttk.Label(
            self,
            text="Controls: [Space] Pause/Play | [Left/Right] Seek 10s | [M] Mute",
            anchor="center", justify="center"
        )
        self.info_label.pack(padx=10, pady=5, fill="x")

        self.video_frame = tk.Frame(self, bg="black")
        self.video_frame.pack(padx=10, pady=5, fill="both", expand=True)

        self.slider_var = tk.DoubleVar()
        self.is_scrubbing = False

        self.slider = ttk.Scale(
            self, from_=0, to=self.duration, orient="horizontal",
            variable=self.slider_var, command=self._on_slider_change
        )
        self.slider.pack(fill="x", padx=15, pady=(5, 10))
        self.slider.bind("<ButtonPress-1>", self._on_slider_press)
        self.slider.bind("<ButtonRelease-1>", self._on_slider_release)

        # Always-visible control bar: play/pause and close.
        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=15, pady=(0, 12))
        self.play_button_var = tk.StringVar(value="▶ Play")
        self.btn_play = ttk.Button(controls, textvariable=self.play_button_var,
                                    command=self._toggle_play)
        self.btn_play.pack(side="left")
        ttk.Button(controls, text="Mute / Unmute",
                   command=self._toggle_mute).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Close",
                   command=self._on_close_window).pack(side="right")

        self.vlc_instance = vlc.Instance("--quiet")
        self.player = self.vlc_instance.media_player_new()
        self.media = self.vlc_instance.media_new(str(self.path))
        self.player.set_media(self.media)

        self.bind("<space>", self._toggle_play)
        self.bind("<Left>", lambda e: self._seek_relative(-10))
        self.bind("<Right>", lambda e: self._seek_relative(10))
        self.bind("m", self._toggle_mute)
        self.bind("M", self._toggle_mute)

        self.update()
        self.after(450, self._start_vlc_player)

    def _start_vlc_player(self):
        """Passes the Tkinter Frame window tracking ID context straight into libvlc core"""
        if not self.winfo_exists():
            return

        win_id = self.video_frame.winfo_id()
        sys_platform = platform.system()

        if sys_platform == "Windows":
            self.player.set_hwnd(win_id)
        elif sys_platform == "Darwin":  # macOS
            self.player.set_nsobject(win_id)
        else:  # Linux / X11
            self.player.set_xwindow(win_id)

        self.player.play()
        self.play_button_var.set("⏸ Pause")

        self.keep_syncing = True
        self.sync_thread = threading.Thread(target=self._update_slider_worker, daemon=True)
        self.sync_thread.start()

    def _update_slider_worker(self):
        """Background thread updating the progress bar dynamically to match VLC playback"""
        while self.keep_syncing and self.winfo_exists():
            if not self.is_scrubbing and self.player.is_playing():
                current_ms = self.player.get_time()
                if current_ms > 0:
                    current_sec = current_ms / 1000.0
                    self.after(0, lambda s=current_sec: self.slider_var.set(s))
            time.sleep(0.25)

    def _on_slider_press(self, event):
        self.is_scrubbing = True

    def _on_slider_release(self, event):
        target_seconds = self.slider_var.get()
        self.player.set_time(int(target_seconds * 1000))
        self.after(100, self._reset_scrubbing_flag)

    def _reset_scrubbing_flag(self):
        self.is_scrubbing = False

    def _on_slider_change(self, value):
        if self.is_scrubbing:
            return

    def _seek_relative(self, seconds):
        current_ms = self.player.get_time()
        if current_ms < 0:
            return
        target_ms = current_ms + (seconds * 1000)
        target_ms = max(0, min(target_ms, int(self.duration * 1000)))
        self.player.set_time(target_ms)
        self.slider_var.set(target_ms / 1000.0)

    def _toggle_play(self, event=None):
        if self.player.is_playing():
            self.player.pause()
            self.play_button_var.set("▶ Play")
        else:
            self.player.play()
            self.play_button_var.set("⏸ Pause")

    def _toggle_mute(self, event=None):
        self.player.audio_set_mute(not self.player.audio_get_mute())

    def _on_close_window(self):
        """Halts background syncing loops and safely releases hardware pipelines"""
        self.keep_syncing = False
        if hasattr(self, 'player'):
            try:
                self.player.stop()
                self.player.release()
            except Exception:
                pass
        if hasattr(self, 'vlc_instance'):
            try:
                self.vlc_instance.release()
            except Exception:
                pass
        self.destroy()


class App(tk.Tk):
    def __init__(self, **tk_kwargs):
        super().__init__(**tk_kwargs)
        
        # --- LOAD CUSTOM FONT DATA INTO MEMORY ---
        # FIXED BUG: the code used to look for .ttf files ("GeneralSans-
        # Regular.ttf" / "GeneralSans-Medium.ttf"), but the font shipped
        # alongside the script is "GeneralSans-Regular.otf" (and no Medium
        # variant exists at all). As a result font_regular_path never
        # existed and the custom font never loaded, not even on Windows.
        # BASE_PATH is also used instead of Path(__file__).parent so it
        # still works once packaged.
        # --- LOAD CUSTOM FONT DATA INTO MEMORY ---
        font_loaded = False
        # Only the Regular file is looked up.
        regular_path = BASE_PATH / "fonts" / "GeneralSans-Regular.otf"

        if regular_path.exists():
            font_loaded = load_dynamic_font(regular_path)
            self.font_regular = "General Sans"
            # For the "Medium" look, the same font is reused with bold.
            self.font_medium = "General Sans"
        else:
            # Fallback if the font file isn't found.
            print("Notice: GeneralSans-Regular.otf not found; using system default font.")
            self.font_regular = "Segoe UI" if platform.system() == "Windows" else "Arial"
            self.font_medium = self.font_regular

        self.custom_font_available = font_loaded

        self.geometry("900x750")
        self.resizable(True, True)
        self.minsize(680, 580)

        self.logo_img = self.load_logo()
        if self.logo_img:
            try:
                self.iconphoto(True, self.logo_img)
            except Exception:
                pass

        self.anim_frames = load_animation_frames()
        self.current_frame_index = 0
        self.anim_playing = False
        self.anim_should_stop = False
        self._theme_timer_id = None

        self.info = None
        self.file_queue = []
        self.queue_errors = {}

        self._config_data = load_config_file()
        saved_lang = self._config_data.get("language")
        if saved_lang in TEXTS:
            CURRENT_LANGUAGE["code"] = saved_lang

        self._build_ui()
        self._apply_loaded_settings()
        self._sync_language_combo()
        self._refresh_texts()
        self._apply_loaded_theme()
        self._inject_plugin_guis()

        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

        dep_error = check_dependencies()
        if dep_error:
            self.after(300, lambda: self._show_missing_ffmpeg_dialog(dep_error))

    def _show_missing_ffmpeg_dialog(self, dep_error):
        """Shown instead of a plain warning when ffmpeg/ffprobe are
        missing: offers a one-click automatic download (see
        download_ffmpeg() / offer_ffmpeg_download()) as an alternative
        to the manual-install instructions in dep_error."""
        system = platform.system()
        if system not in FFMPEG_DOWNLOAD_URLS:
            messagebox.showwarning(t("missing_software_title"), dep_error)
            return
        if messagebox.askyesno(
            t("missing_software_title"),
            dep_error + "\n\nWould you like DVtools to download ffmpeg automatically now?",
        ):
            offer_ffmpeg_download(self)

    def _apply_loaded_settings(self):
        """Restores every persisted setting (all "*_var" Tk variables not
        in CONFIG_EXCLUDED_VARS, plus the saved theme) from the config.txt
        contents already read into self._config_data. Called right after
        _build_ui() so every variable already exists. Language is handled
        separately, before _build_ui(), so the language combobox is built
        already showing the right selection (see _sync_language_combo)."""
        data = self._config_data
        if not data:
            return

        for name, value in data.get("settings", {}).items():
            if name in CONFIG_EXCLUDED_VARS:
                continue
            var = getattr(self, name, None)
            if var is not None and hasattr(var, "set"):
                try:
                    var.set(value)
                except Exception:
                    pass

        theme = data.get("theme")
        if theme in ("light", "dark", "auto"):
            self.theme_var_name.set(theme)

    def _sync_language_combo(self):
        code_to_index = {"en": 0, "es": 1, "fr": 2}
        self.lang_combo.current(code_to_index.get(CURRENT_LANGUAGE["code"], 0))

    def _apply_loaded_theme(self):
        """Applies self.theme_var_name (possibly just restored from
        config.txt) now that _refresh_texts() has populated the theme
        combobox's translated option strings."""
        theme = self.theme_var_name.get() or "auto"
        if theme == "light":
            self.theme_combo.set(t("theme_light"))
            self._apply_style("light")
        elif theme == "dark":
            self.theme_combo.set(t("theme_dark"))
            self._apply_style("dark")
        else:
            self.theme_var_name.set("auto")
            self.theme_combo.set(t("theme_auto"))
            self._apply_theme_by_hour()

    def _save_config(self):
        """Writes every current setting to config.txt: every "*_var" Tk
        variable not in CONFIG_EXCLUDED_VARS, the active language, the
        active theme, and which plugins are enabled/disabled. Called on
        app close (_on_app_close) so DVtools reopens exactly as it was
        left."""
        settings = {}
        for name, var in vars(self).items():
            if name in CONFIG_EXCLUDED_VARS or not name.endswith("_var"):
                continue
            if isinstance(var, (tk.BooleanVar, tk.StringVar, tk.IntVar, tk.DoubleVar)):
                try:
                    settings[name] = var.get()
                except Exception:
                    pass

        data = {
            "language": CURRENT_LANGUAGE["code"],
            "theme": self.theme_var_name.get(),
            "settings": settings,
            "plugins": dict(PLUGIN_ENABLED),
        }
        save_config_file(data)

    def _on_app_close(self):
        self._save_config()
        self.destroy()

    def load_logo(self):
        try:
            return tk.PhotoImage(data=LOGO_B64)
        except Exception as e:
            print(f"Error loading logo asset: {e}")
            return None
        
    def _play_animation_cycle(self):
        """Plays the animation in a loop (back and forth) at 8 FPS until told to stop."""
        if not self.anim_frames:
            return

        # 12-step sequence (0,1,2,3,4,5,4,3,2,1,0, ... etc)
        sequence = [0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0]

        def step():
            if not self.anim_playing:
                return

            # Show the current frame
            frame = self.anim_frames[sequence[self.current_frame_index]]
            self.logo_label.configure(image=frame)
            self.logo_label.image = frame

            # Advance the index
            self.current_frame_index += 1
            if self.current_frame_index >= len(sequence):
                self.current_frame_index = 0

            # If we should stop and we're back at the start (frame 0), stop.
            if self.anim_should_stop and self.current_frame_index == 5:
                self._stop_animation()
                return

            # 8 FPS = 1000ms / 8 = 125ms per frame
            self.after(125, step)

        step()

    def _start_animation(self):
        """Starts the animation, replacing the static logo."""
        if not self.anim_frames:
            return
        self.anim_playing = True
        self.anim_should_stop = False
        self.current_frame_index = 0
        self._play_animation_cycle()

    def _stop_animation(self):
        """Stops the animation and restores the static logo."""
        self.anim_playing = False
        self.logo_label.configure(image=self.logo_img)
        self.logo_label.image = self.logo_img
        self.anim_should_stop = False

    def _build_ui(self):
        header = ttk.Frame(self, padding=(15, 10))
        header.pack(fill="x")

        if self.logo_img:
            self.logo_label = tk.Label(header, image=self.logo_img)
            self.logo_label.image = self.logo_img
            self.logo_label.pack(side="left", padx=(0, 10))

        self.title_var = tk.StringVar()
        ttk.Label(header, textvariable=self.title_var, font=(self.font_medium, 14, "bold")).pack(side="left")

        selectors_frame = ttk.Frame(header)
        selectors_frame.pack(side="right")

        self.lang_label_var = tk.StringVar()
        ttk.Label(selectors_frame, textvariable=self.lang_label_var).pack(side="left", padx=(5, 2))
        self.lang_combo = ttk.Combobox(selectors_frame, width=10, state="readonly", values=["English", "Español", "Français"])
        self.lang_combo.current(0 if CURRENT_LANGUAGE["code"] == "en" else 1)
        self.lang_combo.bind("<<ComboboxSelected>>", self._change_language)
        self.lang_combo.pack(side="left", padx=(0, 10))

        self.theme_label_var = tk.StringVar()
        ttk.Label(selectors_frame, textvariable=self.theme_label_var).pack(side="left", padx=(5, 2))
        self.theme_var_name = tk.StringVar()
        self.theme_combo = ttk.Combobox(selectors_frame, width=15, state="readonly")
        self.theme_combo.bind("<<ComboboxSelected>>", self._change_theme_manual)
        self.theme_combo.pack(side="left")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self.tab_file = ttk.Frame(self.notebook, padding=15)
        self.tab_correction = ttk.Frame(self.notebook, padding=15)
        self.tab_audio = ttk.Frame(self.notebook, padding=15)
        self.tab_format = ttk.Frame(self.notebook, padding=15)
        self.tab_metadata = ttk.Frame(self.notebook, padding=15)
        self.tab_tape = ttk.Frame(self.notebook, padding=15)
        self.tab_advanced = ttk.Frame(self.notebook, padding=15)
        self.tab_batch = ttk.Frame(self.notebook, padding=15)
        self.tab_plugins = ttk.Frame(self.notebook, padding=15)

        self.notebook.add(self.tab_file, text="")
        self.notebook.add(self.tab_correction, text="")
        self.notebook.add(self.tab_audio, text="")
        self.notebook.add(self.tab_format, text="")
        self.notebook.add(self.tab_metadata, text="")
        self.notebook.add(self.tab_tape, text="")
        self.notebook.add(self.tab_advanced, text="")
        self.notebook.add(self.tab_batch, text="")
        self.notebook.add(self.tab_plugins, text="")

        self._build_tab_file()
        self._build_tab_correction()
        self._build_tab_audio()
        self._build_tab_format()
        self._build_tab_metadata()
        self._build_tab_tape()
        self._build_tab_advanced()
        self._build_tab_batch()
        self._build_tab_plugins()

        footer = ttk.Frame(self, padding=(15, 5))
        footer.pack(fill="x")
        self.progress = ttk.Progressbar(footer, mode="determinate")
        self.progress.pack(fill="x")
        self.status_var = tk.StringVar()
        ttk.Label(footer, textvariable=self.status_var).pack(anchor="w", pady=(3, 0))

    def _update_theme_list(self):
        self.theme_label_var.set(t("theme_label"))
        available_themes = [t("theme_light"), t("theme_dark"), t("theme_auto")]
        self.theme_combo.configure(values=available_themes)
        if not self.theme_var_name.get():
            self.theme_combo.current(2)
            self._apply_theme_by_hour()

    def _change_theme_manual(self, _event=None):
        if self._theme_timer_id is not None:
            self.after_cancel(self._theme_timer_id)
            self._theme_timer_id = None

        selection = self.theme_combo.get()
        if selection == t("theme_light"):
            self.theme_var_name.set("light")
            self._apply_style("light")
        elif selection == t("theme_dark"):
            self.theme_var_name.set("dark")
            self._apply_style("dark")
        elif selection == t("theme_auto"):
            self.theme_var_name.set("auto")
            self._apply_theme_by_hour()

    def _apply_theme_by_hour(self):
        import datetime
        current_hour = datetime.datetime.now().hour
        
        if current_hour >= 19 or current_hour < 6:
            self._apply_style("dark")
        else:
            self._apply_style("light")
            
        if self.theme_combo.get() == t("theme_auto"):
            self._theme_timer_id = self.after(60000, self._apply_theme_by_hour)

    def _apply_style(self, mode):
        style = ttk.Style()
        import tkinter.font as tkfont

        # FIXED BUG: "General Sans" used to be forced on every base font
        # without checking whether it had actually loaded (see __init__).
        # If loading failed (e.g. on a platform where the font couldn't be
        # copied into the user's font folder), Tk silently ignored the
        # unknown family and fell back to a default font anyway, with no
        # warning. An explicit, sensible per-platform default family is
        # now used whenever the custom font isn't available.
        if getattr(self, "custom_font_available", False):
            real_font_name = self.font_regular
        elif platform.system() == "Windows":
            real_font_name = "Segoe UI"
        elif platform.system() == "Darwin":
            real_font_name = "SF Pro Text"
        else:
            real_font_name = "DejaVu Sans"

        for name in ("TkDefaultFont", "TkTextFont", "TkCaptionFont", "TkMenuFont"):
            base_font = tkfont.nametofont(name)
            base_font.config(family=real_font_name)

        self.title_font = tkfont.Font(family=real_font_name, size=14, weight="bold")

        if mode == "dark":
            bg_color = "#313235"
            fg_color = "#ffffff"
            field_bg = "#2A2A2C"
            accent_bg = "#303033"
            
            self.option_add("*TCombobox*Listbox.selectForeground", fg_color)
            self.configure(bg=bg_color)
            style.theme_use("clam")
            
            style.configure(".", background=bg_color, foreground=fg_color, fieldbackground=field_bg)
            style.configure("TNotebook", background=bg_color, borderwidth=0)
            style.configure("TNotebook.Tab", background="#333336", foreground=fg_color, padding=[10, 5])
            style.map("TNotebook.Tab", background=[("selected", "#323235")], foreground=[("selected", "#6d6d6d")])
            style.configure("TLabelFrame", background=bg_color, foreground=fg_color)
            style.configure("TButton", background=accent_bg, foreground=fg_color, borderwidth=1)
            style.map("TButton", background=[("active", "#080820")])
            
            style.configure("TEntry", fieldbackground=field_bg, foreground=fg_color, insertcolor=fg_color)
            style.configure("TCombobox", fieldbackground=field_bg, background=accent_bg, foreground=fg_color, arrowcolor=fg_color)
            style.map("TCombobox", fieldbackground=[("readonly", field_bg)], foreground=[("readonly", fg_color)])
            style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
            style.map("TCheckbutton", background=[("active", bg_color)], foreground=[("active", fg_color)], indicatorbackground=[("selected", field_bg)])

            # FIXED BUG: the Treeview widget (used for the plugin list and
            # the batch queue) was never given its own style in dark mode.
            # ttk's "clam" theme then fell back to its built-in Treeview
            # colors -- a light/white row background -- while the generic
            # style.configure(".", foreground=fg_color) above still forced
            # the TEXT to white, so rows looked completely blank (white on
            # white) until clicked, at which point the selection highlight
            # finally gave the text some contrast. Both the rows and the
            # column headings now get explicit dark-mode colors.
            style.configure("Treeview", background=field_bg, foreground=fg_color,
                             fieldbackground=field_bg, bordercolor=bg_color, borderwidth=0)
            style.map("Treeview",
                      background=[("selected", accent_bg)],
                      foreground=[("selected", fg_color)])
            style.configure("Treeview.Heading", background=accent_bg, foreground=fg_color,
                             relief="flat")
            style.map("Treeview.Heading", background=[("active", accent_bg)])

            self.option_add("*TCombobox*Listbox.background", field_bg)
            self.option_add("*TCombobox*Listbox.foreground", fg_color)
            self.option_add("*TCombobox*Listbox.selectBackground", accent_bg)
            self.option_add("*TCombobox*Listbox.selectForeground", fg_color)
            
            change_windows_title_bar(self, dark_mode=True)

            if hasattr(self, 'logo_label') and self.logo_label.winfo_exists():
                self.logo_label.configure(bg=bg_color, image=self.logo_img)
                self.logo_label.image = self.logo_img
        else:
            bg_color = "#f0f0f0"
            self.configure(bg=bg_color)
            style.theme_use("vista" if "vista" in style.theme_names() else "default")
            style.configure(".", background=bg_color, foreground="#000000", fieldbackground="#ffffff")
            style.configure("TNotebook", background=bg_color)
            style.configure("TNotebook.Tab", padding=[10, 5])
            style.configure("TLabelFrame", background=bg_color, foreground="#000000")

            # Explicit light-mode colors for the same Treeview used above
            # in dark mode (plugin list / batch queue), for consistency
            # across platforms/themes.
            style.configure("Treeview", background="#ffffff", foreground="#000000",
                             fieldbackground="#ffffff")
            style.map("Treeview", background=[("selected", "#cfe4ff")],
                      foreground=[("selected", "#000000")])
            style.configure("Treeview.Heading", background="#e6e6e6", foreground="#000000")

            self.option_add("*TCombobox*Listbox.foreground", "#000000")
            self.option_add("*TCombobox*Listbox.background", "#ffffff")

            # FIXED BUG: this call used to be nested inside the "if
            # hasattr(self, 'logo_label')..." block, so if the logo hadn't
            # loaded (self.logo_img is None) the Windows title bar stayed
            # dark forever after switching back to the light theme. It's
            # now called unconditionally, just like in the dark branch
            # above.
            change_windows_title_bar(self, dark_mode=False)

            if hasattr(self, 'logo_label') and self.logo_label.winfo_exists():
                self.logo_label.configure(bg=bg_color, image=self.logo_img)
                self.logo_label.image = self.logo_img

    def _build_tab_file(self):
        f = self.tab_file
        f.grid_columnconfigure(0, weight=1)

        self.lbl_file = ttk.Label(f)
        self.lbl_file.grid(row=0, column=0, sticky="w")
        self.path_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.path_var).grid(
            row=1, column=0, columnspan=2, sticky="we")
        self.btn_browse = ttk.Button(f, command=self.choose_file)
        self.btn_browse.grid(row=1, column=2, padx=5)

        self.lbl_data = ttk.Label(f)
        self.lbl_data.grid(row=2, column=0, sticky="w", pady=(15, 0))
        self.info_var = tk.StringVar(value="—")
        ttk.Label(f, textvariable=self.info_var).grid(
            row=2, column=1, columnspan=2, sticky="w", pady=(15, 0))

        buttons = ttk.Frame(f)
        buttons.grid(row=3, column=0, columnspan=3, pady=25)
        self.btn_preview = ttk.Button(buttons, command=self.open_preview)
        self.btn_preview.grid(row=0, column=0, padx=5)
        self.btn_process = ttk.Button(buttons, command=self.process)
        self.btn_process.grid(row=0, column=1, padx=5)

    def _build_tab_correction(self):
        f = self.tab_correction

        self.lbl_height = ttk.Label(f)
        self.lbl_height.grid(row=0, column=0, sticky="w")
        self.height_var = tk.StringVar(value="1440")
        ttk.Combobox(f, textvariable=self.height_var, width=10,
                     values=["1080", "1440", "2160", "2880"]).grid(row=0, column=1, sticky="w")
        self.lbl_auto_width = ttk.Label(f)
        self.lbl_auto_width.grid(row=0, column=2, sticky="w", padx=5)

        self.lbl_force_aspect = ttk.Label(f)
        self.lbl_force_aspect.grid(row=1, column=0, sticky="w", pady=(15, 0))
        self.aspect_var = tk.StringVar()
        self.combo_aspect = ttk.Combobox(f, textvariable=self.aspect_var, width=25,
                                           state="readonly")
        self.combo_aspect.grid(row=1, column=1, columnspan=2, sticky="w", pady=(15, 0))

        self.chk_pixel_corr_var = tk.BooleanVar(value=True)
        self.chk_pixel_corr = ttk.Checkbutton(f, variable=self.chk_pixel_corr_var)
        self.chk_pixel_corr.grid(row=2, column=0, columnspan=3, sticky="w", pady=(15, 0))

        self.crop_var = tk.BooleanVar(value=True)
        self.chk_crop = ttk.Checkbutton(f, variable=self.crop_var)
        self.chk_crop.grid(row=3, column=0, sticky="w", pady=(15, 0))
        self.lbl_px = ttk.Label(f)
        self.lbl_px.grid(row=3, column=1, sticky="e")
        self.crop_px_var = tk.StringVar(value="8")
        ttk.Spinbox(f, from_=1, to=40, width=5, textvariable=self.crop_px_var).grid(
            row=3, column=2, sticky="w")

        self.noise_var = tk.BooleanVar(value=True)
        self.chk_noise = ttk.Checkbutton(f, variable=self.noise_var)
        self.chk_noise.grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.color_var = tk.BooleanVar(value=True)
        self.chk_color = ttk.Checkbutton(f, variable=self.color_var)
        self.chk_color.grid(row=5, column=0, columnspan=3, sticky="w", pady=(5, 0))

        self.deint_var = tk.BooleanVar(value=True)
        self.chk_deint = ttk.Checkbutton(f, variable=self.deint_var)
        self.chk_deint.grid(row=6, column=0, columnspan=3, sticky="w", pady=(5, 0))

        self.sharp_var = tk.BooleanVar(value=False)
        self.chk_sharp = ttk.Checkbutton(f, variable=self.sharp_var)
        self.chk_sharp.grid(row=7, column=0, columnspan=3, sticky="w", pady=(5, 0))

        # --- Image stabilization (deshake) ---
        self.stabilize_var = tk.BooleanVar(value=False)
        self.chk_stabilize = ttk.Checkbutton(f, variable=self.stabilize_var)
        self.chk_stabilize.grid(row=8, column=0, columnspan=2, sticky="w", pady=(15, 0))
        self.lbl_stabilize_strength = ttk.Label(f)
        self.lbl_stabilize_strength.grid(row=9, column=0, sticky="w", pady=(2, 0))
        self.stabilize_strength_var = tk.StringVar(value="16")
        ttk.Spinbox(f, from_=4, to=64, width=5,
                    textvariable=self.stabilize_strength_var).grid(
            row=9, column=1, sticky="w", pady=(2, 0))

        # --- Auto-crop black borders ---
        self.autocrop_black_var = tk.BooleanVar(value=False)
        self.chk_autocrop_black = ttk.Checkbutton(f, variable=self.autocrop_black_var)
        self.chk_autocrop_black.grid(row=10, column=0, columnspan=3, sticky="w", pady=(15, 0))
        self.lbl_autocrop_black_note = ttk.Label(f, wraplength=560, foreground="#666666")
        self.lbl_autocrop_black_note.grid(row=11, column=0, columnspan=3, sticky="w", pady=(5, 0))

    def _build_tab_format(self):
        f = self.tab_format

        self.lbl_out_format = ttk.Label(f)
        self.lbl_out_format.grid(row=0, column=0, sticky="w")
        self.container_var = tk.StringVar(value="MP4")
        combo_cont = ttk.Combobox(f, textvariable=self.container_var, width=15,
                                   state="readonly", values=list(CONTAINERS.keys()))
        combo_cont.grid(row=0, column=1, sticky="w")
        combo_cont.bind("<<ComboboxSelected>>", self._update_codecs)

        self.lbl_codec = ttk.Label(f)
        self.lbl_codec.grid(row=1, column=0, sticky="w", pady=(15, 0))
        self.codec_var = tk.StringVar()
        self.combo_codec = ttk.Combobox(f, textvariable=self.codec_var, width=42,
                                         state="readonly")
        self.combo_codec.grid(row=1, column=1, columnspan=2, sticky="w", pady=(15, 0))
        self._update_codecs()

        self.lbl_accel = ttk.Label(f)
        self.lbl_accel.grid(row=2, column=0, sticky="w", pady=(15, 0))
        self.accel_var = tk.StringVar()
        self.combo_accel = ttk.Combobox(f, textvariable=self.accel_var, width=25,
                                               state="readonly")
        self.combo_accel.grid(row=2, column=1, columnspan=2, sticky="w", pady=(15, 0))

    def _build_tab_tape(self):
        f = self.tab_tape
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(2, weight=1)

        # --- Dropout Detector ---
        self.lbl_dropout_section = ttk.Label(f, font=(self.font_medium, 10, "bold"))
        self.lbl_dropout_section.grid(row=0, column=0, columnspan=2, sticky="w")
        self.lbl_dropout_note = ttk.Label(f, wraplength=560, foreground="#666666")
        self.lbl_dropout_note.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 10))

        results_frame = ttk.Frame(f)
        results_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(0, weight=1)
        self.list_dropouts = tk.Listbox(results_frame, height=10)
        self.list_dropouts.grid(row=0, column=0, sticky="nsew")
        scroll_dropouts = ttk.Scrollbar(results_frame, orient="vertical",
                                         command=self.list_dropouts.yview)
        scroll_dropouts.grid(row=0, column=1, sticky="ns")
        self.list_dropouts.configure(yscrollcommand=scroll_dropouts.set)

        self.btn_scan_dropouts = ttk.Button(f, command=self.scan_dropouts_action)
        self.btn_scan_dropouts.grid(row=3, column=0, sticky="w", pady=(10, 0))

        ttk.Separator(f, orient="horizontal").grid(
            row=4, column=0, columnspan=2, sticky="we", pady=20)

        # --- Timecode Repair ---
        self.lbl_timecode_section = ttk.Label(f, font=(self.font_medium, 10, "bold"))
        self.lbl_timecode_section.grid(row=5, column=0, columnspan=2, sticky="w")

        self.timecode_repair_var = tk.BooleanVar(value=False)
        self.chk_timecode_repair = ttk.Checkbutton(f, variable=self.timecode_repair_var)
        self.chk_timecode_repair.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.lbl_timecode_start = ttk.Label(f)
        self.lbl_timecode_start.grid(row=7, column=0, sticky="w", pady=(8, 0))
        self.timecode_start_var = tk.StringVar(value="00:00:00:00")
        ttk.Entry(f, textvariable=self.timecode_start_var, width=14).grid(
            row=7, column=1, sticky="w", pady=(8, 0))

        self.lbl_timecode_note = ttk.Label(f, wraplength=560, foreground="#666666")
        self.lbl_timecode_note.grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _build_tab_advanced(self):
        f = self.tab_advanced

        self.metadata_var = tk.BooleanVar(value=True)
        self.chk_metadata = ttk.Checkbutton(f, variable=self.metadata_var)
        self.chk_metadata.grid(row=0, column=0, columnspan=2, sticky="w")

        self.scenes_var = tk.BooleanVar(value=False)
        self.chk_scenes = ttk.Checkbutton(f, variable=self.scenes_var)
        self.chk_scenes.grid(row=1, column=0, columnspan=2, sticky="w", pady=(15, 0))

        self.lbl_scenes_note = ttk.Label(f, wraplength=560, foreground="#666666")
        self.lbl_scenes_note.grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))

        # --- Optional VapourSynth processing engine (dvtools_vs.py) ---
        self.use_vs_var = tk.BooleanVar(value=False)
        self.chk_use_vs = ttk.Checkbutton(f, variable=self.use_vs_var)
        self.chk_use_vs.grid(row=3, column=0, columnspan=2, sticky="w", pady=(20, 0))
        self.lbl_vs_note = ttk.Label(f, wraplength=560, foreground="#666666")
        self.lbl_vs_note.grid(row=4, column=0, columnspan=2, sticky="w", pady=(5, 0))

        if not dvtools_vs.is_available():
            self.chk_use_vs.state(["disabled"])
            self.use_vs_var.set(False)

        # --- Chromatic aberration correction (VapourSynth-only, best-effort) ---
        self.chromatic_aberration_var = tk.BooleanVar(value=False)
        self.chk_chromatic_aberration = ttk.Checkbutton(f, variable=self.chromatic_aberration_var)
        self.chk_chromatic_aberration.grid(row=5, column=0, columnspan=2, sticky="w", pady=(20, 0))
        self.lbl_chromatic_shift = ttk.Label(f)
        self.lbl_chromatic_shift.grid(row=6, column=0, sticky="w", pady=(4, 0))
        self.chromatic_aberration_shift_var = tk.StringVar(value="0.3")
        ttk.Spinbox(f, from_=0.1, to=1.5, increment=0.1, width=6,
                    textvariable=self.chromatic_aberration_shift_var).grid(
            row=6, column=1, sticky="w", pady=(4, 0))
        self.lbl_chromatic_note = ttk.Label(f, wraplength=560, foreground="#666666")
        self.lbl_chromatic_note.grid(row=7, column=0, columnspan=2, sticky="w", pady=(5, 0))

        if not dvtools_vs.is_available():
            self.chk_chromatic_aberration.state(["disabled"])
            self.chromatic_aberration_var.set(False)

    def _build_tab_audio(self):
        f = self.tab_audio

        self.audio_declick_var = tk.BooleanVar(value=False)
        self.chk_audio_declick = ttk.Checkbutton(f, variable=self.audio_declick_var)
        self.chk_audio_declick.grid(row=0, column=0, columnspan=3, sticky="w")

        self.audio_denoise_var = tk.BooleanVar(value=False)
        self.chk_audio_denoise = ttk.Checkbutton(f, variable=self.audio_denoise_var)
        self.chk_audio_denoise.grid(row=1, column=0, columnspan=2, sticky="w", pady=(15, 0))
        self.lbl_audio_denoise_strength = ttk.Label(f)
        self.lbl_audio_denoise_strength.grid(row=2, column=0, sticky="w", pady=(2, 0))
        self.audio_denoise_strength_var = tk.StringVar(value="12")
        ttk.Spinbox(f, from_=1, to=97, width=5,
                    textvariable=self.audio_denoise_strength_var).grid(
            row=2, column=1, sticky="w", pady=(2, 0))
        self.lbl_audio_denoise_floor = ttk.Label(f)
        self.lbl_audio_denoise_floor.grid(row=3, column=0, sticky="w", pady=(2, 0))
        self.audio_denoise_floor_var = tk.StringVar(value="-50")
        ttk.Spinbox(f, from_=-80, to=-20, width=5,
                    textvariable=self.audio_denoise_floor_var).grid(
            row=3, column=1, sticky="w", pady=(2, 0))

        self.audio_highpass_var = tk.BooleanVar(value=False)
        self.chk_audio_highpass = ttk.Checkbutton(f, variable=self.audio_highpass_var)
        self.chk_audio_highpass.grid(row=4, column=0, columnspan=2, sticky="w", pady=(15, 0))
        self.lbl_audio_highpass_hz = ttk.Label(f)
        self.lbl_audio_highpass_hz.grid(row=5, column=0, sticky="w", pady=(2, 0))
        self.audio_highpass_hz_var = tk.StringVar(value="100")
        ttk.Spinbox(f, from_=20, to=300, increment=10, width=5,
                    textvariable=self.audio_highpass_hz_var).grid(
            row=5, column=1, sticky="w", pady=(2, 0))

        self.audio_loudnorm_var = tk.BooleanVar(value=False)
        self.chk_audio_loudnorm = ttk.Checkbutton(f, variable=self.audio_loudnorm_var)
        self.chk_audio_loudnorm.grid(row=6, column=0, columnspan=3, sticky="w", pady=(15, 0))
        self.lbl_audio_loudnorm_note = ttk.Label(f, wraplength=560, foreground="#666666")
        self.lbl_audio_loudnorm_note.grid(row=7, column=0, columnspan=3, sticky="w", pady=(5, 0))

    def _build_tab_metadata(self):
        f = self.tab_metadata
        f.grid_columnconfigure(1, weight=1)

        self.lbl_metadata_intro = ttk.Label(f, wraplength=560, foreground="#666666")
        self.lbl_metadata_intro.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))

        self.lbl_meta_date = ttk.Label(f)
        self.lbl_meta_date.grid(row=1, column=0, sticky="w", pady=4)
        self.meta_date_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.meta_date_var).grid(
            row=1, column=1, sticky="we", pady=4)

        self.lbl_meta_title = ttk.Label(f)
        self.lbl_meta_title.grid(row=2, column=0, sticky="w", pady=4)
        self.meta_title_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.meta_title_var).grid(
            row=2, column=1, sticky="we", pady=4)

        self.lbl_meta_author = ttk.Label(f)
        self.lbl_meta_author.grid(row=3, column=0, sticky="w", pady=4)
        self.meta_author_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.meta_author_var).grid(
            row=3, column=1, sticky="we", pady=4)

        self.lbl_meta_comment = ttk.Label(f)
        self.lbl_meta_comment.grid(row=4, column=0, sticky="nw", pady=4)
        self.meta_comment_text = tk.Text(f, height=4, width=40, wrap="word")
        self.meta_comment_text.grid(row=4, column=1, sticky="we", pady=4)

    def _build_tab_batch(self):
        f = self.tab_batch
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(2, weight=1)

        self.lbl_folder = ttk.Label(f)
        self.lbl_folder.grid(row=0, column=0, sticky="w")
        self.folder_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.folder_var).grid(
            row=1, column=0, sticky="we")
        self.btn_choose_folder = ttk.Button(f, command=self.choose_folder)
        self.btn_choose_folder.grid(row=1, column=1, padx=5)
        self.btn_add_queue = ttk.Button(f, command=self.add_folder_to_queue)
        self.btn_add_queue.grid(row=1, column=2, padx=5)

        self.table_queue = ttk.Treeview(f, columns=("file", "status"),
                                        show="headings", height=12)
        self.table_queue.grid(row=2, column=0, columnspan=3, pady=(15, 0), sticky="nsew")
        self.table_queue.column("file", width=430)
        self.table_queue.column("status", width=100, anchor="center")
        # Double-clicking a row with an error shows ffmpeg's actual detail
        # (previously there was no way to see why a batch file failed).
        self.table_queue.bind("<Double-1>", self._show_queue_error)

        # Priority queue: dragging a row with the mouse reorders it within
        # the list, and that order is what's used when processing.
        self._drag_item = None
        self.table_queue.bind("<ButtonPress-1>", self._on_queue_drag_start, add="+")
        self.table_queue.bind("<B1-Motion>", self._on_queue_drag_motion, add="+")
        self.table_queue.bind("<ButtonRelease-1>", self._on_queue_drag_release, add="+")

        self.lbl_queue_drag_note = ttk.Label(f, foreground="#666666")
        self.lbl_queue_drag_note.grid(row=3, column=0, columnspan=3, sticky="w", pady=(5, 0))

        buttons = ttk.Frame(f)
        buttons.grid(row=4, column=0, columnspan=3, pady=15)
        self.btn_process_queue = ttk.Button(buttons, command=self.process_queue)
        self.btn_process_queue.grid(row=0, column=0, padx=5)
        self.btn_clear_queue = ttk.Button(buttons, command=self.clear_queue)
        self.btn_clear_queue.grid(row=0, column=1, padx=5)

        ttk.Separator(f, orient="horizontal").grid(
            row=5, column=0, columnspan=3, sticky="we", pady=10)

        # --- Nightly processing / when the PC is idle ---
        self.lbl_schedule_section = ttk.Label(f, font=(self.font_medium, 10, "bold"))
        self.lbl_schedule_section.grid(row=6, column=0, columnspan=3, sticky="w")

        self.idle_wait_var = tk.BooleanVar(value=False)
        self.chk_idle_wait = ttk.Checkbutton(f, variable=self.idle_wait_var)
        self.chk_idle_wait.grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.lbl_idle_minutes = ttk.Label(f)
        self.lbl_idle_minutes.grid(row=8, column=0, sticky="w", pady=(2, 0))
        self.idle_minutes_var = tk.StringVar(value="5")
        ttk.Spinbox(f, from_=1, to=60, width=5,
                    textvariable=self.idle_minutes_var).grid(
            row=8, column=1, sticky="w", pady=(2, 0))
        if not is_system_idle_available():
            self.chk_idle_wait.state(["disabled"])
            self.idle_wait_var.set(False)

        self.scheduled_start_var = tk.BooleanVar(value=False)
        self.chk_scheduled_start = ttk.Checkbutton(f, variable=self.scheduled_start_var)
        self.chk_scheduled_start.grid(row=9, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.lbl_scheduled_time = ttk.Label(f)
        self.lbl_scheduled_time.grid(row=10, column=0, sticky="w", pady=(2, 0))
        self.scheduled_time_var = tk.StringVar(value="02:00")
        ttk.Entry(f, textvariable=self.scheduled_time_var, width=8).grid(
            row=10, column=1, sticky="w", pady=(2, 0))
        self.lbl_schedule_note = ttk.Label(f, wraplength=560, foreground="#666666")
        self.lbl_schedule_note.grid(row=11, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _build_tab_plugins(self):
        f = self.tab_plugins

        self.lbl_plugins = ttk.Label(f, font=(self.font_medium, 10, "bold"))
        self.lbl_plugins.pack(anchor="w", pady=(0, 5))

        # "enabled" is the leftmost column: it shows a checkbox glyph the
        # user can click to enable/disable a plugin instantly, without
        # restarting DVtools (see _on_plugin_tree_click / PLUGIN_ENABLED).
        self.table_plugins = ttk.Treeview(
            f, columns=("enabled", "name", "type", "author"), show="headings", height=5)
        self.table_plugins.pack(fill="x", pady=(0, 10))

        self.table_plugins.column("enabled", width=70, anchor="center")
        self.table_plugins.column("name", width=220)
        self.table_plugins.column("type", width=100)
        self.table_plugins.column("author", width=150)
        self.table_plugins.bind("<Button-1>", self._on_plugin_tree_click)

        self.plugin_options_frame = ttk.LabelFrame(f, text="", padding=10)
        self.plugin_options_frame.pack(fill="both", expand=True)

    def _on_plugin_tree_click(self, event):
        """Toggles a plugin on/off in place when the user clicks its
        checkbox cell -- this is what lets plugins be enabled/disabled
        temporarily, right from the app, with no restart needed."""
        if self.table_plugins.identify("region", event.x, event.y) != "cell":
            return
        row_id = self.table_plugins.identify_row(event.y)
        column = self.table_plugins.identify_column(event.x)
        if not row_id or column != "#1":
            return
        PLUGIN_ENABLED[row_id] = not PLUGIN_ENABLED.get(row_id, True)
        self._refresh_plugin_tree()

    def _refresh_plugin_tree(self):
        """(Re)populates the plugin table. Split out of _refresh_texts()
        so toggling a plugin's enabled state can redraw just this table
        without needing a full text/language refresh."""
        for item in self.table_plugins.get_children():
            self.table_plugins.delete(item)

        if not ACTIVE_PLUGINS["info_list"]:
            self.table_plugins.insert("", "end", values=("—", t("no_plugins"), "—", "—"))
            return

        for info in ACTIVE_PLUGINS["info_list"]:
            plugin_id = info.get("id", info.get("name", ""))
            enabled = PLUGIN_ENABLED.get(plugin_id, True)
            check_glyph = "\u2611" if enabled else "\u2610"  # ☑ / ☐
            # iid=plugin_id lets _on_plugin_tree_click identify which
            # plugin was clicked directly from the row id.
            self.table_plugins.insert("", "end", iid=plugin_id, values=(
                check_glyph,
                info.get("name", "Unknown"),
                info.get("type", "Unknown"),
                info.get("author", "—")
            ))

    def _inject_plugin_guis(self):
        for plugin in ACTIVE_PLUGINS["info_list"]:
            module = plugin.get("module")
            if module and hasattr(module, "build_gui"):
                try:
                    module.build_gui(self.plugin_options_frame)
                except Exception as e:
                    print(f"Error rendering plugin GUI context: {e}")

    def _change_language(self, _event=None):
        selection = self.lang_combo.get()
        if selection == "English":
            CURRENT_LANGUAGE["code"] = "en"
        elif selection == "Español":
            CURRENT_LANGUAGE["code"] = "es"
        elif selection == "Français":
            CURRENT_LANGUAGE["code"] = "fr"
        self._refresh_texts()

    def _refresh_texts(self):
        self.title(t("title"))
        self.title_var.set("DVtools")
        self.lang_label_var.set(t("lang_label"))
        self._update_theme_list()

        self.notebook.tab(self.tab_file, text=t("tab_file"))
        self.notebook.tab(self.tab_correction, text=t("tab_correction"))
        self.notebook.tab(self.tab_audio, text=t("tab_audio"))
        self.notebook.tab(self.tab_format, text=t("tab_format"))
        self.notebook.tab(self.tab_metadata, text=t("tab_metadata"))
        self.notebook.tab(self.tab_tape, text=t("tab_tape"))
        self.notebook.tab(self.tab_advanced, text=t("tab_advanced"))
        self.notebook.tab(self.tab_batch, text=t("tab_batch"))
        self.notebook.tab(self.tab_plugins, text=t("tab_plugins"))

        self.lbl_file.configure(text=t("file_label"))
        self.btn_browse.configure(text=t("browse"))
        self.lbl_data.configure(text=t("detected_data"))
        self.btn_preview.configure(text=t("built_in_preview"))
        self.btn_process.configure(text=t("process"))

        self.lbl_height.configure(text=t("target_height"))
        self.lbl_auto_width.configure(text=t("auto_width"))
        self.lbl_force_aspect.configure(text=t("force_aspect"))
        
        aspect_values = [t("aspect_auto"), t("aspect_4_3"), t("aspect_16_9")]
        self.combo_aspect.configure(values=aspect_values)
        if not self.aspect_var.get() or self.aspect_var.get() not in aspect_values:
            self.combo_aspect.current(0)
            
        self.chk_pixel_corr.configure(text=t("pixel_correction"))
        self.chk_crop.configure(text=t("crop_edges"))
        self.lbl_px.configure(text=t("px_per_side"))
        self.chk_noise.configure(text=t("noise_reduction"))
        self.chk_color.configure(text=t("color_restoration"))
        self.chk_deint.configure(text=t("deinterlace"))
        self.chk_sharp.configure(text=t("sharpening"))

        self.lbl_out_format.configure(text=t("output_format"))
        self.lbl_codec.configure(text=t("video_codec"))
        self.lbl_accel.configure(text=t("hw_accel"))
        
        accel_values = [t("accel_cpu")]
        available = get_available_encoders()
        if any("nvenc" in e for e in available):
            accel_values.append(t("accel_nvenc"))
        if any("amf" in e for e in available):
            accel_values.append(t("accel_amf"))
        if any("qsv" in e for e in available):
            accel_values.append(t("accel_qsv"))
            
        self.combo_accel.configure(values=accel_values)
        if not self.accel_var.get() or self.accel_var.get() not in accel_values:
            self.combo_accel.current(0)

        self.chk_stabilize.configure(text=t("stabilize_check"))
        self.lbl_stabilize_strength.configure(text=t("stabilize_strength_label"))
        self.chk_autocrop_black.configure(text=t("autocrop_black_check"))
        self.lbl_autocrop_black_note.configure(text=t("autocrop_black_note"))

        self.chk_audio_declick.configure(text=t("audio_declick_check"))
        self.chk_audio_denoise.configure(text=t("audio_denoise_check"))
        self.lbl_audio_denoise_strength.configure(text=t("audio_denoise_strength_label"))
        self.lbl_audio_denoise_floor.configure(text=t("audio_denoise_floor_label"))
        self.chk_audio_highpass.configure(text=t("audio_highpass_check"))
        self.lbl_audio_highpass_hz.configure(text=t("audio_highpass_hz_label"))
        self.chk_audio_loudnorm.configure(text=t("audio_loudnorm_check"))
        self.lbl_audio_loudnorm_note.configure(text=t("audio_loudnorm_note"))

        self.lbl_metadata_intro.configure(text=t("metadata_intro"))
        self.lbl_meta_date.configure(text=t("metadata_date_label"))
        self.lbl_meta_title.configure(text=t("metadata_title_label"))
        self.lbl_meta_author.configure(text=t("metadata_author_label"))
        self.lbl_meta_comment.configure(text=t("metadata_comment_label"))

        self.chk_metadata.configure(text=t("metadata_check"))
        self.chk_scenes.configure(text=t("scenes_check"))
        self.lbl_scenes_note.configure(text=t("scenes_note"))

        self.chk_use_vs.configure(text=t("vs_engine_check"))
        self.lbl_vs_note.configure(
            text=t("vs_engine_note") if dvtools_vs.is_available() else t("vs_engine_unavailable"))

        self.chk_chromatic_aberration.configure(text=t("chromatic_aberration_check"))
        self.lbl_chromatic_shift.configure(text=t("chromatic_aberration_shift_label"))
        self.lbl_chromatic_note.configure(
            text=t("chromatic_aberration_note") if dvtools_vs.is_available()
            else t("vs_engine_unavailable"))

        self.lbl_folder.configure(text=t("folder_label"))
        self.btn_choose_folder.configure(text=t("choose_folder"))
        self.btn_add_queue.configure(text=t("add_queue"))
        self.btn_process_queue.configure(text=t("process_queue"))
        self.btn_clear_queue.configure(text=t("clear_queue"))
        self.table_queue.heading("file", text=t("col_file"))
        self.table_queue.heading("status", text=t("col_status"))
        self.lbl_queue_drag_note.configure(text=t("queue_drag_note"))

        self.lbl_schedule_section.configure(text=t("schedule_section_title"))
        self.chk_idle_wait.configure(
            text=t("idle_wait_check") if is_system_idle_available()
            else t("idle_wait_unavailable"))
        self.lbl_idle_minutes.configure(text=t("idle_minutes_label"))
        self.chk_scheduled_start.configure(text=t("scheduled_start_check"))
        self.lbl_scheduled_time.configure(text=t("scheduled_time_label"))
        self.lbl_schedule_note.configure(text=t("schedule_note"))

        self.lbl_dropout_section.configure(text=t("dropout_section_title"))
        self.lbl_dropout_note.configure(text=t("dropout_note"))
        self.btn_scan_dropouts.configure(text=t("dropout_scan_btn"))
        self.lbl_timecode_section.configure(text=t("timecode_section_title"))
        self.chk_timecode_repair.configure(text=t("timecode_repair_check"))
        self.lbl_timecode_start.configure(text=t("timecode_start_label"))
        self.lbl_timecode_note.configure(text=t("timecode_repair_note"))

        self.status_var.set(t("ready"))

        self.lbl_plugins.configure(text=t("plugins_detected"))
        self.table_plugins.heading("enabled", text=t("col_plugin_enabled"))
        self.table_plugins.heading("name", text=t("col_plugin_name"))
        self.table_plugins.heading("type", text=t("col_plugin_type"))
        self.table_plugins.heading("author", text=t("col_plugin_author"))
        self.plugin_options_frame.configure(text=t("plugin_frame_title"))

        self._refresh_plugin_tree()

        for item in self.table_queue.get_children():
            vals = self.table_queue.item(item, 'values')
            self.table_queue.item(item, values=(vals[0], t("status_pending")))

    def _update_codecs(self, _event=None):
        container = self.container_var.get()
        _, codecs = CONTAINERS.get(container, (".mp4", ["h264"]))
        values = [CODEC_NAMES[c] for c in codecs]
        self.combo_codec.configure(values=values)
        self.combo_codec.current(0)

    def _get_selected_codec(self):
        container = self.container_var.get()
        _, codecs = CONTAINERS.get(container, (".mp4", ["h264"]))
        idx = self.combo_codec.current()
        if idx < 0:
            idx = 0
        return codecs[idx]

    def _get_selected_accel(self):
        text = self.accel_var.get()
        if text == t("accel_nvenc"):
            return "nvenc"
        if text == t("accel_amf"):
            return "amf"
        if text == t("accel_qsv"):
            return "qsv"
        return "auto"

    def _get_forced_aspect(self):
        text = self.aspect_var.get()
        if text == t("aspect_4_3"):
            return "4:3"
        if text == t("aspect_16_9"):
            return "16:9"
        return "auto"

    def choose_file(self):
        exts = get_all_supported_extensions()
        # Build the file type filter string dynamically.
        types = [
            ("All supported videos", " ".join(exts)),
            ("DV files", "*.dv *.dif"),
            ("All files", "*.*")
        ]
        path = filedialog.askopenfilename(
            title=t("file_label"),
            filetypes=types)
        if not path:
            return
        self.path_var.set(path)
        self._read_info(path)

    def _read_info(self, path):
        try:
            self.info = get_video_info(path)
            self.info_var.set(
                f'{self.info["width"]}x{self.info["height"]} ({self.info["system"]}) · '
                f'{self.info["fps"]:.2f} fps · '
                f'{self.info["duration"] / 60:.1f} min')

            self._load_metadata_tab(path)

            if self.info:
                dispatch_event("on_file_loaded", {"info": self.info, "path": path})
        except Exception as e:
            self.info = None
            self.info_var.set(t("no_data"))
            messagebox.showerror(t("error_read"), str(e))

    def _load_metadata_tab(self, path):
        """Fills the Metadata tab with whatever the original file already
        has, so the user can edit it before exporting."""
        tags = get_metadata_tags(path)
        self.meta_date_var.set(tags.get("creation_time", "") or (self.info or {}).get("date") or "")
        self.meta_title_var.set(tags.get("title", ""))
        self.meta_author_var.set(tags.get("artist", "") or tags.get("author", ""))
        self.meta_comment_text.delete("1.0", "end")
        self.meta_comment_text.insert("1.0", tags.get("comment", ""))

    def open_preview(self):
        path = self.path_var.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning(t("error_read"), t("error_path"))
            return
        if not self.info:
            self._read_info(path)
        if self.info:
            PreviewWindow(self, path, self.info["duration"])

    def _get_current_options(self):
        try:
            crop_px = int(self.crop_px_var.get())
        except ValueError:
            crop_px = 8
        try:
            stabilize_strength = int(self.stabilize_strength_var.get())
        except ValueError:
            stabilize_strength = 16
        try:
            audio_denoise_strength = int(self.audio_denoise_strength_var.get())
        except ValueError:
            audio_denoise_strength = 12
        try:
            audio_denoise_floor = int(self.audio_denoise_floor_var.get())
        except ValueError:
            audio_denoise_floor = -50
        try:
            audio_highpass_hz = int(self.audio_highpass_hz_var.get())
        except ValueError:
            audio_highpass_hz = 100
        try:
            chromatic_aberration_shift = float(self.chromatic_aberration_shift_var.get())
        except ValueError:
            chromatic_aberration_shift = 0.3

        custom_metadata = {
            "title": self.meta_title_var.get().strip(),
            "artist": self.meta_author_var.get().strip(),
            "comment": self.meta_comment_text.get("1.0", "end").strip(),
        }
        meta_date = self.meta_date_var.get().strip()

        return {
            "crop": self.crop_var.get(),
            "crop_px": crop_px,
            "deinterlace": self.deint_var.get(),
            "noise_reduction": self.noise_var.get(),
            "color_restoration": self.color_var.get(),
            "sharpening": self.sharp_var.get(),
            "pixel_correction": self.chk_pixel_corr_var.get(),
            "stabilize": self.stabilize_var.get(),
            "stabilize_strength": stabilize_strength,
            "autocrop_black": self.autocrop_black_var.get(),
            "audio_declick": self.audio_declick_var.get(),
            "audio_denoise": self.audio_denoise_var.get(),
            "audio_denoise_strength": audio_denoise_strength,
            "audio_denoise_floor": audio_denoise_floor,
            "audio_highpass": self.audio_highpass_var.get(),
            "audio_highpass_hz": audio_highpass_hz,
            "audio_loudnorm": self.audio_loudnorm_var.get(),
            "codec": self._get_selected_codec(),
            "container": self.container_var.get(),
            "accel": self._get_selected_accel(),
            "copy_metadata": self.metadata_var.get(),
            "custom_metadata": custom_metadata,
            "custom_metadata_date": meta_date,
            "use_vapoursynth": self.use_vs_var.get() and dvtools_vs.is_available(),
            "timecode_repair": self.timecode_repair_var.get(),
            "timecode_start": self.timecode_start_var.get().strip(),
            "chromatic_aberration": self.chromatic_aberration_var.get() and dvtools_vs.is_available(),
            "chromatic_aberration_shift": chromatic_aberration_shift,
        }

    def process(self):
        path = self.path_var.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning(t("error_read"), t("error_path"))
            return
        if not self.info:
            self._read_info(path)
            if not self.info:
                return
        try:
            target_height = int(self.height_var.get())
        except ValueError:
            messagebox.showwarning(t("error_read"), t("error_height"))
            return

        width, height = calculate_target_resolution(
            self.info, target_height, self._get_forced_aspect())

        container = self.container_var.get()
        extension, _ = CONTAINERS[container]
        suggested = str(Path(path).with_name(Path(path).stem + f"_{height}p{extension}"))
        output_file = filedialog.asksaveasfilename(
            title=t("save_as"), initialfile=Path(suggested).name,
            defaultextension=extension, filetypes=[("Video", f"*{extension}")])
        if not output_file:
            return

        options = self._get_current_options()
        options["recording_date"] = options.pop("custom_metadata_date", "") or self.info.get("date")

        if options.get("autocrop_black"):
            self.status_var.set(t("autocrop_analyzing"))
            self.update_idletasks()
            options["autocrop_filter"] = detect_black_borders(path, self.info)

        use_vs = options.get("use_vapoursynth", False)
        if use_vs:
            try:
                vspipe_cmd, ffmpeg_cmd, script_path = build_vapoursynth_command(
                    path, output_file, width, height, self.info, options)
            except Exception as e:
                messagebox.showerror(t("vs_engine_error"), str(e))
                return
            run_args = ("vs", vspipe_cmd, ffmpeg_cmd)
        else:
            cmd = build_ffmpeg_command(path, output_file, width, height, self.info, options)
            run_args = ("ffmpeg", cmd, None)

        self.progress["value"] = 0
        self.status_var.set(t("processing", width=width, height=height))
        threading.Thread(target=self._run_ffmpeg,
                          args=(run_args, self.info["duration"], output_file, options, path),
                          daemon=True).start()

    # FROM HERE ON, ALL THESE METHODS ARE INDENTED INSIDE THE CLASS
    def _run_ffmpeg(self, run_args, duration, output, options, original_path):
        self.after(0, self._start_animation)
        mode, cmd_or_vspipe, ffmpeg_cmd_if_vs = run_args
        try:
            log_path = Path(tempfile.gettempdir()) / "dvtools_ffmpeg_error.log"
            if mode == "vs":
                # Run vspipe piped directly into ffmpeg; dvtools_vs.run_pipeline
                # returns the ffmpeg Popen object, whose stdout carries the same
                # "-progress pipe:1" lines the plain-ffmpeg path already parses,
                # so the progress-bar logic below is identical either way. It
                # opens/closes the log file internally.
                _vspipe_proc, process = dvtools_vs.run_pipeline(
                    cmd_or_vspipe, ffmpeg_cmd_if_vs, log_path)
                for line in process.stdout:
                    if line.startswith("out_time_ms=") and duration > 0:
                        try:
                            ms = int(line.strip().split("=")[1])
                            seconds = ms / 1_000_000
                            pct = min(100, (seconds / duration) * 100)
                            self.progress["value"] = pct
                            self.status_var.set(t("processing_pct", pct=pct))
                        except (ValueError, IndexError):
                            pass
                process.wait()
            else:
                with open(log_path, "w", encoding="utf-8", errors="replace") as log_f:
                    process = subprocess.Popen(cmd_or_vspipe, stdout=subprocess.PIPE,
                                                stderr=log_f, text=True)
                    for line in process.stdout:
                        if line.startswith("out_time_ms=") and duration > 0:
                            try:
                                ms = int(line.strip().split("=")[1])
                                seconds = ms / 1_000_000
                                pct = min(100, (seconds / duration) * 100)
                                self.progress["value"] = pct
                                self.status_var.set(t("processing_pct", pct=pct))
                            except (ValueError, IndexError):
                                pass
                    process.wait()

            if process.returncode == 0:
                self.progress["value"] = 100
                self.after(0, lambda: setattr(self, 'anim_should_stop', True))
                
                if self.scenes_var.get():
                    times = detect_scene_changes(original_path)
                    split_by_scenes(output, Path(output).parent, times, duration, options)
                
                notify_post_process(output, original_path, options)
                self.status_var.set(t("ready"))
                self.after(0, lambda: messagebox.showinfo(t("done_title"), t("done_msg", path=output)))
            else:
                self.after(0, self._stop_animation)
                self.status_var.set(t("error_read"))
                try:
                    log_text = log_path.read_text(encoding="utf-8", errors="replace")
                    last_lines = "\n".join(log_text.strip().splitlines()[-15:])
                except OSError:
                    last_lines = "(could not read the ffmpeg log)"
                self.after(0, lambda: messagebox.showerror(t("error_read"), f"ffmpeg (code {process.returncode}):\n\n{last_lines}"))
        except Exception as e:
            self.after(0, self._stop_animation)
            error_msg = str(e)
            self.status_var.set(t("error_read"))
            self.after(0, lambda: messagebox.showerror(t("error_read"), error_msg))

    def choose_folder(self):
        folder = filedialog.askdirectory(title=t("choose_folder"))
        if folder:
            self.folder_var.set(folder)

    def add_folder_to_queue(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            return
        exts = get_all_supported_extensions()
        found = sorted(
            [str(p) for p in Path(folder).rglob("*") 
             if p.suffix.lower() in exts])
        for path in found:
            if path not in self.file_queue:
                self.file_queue.append(path)
                self.table_queue.insert("", "end", iid=path,
                                        values=(Path(path).name, t("status_pending")))

    def clear_queue(self):
        self.file_queue = []
        self.queue_errors = {}
        for item in self.table_queue.get_children():
            self.table_queue.delete(item)

    def _show_queue_error(self, _event=None):
        selection = self.table_queue.selection()
        if not selection:
            return
        path = selection[0]
        error_text = (self.queue_errors.get(path) or "").strip()
        if not error_text:
            return
        last_lines = "\n".join(error_text.splitlines()[-20:])
        messagebox.showerror(Path(path).name, last_lines)

    def _on_queue_drag_start(self, event):
        self._drag_item = self.table_queue.identify_row(event.y)

    def _on_queue_drag_motion(self, event):
        if not self._drag_item:
            return
        target = self.table_queue.identify_row(event.y)
        if target and target != self._drag_item:
            self.table_queue.move(self._drag_item, "", self.table_queue.index(target))

    def _on_queue_drag_release(self, _event):
        if self._drag_item:
            # The Treeview's visual order becomes the actual processing
            # order of the queue (drag-to-prioritize).
            self.file_queue = list(self.table_queue.get_children(""))
        self._drag_item = None

    def process_queue(self):
        if not self.file_queue:
            messagebox.showinfo(t("tab_batch"), t("queue_empty"))
            return
        try:
            target_height = int(self.height_var.get())
        except ValueError:
            messagebox.showwarning(t("error_read"), t("error_height"))
            return

        out_folder = filedialog.askdirectory(title=t("save_as"))
        if not out_folder:
            return

        base_options = self._get_current_options()

        wait_idle = self.idle_wait_var.get() and is_system_idle_available()
        wait_schedule = self.scheduled_start_var.get()

        if wait_idle or wait_schedule:
            threading.Thread(target=self._wait_then_process_queue,
                              args=(list(self.file_queue), target_height,
                                    out_folder, base_options, wait_idle, wait_schedule),
                              daemon=True).start()
        else:
            threading.Thread(target=self._process_queue_thread,
                              args=(list(self.file_queue), target_height,
                                    out_folder, base_options),
                              daemon=True).start()

    def _next_datetime_for_time(self, hhmm):
        try:
            hh, mm = (int(x) for x in hhmm.strip().split(":"))
        except ValueError:
            return None
        now = datetime.now()
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    def _wait_then_process_queue(self, files, target_height, out_folder,
                                  base_options, wait_idle, wait_schedule):
        """Runs in a separate thread: waits for the scheduled time and/or
        for the system to be idle long enough, and only then starts
        actually processing the queue. Checks every 15 seconds so it
        doesn't waste CPU."""
        if wait_schedule:
            target_dt = self._next_datetime_for_time(self.scheduled_time_var.get())
            if target_dt:
                self.status_var.set(
                    t("queue_waiting_schedule", time=target_dt.strftime("%H:%M")))
                while datetime.now() < target_dt:
                    time.sleep(15)

        if wait_idle:
            try:
                idle_minutes = int(self.idle_minutes_var.get())
            except ValueError:
                idle_minutes = 5
            needed_seconds = idle_minutes * 60
            self.status_var.set(t("queue_waiting_idle", minutes=idle_minutes))
            while True:
                idle = get_system_idle_seconds()
                if idle is not None and idle >= needed_seconds:
                    break
                time.sleep(15)

        self._process_queue_thread(files, target_height, out_folder, base_options)

    def scan_dropouts_action(self):
        path = self.path_var.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning(t("error_read"), t("error_path"))
            return
        if not self.info:
            self._read_info(path)
            if not self.info:
                return

        self.list_dropouts.delete(0, "end")
        self.list_dropouts.insert("end", t("dropout_scanning"))
        self.btn_scan_dropouts.state(["disabled"])
        threading.Thread(target=self._run_dropout_scan, args=(path,), daemon=True).start()

    def _run_dropout_scan(self, path):
        events, error = detect_dropouts(path, self.info)

        def _show_results():
            self.btn_scan_dropouts.state(["!disabled"])
            self.list_dropouts.delete(0, "end")
            if error:
                self.list_dropouts.insert("end", t("dropout_error", error=error))
                return
            if not events:
                self.list_dropouts.insert("end", t("dropout_none_found"))
                return
            for ev in events:
                self.list_dropouts.insert("end", t(
                    "dropout_event",
                    start=_seconds_to_mmss(ev["start"]),
                    end=_seconds_to_mmss(ev["end"]),
                    severity=f'{ev["severity"] * 100:.0f}'))

        self.after(0, _show_results)

    def _process_queue_thread(self, files, target_height, out_folder, base_options):
        total = len(files)
        for i, path in enumerate(files, start=1):
            name = Path(path).name
            self.status_var.set(t("queue_processing", current=i, total=total, name=name))
            try:
                info = get_video_info(path)
                width, height = calculate_target_resolution(
                    info, target_height, self._get_forced_aspect())
                extension, _ = CONTAINERS[base_options["container"]]
                output = str(Path(out_folder) / (Path(path).stem + f"_{height}p{extension}"))
                options = dict(base_options)
                options["recording_date"] = options.get("custom_metadata_date") or info.get("date")
                if options.get("autocrop_black"):
                    options["autocrop_filter"] = detect_black_borders(path, info)
                if options.get("use_vapoursynth"):
                    vspipe_cmd, ffmpeg_cmd, _script = build_vapoursynth_command(
                        path, output, width, height, info, options)
                    process = dvtools_vs.run_pipeline_sync(vspipe_cmd, ffmpeg_cmd)
                else:
                    # NOTE: 'info' must be passed here, it was previously missing.
                    cmd = build_ffmpeg_command(path, output, width, height, info, options)
                    process = subprocess.run(cmd, capture_output=True, text=True)
                self.queue_errors[path] = process.stderr

                if process.returncode == 0:
                    if self.scenes_var.get():
                        times = detect_scene_changes(path)
                        split_by_scenes(output, out_folder, times,
                                             info["duration"], options)
                                             
                    notify_post_process(output, path, options)
                    self.table_queue.item(path, values=(name, t("status_done")))
                else:
                    self.table_queue.item(path, values=(name, t("status_error")))
            except Exception:
                self.table_queue.item(path, values=(name, t("status_error")))
            self.progress["value"] = (i / total) * 100
        self.status_var.set(t("queue_done", total=total))


# ----------------------------------------------------------------------
# CLI Mode
# ----------------------------------------------------------------------

def run_cli_mode():
    import argparse
    parser = argparse.ArgumentParser(description="DVtools: Scans and processes MiniDV tapes (.dv files)")
    parser.add_argument("--play", metavar="PATH", help="Open the .dv file directly with VLC")
    parser.add_argument("--upscale", metavar="PATH", help="Path of the .dv file to process")
    parser.add_argument("--batch", metavar="FOLDER", help="Process all matching .dv files in a folder")
    parser.add_argument("--height", type=int, default=1440, help="Target height in pixels configuration")
    parser.add_argument("--output", help="Output destination folder or file path template")
    parser.add_argument("--container", choices=list(CONTAINERS.keys()), default="MP4")
    parser.add_argument("--codec", choices=["h264", "h265", "av1", "prores", "vp9"], default="h264")
    parser.add_argument("--accel", choices=["auto", "nvenc", "amf", "qsv"], default="auto")
    parser.add_argument("--aspect", choices=["auto", "4:3", "16:9"], default="auto")
    parser.add_argument("--no-crop", action="store_true")
    parser.add_argument("--crop-px", type=int, default=8)
    parser.add_argument("--no-deinterlace", action="store_true")
    parser.add_argument("--no-noise", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--sharpen", action="store_true")
    parser.add_argument("--scenes", action="store_true")
    parser.add_argument("--vapoursynth", action="store_true",
                         help="Use the optional VapourSynth engine instead of ffmpeg's "
                              "built-in filters (requires VapourSynth + vspipe installed)")
    args = parser.parse_args()

    if args.vapoursynth and not dvtools_vs.is_available():
        print("Error: --vapoursynth was requested but VapourSynth (and/or vspipe) "
              "was not found on this system. Install it from vapoursynth.com.")
        sys.exit(1)

    dep_error = check_dependencies()
    if dep_error:
        print(dep_error)
        sys.exit(1)

    options = {
        "crop": not args.no_crop,
        "crop_px": args.crop_px,
        "deinterlace": not args.no_deinterlace,
        "noise_reduction": not args.no_noise,
        "color_restoration": not args.no_color,
        "sharpening": args.sharpen,
        "codec": args.codec,
        "container": args.container,
        "accel": args.accel,
        "copy_metadata": True,
        "use_vapoursynth": args.vapoursynth,
    }
    extension, _ = CONTAINERS[args.container]

    if args.play:
        play_with_vlc(args.play)
        return

    def process_single(path, output):
        info = get_video_info(path)
        width, height = calculate_target_resolution(info, args.height, args.aspect)
        local_options = dict(options)
        local_options["recording_date"] = info.get("date")
        # NOTE: 'info' must be passed positionally (build_ffmpeg_command's
        # signature is input, output, width, height, info, options).
        print(f"{Path(path).name}: {info['width']}x{info['height']} ({info['system']}) "
              f"-> {width}x{height}")
        if local_options.get("use_vapoursynth"):
            print("  (using VapourSynth engine)")
            vspipe_cmd, ffmpeg_cmd, _script = build_vapoursynth_command(
                path, output, width, height, info, local_options)
            dvtools_vs.run_pipeline_sync(vspipe_cmd, ffmpeg_cmd)
        else:
            cmd = build_ffmpeg_command(path, output, width, height, info, local_options)
            subprocess.run(cmd)
        if args.scenes:
            times = detect_scene_changes(path)
            split_by_scenes(output, Path(output).parent, times, info["duration"],
                                 local_options)
        
        notify_post_process(output, path, local_options)

        print(f"Done: {output}")

    if args.upscale:
        output = args.output or str(
            Path(args.upscale).with_name(Path(args.upscale).stem + f"_upscaled{extension}"))
        process_single(args.upscale, output)
        return

    if args.batch:
        out_folder = args.output or args.batch
        os.makedirs(out_folder, exist_ok=True)
        files = sorted(
            [str(p) for p in Path(args.batch).rglob("*") if p.suffix.lower() in (".dv", ".dif")])
        for path in files:
            output = str(Path(out_folder) / (Path(path).stem + f"_upscaled{extension}"))
            process_single(path, output)
        return

    parser.print_help()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli_mode()
    else:
        App().mainloop()