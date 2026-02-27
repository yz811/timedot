import copy

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QScrollArea,
                             QFrame, QLabel, QTimeEdit, QComboBox, QDoubleSpinBox, QSpinBox, QColorDialog)
from PyQt6.QtCore import Qt, QPoint, QRect, QRectF
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QPainterPath

from .constants import DEFAULT_CONFIG_VALUES, SOUND_NAMES

class SettingsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Settings")
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.resize(450, 800) # 绋嶅井鍔犲涓€鐐逛互瀹圭撼宸︿晶鐨勯噸缃寜閽?
        
        self.original_config = copy.deepcopy(main_window.config)
        self.original_day_time_ranges = copy.deepcopy(main_window.day_time_ranges)
        self.settings = main_window.config 
        
        self.dragging = False
        self.drag_start_pos = QPoint()

        self.init_ui()

    def paintEvent(self, event):
        pt = QPainter(self)
        pt.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 鑳屾櫙
        bg_rect = self.rect()
        pt.setBrush(QBrush(QColor(0, 0, 0))) 
        pt.setPen(QPen(QColor(50, 50, 50), 1))
        pt.drawRoundedRect(bg_rect, 18, 18)
        
        # 鏍囬鏍?
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
        pt.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, "Settings")

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
        
        # 椤堕儴鎸夐挳瀹瑰櫒
        nav_overlay = QWidget(self)
        nav_overlay.setGeometry(0, 0, self.width(), 54)
        nav_layout = QHBoxLayout(nav_overlay)
        nav_layout.setContentsMargins(12, 0, 12, 0)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("NavBtn")
        cancel_btn.clicked.connect(self.cancel)
        
        save_btn = QPushButton("Done")
        save_btn.setObjectName("NavBtnDone")
        save_btn.clicked.connect(self.save_and_close)
        
        nav_layout.addWidget(cancel_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(save_btn)
        
        # 婊氬姩鍖哄煙
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
            /* iOS 椋庢牸鍩虹鏍峰紡 */
            QFrame#GroupFrame { background-color: #1C1C1E; border-radius: 12px; }
            QLabel#GroupHeader { color: #8E8E93; font-size: 13px; text-transform: uppercase; margin-left: 12px; margin-bottom: 4px; }
            QLabel { color: #FFFFFF; font-size: 16px; }
            QFrame#Separator { background-color: #38383A; max-height: 1px; }
            
            /* 瀵艰埅鎸夐挳 */
            QPushButton#NavBtn { background-color: transparent; border: none; color: #0A84FF; font-size: 16px; }
            QPushButton#NavBtnDone { background-color: transparent; border: none; color: #0A84FF; font-size: 16px; font-weight: bold; }
            QPushButton#NavBtn:hover, QPushButton#NavBtnDone:hover { opacity: 0.7; }
            
            /* 杈撳叆鎺т欢 */
            QComboBox, QTimeEdit, QSpinBox, QDoubleSpinBox {
                background-color: rgba(118, 118, 128, 0.24); color: #0A84FF;
                border: none; border-radius: 6px; padding: 4px 8px; font-size: 16px;
                min-width: 60px; max-width: 90px;
                selection-background-color: #0A84FF;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button, QTimeEdit::up-button, QTimeEdit::down-button { width: 0px; }
            
            /* 鍗曢」閲嶇疆鎸夐挳 (灏忓渾鍦堢澶? */
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
                color: #FF453A; /* 鎮仠鍙樼孩 */
                background-color: rgba(255, 69, 58, 0.1);
            }
            
            /* 鍏ㄥ眬閲嶇疆鎸夐挳 */
            QPushButton#ResetBtn {
                background-color: #1C1C1E; color: #FF453A; font-size: 16px;
                border-radius: 12px; padding: 12px; border: none;
            }
            QPushButton#ResetBtn:pressed { background-color: #2C2C2E; }
        """)

        # --- 1. 鏃堕棿閰嶇疆 ---
        self.add_group_header("TIME SETTINGS")
        time_group = self.create_group_container()
        tg_layout = QVBoxLayout(time_group)
        tg_layout.setSpacing(0); tg_layout.setContentsMargins(0,0,0,0)
        
        current_day_start, current_day_end = self.main_window.get_day_time_range(self.main_window.current_view_date)
        self.start_edit = QTimeEdit(current_day_start)
        self.end_edit = QTimeEdit(current_day_end)
        self.start_edit.setDisplayFormat("HH:mm"); self.end_edit.setDisplayFormat("HH:mm")
        
        self.row_dur_combo = QComboBox()
        self.row_dur_combo.addItems(["30m", "1h", "2h", "3h"])
        idx = {30:0, 60:1, 120:2, 180:3}.get(self.settings['row_duration'], 1)
        self.row_dur_combo.setCurrentIndex(idx)
        
        self.interval_combo = QComboBox() 
        
        self.add_row(tg_layout, "Start Time", self.start_edit)
        self.add_separator(tg_layout)
        self.add_row(tg_layout, "End Time", self.end_edit)
        self.add_separator(tg_layout)
        self.add_row(tg_layout, "Row Duration", self.row_dur_combo)
        self.add_separator(tg_layout)
        # [淇敼] 鍚嶅瓧鏀逛负 鍒嗛挓/鐐?
        self.add_row(tg_layout, "Interval", self.interval_combo, is_last=True)
        
        self.content_layout.addWidget(time_group)

        # --- 2. 瑙嗚澶栬 ---
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
        self.time_scale_combo = QComboBox()
        self.time_scale_combo.addItems(["Off", "On"])
        self.time_scale_combo.setCurrentIndex(1 if self.settings.get('time_scale_always_on', False) else 0)
        self.font_weight_spin = self.create_spinbox(100, 900, self.settings.get('font_weight', 700), step=100)
        
        # [鏍稿績] 浣跨敤 key 鍙傛暟鏉ヨ嚜鍔ㄦ坊鍔犲乏渚ч噸缃寜閽?
        self.add_row(vg_layout, "Dot Size", self.dot_size_spin, key='dot_radius')
        self.add_separator(vg_layout)
        self.add_row(vg_layout, "Dot Spacing", self.dot_space_spin, key='dot_spacing')
        self.add_separator(vg_layout)
        self.add_row(vg_layout, "Note Dot Scale", self.note_scale_spin, key='note_dot_scale')
        self.add_separator(vg_layout)
        self.add_row(vg_layout, "Time Font Size", self.font_size_spin, key='font_size')
        self.add_separator(vg_layout)
        self.add_row(vg_layout, "Calendar Font Size", self.cal_font_spin, key='calendar_font_size')
        self.add_separator(vg_layout)
        self.add_row(vg_layout, "Always Show Time Scale", self.time_scale_combo)
        self.add_separator(vg_layout)
        self.add_row(vg_layout, "Font Weight", self.font_weight_spin, key='font_weight', is_last=True)
        
        self.content_layout.addWidget(vis_group)

        # --- 3. Segment 甯冨眬 ---
        self.add_group_header("SEGMENT LAYOUT")
        seg_group = self.create_group_container()
        sg_layout = QVBoxLayout(seg_group)
        sg_layout.setSpacing(0); sg_layout.setContentsMargins(0,0,0,0)
        
        self.seg_offset_spin = self.create_spinbox(-50, 100, self.settings.get('seg_base_offset', 6))
        self.seg_step_spin = self.create_spinbox(0, 100, self.settings.get('seg_layer_step', 12))
        self.seg_margin_spin = self.create_spinbox(-50, 100, self.settings.get('seg_bottom_margin', 8))
        
        self.add_row(sg_layout, "Base Offset (A)", self.seg_offset_spin, key='seg_base_offset')
        self.add_separator(sg_layout)
        self.add_row(sg_layout, "Layer Step (B)", self.seg_step_spin, key='seg_layer_step')
        self.add_separator(sg_layout)
        self.add_row(sg_layout, "Bottom Margin (C)", self.seg_margin_spin, key='seg_bottom_margin', is_last=True)
        self.content_layout.addWidget(seg_group)

        # --- 4. 棰滆壊涓庡弽棣?---
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

        self.add_row(sc_layout, "Timer End Sound", self.sound_timer)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "Note Alert Sound", self.sound_note)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "Background Color", self.bg_btn)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "Current Color", self.curr_btn)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "Today Color", self.cal_btn)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "Past Date Color", self.past_btn)
        self.add_separator(sc_layout)
        self.add_row(sc_layout, "Future Date Color", self.future_btn, is_last=True)
        
        self.content_layout.addWidget(sc_group)
        
        # --- 鍏ㄥ眬閲嶇疆 ---
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("ResetBtn")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self.reset_to_defaults)
        self.content_layout.addWidget(reset_btn)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
        
        self.update_interval() # 鍒濆鍖栭棿闅斾笅鎷夋
        self.connect_signals()

    # --- 杈呭姪鏋勫缓鍑芥暟 ---
    def create_group_container(self):
        frame = QFrame()
        frame.setObjectName("GroupFrame")
        return frame
    
    def add_group_header(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("GroupHeader")
        self.content_layout.addWidget(lbl)

    def create_item_reset_btn(self, key, widget):
        # 鍒涘缓涓€涓皬鐨勯噸缃寜閽?
        btn = QPushButton("↻") # 浣跨敤Unicode鍥炴棆绠ご浣滀负鍥炬爣
        btn.setObjectName("ItemResetBtn")
        btn.setToolTip("Reset this item")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        def reset_action():
            default_val = DEFAULT_CONFIG_VALUES.get(key)
            if default_val is not None:
                # 鏍规嵁鎺т欢绫诲瀷璁剧疆鍊?
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget.setValue(default_val)
                # 濡傛灉鏈潵鏀寔鍏朵粬绫诲瀷(濡侰omboBox)鐨勫崟椤归噸缃紝鍙湪杩欓噷鎵╁睍
        
        btn.clicked.connect(reset_action)
        return btn

    def add_row(self, layout, label_text, widget, key=None, is_last=False):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        # 宸﹁竟璺濈粰澶т竴鐐癸紝濡傛灉鍔犱簡閲嶇疆鎸夐挳锛岃瑙変笂浼氬崰鐢ㄥ乏杈硅窛绌洪棿
        row_layout.setContentsMargins(16, 12, 16, 12) 
        
        # 濡傛灉鎻愪緵浜?key 涓旇 key 鏈夐粯璁ゅ€硷紝鍒欐坊鍔犲乏渚ч噸缃寜閽?
        if key and key in DEFAULT_CONFIG_VALUES:
            reset_btn = self.create_item_reset_btn(key, widget)
            row_layout.addWidget(reset_btn)
            # 鍔犱竴鐐圭偣闂磋窛璁╂寜閽拰鏂囧瓧鍒嗗紑
            row_layout.addSpacing(4)
        
        lbl = QLabel(label_text)
        row_layout.addWidget(lbl)
        row_layout.addStretch() 
        row_layout.addWidget(widget)
        
        layout.addWidget(row_widget)
    
    def add_separator(self, layout):
        sep_container = QWidget()
        sep_layout = QHBoxLayout(sep_container)
        # 鍒嗗壊绾垮乏渚х暀鐧斤細濡傛灉鏈夐噸缃寜閽紝鍒嗗壊绾垮簲璇ヤ粠鏂囧瓧寮€濮嬶紝杩樻槸閫氭爮锛?
        # iOS 閫氬父鏄枃瀛楀榻愩€傛垜浠涓?50px 澶ф瀵归綈鏂囧瓧
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
        self.time_scale_combo.currentIndexChanged.connect(self.sync_settings)
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
        self.time_scale_combo.setCurrentIndex(0)
        self.font_weight_spin.setValue(defaults['font_weight'])
        self.seg_offset_spin.setValue(defaults['seg_base_offset'])
        self.seg_step_spin.setValue(defaults['seg_layer_step'])
        self.seg_margin_spin.setValue(defaults['seg_bottom_margin'])
        self.sync_settings()

    def update_interval(self):
        # [鏍稿績淇] 鍒濆鍖栨椂锛屽厛鑾峰彇褰撳墠閰嶇疆涓殑鐪熷疄 interval 鍊?
        current_config_val = self.settings.get('interval', 10)
        
        idx = self.row_dur_combo.currentIndex()
        rm = [30, 60, 120, 180][idx]
        opts = [5, 10, 15, 30] 
        valid = [str(x) for x in opts if x <= rm and rm % x == 0]
        if not valid: valid = ["10"]
        
        self.interval_combo.blockSignals(True)
        self.interval_combo.clear()
        self.interval_combo.addItems(valid)
        
        # 灏濊瘯鍦ㄦ柊鐨勫垪琛ㄤ腑鎵惧埌閰嶇疆鐨勫€?
        target_text = str(current_config_val)
        idx = self.interval_combo.findText(target_text)
        
        if idx >= 0:
            self.interval_combo.setCurrentIndex(idx)
        else:
            self.interval_combo.setCurrentIndex(0) # 濡傛灉褰撳墠鍊间笉鍚堟硶锛屾墠鍥為€€鍒伴粯璁?
            
        self.interval_combo.blockSignals(False)
        
        # 鍙湁褰撳€肩湡鐨勫彉浜嗘墠鍐欏洖锛岄伩鍏嶅垵濮嬪寲灏辫鐩?
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
        start_t = self.start_edit.time().toPyTime()
        end_t = self.end_edit.time().toPyTime()
        self.main_window.set_current_day_time_range(start_t, end_t, save=False, refresh=False)
        self.settings['row_duration'] = [30,60,120,180][self.row_dur_combo.currentIndex()]
        if self.interval_combo.currentText():
            self.settings['interval'] = int(self.interval_combo.currentText())
        
        self.settings['dot_radius'] = self.dot_size_spin.value()
        self.settings['dot_spacing'] = self.dot_space_spin.value()
        self.settings['note_dot_scale'] = self.note_scale_spin.value()
        self.settings['font_size'] = self.font_size_spin.value()
        self.settings['calendar_font_size'] = self.cal_font_spin.value()
        self.settings['time_scale_always_on'] = (self.time_scale_combo.currentIndex() == 1)
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
        self.main_window.day_time_ranges = copy.deepcopy(self.original_day_time_ranges)
        self.main_window.apply_current_day_time_range()
        self.main_window.force_refresh_max_geometry() 
        self.main_window.update()
        self.reject()

