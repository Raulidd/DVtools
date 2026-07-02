# plugins/formatos_extra.py
def register_plugin():
    return {
        "name": "Formats+ - New Formats for DVtools",
        "version": "1.0",
        "author": "DVtools",
        "type": "extension_provider"
    }

def register_extensions():
    """
    Returns a list of file extensions (with the dot) that the program
    will be able to read in the file selector and in batch processing.
    """
    return [
        ".m2t", ".mts",      # HDV (MiniDV HD camcorders)
        ".avi", ".mov",      # Analog captures (VHS/Hi8)
        ".mpg", ".mpeg",     # DVD / MPEG-2
        ".vob",              # DVD files
        ".mp4", ".mkv",      # Modern formats
        ".webm",             # For the web
        ".wav", ".flac"      # Audio only (in case you want to improve the soundtrack)
    ]