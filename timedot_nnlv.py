import sys
import json
import os
import math
import platform
import threading
import copy
from datetime import datetime, time, timedelta
from PyQt6.QtWidgets import (QApplication, QWidget, QMenu, QDialog, QVBoxLayout, 
                             QHBoxLayout, QLabel, QTimeEdit, QComboBox, QSlider, 
                             QPushButton, QColorDialog, QSystemTrayIcon, QToolTip,
                             QFormLayout, QFrame, QTextEdit, QScrollArea, 
                             QSpinBox, QDoubleSpinBox, QStyle)
from PyQt6.QtCore import (Qt, QTimer, QPoint, QRect, QRectF, QPropertyAnimation, 
                          pyqtProperty, QEasingCurve, QPointF, QSize, QDate, QVariantAnimation)
from PyQt6.QtGui import (QPainter, QBrush, QColor, QAction, QMouseEvent, QWheelEvent,
                         QCursor, QIcon, QPixmap, QFont, QPen, QPainterPath, QFontMetrics, QGuiApplication, QRegion)

# --- 常量定义 ---
BASE_MARGIN = 16       
SIDEBAR_WIDTH = 40     
CALENDAR_HEIGHT = 30   
GAP_WIDTH_NARROW = 14  # 虚线处的紧凑间距
GAP_WIDTH_WIDE = 36    # 整点数字处的宽敞间距   
HEADER_FULL_HEIGHT = 42 
FOOTER_GAP = 25        
MIN_CAL_STEP = 24      
ARROW_MARGIN = 35      
# [核心] 这里的 Padding 必须足够大，容纳圆角、阴影以及布局计算的微小误差
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

# --- 系统环境检测 ---
IS_WINDOWS = platform.system() == "Windows"
HAS_SOUND = False

if IS_WINDOWS:
    try:
        import winsound
        HAS_SOUND = True
    except ImportError:
        HAS_SOUND = False

def get_config_path():
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(application_path, 'config.json')

CONFIG_FILE = get_config_path()

class InteractionState:
    Idle = 0
    CreatingSegment = 1 
    DraggingWindow = 2   

class SoundType:
    Mute = 0
    Beep = 1
    Chime = 2
    Alert = 3

SOUND_NAMES = ["无 (Mute)", "短促 (Beep)", "清脆 (Chime)", "警报 (Alert)"]

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

def play_sound_by_type(sound_type):
    if not HAS_SOUND or sound_type == SoundType.Mute: return
    def _play_worker():
        try:
            if IS_WINDOWS:
                if sound_type == SoundType.Beep: winsound.Beep(800, 150)
                elif sound_type == SoundType.Chime: 
                    winsound.Beep(1200, 100); winsound.Beep(1600, 300)
                elif sound_type == SoundType.Alert:
                    for i in range(3): winsound.Beep(1000, 100)
        except: pass
    threading.Thread(target=_play_worker, daemon=True).start()

class OverlayTooltip(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.text = text
        self.font = QFont("Segoe UI", 10)
        fm = QFontMetrics(self.font)
        self.text_rect = fm.boundingRect(QRect(0,0,300,100), Qt.TextFlag.TextWordWrap, self.text)
        self.w = self.text_rect.width() + 20
        self.h = self.text_rect.height() + 16
        self.resize(self.w, self.h)

    def paintEvent(self, event):
        pt = QPainter(self)
        pt.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1,1,-1,-1)
        pt.setBrush(QBrush(QColor(255, 255, 255)))
        pt.setPen(QPen(QColor(200, 200, 200), 1))
        pt.drawRoundedRect(rect, 8, 8)
        pt.setFont(self.font)
        pt.setPen(QColor(30, 30, 30))
        pt.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)

class EditPopup(QDialog):
    def __init__(self, parent=None, initial_color=None, initial_text="", default_color=None, on_save=None, on_delete=None, on_live_change=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.on_save = on_save
        self.on_delete = on_delete
        self.on_live_change = on_live_change
        self.selected_color = initial_color if initial_color else (default_color if default_color else QColor(255, 255, 255))
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0,0,0,0)
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #2b2b2b; border-radius: 8px; border: 1px solid #555; }")
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        
        colors = [
            QColor(255, 80, 80), QColor(255, 160, 80), QColor(255, 220, 80),
            QColor(100, 220, 100), QColor(80, 180, 255), QColor(160, 100, 255),
            QColor(255, 100, 200), QColor(255, 255, 255)
        ]
        self.color_btns = []
        color_layout = QHBoxLayout()
        for col in colors:
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setProperty("color_val", col)
            btn.clicked.connect(lambda _, c=col: self.set_color(c))
            color_layout.addWidget(btn)
            self.color_btns.append(btn)
        layout.addLayout(color_layout)
        self.update_color_btns() 
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("添加备注 (可选)...")
        self.text_edit.setText(initial_text)
        self.text_edit.setFixedHeight(60)
        self.text_edit.setStyleSheet("QTextEdit { color: white; background-color: #444; border: 1px solid #555; border-radius: 4px; padding: 4px; }") 
        self.text_edit.textChanged.connect(self.handle_live_change)
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        del_btn = QPushButton("删除")
        del_btn.setStyleSheet("QPushButton { background-color: #444; color: #ff6666; border: 1px solid #555; border-radius: 4px; } QPushButton:hover { background-color: #555; }")
        del_btn.clicked.connect(self.handle_delete)
        save_btn = QPushButton("确定")
        save_btn.setStyleSheet("QPushButton { background-color: #4a90e2; color: white; border: none; border-radius: 4px; font-weight: bold; } QPushButton:hover { background-color: #5a9bef; }")
        save_btn.clicked.connect(self.handle_save)
        btn_layout.addWidget(del_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
        main_layout.addWidget(frame)
        self.setLayout(main_layout)
        
    def set_color(self, color):
        self.selected_color = color
        self.update_color_btns()
        self.handle_live_change()
        
    def update_color_btns(self):
        for btn in self.color_btns:
            c = btn.property("color_val")
            style = f"background-color: {c.name()}; border-radius: 12px;"
            if c == self.selected_color: style += "border: 2px solid white;" 
            else: style += "border: none;"
            btn.setStyleSheet(style)

    def handle_live_change(self):
        if self.on_live_change: self.on_live_change(self.selected_color, self.text_edit.toPlainText())
    def handle_save(self):
        if self.on_save: self.on_save(self.selected_color, self.text_edit.toPlainText())
        self.accept()
    def handle_delete(self):
        if self.on_delete: self.on_delete()
        self.reject()
    def showEvent(self, event):
        super().showEvent(event)
        self.text_edit.setFocus()
        screen = QGuiApplication.screenAt(self.geometry().center())
        if not screen: screen = QGuiApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        geo = self.geometry()
        new_x, new_y = geo.x(), geo.y()
        if geo.right() > screen_geo.right(): new_x = screen_geo.right() - geo.width() - 10
        if geo.left() < screen_geo.left(): new_x = screen_geo.left() + 10
        if geo.bottom() > screen_geo.bottom(): new_y = screen_geo.bottom() - geo.height() - 10
        if geo.top() < screen_geo.top(): new_y = screen_geo.top() + 10
        self.move(new_x, new_y)

class QuickSelector(QWidget):
    def __init__(self, parent, items, current_val, on_select):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.items = items
        self.on_select = on_select
        self.current_val = current_val
        
        # 布局计算
        self.item_height = 36
        self.w = 120
        self.h = len(items) * self.item_height + 10 # +padding
        self.resize(self.w, self.h)
        
        # 动画容器
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(200)
        self.opacity_anim.setEasingCurve(QEasingCurve.Type.OutQuad)

    def show_at(self, global_pos):
        # 调整位置，使其右对齐
        x = global_pos.x() - self.w
        y = global_pos.y() + 10
        self.move(x, y)
        self.setWindowOpacity(0.0)
        self.show()
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.start()

    def paintEvent(self, event):
        pt = QPainter(self)
        pt.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景
        bg_rect = self.rect().adjusted(1, 1, -1, -1)
        pt.setBrush(QBrush(QColor(28, 28, 30, 250))) # iOS Secondary Background
        pt.setPen(QPen(QColor(60, 60, 60), 1))
        pt.drawRoundedRect(bg_rect, 12, 12)
        
        # 绘制选项
        f = pt.font()
        f.setPixelSize(14)
        f.setBold(True)
        pt.setFont(f)
        
        mouse_pos = self.mapFromGlobal(QCursor.pos())
        
        for i, val in enumerate(self.items):
            rect = QRectF(1, 5 + i * self.item_height, self.w - 2, self.item_height)
            
            # Hover 效果
            if rect.contains(QPointF(mouse_pos)):
                pt.setBrush(QBrush(QColor(255, 255, 255, 30)))
                pt.setPen(Qt.PenStyle.NoPen)
                pt.drawRoundedRect(rect.adjusted(4, 2, -4, -2), 6, 6)
            
            # 文字与选中状态
            is_selected = (val == self.current_val)
            color = QColor(10, 132, 255) if is_selected else QColor(220, 220, 220)
            pt.setPen(color)
            
            # 绘制圆点示意 (左侧)
            dot_cx = rect.left() + 20
            dot_cy = rect.center().y()
            pt.setBrush(QBrush(color))
            pt.setPen(Qt.PenStyle.NoPen)
            pt.drawEllipse(QPointF(dot_cx, dot_cy), 3, 3)
            
            # 绘制文字
            pt.setPen(color)
            text_rect = rect.adjusted(35, 0, -10, 0)
            pt.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"{val} min")

    def mousePressEvent(self, event):
        y = event.pos().y() - 5
        idx = y // self.item_height
        if 0 <= idx < len(self.items):
            val = self.items[int(idx)]
            self.on_select(val)
            self.close()
            
    def mouseMoveEvent(self, event):
        self.update() # 刷新 Hover 效果

class SettingsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("设置")
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.resize(450, 800) # 稍微加宽一点以容纳左侧的重置按钮
        
        self.original_config = copy.deepcopy(main_window.config)
        self.settings = main_window.config 
        
        self.dragging = False
        self.drag_start_pos = QPoint()

        self.init_ui()

    def paintEvent(self, event):
        pt = QPainter(self)
        pt.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景
        bg_rect = self.rect()
        pt.setBrush(QBrush(QColor(0, 0, 0))) 
        pt.setPen(QPen(QColor(50, 50, 50), 1))
        pt.drawRoundedRect(bg_rect, 18, 18)
        
        # 标题栏
        header_height = 54
        header_rect = QRect(0, 0, self.width(), header_height)
        pt.setBrush(QBrush(QColor(28, 28, 30, 255)))
        pt.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.addRoundedRect(QRectF(header_rect), 18, 18)
        rect_bottom = QRectF(0, header_height/2, self.width(), header_height/2)
        path.addRect(rect_bottom)
        pt.drawPath(path)
        
        pt.setPen(QPen(QColor(56, 56, 58), 1))
        pt.drawLine(0, header_height, self.width(), header_height)
        
        pt.setPen(QColor(255, 255, 255))
        f = pt.font()
        f.setBold(True)
        f.setPixelSize(17)
        pt.setFont(f)
        pt.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, "设置")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.pos().y() < 60:
            self.dragging = True
            self.drag_start_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 54, 0, 0)
        
        # 顶部按钮容器
        nav_overlay = QWidget(self)
        nav_overlay.setGeometry(0, 0, self.width(), 54)
        nav_layout = QHBoxLayout(nav_overlay)
        nav_layout.setContentsMargins(12, 0, 12, 0)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("NavBtn")
        cancel_btn.clicked.connect(self.cancel)
        
        save_btn = QPushButton("完成")
        save_btn.setObjectName("NavBtnDone")
        save_btn.clicked.connect(self.save_and_close)
        
        nav_layout.addWidget(cancel_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(save_btn)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 0px; background: transparent; }
            QWidget#ScrollContent { background: transparent; }
        """)
        
        content_widget = QWidget()
        content_widget.setObjectName("ScrollContent")
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setSpacing(24)
        self.content_layout.setContentsMargins(16, 20, 16, 40)
        
        self.setStyleSheet("""
            /* iOS 风格基础样式 */
            QFrame#GroupFrame { background-color: #1C1C1E; border-radius: 12px; }
            QLabel#GroupHeader { color: #8E8E93; font-size: 13px; text-transform: uppercase; margin-left: 12px; margin-bottom: 4px; }
            QLabel { color: #FFFFFF; font-size: 16px; }
            QFrame#Separator { background-color: #38383A; max-height: 1px; }
            
            /* 导航按钮 */
            QPushButton#NavBtn { background-color: transparent; border: none; color: #0A84FF; font-size: 16px; }
            QPushButton#NavBtnDone { background-color: transparent; border: none; color: #0A84FF; font-size: 16px; font-weight: bold; }
            QPushButton#NavBtn:hover, QPushButton#NavBtnDone:hover { opacity: 0.7; }
            
            /* 输入控件 */
            QComboBox, QTimeEdit, QSpinBox, QDoubleSpinBox {
                background-color: rgba(118, 118, 128, 0.24); color: #0A84FF;
                border: none; border-radius: 6px; padding: 4px 8px; font-size: 16px;
                min-width: 60px; max-width: 90px;
                selection-background-color: #0A84FF;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button, QTimeEdit::up-button, QTimeEdit::down-button { width: 0px; }
            
            /* 单项重置按钮 (小圆圈箭头) */
            QPushButton#ItemResetBtn {
                background-color: transparent;
                color: #555;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 10px;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
                padding: 0px;
            }
            QPushButton#ItemResetBtn:hover {
                color: #FF453A; /* 悬停变红 */
                background-color: rgba(255, 69, 58, 0.1);
            }
            
            /* 全局重置按钮 */
            QPushButton#ResetBtn {
                background-color: #1C1C1E; color: #FF453A; font-size: 16px;
                border-radius: 12px; padding: 12px; border: none;
            }
            QPushButton#ResetBtn:pressed { background-color: #2C2C2E; }
        """)

        # --- 1. 时间配置 ---
        self.add_group_header("TIME SETTINGS")
        time_group = self.create_group_container()
        tg_layout = QVBoxLayout(time_group)
        tg_layout.setSpacing(0); tg_layout.setContentsMargins(0,0,0,0)
        
        self.start_edit = QTimeEdit(self.settings['start_time'])
        self.end_edit = QTimeEdit(self.settings['end_time'])
        self.start_edit.setDisplayFormat("HH:mm"); self.end_edit.setDisplayFormat("HH:mm")
        
        self.row_dur_combo = QComboBox()
        self.row_dur_combo.addItems(["30m", "1h", "2h", "3h"])
        idx = {30:0, 60:1, 120:2, 180:3}.get(self.settings['row_duration'], 1)
        self.row_dur_combo.setCurrentIndex(idx)
        
        self.interval_combo = QComboBox() 
        
        self.add_row(tg_layout, "开始时间", self.start_edit)
        self.add_separator(tg_layout)
        self.add_row(tg_layout, "结束时间", self.end_edit)
        self.add_separator(tg_layout)
        self.add_row(tg_layout, "每行时长", self.row_dur_combo)
        self.add_separator(tg_layout)
        # [修改] 名字改为 分钟/点
        self.add_row(tg_layout, "分钟/点", self.interval_combo, is_last=True)
        
        self.content_layout.addWidget(time_group)

        # --- 2. 视觉外观 ---
        self.add_group_header("APPEARANCE")
        vis_group = self.create_group_container()
        vg_layout = QVBoxLayout(vis_group)
        vg_layout.setSpacing(0); vg_layout.setContentsMargins(0,0,0,0)

        self.dot_size_spin = self.create_spinbox(1, 100, self.settings.get('dot_radius', 6))
        self.dot_space_spin = self.create_spinbox(0, 200, self.settings.get('dot_spacing', 8))
        
        self.note_scale_spin = QDoubleSpinBox()
        self.note_scale_spin.setRange(0.1, 5.0)
        self.note_scale_spin.setSingleStep(0.1)
        self.note_scale_spin.setValue(self.settings.get('note_dot_scale', 0.4))
        self.note_scale_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.note_scale_spin.setFixedWidth(70)

        self.font_size_spin = self.create_spinbox(5, 100, self.settings.get('font_size', 11))
        self.cal_font_spin = self.create_spinbox(5, 100, self.settings.get('calendar_font_size', 8))
        self.font_weight_spin = self.create_spinbox(100, 900, self.settings.get('font_weight', 700), step=100)
        
        # [核心] 使用 key 参数来自动添加左侧重置按钮
        self.add_row(vg_layout, "点的大小", self.dot_size_spin, key='dot_radius')
        self.add_separator(vg_layout)
        self.add_row(vg_layout, "点间距", self.dot_space_spin, key='dot_spacing')
        self.add_separator(vg_layout)
        self.add_row(vg_layout, "Note点比例", self.note_scale_spin, key='note_dot_scale')
        self.add_separator(vg_layout)
        self.add_row(vg_layout, "时间字体", self.font_size_spin, key='font_size')
        self.add_separator(vg_layout)
        self.add_row(vg_layout, "日历字体", self.cal_font_spin, key='calendar_font_size')
        self.add_separator(vg_layout)
        self.add_row(vg_layout, "字体粗细", self.font_weight_spin, key='font_weight', is_last=True)
        
        self.content_layout.addWidget(vis_group)

        # --- 3. Segment 布局 ---
        self.add_group_header("SEGMENT LAYOUT")
        seg_group = self.create_group_container()
        sg_layout = QVBoxLayout(seg_group)
        sg_layout.setSpacing(0); sg_layout.setContentsMargins(0,0,0,0)
        
        self.seg_offset_spin = self.create_spinbox(-50, 100, self.settings.get('seg_base_offset', 6))
        self.seg_step_spin = self.create_spinbox(0, 100, self.settings.get('seg_layer_step', 12))
        self.seg_margin_spin = self.create_spinbox(-50, 100, self.settings.get('seg_bottom_margin', 8))
        
        self.add_row(sg_layout, "起点偏移 (A)", self.seg_offset_spin, key='seg_base_offset')
        self.add_separator(sg_layout)
        self.add_row(sg_layout, "层级间距 (B)", self.seg_step_spin, key='seg_layer_step')
        self.add_separator(sg_layout)
        self.add_row(sg_layout, "底部留白 (C)", self.seg_margin_spin, key='seg_bottom_margin', is_last=True)
        self.content_layout.addWidget(seg_group)

        # --- 4. 颜色与反馈 ---
        self.add_group_header("COLORS & SOUNDS")
        sc_group = self.create_group_container()
        sc_layout = QVBoxLayout(sc_group)
        sc_layout.setSpacing(0); sc_layout.setContentsMargins(0,0,0,0)
        
        self.sound_timer = QComboBox(); self.sound_timer.addItems(SOUND_NAMES)
        self.sound_timer.setCurrentIndex(self.settings.get('sound_timer', 2))
        self.sound_note = QComboBox(); self.sound_note.addItems(SOUND_NAMES)
        self.sound_note.setCurrentIndex(self.settings.get('sound_note', 1))
        
        self.bg_btn = self.create_col_btn('bg_color')
        self.curr_btn = self.create_col_btn('current_color')
        self.cal_btn = self.create_col_btn('calendar_today_color')
        self.past_btn = self.create_col_btn('past_date_color')
        self.future_btn = self.create_col_btn('future_date_color')

        self.add_row(sc_layout, "计时结束音", self.sound_timer)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "Note到达音", self.sound_note)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "背景颜色", self.bg_btn)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "进行中颜色", self.curr_btn)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "今天颜色", self.cal_btn)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "过去日期", self.past_btn)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "未来日期", self.future_btn, is_last=True)
        
        self.content_layout.addWidget(sc_group)
        
        # --- 全局重置 ---
        reset_btn = QPushButton("恢复默认设置")
        reset_btn.setObjectName("ResetBtn")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self.reset_to_defaults)
        self.content_layout.addWidget(reset_btn)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
        
        self.update_interval() # 初始化间隔下拉框
        self.connect_signals()

    # --- 辅助构建函数 ---
    def create_group_container(self):
        frame = QFrame()
        frame.setObjectName("GroupFrame")
        return frame
    
    def add_group_header(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("GroupHeader")
        self.content_layout.addWidget(lbl)

    def create_item_reset_btn(self, key, widget):
        # 创建一个小的重置按钮
        btn = QPushButton("↺") # 使用Unicode回旋箭头作为图标
        btn.setObjectName("ItemResetBtn")
        btn.setToolTip("重置此项")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        def reset_action():
            default_val = DEFAULT_CONFIG_VALUES.get(key)
            if default_val is not None:
                # 根据控件类型设置值
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.setValue(default_val)
                # 如果未来支持其他类型(如ComboBox)的单项重置，可在这里扩展
        
        btn.clicked.connect(reset_action)
        return btn

    def add_row(self, layout, label_text, widget, key=None, is_last=False):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        # 左边距给大一点，如果加了重置按钮，视觉上会占用左边距空间
        row_layout.setContentsMargins(16, 12, 16, 12) 
        
        # 如果提供了 key 且该 key 有默认值，则添加左侧重置按钮
        if key and key in DEFAULT_CONFIG_VALUES:
            reset_btn = self.create_item_reset_btn(key, widget)
            row_layout.addWidget(reset_btn)
            # 加一点点间距让按钮和文字分开
            row_layout.addSpacing(4)
        
        lbl = QLabel(label_text)
        row_layout.addWidget(lbl)
        row_layout.addStretch() 
        row_layout.addWidget(widget)
        
        layout.addWidget(row_widget)
    
    def add_separator(self, layout):
        sep_container = QWidget()
        sep_layout = QHBoxLayout(sep_container)
        # 分割线左侧留白：如果有重置按钮，分割线应该从文字开始，还是通栏？
        # iOS 通常是文字对齐。我们设为 50px 大概对齐文字
        sep_layout.setContentsMargins(50, 0, 0, 0) 
        sep_layout.setSpacing(0)
        line = QFrame()
        line.setObjectName("Separator")
        line.setFixedHeight(1)
        sep_layout.addWidget(line)
        layout.addWidget(sep_container)

    def create_spinbox(self, min_v, max_v, val, step=1):
        s = QSpinBox()
        s.setRange(min_v, max_v)
        s.setValue(val)
        s.setSingleStep(step)
        s.setAlignment(Qt.AlignmentFlag.AlignRight)
        s.setFixedWidth(70) 
        return s
    
    def create_col_btn(self, key):
        btn = QPushButton()
        btn.setFixedSize(28, 28)
        col = self.settings.get(key, QColor(255,255,255))
        self.style_col_btn(btn, col)
        btn.clicked.connect(lambda: self.pick_col(key, btn))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn
    
    def style_col_btn(self, btn, col):
        btn.setStyleSheet(f"""
            QPushButton {{ 
                background-color: {col.name()}; 
                border-radius: 14px; 
                border: 1px solid #555;
            }}
            QPushButton:hover {{ border: 1px solid white; }}
        """)

    def connect_signals(self):
        self.start_edit.timeChanged.connect(self.sync_settings)
        self.end_edit.timeChanged.connect(self.sync_settings)
        self.row_dur_combo.currentIndexChanged.connect(self.sync_settings)
        self.row_dur_combo.currentIndexChanged.connect(self.update_interval)
        self.interval_combo.currentIndexChanged.connect(self.sync_settings)
        
        self.dot_size_spin.valueChanged.connect(self.sync_settings)
        self.dot_space_spin.valueChanged.connect(self.sync_settings)
        self.note_scale_spin.valueChanged.connect(self.sync_settings)
        self.font_size_spin.valueChanged.connect(self.sync_settings)
        self.cal_font_spin.valueChanged.connect(self.sync_settings)
        self.font_weight_spin.valueChanged.connect(self.sync_settings)
        
        self.seg_offset_spin.valueChanged.connect(self.sync_settings)
        self.seg_step_spin.valueChanged.connect(self.sync_settings)
        self.seg_margin_spin.valueChanged.connect(self.sync_settings)
        
        self.sound_timer.currentIndexChanged.connect(self.sync_settings)
        self.sound_note.currentIndexChanged.connect(self.sync_settings)

    def reset_to_defaults(self):
        defaults = DEFAULT_CONFIG_VALUES
        self.dot_size_spin.setValue(defaults['dot_radius'])
        self.dot_space_spin.setValue(defaults['dot_spacing'])
        self.note_scale_spin.setValue(defaults['note_dot_scale'])
        self.font_size_spin.setValue(defaults['font_size'])
        self.cal_font_spin.setValue(defaults['calendar_font_size'])
        self.font_weight_spin.setValue(defaults['font_weight'])
        self.seg_offset_spin.setValue(defaults['seg_base_offset'])
        self.seg_step_spin.setValue(defaults['seg_layer_step'])
        self.seg_margin_spin.setValue(defaults['seg_bottom_margin'])
        self.sync_settings()

    def update_interval(self):
        # [核心修复] 初始化时，先获取当前配置中的真实 interval 值
        current_config_val = self.settings.get('interval', 10)
        
        idx = self.row_dur_combo.currentIndex()
        rm = [30, 60, 120, 180][idx]
        opts = [5, 10, 15, 30] 
        valid = [str(x) for x in opts if x <= rm and rm % x == 0]
        if not valid: valid = ["10"]
        
        self.interval_combo.blockSignals(True)
        self.interval_combo.clear()
        self.interval_combo.addItems(valid)
        
        # 尝试在新的列表中找到配置的值
        target_text = str(current_config_val)
        idx = self.interval_combo.findText(target_text)
        
        if idx >= 0:
            self.interval_combo.setCurrentIndex(idx)
        else:
            self.interval_combo.setCurrentIndex(0) # 如果当前值不合法，才回退到默认
            
        self.interval_combo.blockSignals(False)
        
        # 只有当值真的变了才写回，避免初始化就覆盖
        if self.interval_combo.currentText():
            new_val = int(self.interval_combo.currentText())
            if new_val != current_config_val:
                self.settings['interval'] = new_val

    def pick_col(self, k, btn):
        dlg = QColorDialog(self.settings[k], self)
        dlg.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel)
        dlg.setStyleSheet("""
            QDialog { background-color: #2C2C2E; color: white; }
            QLabel { color: white; }
            QPushButton { background-color: #3A3A3C; color: white; border: none; padding: 5px; border-radius: 4px; }
            QPushButton:hover { background-color: #4A4A4C; }
            QSpinBox { background-color: #1C1C1E; color: white; border: 1px solid #555; }
        """)
        if dlg.exec():
            c = dlg.selectedColor()
            if c.isValid():
                self.settings[k] = c
                self.style_col_btn(btn, c)
                self.sync_settings()

    def sync_settings(self):
        self.settings['start_time'] = self.start_edit.time().toPyTime()
        self.settings['end_time'] = self.end_edit.time().toPyTime()
        self.settings['row_duration'] = [30,60,120,180][self.row_dur_combo.currentIndex()]
        if self.interval_combo.currentText():
            self.settings['interval'] = int(self.interval_combo.currentText())
        
        self.settings['dot_radius'] = self.dot_size_spin.value()
        self.settings['dot_spacing'] = self.dot_space_spin.value()
        self.settings['note_dot_scale'] = self.note_scale_spin.value()
        self.settings['font_size'] = self.font_size_spin.value()
        self.settings['calendar_font_size'] = self.cal_font_spin.value()
        self.settings['font_weight'] = self.font_weight_spin.value()
        
        self.settings['seg_base_offset'] = self.seg_offset_spin.value()
        self.settings['seg_layer_step'] = self.seg_step_spin.value()
        self.settings['seg_bottom_margin'] = self.seg_margin_spin.value()
        
        self.settings['sound_timer'] = self.sound_timer.currentIndex()
        self.settings['sound_note'] = self.sound_note.currentIndex()
        
        self.main_window.force_refresh_max_geometry() 
        self.main_window.update()

    def save_and_close(self):
        self.main_window.save_config()
        self.accept()
        
    def cancel(self):
        curr_pos = self.main_window.pos()
        self.original_config['window_pos'] = [curr_pos.x(), curr_pos.y()]
        self.main_window.config.update(self.original_config)
        self.main_window.force_refresh_max_geometry() 
        self.main_window.update()
        self.reject()

class TimeDotsWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        self.config = {
            'start_time': time(9, 0),
            'end_time': time(19, 0),
            'interval': 10,
            'row_duration': 60,
            'dot_spacing': 8,
            'dot_radius': 6,
            'note_dot_scale': 0.4,
            'font_size': 11,
            'calendar_font_size': 8,
            'font_weight': 700,
            'window_pos': None, 
            'bg_color': QColor(20, 20, 20, 220), 
            'active_color': QColor(255, 255, 255, 230),
            'current_color': QColor(100, 200, 255, 255),
            'inactive_color': QColor(80, 80, 80, 150),
            'calendar_today_color': QColor(255, 200, 100, 255), 
            'past_date_color': QColor(120, 120, 120, 150),
            'future_date_color': QColor(200, 200, 200, 255),
            'sidebar_always_on': False,
            'sound_timer': 2,
            'sound_note': 1,
            # [新增] 时间块布局参数
            'seg_base_offset': 6,    # A: 圆点到底部第一层的距离
            'seg_layer_step': 12,    # B: 层级之间的间距
            'seg_bottom_margin': 8   # C: 最后一层到下一行的距离
        }
        self.data_store = {} 
        self.current_view_date = QDate.currentDate()
        self.last_date_check = QDate.currentDate()
        
        self.load_config()

        self.hover_expansion_ratio = 1.3 
        
        self._hover_val = 0.0 
        self._header_val = 0.0 
        
        self.is_locked = False
        self.controls_visible = False 
        self.hover_time_acc = 0       
        self.last_sound_min = -1 
        
        self.state = InteractionState.Idle
        self.window_start_pos = None
        self.drag_start_global = None 
        
        self.active_segment_idx = -1
        self.temp_end_idx = -1       
        self.hovered_dot_idx = -1
        self.hovered_segment = None 
        self.hovered_light_idx = -1
        self.hovered_date = None 
        self.hovered_arrow = None 
        
        self.preview_segment = None 
        self.current_popup = None 
        self.active_tooltip = None 

        self.cal_anim_val = 0.0 
        self.cal_anim = QVariantAnimation()
        self.cal_anim.setDuration(300)
        self.cal_anim.setEasingCurve(QEasingCurve.Type.OutQuad) 
        self.cal_anim.valueChanged.connect(self.update_cal_anim_val)

        self.cached_row_heights = {} 
        self.update_grid_cache()
        
        self.max_dims = (100, 100) 
        self.current_content_rect = QRect()
        
        self.tooltip_timer = QTimer(self)
        self.tooltip_timer.setSingleShot(True)
        self.tooltip_timer.timeout.connect(self.show_hover_tooltip)
        self.last_hovered_obj = None 

        self.arrow_rects = {} 

        self.init_ui()
        self.init_tray()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.loop)
        self.timer.start(16) 

    def update_cal_anim_val(self, val):
        self.cal_anim_val = val
        self.update()

    def scroll_date(self, days):
        self.current_view_date = self.current_view_date.addDays(days)
        current_anim_val = self.cal_anim.currentValue() if self.cal_anim.state() == QVariantAnimation.State.Running else 0.0
        start_val = current_anim_val + days 
        self.cal_anim.stop()
        self.cal_anim.setStartValue(start_val)
        self.cal_anim.setEndValue(0.0)
        self.cal_anim.start()
        self.force_refresh_max_geometry()
        self.update()

    def init_ui(self):
        self.setWindowTitle('Time Dots')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        move_to_pos = None
        if self.config.get('window_pos'):
            saved_x, saved_y = self.config['window_pos']
            screen = QGuiApplication.screenAt(QPoint(saved_x, saved_y))
            if screen:
                move_to_pos = QPoint(saved_x, saved_y)
        
        if not move_to_pos:
            screen_geo = QGuiApplication.primaryScreen().availableGeometry()
            move_to_pos = screen_geo.center() - QPoint(200, 150)

        self.move(move_to_pos)
        self.force_refresh_max_geometry()

    def init_tray(self):
        self.tray = QSystemTrayIcon(self)
        px = QPixmap(32, 32)
        px.fill(Qt.GlobalColor.transparent)
        pt = QPainter(px)
        pt.setRenderHint(QPainter.RenderHint.Antialiasing)
        pt.setBrush(QBrush(QColor(200, 60, 60)))
        pt.setPen(Qt.PenStyle.NoPen)
        pt.drawEllipse(6, 6, 20, 20)
        pt.end()
        self.tray.setIcon(QIcon(px))
        m = QMenu()
        m.setStyleSheet(GLOBAL_STYLESHEET)
        m.addAction("设置", self.open_settings)
        m.addSeparator()
        m.addAction("显示/隐藏", self.toggle_visibility)
        self.act_lock = m.addAction("锁定/解锁")
        self.act_lock.setCheckable(True)
        self.act_lock.triggered.connect(self.toggle_lock)
        m.addAction("退出", self.quit_app)
        self.tray.setContextMenu(m)
        self.tray.show()
        self.tray.activated.connect(lambda r: self.toggle_visibility() if r == QSystemTrayIcon.ActivationReason.Trigger else None)

    def load_config(self):
        if not os.path.exists(CONFIG_FILE): return
        try:
            with open(CONFIG_FILE, 'r') as f:
                d = json.load(f)
            def gc(k, def_c): 
                v = d.get(k)
                if not v: return def_c
                return QColor(*v)
            
            safe_interval = max(1, d.get('interval', 10))
            safe_row_dur = max(10, d.get('row_duration', 60))

            self.config.update({
                'start_time': datetime.strptime(d['start_time'], "%H:%M").time(),
                'end_time': datetime.strptime(d['end_time'], "%H:%M").time(),
                'interval': safe_interval,
                'row_duration': safe_row_dur,
                'dot_spacing': d.get('dot_spacing', 8),
                'dot_radius': d.get('dot_radius', 6),
                'note_dot_scale': d.get('note_dot_scale', 0.4),
                'font_size': d.get('font_size', 11),
                'calendar_font_size': d.get('calendar_font_size', 8),
                'font_weight': d.get('font_weight', 700),
                'window_pos': d.get('window_pos'), 
                'bg_color': gc('bg_color', self.config['bg_color']),
                'current_color': gc('current_color', self.config['current_color']),
                'calendar_today_color': gc('calendar_today_color', self.config['calendar_today_color']),
                'past_date_color': gc('past_date_color', self.config['past_date_color']),
                'future_date_color': gc('future_date_color', self.config['future_date_color']),
                'sound_type': d.get('sound_type', 1),
                'sound_timer': d.get('sound_timer', 2),
                'sound_note': d.get('sound_note', 1)
            })
            self.data_store = d.get('data_store', {})
        except Exception as e: 
            print(f"Config load error: {e}")

    def save_config(self):
        p = self.pos() 
        d = self.config.copy()
        d['start_time'] = d['start_time'].strftime("%H:%M")
        d['end_time'] = d['end_time'].strftime("%H:%M")
        d['bg_color'] = self.config['bg_color'].getRgb()
        d['current_color'] = self.config['current_color'].getRgb()
        d['calendar_today_color'] = self.config['calendar_today_color'].getRgb()
        d['past_date_color'] = self.config['past_date_color'].getRgb()
        d['future_date_color'] = self.config['future_date_color'].getRgb()
        d['window_pos'] = [p.x(), p.y()]
        d['data_store'] = self.data_store
        for k in ['active_color', 'inactive_color']: 
            if k in d: del d[k]
        try:
            with open(CONFIG_FILE, 'w') as f: json.dump(d, f)
        except Exception as e: pass

    def quit_app(self):
        self.save_config()
        QApplication.instance().quit()

    def toggle_visibility(self):
        if self.isVisible(): self.hide()
        else: self.show(); self.activateWindow()

    def close_current_popup(self):
        if self.current_popup:
            self.current_popup.close()
            self.current_popup = None

    def get_current_data(self):
        k = self.current_view_date.toString(Qt.DateFormat.ISODate)
        if k not in self.data_store: self.data_store[k] = {"segments": [], "notes": {}}
        return self.data_store[k]

    def get_grid_info(self):
        st = self.config['start_time']
        et = self.config['end_time']
        rd = self.config['row_duration']
        inv = self.config['interval']
        def tm(t):
            b = st.hour * 60
            c = t.hour * 60 + t.minute
            if c < b: c += 24*60
            return c - b
        
        # [修复] 移除 + st.minute。
        # tm(et) 计算的是 "结束时间" 相对于 "开始小时(整点)" 的总分钟数。
        # 这个值就是我们 Grid 系统中需要的 End Offset。
        total = tm(et)
        
        if rd == 0: rd = 60 
        if inv == 0: inv = 10
        rows = math.ceil(total / rd)
        cols = rd // inv
        return rows, cols, st.minute, total

    def calc_layers(self, extra_seg=None):
        data = self.get_current_data()
        all_segs = data['segments'][:]
        if extra_seg:
            all_segs.append(extra_seg)
        segs = sorted(all_segs, key=lambda x: x['start'])
        layers_end = []
        for s in segs:
            placed = False
            for i, end in enumerate(layers_end):
                if end <= s['start']:
                    layers_end[i] = s['end']
                    s['layer'] = i
                    placed = True
                    break
            if not placed:
                s['layer'] = len(layers_end)
                layers_end.append(s['end'])
        return segs

    def update_grid_cache(self):
        rows, cols, _, _ = self.get_grid_info()
        if rows == 0: return
        segs = self.calc_layers(extra_seg=self.preview_segment)
        
        base_h_px = self.config['dot_radius'] * 2
        
        # 读取配置参数
        offset_a = self.config.get('seg_base_offset', 6)
        step_b = self.config.get('seg_layer_step', 12)
        margin_c = self.config.get('seg_bottom_margin', 8)
        
        self.cached_row_heights = {}
        for r in range(rows):
            rs = r * self.config['row_duration']
            re = (r+1) * self.config['row_duration']
            max_l = -1
            for s in segs:
                if not (s['end'] <= rs or s['start'] >= re):
                    max_l = max(max_l, s.get('layer', 0))
            
            # 计算行高：
            # 如果没有 segment (max_l == -1)，行高 = 圆点高度
            # 如果有 segment，行高 = 圆点高度 + A + (max_l * B) + C
            # 这里的 C 还承担了“最底层 Segment 自身的厚度 (约4px)”的功能
            if max_l == -1:
                self.cached_row_heights[r] = base_h_px
            else:
                # 额外加 4px 是为了容纳最后一根线的视觉厚度
                self.cached_row_heights[r] = base_h_px + offset_a + (max_l * step_b) + margin_c + 4

    def get_vertical_margins(self, h_val, head_val):
        top_extra = HEADER_FULL_HEIGHT * head_val 
        bottom_extra = (CALENDAR_HEIGHT + FOOTER_GAP) * h_val 
        
        top_m = BASE_MARGIN + top_extra
        bottom_m = BASE_MARGIN + bottom_extra
        return top_m, bottom_m
    
    def update_layout_dynamic(self):
        ideal_w, ideal_h = self.calculate_ideal_dim(self._hover_val, self._header_val)
        
        draw_x = (self.width() - ideal_w) / 2
        draw_y = (self.height() - ideal_h) / 2
        
        screen_geo = self.screen().availableGeometry()
        win_geo = self.geometry()
        padding = GEOMETRY_PADDING
        
        if win_geo.right() >= screen_geo.right() - 5:
             draw_x = self.width() - ideal_w - padding 
        elif win_geo.left() <= screen_geo.left() + 5:
             draw_x = padding
        if win_geo.bottom() >= screen_geo.bottom() - 5:
             draw_y = self.height() - ideal_h - padding
        elif win_geo.top() <= screen_geo.top() + 5:
             draw_y = padding
             
        self.current_content_rect = QRect(int(draw_x), int(draw_y), int(ideal_w), int(ideal_h))
        
        if not self.is_locked:
            self.setMask(QRegion(self.current_content_rect.adjusted(-4, -4, 4, 4)))
        elif self.controls_visible:
            self.setMask(QRegion(self.current_content_rect.adjusted(-4, -4, 4, 4)))

    # [新增] 计算前 n 个缝隙的总宽度 (考虑了宽窄混合的情况)
    def get_cumulative_gap_offset(self, gap_count, expansion_ratio=1.0):
        total_offset = 0
        # [核心修复] 移除 start_min。
        # 因为网格布局现在是绝对对齐到整点的 (Column 0 总是 XX:00)，
        # 所以缝隙的位置也是固定的：第一个缝隙总是对应 XX:30，第二个总是 XX:60(整点)。
        for k in range(1, gap_count + 1):
            # k=1 -> 30分 (窄)
            # k=2 -> 60分 (宽)
            # k=3 -> 90分 (窄)
            gap_time = k * 30
            
            if gap_time % 60 == 0:
                base_w = GAP_WIDTH_WIDE
            else:
                base_w = GAP_WIDTH_NARROW
            
            total_offset += base_w * expansion_ratio
            
        return total_offset

    def calculate_ideal_dim(self, h_val, head_val):
        self.update_grid_cache()
        rows, cols, _, _ = self.get_grid_info()
        r_base = self.config['dot_radius']
        
        expansion = 1.0 + ((self.hover_expansion_ratio - 1.0) * h_val)
        sp_curr = self.config['dot_spacing'] * expansion
        mg = BASE_MARGIN
        sw = SIDEBAR_WIDTH * h_val
        top_m, bottom_m = self.get_vertical_margins(h_val, head_val)
        
        col_unit = r_base * 2 + sp_curr
        inv = self.config['interval']
        
        div_check = max(1, 30 // inv)
        gap_count = (cols - 1) // div_check if inv > 0 else 0
        
        # [核心变化] 这里不再是简单的乘法，而是调用累加函数
        total_gaps_w = self.get_cumulative_gap_offset(gap_count, h_val)
        
        w_content = mg*2 + sw + cols*col_unit - sp_curr + total_gaps_w
        h_content = top_m + bottom_m
        for r in range(rows):
             h_content += self.cached_row_heights[r]
             if r < rows - 1: 
                 h_content += sp_curr
        
        if head_val > 0.1:
            min_header_w = 16 + (6*2 + 8)*2 + 6*2 + 16 
            if w_content < min_header_w:
                w_content = min_header_w

        return w_content, h_content
    
    def force_refresh_max_geometry(self):
        # 1. 记录调整前的状态
        old_geo = self.geometry()
        screen_geo = self.screen().availableGeometry()
        
        # 检测吸附状态 (阈值设为 15px，稍微宽容一点以防微小偏差)
        # 如果底部距离屏幕底部小于 15px，认为已吸附到底部
        is_bottom_snapped = abs(old_geo.bottom() - screen_geo.bottom()) < 15
        # 如果右侧距离屏幕右侧小于 15px，认为已吸附到右侧
        is_right_snapped = abs(old_geo.right() - screen_geo.right()) < 15
        
        # 2. 计算新的理想尺寸
        max_w, max_h = self.calculate_ideal_dim(1.0, 1.0)
        padding = GEOMETRY_PADDING
        target_w = math.ceil(max_w) + padding * 2
        target_h = math.ceil(max_h) + padding * 2
        
        # 3. 应用新尺寸
        self.max_dims = (target_w, target_h)
        self.setFixedSize(target_w, target_h)
        
        # 4. 根据之前的吸附状态修正位置
        new_geo = self.geometry() # 获取新尺寸后的几何 (默认左上角不变)
        
        # 修正垂直方向
        if is_bottom_snapped:
            # 如果之前吸附在底部，现在也要吸附在底部 (意味着高度变化时，Top 会动)
            new_geo.moveBottom(screen_geo.bottom())
        elif new_geo.bottom() > screen_geo.bottom():
            # 如果没吸附，但变大后超出了底部，推回去
            new_geo.moveBottom(screen_geo.bottom())
            
        # 修正水平方向
        if is_right_snapped:
            # 如果之前吸附在右侧，现在也要吸附在右侧 (意味着宽度变化时，Left 会动)
            new_geo.moveRight(screen_geo.right())
        elif new_geo.right() > screen_geo.right():
            # 如果没吸附，但变大后超出了右侧，推回去
            new_geo.moveRight(screen_geo.right())
        
        # 5. 最后进行越界保护 (防止窗口因为上述移动跑出左上边界)
        if new_geo.top() < screen_geo.top():
            new_geo.moveTop(screen_geo.top())
        if new_geo.left() < screen_geo.left():
            new_geo.moveLeft(screen_geo.left())
            
        # 6. 移动窗口并更新布局
        self.move(new_geo.topLeft())
        self.update_layout_dynamic()
        self.update_mask()

    def get_render_params(self):
        val = self._hover_val
        expansion = 1.0 + ((self.hover_expansion_ratio - 1.0) * val)
        r = self.config['dot_radius']
        sp = self.config['dot_spacing'] * expansion
        sw = SIDEBAR_WIDTH * val 
        return r, sp, sw

    def get_bg_rect(self):
        return self.current_content_rect

    def get_col_x_offset(self, c_idx, col_unit):
        inv = self.config['interval']
        if inv == 0: return 0
        cols_per_30 = 30 // inv
        if cols_per_30 == 0: cols_per_30 = 1 
        
        # 计算当前列之前有多少个缝隙
        num_gaps = c_idx // cols_per_30
        
        # [核心变化] 调用累加函数计算具体的像素偏移
        return self.get_cumulative_gap_offset(num_gaps, self._hover_val)

    def get_dot_abs_pos(self, r_idx, c_idx):
        bg = self.current_content_rect 
        if not bg.isValid(): return QPointF(0,0)
        
        rad, sp, sw = self.get_render_params()
        top_m, _ = self.get_vertical_margins(self._hover_val, self._header_val)
        
        y = bg.top() + top_m
        for i in range(r_idx):
            y += self.cached_row_heights.get(i, 20) 
            y += sp 
        y += rad 
        col_unit = 2*rad + sp
        gap_offset = self.get_col_x_offset(c_idx, col_unit)
        
        x = bg.left() + BASE_MARGIN + sw + c_idx * col_unit + rad + gap_offset
        return QPointF(x, y)

    def get_idx_at_pos(self, pos):
        if not self.current_content_rect.contains(pos): return -1
        
        rows, cols, s_off, e_off = self.get_grid_info()
        rd = self.config['row_duration']
        inv = self.config['interval']
        rad, sp, sw = self.get_render_params()
        top_m, _ = self.get_vertical_margins(self._hover_val, self._header_val)
        pos_f = QPointF(pos)
        
        if pos_f.y() < self.current_content_rect.top() + top_m: return -1
        col_unit = 2*rad + sp
        
        rel_x = pos_f.x() - (self.current_content_rect.left() + BASE_MARGIN + sw)
        
        found_c = -1
        for c in range(cols):
            gap = self.get_col_x_offset(c, col_unit)
            cx = c * col_unit + gap
            center_x = cx + rad
            if abs(rel_x - center_x) < rad * 2.5:
                found_c = c
                break
        if found_c == -1: return -1
        curr_y = self.current_content_rect.top() + top_m
        found_r = -1
        for r in range(rows):
            row_h = self.cached_row_heights.get(r, 20)
            total_row_block = row_h + sp
            if curr_y <= pos_f.y() < curr_y + total_row_block:
                found_r = r
                break
            curr_y += total_row_block
        if found_r == -1: return -1
        center = self.get_dot_abs_pos(found_r, found_c)
        if (pos_f - center).manhattanLength() < rad * 2.5:
             idx = found_r*rd + found_c*inv
             if idx < s_off or idx >= e_off: return -1
             return idx
        return -1
    
    def get_segment_at_pos(self, pos):
        if not self.current_content_rect.contains(pos): return None
        data = self.get_current_data()
        segs = data['segments'][:]
        if self.preview_segment: segs.append(self.preview_segment)
        rad, sp, sw = self.get_render_params()
        rd = self.config['row_duration']
        inv = self.config['interval']
        pos_f = QPointF(pos)
        
        # 读取布局参数
        offset_a = self.config.get('seg_base_offset', 6)
        step_b = self.config.get('seg_layer_step', 12)
        
        # [核心修复] 严格的判定高度，不随 layer_step 变大而变大
        # 无论间距拉多大，只检测线段上下 4px 的范围 (总高 8px)
        hit_threshold = 4.0 

        for s in segs:
            layer = s.get('layer', 0)
            y_offset_from_center = rad + offset_a + (layer * step_b)
            
            s_idx = s['start']; e_idx = s['end']
            s_row = s_idx // rd; e_row = e_idx // rd
            
            for r in range(s_row, e_row + 1):
                row_s = r * rd; row_e = (r+1) * rd
                d_s = max(s_idx, row_s); d_e = min(e_idx, row_e)
                if d_s >= d_e: continue 
                
                c_s = (d_s % rd) // inv
                p1 = self.get_dot_abs_pos(r, c_s)
                x1 = p1.x() - rad - (sp/2)
                
                if d_e == row_e:
                    p_end = self.get_dot_abs_pos(r, (rd//inv)-1)
                    x2 = p_end.x() + rad + sp/2
                else:
                    c_e = (d_e % rd) // inv
                    p_end = self.get_dot_abs_pos(r, c_e)
                    x2 = p_end.x() - rad - sp/2
                
                y_line = p1.y() + y_offset_from_center
                
                # 创建一个窄的判定矩形
                rect = QRectF(x1, y_line - hit_threshold, x2 - x1, hit_threshold * 2)
                
                if rect.contains(pos_f): return s
        return None

    def get_date_at_pos(self, pos):
        if not self.current_content_rect.contains(pos): return None
        if self._hover_val <= 0.01: return None
        bg_rect = self.current_content_rect
        dh = CALENDAR_HEIGHT
        
        bottom_limit = bg_rect.bottom() - dh - BASE_MARGIN - FOOTER_GAP
        if not (pos.y() > bottom_limit and bg_rect.contains(pos)):
            return None
            
        w = bg_rect.width()
        visible_count, step_x, first_center_x = self.get_calendar_layout(w)
        offset = pos.x() - first_center_x 
        
        visual_idx = round(offset / step_x)
        idx = int(round(visual_idx - self.cal_anim_val))
        
        if 0 <= idx < visible_count:
            center_offset = (visible_count - 1) // 2
            start_date = self.current_view_date.addDays(-center_offset)
            return start_date.addDays(idx)
        return None

    def get_calendar_layout(self, w):
        # [核心修复] 不要使用传入的 w (当前动画中的宽度) 来计算天数
        # 而是根据 Hover=1.0 时的最大宽度来计算，确保天数固定不变
        
        # 计算最大展开时的理想宽度
        max_w, _ = self.calculate_ideal_dim(1.0, 1.0)
        
        # 使用最大宽度计算布局参数
        arrow_area_width = 30 
        available_w_max = max(50, max_w - arrow_area_width * 2) 
        
        safe_step = max(MIN_CAL_STEP, available_w_max / 15)
        visible_count = int(available_w_max / safe_step)
        
        if visible_count > 15: visible_count = 15
        if visible_count % 2 == 0: visible_count -= 1 
        if visible_count < 3: visible_count = 3
        
        # step_x 依然要基于当前宽度计算，以保证拉伸动画
        # 但 visible_count 被锁定了，就不会突变
        current_available_w = max(50, w - arrow_area_width * 2)
        
        # 如果当前宽度太小(Idle状态)，会导致 step_x 过小挤在一起
        # 但因为此时 alpha=0 看不见，所以没关系。重点是数量不跳变。
        step_x = current_available_w / visible_count
        
        bg_rect = self.current_content_rect
        actual_width = visible_count * step_x
        start_x_abs = bg_rect.left() + (w - actual_width) / 2
        first_center_x = start_x_abs + step_x/2
        
        return visible_count, step_x, first_center_x

    def get_traffic_lights_rects(self):
        bg = self.current_content_rect
        top_m = BASE_MARGIN + (HEADER_FULL_HEIGHT * self._header_val)
        
        base_y = bg.top() + 16 
        base_x = bg.left() + 16
        r = 6 
        gap = 8 
        red = QRectF(base_x, base_y, r*2, r*2)
        yel = QRectF(base_x + r*2 + gap, base_y, r*2, r*2)
        grn = QRectF(base_x + (r*2 + gap)*2, base_y, r*2, r*2)
        return red, yel, grn

    def show_popup(self, idx, global_pos):
        self.close_current_popup()
        data = self.get_current_data()
        curr_note = data['notes'].get(str(idx), {})
        pop = EditPopup(self, 
                        initial_color=QColor(*curr_note['color']) if 'color' in curr_note else None,
                        initial_text=curr_note.get('text', ""),
                        default_color=QColor(255, 80, 80),
                        on_save=lambda c, t: self.save_note(idx, c, t),
                        on_delete=lambda: self.del_note(idx))
        pop.move(global_pos)
        self.current_popup = pop
        pop.show()

    def show_segment_popup(self, seg, global_pos):
        self.close_current_popup()
        self.preview_segment = None 
        c = QColor(*seg['color'])
        txt = seg.get('text', "")
        def on_live_change(new_c, new_t):
            seg['color'] = [new_c.red(), new_c.green(), new_c.blue()]
            seg['text'] = new_t
            self.update()
        def save_seg(new_c, new_t):
            on_live_change(new_c, new_t)
            self.save_config()
        def del_seg_action():
            self.del_seg(seg)
        pop = EditPopup(self, 
                        initial_color=c,
                        initial_text=txt,
                        default_color=QColor(255, 80, 80),
                        on_save=save_seg,
                        on_delete=del_seg_action,
                        on_live_change=on_live_change)
        pop.move(global_pos)
        self.current_popup = pop
        pop.show()

    def update_mask(self):
        if not self.is_locked:
            self.setMask(QRegion(self.current_content_rect.adjusted(-4, -4, 4, 4)))
            return

        if self.controls_visible:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, False)
            self.setMask(QRegion(self.current_content_rect.adjusted(-4, -4, 4, 4)))
            self.show()
        else:
            self.clearMask()
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
            self.show()

    def loop(self):
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        
        # 1. 基础命中测试 (用于唤醒 Hover)
        # 注意：这里必须用当前的 rect 进行计算
        in_content = self.current_content_rect.contains(local_pos)
        
        target_hover = 0.0
        target_header = 0.0
        
        if self.is_locked:
            # --- 锁定模式核心逻辑 ---
            
            # A. 状态机：计算是否应该显示控件 (Hover唤醒)
            if in_content:
                self.hover_time_acc += 50 
                if self.hover_time_acc > 1200: 
                    self.controls_visible = True
            else:
                self.hover_time_acc = 0
                self.controls_visible = False
            
            # B. 穿透控制：根据鼠标位置动态切换窗口属性 (Pixel-Perfect Click-Through)
            desired_transparent = True # 默认应该是穿透的
            
            if self.controls_visible:
                # 控件可见时：检查鼠标是否在红绿灯上
                r, y, g = self.get_traffic_lights_rects()
                # 稍微扩大一点判定范围(5px)，提升操作手感，防止鼠标快划时丢失焦点
                hit_zone = r.united(y).united(g).adjusted(-5, -5, 5, 5)
                
                if hit_zone.contains(QPointF(local_pos)):
                    desired_transparent = False # 在灯上 -> 实体化 (捕获点击)
            
            # C. 应用 Flag (仅当状态改变时调用 setWindowFlag + show，避免闪烁和性能开销)
            current_transparent = bool(self.windowFlags() & Qt.WindowType.WindowTransparentForInput)
            if current_transparent != desired_transparent:
                self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, desired_transparent)
                self.show()

            # D. 状态清理：如果处于穿透状态，强制清除所有内部元素的 Hover 高亮
            if desired_transparent:
                if self.hovered_dot_idx != -1 or self.hovered_segment is not None or self.hovered_date is not None:
                    self.hovered_dot_idx = -1
                    self.hovered_segment = None
                    self.hovered_date = None
                    self.hovered_arrow = None
                    self.setCursor(Qt.CursorShape.ArrowCursor)
                    self.update()

            # E. 设定动画目标
            target_hover = 0.0 # 锁定下内容主体不展开
            target_header = 1.0 if self.controls_visible else 0.0
            
        else:
            # --- 非锁定模式逻辑 ---
            target_header = 1.0 if (in_content or self.config['sidebar_always_on']) else 0.0
            target_hover = 1.0 if (in_content or self.config['sidebar_always_on']) else 0.0
            self.controls_visible = False
            self.hover_time_acc = 0
            
            # 确保非锁定模式下始终接收输入
            current_transparent = bool(self.windowFlags() & Qt.WindowType.WindowTransparentForInput)
            if current_transparent:
                self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, False)
                self.show()

        # --- 动画插值逻辑 (保持不变) ---
        needs_repaint = False
        speed = 0.15
        
        if abs(self._hover_val - target_hover) > 0.001:
            self._hover_val += (target_hover - self._hover_val) * speed
            needs_repaint = True
        else:
            self._hover_val = target_hover
            
        if abs(self._header_val - target_header) > 0.001:
            self._header_val += (target_header - self._header_val) * speed
            needs_repaint = True
        else:
            self._header_val = target_header

        if needs_repaint:
            self.update_layout_dynamic()
            self.update()

        # --- 时间/声音检查逻辑 (保持不变) ---
        now_date = QDate.currentDate()
        if self.last_date_check != now_date:
            if self.current_view_date == self.last_date_check:
                self.current_view_date = now_date
                self.update()
            self.last_date_check = now_date

        now = datetime.now()
        curr_min = now.minute
        if self.last_sound_min != curr_min:
            self.last_sound_min = curr_min
            if self.current_view_date == QDate.currentDate():
                data = self.get_current_data()
                base_dt = datetime.combine(now.date(), time(self.config['start_time'].hour, 0))
                inv = self.config['interval']
                passed_mins = (now - base_dt).total_seconds() / 60
                for s in data['segments']:
                    seg_end_mins = s['end'] + inv
                    if abs(passed_mins - seg_end_mins) < 1.0: 
                        play_sound_by_type(self.config['sound_timer'])
                curr_dot_idx = int(passed_mins // inv)
                if str(curr_dot_idx) in data['notes']:
                    dot_start_time = curr_dot_idx * inv
                    if abs(passed_mins - dot_start_time) < 1.0:
                        play_sound_by_type(self.config['sound_note'])

        if self.current_view_date == QDate.currentDate():
            if now.microsecond < 150000: 
                self.update()
                
    def paintEvent(self, event):
        if self.current_content_rect.isNull():
             self.update_layout_dynamic()

        pt = QPainter(self)
        pt.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        ideal_w, ideal_h = self.calculate_ideal_dim(self._hover_val, self._header_val)
        screen_geo = self.screen().availableGeometry()
        win_geo = self.geometry()
        
        draw_x = (self.width() - ideal_w) / 2
        draw_y = (self.height() - ideal_h) / 2
        padding = GEOMETRY_PADDING
        
        if win_geo.right() >= screen_geo.right() - 5: draw_x = self.width() - ideal_w - padding 
        elif win_geo.left() <= screen_geo.left() + 5: draw_x = padding
        if win_geo.bottom() >= screen_geo.bottom() - 5: draw_y = self.height() - ideal_h - padding
        elif win_geo.top() <= screen_geo.top() + 5: draw_y = padding
             
        self.current_content_rect = QRect(int(draw_x), int(draw_y), int(ideal_w), int(ideal_h))
        
        if not self.is_locked:
            self.setMask(QRegion(self.current_content_rect.adjusted(-4, -4, 4, 4)))

        rad, sp, sw = self.get_render_params()
        rows, cols, s_off, e_off = self.get_grid_info()
        rd = self.config['row_duration']
        inv = self.config['interval']
        bg_rect = QRectF(self.current_content_rect) 
        
        pt.setBrush(QBrush(self.config['bg_color']))
        pt.setPen(Qt.PenStyle.NoPen)
        pt.drawRoundedRect(bg_rect, 16, 16)
        
        # 绘制 Header
        if self._header_val > 0.01:
            light_alpha = int(255 * self._header_val)
            r_rect, y_rect, g_rect = self.get_traffic_lights_rects()
            
            # [核心修改] 绘制右上角信息：仅在非锁定状态下显示
            if light_alpha > 5 and not self.is_locked:
                info_text = f"{inv} min /"
                f_info = pt.font()
                f_info.setPixelSize(12)
                f_info.setBold(True)
                pt.setFont(f_info)
                
                fm = QFontMetrics(f_info)
                txt_w = fm.horizontalAdvance(info_text)
                
                right_margin = 22
                dot_size = rad * 0.8
                gap = 6
                
                total_w = txt_w + gap + dot_size*2
                area_h = 20
                
                # 智能对齐计算
                available_w = bg_rect.width()
                pos_right_align = bg_rect.right() - right_margin - total_w
                left_margin_if_right = pos_right_align - bg_rect.left()
                
                if left_margin_if_right < right_margin:
                    info_x = bg_rect.left() + (available_w - total_w) / 2
                else:
                    info_x = pos_right_align
                
                info_y = bg_rect.top() + 36 
                
                self.interval_info_rect = QRectF(info_x - 5, info_y - 5, total_w + 10, area_h + 10)
                
                mouse_pos = self.mapFromGlobal(QCursor.pos())
                is_hover_info = self.interval_info_rect.contains(QPointF(mouse_pos))
                
                base_col = QColor(255, 255, 255)
                if is_hover_info: base_col = QColor(10, 132, 255)
                base_col.setAlpha(light_alpha)
                
                pt.setPen(base_col)
                pt.drawText(QPointF(info_x, info_y + 11), info_text)
                
                dot_cx = info_x + txt_w + gap + dot_size
                dot_cy = info_y + 6
                pt.setBrush(QBrush(base_col))
                pt.setPen(Qt.PenStyle.NoPen)
                pt.drawEllipse(QPointF(dot_cx, dot_cy), dot_size, dot_size)

            def draw_light(rect, color, is_hover):
                c = QColor(color)
                c.setAlpha(light_alpha)
                pt.setBrush(c)
                if is_hover:
                    center = rect.center()
                    pt.drawEllipse(center, 7.2, 7.2)
                else:
                    pt.drawEllipse(rect)
            
            if light_alpha > 5:
                draw_light(r_rect, QColor(255, 95, 87), self.hovered_light_idx == 0)
                draw_light(y_rect, QColor(255, 189, 46), self.hovered_light_idx == 1)
                draw_light(g_rect, QColor(39, 201, 63), self.hovered_light_idx == 2)

        # 绘制网格
        if self._hover_val > 0.05:
            op = int(255 * self._hover_val)
            unified_font = pt.font()
            unified_font.setPixelSize(self.config['font_size'])
            unified_font.setWeight(self.config['font_weight'])
            pt.setFont(unified_font)
            pt.setPen(QColor(255, 255, 255, op))

            start_hour_abs_min = self.config['start_time'].hour * 60
            last_drawn_sidebar_hour = -1

            for r in range(rows):
                row_base_min = start_hour_abs_min + r * rd
                row_hour = (row_base_min // 60) % 24
                cp_start = self.get_dot_abs_pos(r, 0)
                
                if row_hour != last_drawn_sidebar_hour:
                    sidebar_rect = QRectF(bg_rect.left() + 2, cp_start.y() - 10, sw - 4, 20)
                    pt.drawText(sidebar_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"{row_hour:02d}")
                    last_drawn_sidebar_hour = row_hour

                if rd == 30: continue 

                row_top_y = cp_start.y() - rad
                row_bottom_y = row_top_y + rad * 2
                
                for c in range(cols):
                    current_min = row_base_min + c * inv
                    idx_val = r * rd + c * inv
                    if idx_val < s_off or idx_val >= e_off: continue
                    
                    pos_c = self.get_dot_abs_pos(r, c)
                    this_gap_width = 0
                    if current_min % 60 == 0: this_gap_width = GAP_WIDTH_WIDE
                    elif current_min % 30 == 0: this_gap_width = GAP_WIDTH_NARROW
                    
                    dynamic_gap_w = this_gap_width * self._hover_val
                    x_center = pos_c.x() - rad - sp/2 - dynamic_gap_w/2
                    
                    if current_min % 60 == 0:
                        if c > 0:
                            h_num = (current_min // 60) % 24
                            num_rect = QRectF(x_center - dynamic_gap_w/2, row_top_y, dynamic_gap_w, rad*2)
                            pt.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, f"{h_num:02d}")
                    elif current_min % 30 == 0:
                        pen_line = QPen(QColor(255, 255, 255, int(50 * self._hover_val)))
                        pen_line.setWidthF(1.0)
                        pt.save()
                        pt.setPen(pen_line)
                        pt.drawLine(QPointF(x_center, row_top_y), QPointF(x_center, row_bottom_y))
                        pt.restore()
                        pt.setPen(QColor(255, 255, 255, op))

        # 绘制点阵
        now = datetime.now()
        view_dt = datetime.combine(self.current_view_date.toPyDate(), time(self.config['start_time'].hour, 0))
        passed_mins = (now - view_dt).total_seconds() / 60
        is_today = (self.current_view_date == QDate.currentDate())
        curr_data = self.get_current_data()
        notes = curr_data['notes']
        
        for r in range(rows):
            for c in range(cols):
                idx = r*rd + c*inv
                if idx < s_off or idx >= e_off: continue
                cp = self.get_dot_abs_pos(r, c)
                r_real = rad
                if idx == self.hovered_dot_idx: r_real *= 1.3 
                col = self.config['active_color']
                if is_today:
                    if idx < passed_mins:
                        if idx + inv > passed_mins: col = self.config['current_color']
                        else: col = self.config['inactive_color']
                    else: col = self.config['active_color']
                elif self.current_view_date < QDate.currentDate():
                    col = self.config['inactive_color']
                if idx == self.hovered_dot_idx: col = col.lighter(150)
                pt.setBrush(QBrush(col))
                pt.setPen(Qt.PenStyle.NoPen)
                pt.drawEllipse(cp, r_real, r_real)
                if str(idx) in notes:
                    nc = notes[str(idx)]['color']
                    pt.setBrush(QBrush(QColor(*nc)))
                    pt.drawEllipse(cp, r_real*self.config.get('note_dot_scale', 0.4), r_real*self.config.get('note_dot_scale', 0.4))

        # 绘制 Segment
        segs = curr_data['segments'][:]
        if self.preview_segment: segs.append(self.preview_segment)
        for s in segs:
            col = QColor(*s['color'])
            is_hovered = (s == self.hovered_segment)
            is_prev = (s == self.preview_segment)
            self.draw_segment(pt, s['start'], s['end'], col, s.get('layer', 0), passed_mins, is_today, is_hovered=is_hovered, is_preview=is_prev)

        # 绘制日历
        if self._hover_val > 0.01:
            dh = CALENDAR_HEIGHT
            cal_base = bg_rect.bottom() - BASE_MARGIN
            pt.save()
            path = QPainterPath()
            path.addRoundedRect(bg_rect, 16, 16)
            pt.setClipPath(path)
            self.draw_calendar_bar(pt, cal_base - dh/2, bg_rect.width(), dh, bg_rect.left())
            pt.restore()

    def draw_segment(self, pt, start_idx, end_idx, color, layer, passed_mins, is_today, is_hovered=False, is_preview=False):
        rad, sp, sw = self.get_render_params()
        rd = self.config['row_duration']
        inv = self.config['interval']
        thickness = 2.5 
        if is_hovered or is_preview: thickness = 4.0
        
        # [核心修改] 使用新参数计算 Y 轴偏移
        offset_a = self.config.get('seg_base_offset', 6)
        step_b = self.config.get('seg_layer_step', 12)
        # 线的中心位置 = 圆点中心 + 半径 + A + 层级*B
        y_offset_from_center = rad + offset_a + (layer * step_b)

        s_row = start_idx // rd
        e_row = end_idx // rd
        for r in range(s_row, e_row + 1):
            row_s = r * rd; row_e = (r+1) * rd
            d_s = max(start_idx, row_s); d_e = min(end_idx, row_e)
            if d_s >= d_e: continue 
            c_s = (d_s % rd) // inv
            p1 = self.get_dot_abs_pos(r, c_s)
            x1 = p1.x() - rad - (sp/2) 
            if d_e == row_e:
                p_end = self.get_dot_abs_pos(r, (rd//inv)-1)
                x2 = p_end.x() + rad + sp/2
            else:
                c_e = (d_e % rd) // inv
                p_end = self.get_dot_abs_pos(r, c_e)
                x2 = p_end.x() - rad - sp/2
                
            y = p1.y() + y_offset_from_center
            
            pt.save()
            if is_hovered or is_preview:
                pen_outline = QPen(QColor(255, 255, 255, 200))
                if is_preview: pen_outline = QPen(color) 
                pen_outline.setWidthF(thickness + (1 if is_hovered else 0))
                pen_outline.setCapStyle(Qt.PenCapStyle.RoundCap)
                pt.setPen(pen_outline)
                pt.drawLine(QPointF(x1, y), QPointF(x2, y))
            if not is_preview:
                pen_color = QPen(color)
                pen_color.setWidthF(thickness)
                pen_color.setCapStyle(Qt.PenCapStyle.RoundCap)
                c_gray = QColor(80, 80, 80, 180)
                pen_gray = QPen(c_gray)
                pen_gray.setWidthF(thickness)
                pen_gray.setCapStyle(Qt.PenCapStyle.RoundCap)
                if is_today:
                    row_start_time = d_s
                    row_end_time = d_e 
                    if passed_mins >= row_end_time: 
                        pt.setPen(pen_gray)
                        pt.drawLine(QPointF(x1, y), QPointF(x2, y))
                    elif passed_mins <= row_start_time: 
                        pt.setPen(pen_color)
                        pt.drawLine(QPointF(x1, y), QPointF(x2, y))
                    else: 
                        total_width = x2 - x1
                        time_in_row = row_end_time - row_start_time
                        passed_in_row = passed_mins - row_start_time
                        ratio = passed_in_row / time_in_row
                        ratio = max(0.0, min(1.0, ratio))
                        x_split = x1 + total_width * ratio
                        pt.setPen(pen_gray)
                        pt.drawLine(QPointF(x1, y), QPointF(x_split, y))
                        pt.setPen(pen_color)
                        pt.drawLine(QPointF(x_split, y), QPointF(x2, y))
                else:
                    pt.setPen(pen_gray if self.current_view_date < QDate.currentDate() else pen_color)
                    pt.drawLine(QPointF(x1, y), QPointF(x2, y))
            pt.restore()

    def draw_calendar_bar(self, pt, y, w, h, left_x):
        visible_count, step_x, first_center_x = self.get_calendar_layout(w)
        days_zh = ["一", "二", "三", "四", "五", "六", "日"]
        center_offset = (visible_count - 1) // 2
        start_date = self.current_view_date.addDays(-center_offset)
        base_font_size = self.config.get('calendar_font_size', 8)
        if visible_count < 7: base_font_size = max(6, base_font_size - 2)
        mid_idx = visible_count // 2
        
        for i in range(visible_count):
            d = start_date.addDays(i)
            cx = first_center_x + (i + self.cal_anim_val) * step_x
            cy = y 
            r = 4 
            # 计算当前动画帧的透明度
            alpha = int(255 * self._hover_val)
            
            is_viewing = (d == self.current_view_date)
            is_today = (d == QDate.currentDate())
            
            # --- 1. 设置圆点颜色 ---
            if d < QDate.currentDate():
                col = self.config.get('past_date_color', QColor(120, 120, 120, 150))
            elif d > QDate.currentDate():
                col = self.config.get('future_date_color', QColor(200, 200, 200, 255))
            else:
                col = self.config['calendar_today_color']
            
            if is_today:
                col = self.config['calendar_today_color']
                r = 5
            if is_viewing:
                col = col.lighter(150)
                r = 6
                
            col.setAlpha(alpha)
            if d == self.hovered_date: r *= 1.3 
            
            pt.setBrush(QBrush(col))
            
            # 设置周末红圈 (带透明度)
            if d.dayOfWeek() >= 6:
                red_pen_color = QColor(255, 80, 80)
                red_pen_color.setAlpha(alpha) 
                pt.setPen(QPen(red_pen_color, 1.5)) 
            else:
                pt.setPen(Qt.PenStyle.NoPen)
                
            pt.drawEllipse(QPointF(cx, cy), r, r)
            
            # --- 2. 绘制文字 (星期和日期) ---
            # [核心修复] 移除了 "if self._hover_val > 0.8" 的判断
            # 只要 alpha > 0 (稍微可见)，就随圆点一起绘制，实现同步淡入
            if alpha > 0:
                txt_col = QColor(180, 180, 180, alpha)
                if d.dayOfWeek() >= 6: 
                    txt_col = QColor(255, 100, 100, alpha) 
                
                f = pt.font()
                f.setPixelSize(base_font_size) 
                pt.setFont(f)
                pt.setPen(txt_col)
                
                # 绘制星期 (圆点上方)
                pt.drawText(QRectF(cx-20, cy-r-15, 40, 15), Qt.AlignmentFlag.AlignCenter, days_zh[d.dayOfWeek()-1])
                
                # 绘制日期 (圆点下方，仅间隔显示)
                dist = abs(i - mid_idx)
                should_show_date = (i == mid_idx) or (dist > 0 and dist % 3 == 0)
                if should_show_date:
                    pt.setPen(QColor(180, 180, 180, alpha))
                    date_str = f"{d.month()}/{d.day()}"
                    pt.drawText(QRectF(cx-20, cy+r+2, 40, 15), Qt.AlignmentFlag.AlignCenter, date_str)
        
        # --- 3. 绘制左右箭头 ---
        today = QDate.currentDate()
        first_vis_date = start_date
        last_vis_date = start_date.addDays(visible_count - 1)
        self.arrow_rects = {} 
        bg_rect = self.current_content_rect
        left_arrow_x = bg_rect.left() + 15
        right_arrow_x = bg_rect.right() - 15
        
        if today < first_vis_date:
            self.draw_arrow(pt, left_arrow_x, y, is_left=True, is_hover=(self.hovered_arrow == 'left'))
            self.arrow_rects['left'] = QRectF(left_arrow_x-12, y-12, 24, 24)
        if today > last_vis_date:
            self.draw_arrow(pt, right_arrow_x, y, is_left=False, is_hover=(self.hovered_arrow == 'right'))
            self.arrow_rects['right'] = QRectF(right_arrow_x-12, y-12, 24, 24)

    def draw_arrow(self, pt, x, y, is_left, is_hover=False):
        pt.save()
        col = self.config['calendar_today_color']
        col.setAlpha(int(200 * self._hover_val))
        scale = 1.0
        if is_hover: 
            scale = 1.3
            col.setAlpha(255) 
        pt.setPen(QPen(col, 2.5 if is_hover else 2))
        pt.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        size = 6 * scale
        if is_left:
            path.moveTo(x + size/2, y - size)
            path.lineTo(x - size/2, y)
            path.lineTo(x + size/2, y + size)
        else:
            path.moveTo(x - size/2, y - size)
            path.lineTo(x + size/2, y)
            path.lineTo(x - size/2, y + size)
        pt.drawPath(path)
        pt.restore()

    def mousePressEvent(self, e: QMouseEvent):
        self.close_current_popup() 
        
        # --- [修复] 锁定状态处理 ---
        if self.is_locked:
            if self.controls_visible:
                r, y, g = self.get_traffic_lights_rects()
                pos_f = QPointF(e.pos())
                if r.contains(pos_f): self.quit_app(); return
                if y.contains(pos_f): self.hide(); return 
                if g.contains(pos_f): self.toggle_lock(); return
                
                # 关键：非红绿灯区域忽略点击
                e.ignore() 
                return
            else:
                e.ignore()
                return
        # ------------------------

        # Header 红绿灯区域 (非锁定)
        if self.cached_row_heights and self._header_val > 0.5:
             r, y, g = self.get_traffic_lights_rects()
             pos = e.pos()
             if r.contains(QPointF(pos)): self.quit_app(); return
             if y.contains(QPointF(pos)): self.hide(); return 
             if g.contains(QPointF(pos)): self.toggle_lock(); return
        
        # 右上角设置菜单 (非锁定)
        if hasattr(self, 'interval_info_rect') and self.interval_info_rect.contains(QPointF(e.pos())) and self._header_val > 0.5:
            def on_interval_selected(val):
                self.config['interval'] = val
                self.save_config()
                self.force_refresh_max_geometry() 
                self.update()
            
            g_pos = self.mapToGlobal(e.pos())
            rd = self.config['row_duration']
            all_opts = [5, 10, 15, 30]
            valid_opts = [x for x in all_opts if rd % x == 0]
            if not valid_opts: valid_opts = [10]
            
            selector = QuickSelector(self, valid_opts, self.config['interval'], on_interval_selected)
            selector.show_at(g_pos)
            self.current_popup = selector
            return 

        # 日历
        pos = e.pos()
        for key, rect in self.arrow_rects.items():
            if rect.contains(QPointF(pos)):
                self.current_view_date = QDate.currentDate()
                self.force_refresh_max_geometry() 
                self.update()
                return
        
        date_at_pos = self.get_date_at_pos(pos)
        if date_at_pos:
            diff = self.current_view_date.daysTo(date_at_pos)
            self.scroll_date(diff)
            return
            
        # 右键菜单
        if e.button() == Qt.MouseButton.RightButton:
            if seg := self.get_segment_at_pos(pos):
                self.show_segment_popup(seg, e.globalPosition().toPoint())
                return
            if (idx := self.get_idx_at_pos(pos)) != -1:
                self.show_popup(idx, e.globalPosition().toPoint())
                return
            return
            
        # 创建 Segment / 拖拽窗口
        if e.button() == Qt.MouseButton.LeftButton:
            idx = self.get_idx_at_pos(pos)
            if idx != -1:
                self.state = InteractionState.CreatingSegment
                self.active_segment_idx = idx
                self.temp_end_idx = idx
                inv = self.config['interval']
                self.preview_segment = {
                    'start': idx, 'end': idx + inv, 'color': [255, 255, 255], 'layer': 0
                }
                self.force_refresh_max_geometry() 
                self.update()
                return
            self.state = InteractionState.DraggingWindow
            self.drag_start_global = e.globalPosition().toPoint()
            self.window_start_pos = self.pos()

    def wheelEvent(self, e: QWheelEvent):
        if self._hover_val > 0.5:
            delta = e.angleDelta().y()
            if delta != 0:
                steps = -1 if delta > 0 else 1
                self.scroll_date(steps)

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = e.pos()
        
        # --- [修复] 锁定状态下的严格交互控制 ---
        if self.is_locked:
            # 如果控件未浮现 (纯 Locked)，直接忽略
            if not self.controls_visible:
                e.ignore()
                return

            # 如果控件已浮现 (Locked-Hover)，只检测红绿灯
            r, y, g = self.get_traffic_lights_rects()
            old_light = self.hovered_light_idx
            
            if r.contains(QPointF(pos)): self.hovered_light_idx = 0
            elif y.contains(QPointF(pos)): self.hovered_light_idx = 1
            elif g.contains(QPointF(pos)): self.hovered_light_idx = 2
            else: 
                self.hovered_light_idx = -1
                # [关键] 如果不在红绿灯上，忽略事件，尝试让鼠标穿透
                e.ignore()

            # 强制清空其他所有元素的 Hover 状态，防止出现互动特效
            self.hovered_dot_idx = -1
            self.hovered_segment = None
            self.hovered_date = None
            self.hovered_arrow = None
            # 右上角设置区也不允许在锁定下交互，所以这里不做检测

            # 仅在红绿灯状态改变时重绘
            if old_light != self.hovered_light_idx:
                self.update()
            
            # 手型光标仅在红绿灯上显示
            if self.hovered_light_idx != -1:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            
            return
        # --- [修复结束] ---

        # --- 以下为非锁定状态 (Normal) 的常规逻辑 ---
        
        # [新增] 右上角交互区 Hover 检测
        if hasattr(self, 'interval_info_rect') and self.interval_info_rect.contains(QPointF(pos)):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.update() 
        
        old_dot = self.hovered_dot_idx
        self.hovered_dot_idx = self.get_idx_at_pos(pos)
        
        old_seg = self.hovered_segment
        self.hovered_segment = self.get_segment_at_pos(pos)
        
        r, y, g = self.get_traffic_lights_rects()
        old_light = self.hovered_light_idx
        if r.contains(QPointF(pos)): self.hovered_light_idx = 0
        elif y.contains(QPointF(pos)): self.hovered_light_idx = 1
        elif g.contains(QPointF(pos)): self.hovered_light_idx = 2
        else: self.hovered_light_idx = -1
        
        old_date = self.hovered_date
        self.hovered_date = self.get_date_at_pos(pos)
        
        old_arrow = self.hovered_arrow
        self.hovered_arrow = None
        for key, rect in self.arrow_rects.items():
            if rect.contains(QPointF(pos)):
                self.hovered_arrow = key
                break

        if old_light != self.hovered_light_idx or old_date != self.hovered_date or old_arrow != self.hovered_arrow:
            self.update()
            
        current_obj = None
        if self.hovered_segment: current_obj = ('seg', self.hovered_segment)
        elif self.hovered_dot_idx != -1:
            data = self.get_current_data()
            if str(self.hovered_dot_idx) in data['notes']:
                current_obj = ('note', self.hovered_dot_idx)
        
        if current_obj != self.last_hovered_obj:
            self.last_hovered_obj = current_obj
            self.tooltip_timer.stop()
            if self.active_tooltip:
                self.active_tooltip.close()
                self.active_tooltip = None
            if current_obj: self.tooltip_timer.start(500) 
        
        if old_dot != self.hovered_dot_idx or old_seg != self.hovered_segment: 
            self.update()

        if self.state == InteractionState.CreatingSegment:
             idx = self.get_idx_at_pos(pos)
             if idx != -1:
                 self.temp_end_idx = idx
                 s, e_idx = min(self.active_segment_idx, self.temp_end_idx), max(self.active_segment_idx, self.temp_end_idx)
                 inv = self.config['interval']
                 if idx >= self.active_segment_idx: e_idx = idx + inv
                 else: s = idx; e_idx = self.active_segment_idx + inv
                 
                 if self.preview_segment:
                     self.preview_segment['start'] = s
                     self.preview_segment['end'] = e_idx
                 
                 self.update_grid_cache() 
                 req_w, req_h = self.calculate_ideal_dim(1.0, 1.0)
                 target_h = math.ceil(req_h) + GEOMETRY_PADDING * 2
                 if abs(target_h - self.height()) > 2: 
                     self.force_refresh_max_geometry()
                 
                 self.update() 
                 
                 base_dt = datetime.combine(datetime.now().date(), time(self.config['start_time'].hour, 0))
                 t1 = base_dt + timedelta(minutes=s)
                 t2 = base_dt + timedelta(minutes=e_idx) 
                 diff = t2 - t1
                 hrs = diff.seconds // 3600
                 mins = (diff.seconds % 3600) // 60
                 dur_str = f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m"
                 QToolTip.showText(e.globalPosition().toPoint(), f"{t1.strftime('%H:%M')} - {t2.strftime('%H:%M')} ({dur_str})", self)
             return

        if self.state == InteractionState.DraggingWindow:
            diff = e.globalPosition().toPoint() - self.drag_start_global
            self.move(self.window_start_pos + diff)
            return

        if self.hovered_dot_idx != -1 or self.hovered_segment is not None or self.hovered_light_idx != -1 or self.hovered_date is not None or self.hovered_arrow is not None: 
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif hasattr(self, 'interval_info_rect') and self.interval_info_rect.contains(QPointF(pos)):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else: 
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def show_hover_tooltip(self):
        if not self.last_hovered_obj: return
        typ, val = self.last_hovered_obj
        text = ""
        if typ == 'seg': text = val.get('text', "")
        elif typ == 'note':
            data = self.get_current_data()
            text = data['notes'][str(val)].get('text', "")
        if text:
            self.active_tooltip = OverlayTooltip(text, self)
            g_pos = QCursor.pos()
            self.active_tooltip.move(g_pos + QPoint(15, 15))
            self.active_tooltip.show()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self.is_locked: return
        
        if self.state == InteractionState.DraggingWindow:
            self.force_refresh_max_geometry()
            self.save_config()
            self.state = InteractionState.Idle
            return
            
        if self.state == InteractionState.CreatingSegment:
            QToolTip.hideText()
            def on_live_change(new_c, new_t):
                if self.preview_segment:
                    self.preview_segment['color'] = [new_c.red(), new_c.green(), new_c.blue()]
                    self.preview_segment['text'] = new_t
                    self.update()
            def confirm(col, txt):
                if self.preview_segment:
                    data = self.get_current_data()
                    data['segments'].append({
                        'start': self.preview_segment['start'], 
                        'end': self.preview_segment['end'],
                        'color': [col.red(), col.green(), col.blue()],
                        'layer': 0,
                        'text': txt 
                    })
                    self.preview_segment = None
                    self.force_refresh_max_geometry() 
                    self.save_config()
                    self.update()
            def cancel_create():
                self.preview_segment = None
                self.update()
            self.close_current_popup()
            pop = EditPopup(self, default_color=QColor(255, 255, 255), 
                            on_save=confirm, 
                            on_delete=cancel_create,
                            on_live_change=on_live_change)
            pop.move(e.globalPosition().toPoint())
            self.current_popup = pop
            pop.show()
            pop.rejected.connect(cancel_create)
        self.state = InteractionState.Idle
        self.active_segment_idx = -1
        self.update()

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if self.is_locked: return
        if seg := self.get_segment_at_pos(e.pos()):
            self.del_seg(seg)

    def save_note(self, idx, color, text):
        data = self.get_current_data()
        data['notes'][str(idx)] = {
            'color': [color.red(), color.green(), color.blue()],
            'text': text
        }
        self.save_config()
        self.update()

    def del_note(self, idx):
        data = self.get_current_data()
        if str(idx) in data['notes']:
            del data['notes'][str(idx)]
            self.save_config()
            self.update()

    def del_seg(self, seg):
        data = self.get_current_data()
        if seg in data['segments']:
            data['segments'].remove(seg)
            self.force_refresh_max_geometry() 
            self.save_config()
            self.update()

    def open_settings(self):
        d = SettingsDialog(self)
        d.show()
    
    def toggle_lock(self):
        self.is_locked = not self.is_locked
        self.act_lock.setChecked(self.is_locked)
        self.update()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = TimeDotsWidget()
    w.show()
    sys.exit(app.exec())