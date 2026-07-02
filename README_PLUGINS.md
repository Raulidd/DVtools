DVtools - Plugin Creation Guide :p
========================================

1. WHAT IS A PLUGIN?
A plugin is a Python file (.py) that adds extra features to DVtools. 
You can add visual filters, change audio settings, or make the program do 
something after the video is saved.

2. WHERE DO I PUT MY PLUGIN?
Put your .py file in one of these two folders:
- The "plugins" folder (next to the dvtools_windows.exe)
- Or the user folder: C:\Users\YOUR_USERNAME\.dvtools\plugins

2.5. ENABLING / DISABLING PLUGINS FROM THE APP
The Plugins tab lists every plugin DVtools found, with a checkbox column
on the left. Clicking it enables or disables that plugin immediately --
no restart needed. While disabled, none of your plugin's hooks
(modify_filters, execute_post, modify_command, on_file_loaded/on_event,
modify_vs_clip, register_extensions) get called, as if the plugin
weren't loaded at all; build_gui() still renders its options panel so
the user can configure it ahead of re-enabling it. This on/off state is
saved to config.txt when the app closes and restored the next time it
opens, along with every other DVtools setting.

3. THE MINIMUM CODE FOR A PLUGIN
Every plugin must have this function. Copy and paste this as a template:

-----------------------------------------------------------
# my_plugin.py
def register_plugin():
    return {
        "name": "My Cool Plugin",
        "version": "1.0",
        "author": "Your Name",
        "type": "video_filter"   # (Optional)
    }
-----------------------------------------------------------

4. HOW TO ADD CHECKBOXES AND SLIDERS (Build GUI)
If your plugin needs settings, add this function:

-----------------------------------------------------------
def build_gui(parent):
    import tkinter as tk
    from tkinter import ttk
    
    # Add a checkbox
    my_checkbox = tk.BooleanVar(value=False)
    ttk.Checkbutton(parent, text="Enable my effect", variable=my_checkbox).pack()
-----------------------------------------------------------

5. HOW TO CHANGE THE VIDEO (MODIFY FILTERS)
This is the most common function. It adds effects to the video.
Return the list of filters back to the program.

-----------------------------------------------------------
def modify_filters(filters, options, info):
    # This is how you add a saturation effect:
    filters.append("eq=saturation=2.0")
    
    # This is how you add a VHS noise effect:
    filters.append("noise=c0s=20:allf=t")
    
    # Always return the list!
    return filters
-----------------------------------------------------------

6. HOW TO CHANGE THE COMMAND (MODIFY COMMAND)
This lets you change audio codecs, bitrates, or advanced FFmpeg settings.

-----------------------------------------------------------
def modify_command(cmd, options):
    # Example: Change audio to mono with low quality
    cmd[-1:-1] = ["-c:a", "aac", "-ac", "1", "-b:a", "96k"]
    return cmd
-----------------------------------------------------------

7. HOW TO RUN CODE AFTER RENDERING (POST PROCESS)
This runs after the video is saved successfully.

-----------------------------------------------------------
def execute_post(output_path, original_path, options):
    from pathlib import Path
    log_file = Path(output_path).with_suffix(".log")
    with open(log_file, "w") as f:
        f.write("Video saved!\n")
-----------------------------------------------------------

8. HOW TO REACT TO EVENTS (ON_EVENT)
You can make the plugin react when a file is loaded or when the video finishes.

-----------------------------------------------------------
def on_event(event_name, data):
    if event_name == "on_file_loaded":
        print("File loaded:", data["path"])
    elif event_name == "on_process_complete":
        print("Video saved to:", data["output"])
-----------------------------------------------------------

9. FULL EXAMPLE PLUGIN (Copy this to test)
Create a file "saturation_plugin.py" in the "plugins" folder and paste this:

-----------------------------------------------------------
# saturation_plugin.py
import tkinter as tk
from tkinter import ttk

saturation_level = None

def register_plugin():
    return {"name": "Color Booster", "version": "1.0", "author": "User"}

def build_gui(parent):
    global saturation_level
    saturation_level = tk.DoubleVar(value=2.0)
    ttk.Scale(parent, from_=1.0, to=5.0, variable=saturation_level).pack()

def modify_filters(filters, options, info):
    if saturation_level and saturation_level.get() > 1.0:
        filters.append(f"eq=saturation={saturation_level.get()}")
    return filters
-----------------------------------------------------------

9.5. HOW TO HOOK INTO THE VAPOURSYNTH ENGINE (OPTIONAL, ADVANCED)
If the user has the optional VapourSynth engine installed and enabled
("Use VapourSynth engine" checkbox in the Advanced tab), you can add a
filter directly to the VapourSynth clip instead of (or in addition to)
modify_filters(). This runs LAST in the VapourSynth pipeline, after
DVtools' own crop/deinterlace/denoise/stabilize/color/sharpen steps and
BEFORE the final resize.

-----------------------------------------------------------
def modify_vs_clip(clip, options, info, vs_core):
    # 'vs_core' is VapourSynth's core object (same as calling
    # vapoursynth.core inside a normal .vpy script).
    # Wrap anything that depends on an optional VapourSynth plugin in a
    # try/except, the same way DVtools' own built-in filters do, so your
    # plugin doesn't crash on machines that don't have that plugin.
    try:
        clip = vs_core.grain.Add(clip, var=2.0)
    except AttributeError:
        pass
    return clip
-----------------------------------------------------------

Notes:
- This hook is ONLY called when the user has both VapourSynth installed
  AND the "Use VapourSynth engine" checkbox enabled. If either is missing,
  DVtools uses its normal ffmpeg pipeline and modify_filters() instead, so
  it's a good idea to implement both hooks if your plugin does video
  filtering, or clearly document that your plugin needs VapourSynth.
- Unlike modify_filters(), this function runs inside a freshly generated
  .vpy script executed by a separate "vspipe" process, not inside the main
  DVtools process. Avoid referencing global GUI state (e.g. a Tkinter
  BooleanVar from build_gui()) directly inside modify_vs_clip -- read the
  current value into a plain Python type (int/float/str/bool) in
  modify_filters() or on_event() instead, and pass it through the
  'options' dict if you need it here.

10. FINAL TIPS
- You can use ANY Python library inside a plugin.
- If you use external libraries (like "requests" or "Pillow"), the user must 
  install them with "pip install library_name".
- Keep your plugins simple. One plugin = one feature.
- Your plugin works on Windows, macOS, and Linux without changes!

that's the basics i guess