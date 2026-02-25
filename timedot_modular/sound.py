import platform
import threading

from .constants import SoundType

IS_WINDOWS = platform.system() == "Windows"
HAS_SOUND = False

if IS_WINDOWS:
    try:
        import winsound
        HAS_SOUND = True
    except ImportError:
        HAS_SOUND = False

def play_sound_by_type(sound_type):
    if not HAS_SOUND or sound_type == SoundType.Mute:
        return

    def _play_worker():
        try:
            if IS_WINDOWS:
                if sound_type == SoundType.Beep:
                    winsound.Beep(800, 150)
                elif sound_type == SoundType.Chime:
                    winsound.Beep(1200, 100)
                    winsound.Beep(1600, 300)
                elif sound_type == SoundType.Alert:
                    for _ in range(3):
                        winsound.Beep(1000, 100)
        except Exception:
            pass

    threading.Thread(target=_play_worker, daemon=True).start()
