import sys
import os

BASE_MARGIN = 16
SIDEBAR_WIDTH = 40
CALENDAR_HEIGHT = 30
GAP_WIDTH_NARROW = 14
GAP_WIDTH_WIDE = 36
HEADER_FULL_HEIGHT = 42
FOOTER_GAP = 25
MIN_CAL_STEP = 24
ARROW_MARGIN = 35
GEOMETRY_PADDING = 20

DEFAULT_CONFIG_VALUES = {
    'dot_radius': 5,
    'dot_spacing': 10,
    'note_dot_scale': 0.5,
    'font_size': 12,
    'calendar_font_size': 10,
    'font_weight': 500,
    'seg_base_offset': 5,
    'seg_layer_step': 6,
    'seg_bottom_margin': 0
}

class InteractionState:
    Idle = 0
    CreatingSegment = 1
    DraggingWindow = 2
    ResizingDayBounds = 3

class SoundType:
    Mute = 0
    Beep = 1
    Chime = 2
    Alert = 3

SOUND_NAMES = ["Mute", "Beep", "Chime", "Alert"]

SETTINGS_STYLESHEET = """
    QDialog { background-color: #2b2b2b; color: #f0f0f0; font-family: "Segoe UI", sans-serif; font-size: 13px; }
    QLabel { color: #cccccc; font-weight: 500; }
    QTimeEdit, QComboBox, QSpinBox { 
        background-color: #3a3a3a; color: white; border: 1px solid #555; 
        border-radius: 6px; padding: 4px 8px; min-height: 24px;
    }
    QTimeEdit:hover, QComboBox:hover { border-color: #777; }
    QTimeEdit::up-button, QTimeEdit::down-button { width: 0px; }
    QSlider::groove:horizontal { border: 1px solid #3a3a3a; height: 6px; background: #3a3a3a; margin: 2px 0; border-radius: 3px; }
    QSlider::handle:horizontal { background: #5a90e2; border: 1px solid #5a90e2; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
    QSlider::handle:horizontal:hover { background: #6aa0f2; }
    QPushButton { 
        background-color: #444; color: white; border: 1px solid #555; 
        border-radius: 6px; padding: 6px 16px; font-weight: bold;
    }
    QPushButton:hover { background-color: #555; border-color: #777; }
    QPushButton:pressed { background-color: #333; }
    QPushButton#PrimaryBtn { background-color: #4a90e2; border-color: #4a90e2; }
    QPushButton#PrimaryBtn:hover { background-color: #5a9bef; border-color: #5a9bef; }
    QFrame#SectionFrame { background-color: #333; border-radius: 8px; border: 1px solid #444; }
"""

GLOBAL_STYLESHEET = """
    QMenu { background-color: #2b2b2b; border: 1px solid #555; border-radius: 6px; padding: 4px; }
    QMenu::item { color: #e0e0e0; padding: 6px 24px; background-color: transparent; border-radius: 4px; }
    QMenu::item:selected { background-color: #4a90e2; color: white; }
    QMenu::separator { height: 1px; background: #555; margin: 4px 0; }
"""

def get_config_path():
    if getattr(sys, "frozen", False):
        application_path = os.path.dirname(sys.executable)
    else:
        package_dir = os.path.dirname(os.path.abspath(__file__))
        application_path = os.path.dirname(package_dir)
    return os.path.join(application_path, "config.json")

CONFIG_FILE = get_config_path()
