import json
import math
import os
from datetime import datetime, time, timedelta

from PyQt6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon, QToolTip
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QRectF, QEasingCurve, QPointF, QDate, QVariantAnimation
from PyQt6.QtGui import (QPainter, QBrush, QColor, QMouseEvent, QWheelEvent, QCursor, QIcon,
                         QPixmap, QPen, QPainterPath, QFontMetrics, QGuiApplication, QRegion)

from .constants import (
    BASE_MARGIN, SIDEBAR_WIDTH, CALENDAR_HEIGHT, GAP_WIDTH_NARROW, GAP_WIDTH_WIDE,
    HEADER_FULL_HEIGHT, FOOTER_GAP, MIN_CAL_STEP, GEOMETRY_PADDING,
    InteractionState, GLOBAL_STYLESHEET, CONFIG_FILE
)
from .popups import OverlayTooltip, EditPopup, QuickSelector
from .settings_dialog import SettingsDialog
from .sound import play_sound_by_type

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
            # [鏂板] 鏃堕棿鍧楀竷灞€鍙傛暟
            'seg_base_offset': 6,    # A: 鍦嗙偣鍒板簳閮ㄧ涓€灞傜殑璺濈
            'seg_layer_step': 12,    # B: 灞傜骇涔嬮棿鐨勯棿璺?
            'seg_bottom_margin': 8   # C: 鏈€鍚庝竴灞傚埌涓嬩竴琛岀殑璺濈
        }
        self.data_store = {} 
        self.day_time_ranges = {}
        self.current_view_date = QDate.currentDate()
        self.last_date_check = QDate.currentDate()
        
        self.load_config()
        self.apply_current_day_time_range()

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

        self.arrow_rects = {} 
        self.day_resize_mode = None
        self.day_resize_initial_start = None
        self.day_resize_initial_end = None
        self.day_resize_candidates = []
        self.day_resize_candidate_times = []
        self.day_resize_candidate_offsets = []
        self.day_resize_selected_idx = -1
        self.day_resize_anim = 0.0
        self.day_resize_cleanup_pending = False
        self.pending_boundary_idx = -1
        self.pending_boundary_mode = None
        self.pending_boundary_pos = QPoint()
        self.pending_boundary_press_pos = QPoint()
        self.boundary_hold_timer = QTimer(self)
        self.boundary_hold_timer.setSingleShot(True)
        self.boundary_hold_timer.timeout.connect(self._activate_pending_day_resize)

        self.cached_row_heights = {} 
        self.update_grid_cache()
        
        self.max_dims = (100, 100) 
        self.current_content_rect = QRect()
        
        self.tooltip_timer = QTimer(self)
        self.tooltip_timer.setSingleShot(True)
        self.tooltip_timer.timeout.connect(self.show_hover_tooltip)
        self.last_hovered_obj = None 

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
        self.apply_current_day_time_range()
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
        m.addAction("Settings", self.open_settings)
        m.addSeparator()
        m.addAction("Show/Hide", self.toggle_visibility)
        self.act_lock = m.addAction("Lock/Unlock")
        self.act_lock.setCheckable(True)
        self.act_lock.triggered.connect(self.toggle_lock)
        m.addAction("Quit", self.quit_app)
        self.tray.setContextMenu(m)
        self.tray.show()
        self.tray.activated.connect(lambda r: self.toggle_visibility() if r == QSystemTrayIcon.ActivationReason.Trigger else None)

    def _date_key(self, date_obj=None):
        d = date_obj if date_obj is not None else self.current_view_date
        return d.toString(Qt.DateFormat.ISODate)

    def _time_to_minutes(self, t):
        return t.hour * 60 + t.minute

    def _minutes_to_time(self, mins):
        mins = int(max(0, min(24 * 60, mins)))
        if mins == 24 * 60:
            return time(0, 0)
        return time(mins // 60, mins % 60)

    def _parse_time_string(self, value, fallback):
        try:
            return datetime.strptime(value, "%H:%M").time()
        except Exception:
            return fallback

    def get_day_time_range(self, date_obj=None):
        key = self._date_key(date_obj)
        base_start = self.config.get('start_time', time(9, 0))
        base_end = self.config.get('end_time', time(19, 0))
        day_conf = self.day_time_ranges.get(key)
        if not isinstance(day_conf, dict):
            return base_start, base_end
        start_t = self._parse_time_string(day_conf.get('start_time', ""), base_start)
        end_t = self._parse_time_string(day_conf.get('end_time', ""), base_end)
        return start_t, end_t

    def apply_current_day_time_range(self):
        start_t, end_t = self.get_day_time_range(self.current_view_date)
        self.config['start_time'] = start_t
        self.config['end_time'] = end_t

    def set_current_day_time_range(self, start_t, end_t, save=False, refresh=True):
        key = self._date_key(self.current_view_date)
        self.day_time_ranges[key] = {
            'start_time': start_t.strftime("%H:%M"),
            'end_time': end_t.strftime("%H:%M")
        }
        self.config['start_time'] = start_t
        self.config['end_time'] = end_t
        if refresh:
            self.force_refresh_max_geometry()
            self.update()
        if save:
            self.save_config()

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

            loaded_start = self._parse_time_string(d.get('start_time', "09:00"), self.config['start_time'])
            loaded_end = self._parse_time_string(d.get('end_time', "19:00"), self.config['end_time'])

            self.config.update({
                'start_time': loaded_start,
                'end_time': loaded_end,
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
            self.day_time_ranges = d.get('day_time_ranges', {}) if isinstance(d.get('day_time_ranges', {}), dict) else {}
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
        d['day_time_ranges'] = self.day_time_ranges
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
        start_abs = st.hour * 60 + st.minute
        end_abs = et.hour * 60 + et.minute
        if end_abs <= start_abs:
            end_abs += 24 * 60
        grid_base = self.get_grid_base_start_minute()
        s_off = start_abs - grid_base
        e_off = end_abs - grid_base

        if (self.state == InteractionState.ResizingDayBounds or self.day_resize_cleanup_pending or self.day_resize_anim > 0.001) and self.day_resize_candidate_offsets and self.day_resize_mode:
            if self.day_resize_mode == 'start':
                target_s = min(self.day_resize_candidate_offsets)
                ext = max(0, s_off - target_s)
                s_off = s_off - int(ext * self.day_resize_anim)
            elif self.day_resize_mode == 'end':
                target_e = max(self.day_resize_candidate_offsets) + max(1, inv)
                ext = max(0, target_e - e_off)
                e_off = e_off + int(ext * self.day_resize_anim)
        
        if rd == 0: rd = 60 
        if inv == 0: inv = 10
        rows = max(1, math.ceil(e_off / rd))
        cols = rd // inv
        return rows, cols, s_off, e_off

    def get_grid_base_start_minute(self):
        st = self.config['start_time']
        base = st.hour * 60
        if self.day_resize_mode == 'start' and (self.state == InteractionState.ResizingDayBounds or self.day_resize_cleanup_pending or self.day_resize_anim > 0.001):
            start_abs = st.hour * 60 + st.minute
            extra = max(1, self.config['row_duration']) * 3
            base = max(0, start_abs - extra)
            # Keep row origin aligned to exact hour to preserve the original y-axis reading.
            base = (base // 60) * 60
        return base

    def get_selected_candidate_row(self):
        if not (0 <= self.day_resize_selected_idx < len(self.day_resize_candidate_offsets)):
            return -1
        rd = max(1, self.config['row_duration'])
        return self.day_resize_candidate_offsets[self.day_resize_selected_idx] // rd

    def get_local_preview_gap_after_row(self, row_idx):
        if self.day_resize_anim <= 0.001:
            return 0.0
        sel_row = self.get_selected_candidate_row()
        if sel_row <= 0:
            return 0.0
        # Add space only in the local gap where the preview label is drawn.
        if row_idx == sel_row - 1:
            return 20.0 * self.day_resize_anim
        return 0.0

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
        
        # 璇诲彇閰嶇疆鍙傛暟
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
            
            # 璁＄畻琛岄珮锛?
            # 濡傛灉娌℃湁 segment (max_l == -1)锛岃楂?= 鍦嗙偣楂樺害
            # 濡傛灉鏈?segment锛岃楂?= 鍦嗙偣楂樺害 + A + (max_l * B) + C
            # 杩欓噷鐨?C 杩樻壙鎷呬簡鈥滄渶搴曞眰 Segment 鑷韩鐨勫帤搴?(绾?px)鈥濈殑鍔熻兘
            if max_l == -1:
                self.cached_row_heights[r] = base_h_px
            else:
                # 棰濆鍔?4px 鏄负浜嗗绾虫渶鍚庝竴鏍圭嚎鐨勮瑙夊帤搴?
                self.cached_row_heights[r] = base_h_px + offset_a + (max_l * step_b) + margin_c + 4

    def get_vertical_margins(self, h_val, head_val):
        top_extra = HEADER_FULL_HEIGHT * head_val 
        bottom_extra = (CALENDAR_HEIGHT + FOOTER_GAP) * h_val 
        if self.day_resize_anim > 0.001:
            bottom_extra *= (1.0 - self.day_resize_anim)
        
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

    # [鏂板] 璁＄畻鍓?n 涓紳闅欑殑鎬诲搴?(鑰冭檻浜嗗绐勬贩鍚堢殑鎯呭喌)
    def get_cumulative_gap_offset(self, gap_count, expansion_ratio=1.0):
        total_offset = 0
        # [鏍稿績淇] 绉婚櫎 start_min銆?
        # 鍥犱负缃戞牸甯冨眬鐜板湪鏄粷瀵瑰榻愬埌鏁寸偣鐨?(Column 0 鎬绘槸 XX:00)锛?
        # 鎵€浠ョ紳闅欑殑浣嶇疆涔熸槸鍥哄畾鐨勶細绗竴涓紳闅欐€绘槸瀵瑰簲 XX:30锛岀浜屼釜鎬绘槸 XX:60(鏁寸偣)銆?
        for k in range(1, gap_count + 1):
            # k=1 -> 30鍒?(绐?
            # k=2 -> 60鍒?(瀹?
            # k=3 -> 90鍒?(绐?
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
        
        # [鏍稿績鍙樺寲] 杩欓噷涓嶅啀鏄畝鍗曠殑涔樻硶锛岃€屾槸璋冪敤绱姞鍑芥暟
        total_gaps_w = self.get_cumulative_gap_offset(gap_count, h_val)
        
        w_content = mg*2 + sw + cols*col_unit - sp_curr + total_gaps_w
        h_content = top_m + bottom_m
        for r in range(rows):
             h_content += self.cached_row_heights[r]
             if r < rows - 1: 
                 h_content += sp_curr + self.get_local_preview_gap_after_row(r)
        
        if head_val > 0.1:
            min_header_w = 16 + (6*2 + 8)*2 + 6*2 + 16 
            if w_content < min_header_w:
                w_content = min_header_w

        return w_content, h_content
    
    def force_refresh_max_geometry(self):
        # 1. 璁板綍璋冩暣鍓嶇殑鐘舵€?
        old_geo = self.geometry()
        screen_geo = self.screen().availableGeometry()
        
        # 妫€娴嬪惛闄勭姸鎬?(闃堝€艰涓?15px锛岀◢寰瀹逛竴鐐逛互闃插井灏忓亸宸?
        # 濡傛灉搴曢儴璺濈灞忓箷搴曢儴灏忎簬 15px锛岃涓哄凡鍚搁檮鍒板簳閮?
        is_bottom_snapped = abs(old_geo.bottom() - screen_geo.bottom()) < 15
        # 濡傛灉鍙充晶璺濈灞忓箷鍙充晶灏忎簬 15px锛岃涓哄凡鍚搁檮鍒板彸渚?
        is_right_snapped = abs(old_geo.right() - screen_geo.right()) < 15
        
        # 2. 璁＄畻鏂扮殑鐞嗘兂灏哄
        max_w, max_h = self.calculate_ideal_dim(1.0, 1.0)
        padding = GEOMETRY_PADDING
        target_w = math.ceil(max_w) + padding * 2
        target_h = math.ceil(max_h) + padding * 2
        
        # 3. 搴旂敤鏂板昂瀵?
        self.max_dims = (target_w, target_h)
        self.setFixedSize(target_w, target_h)
        
        # 4. 鏍规嵁涔嬪墠鐨勫惛闄勭姸鎬佷慨姝ｄ綅缃?
        new_geo = self.geometry() # 鑾峰彇鏂板昂瀵稿悗鐨勫嚑浣?(榛樿宸︿笂瑙掍笉鍙?
        
        # 淇鍨傜洿鏂瑰悜
        if is_bottom_snapped:
            # 濡傛灉涔嬪墠鍚搁檮鍦ㄥ簳閮紝鐜板湪涔熻鍚搁檮鍦ㄥ簳閮?(鎰忓懗鐫€楂樺害鍙樺寲鏃讹紝Top 浼氬姩)
            new_geo.moveBottom(screen_geo.bottom())
        elif new_geo.bottom() > screen_geo.bottom():
            # 濡傛灉娌″惛闄勶紝浣嗗彉澶у悗瓒呭嚭浜嗗簳閮紝鎺ㄥ洖鍘?
            new_geo.moveBottom(screen_geo.bottom())
            
        # 淇姘村钩鏂瑰悜
        if is_right_snapped:
            # 濡傛灉涔嬪墠鍚搁檮鍦ㄥ彸渚э紝鐜板湪涔熻鍚搁檮鍦ㄥ彸渚?(鎰忓懗鐫€瀹藉害鍙樺寲鏃讹紝Left 浼氬姩)
            new_geo.moveRight(screen_geo.right())
        elif new_geo.right() > screen_geo.right():
            # 濡傛灉娌″惛闄勶紝浣嗗彉澶у悗瓒呭嚭浜嗗彸渚э紝鎺ㄥ洖鍘?
            new_geo.moveRight(screen_geo.right())
        
        # 5. 鏈€鍚庤繘琛岃秺鐣屼繚鎶?(闃叉绐楀彛鍥犱负涓婅堪绉诲姩璺戝嚭宸︿笂杈圭晫)
        if new_geo.top() < screen_geo.top():
            new_geo.moveTop(screen_geo.top())
        if new_geo.left() < screen_geo.left():
            new_geo.moveLeft(screen_geo.left())
            
        # 6. 绉诲姩绐楀彛骞舵洿鏂板竷灞€
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
        
        # 璁＄畻褰撳墠鍒椾箣鍓嶆湁澶氬皯涓紳闅?
        num_gaps = c_idx // cols_per_30
        
        # [鏍稿績鍙樺寲] 璋冪敤绱姞鍑芥暟璁＄畻鍏蜂綋鐨勫儚绱犲亸绉?
        return self.get_cumulative_gap_offset(num_gaps, self._hover_val)

    def get_dot_abs_pos(self, r_idx, c_idx):
        bg = self.current_content_rect 
        if not bg.isValid(): return QPointF(0,0)
        
        rad, sp, sw = self.get_render_params()
        top_m, _ = self.get_vertical_margins(self._hover_val, self._header_val)
        
        y = bg.top() + top_m
        for i in range(r_idx):
            y += self.cached_row_heights.get(i, 20) 
            y += sp + self.get_local_preview_gap_after_row(i)
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
            
            # [淇敼 1] 缂╁皬鍒楀垽瀹氱殑姘村钩鑼冨洿锛氫粠 2.5鍊嶅崐寰?鏀逛负 1鍊嶅崐寰?
            # 鍙湁榧犳爣姘村钩浣嶇疆涓ユ牸鍦ㄥ渾鐐瑰搴﹀唴鏃讹紝鎵嶈涓哄懡涓簡璇ュ垪
            if abs(rel_x - center_x) <= 1.2*rad:
                found_c = c
                break
                
        if found_c == -1: return -1
        
        curr_y = self.current_content_rect.top() + top_m
        found_r = -1
        for r in range(rows):
            row_h = self.cached_row_heights.get(r, 20)
            total_row_block = row_h + sp + self.get_local_preview_gap_after_row(r)
            if curr_y <= pos_f.y() < curr_y + total_row_block:
                found_r = r
                break
            curr_y += total_row_block
            
        if found_r == -1: return -1
        
        center = self.get_dot_abs_pos(found_r, found_c)
        
        # [淇敼 2] 缂╁皬鏈€缁堝垽瀹氳寖鍥达細浣跨敤涓ユ牸鐨勬鍑犻噷寰楄窛绂?
        # 鍙湁榧犳爣璺濈鍦嗗績鐨勮窛绂诲皬浜庡崐寰勬椂锛屾墠绠楀懡涓?
        # 鍘熸潵鐨勪唬鐮佹槸 .manhattanLength() < rad * 2.5锛岃寖鍥存槸涓€涓緢澶х殑鑿卞舰
        dx = pos_f.x() - center.x()
        dy = pos_f.y() - center.y()
        
        # 浣跨敤骞虫柟姣旇緝閬垮厤寮€鏍瑰彿锛屾晥鐜囩◢楂樹笖閫昏緫绛変环
        if (dx*dx + dy*dy) <= rad*rad:
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
        
        # 璇诲彇甯冨眬鍙傛暟
        offset_a = self.config.get('seg_base_offset', 6)
        step_b = self.config.get('seg_layer_step', 12)
        
        # [鏍稿績淇] 涓ユ牸鐨勫垽瀹氶珮搴︼紝涓嶉殢 layer_step 鍙樺ぇ鑰屽彉澶?
        # 鏃犺闂磋窛鎷夊澶э紝鍙娴嬬嚎娈典笂涓?4px 鐨勮寖鍥?(鎬婚珮 8px)
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
                
                # 鍒涘缓涓€涓獎鐨勫垽瀹氱煩褰?
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
        # [鏍稿績淇] 涓嶈浣跨敤浼犲叆鐨?w (褰撳墠鍔ㄧ敾涓殑瀹藉害) 鏉ヨ绠楀ぉ鏁?
        # 鑰屾槸鏍规嵁 Hover=1.0 鏃剁殑鏈€澶у搴︽潵璁＄畻锛岀‘淇濆ぉ鏁板浐瀹氫笉鍙?
        
        # 璁＄畻鏈€澶у睍寮€鏃剁殑鐞嗘兂瀹藉害
        max_w, _ = self.calculate_ideal_dim(1.0, 1.0)
        
        # 浣跨敤鏈€澶у搴﹁绠楀竷灞€鍙傛暟
        arrow_area_width = 30 
        available_w_max = max(50, max_w - arrow_area_width * 2) 
        
        safe_step = max(MIN_CAL_STEP, available_w_max / 15)
        visible_count = int(available_w_max / safe_step)
        
        if visible_count > 15: visible_count = 15
        if visible_count % 2 == 0: visible_count -= 1 
        if visible_count < 3: visible_count = 3
        
        # step_x 渚濈劧瑕佸熀浜庡綋鍓嶅搴﹁绠楋紝浠ヤ繚璇佹媺浼稿姩鐢?
        # 浣?visible_count 琚攣瀹氫簡锛屽氨涓嶄細绐佸彉
        current_available_w = max(50, w - arrow_area_width * 2)
        
        # 濡傛灉褰撳墠瀹藉害澶皬(Idle鐘舵€?锛屼細瀵艰嚧 step_x 杩囧皬鎸ゅ湪涓€璧?
        # 浣嗗洜涓烘鏃?alpha=0 鐪嬩笉瑙侊紝鎵€浠ユ病鍏崇郴銆傞噸鐐规槸鏁伴噺涓嶈烦鍙樸€?
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
        # ---------------------------------------------------------
        # 1. [鍘熸湁閫昏緫] 榧犳爣浜や簰涓庨攣瀹氱姸鎬佸鐞?(淇濇寔涓嶅彉)
        # ---------------------------------------------------------
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        
        in_content = self.current_content_rect.contains(local_pos)
        
        target_hover = 0.0
        target_header = 0.0
        
        if self.is_locked:
            if in_content:
                self.hover_time_acc += 50 
                if self.hover_time_acc > 1200: 
                    self.controls_visible = True
            else:
                self.hover_time_acc = 0
                self.controls_visible = False
            
            desired_transparent = True 
            
            if self.controls_visible:
                r, y, g = self.get_traffic_lights_rects()
                hit_zone = r.united(y).united(g).adjusted(-5, -5, 5, 5)
                if hit_zone.contains(QPointF(local_pos)):
                    desired_transparent = False 
            
            current_transparent = bool(self.windowFlags() & Qt.WindowType.WindowTransparentForInput)
            if current_transparent != desired_transparent:
                self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, desired_transparent)
                self.show()

            if desired_transparent:
                if self.hovered_dot_idx != -1 or self.hovered_segment is not None or self.hovered_date is not None:
                    self.hovered_dot_idx = -1
                    self.hovered_segment = None
                    self.hovered_date = None
                    self.hovered_arrow = None
                    self.setCursor(Qt.CursorShape.ArrowCursor)
                    self.update()

            target_hover = 0.0 
            target_header = 1.0 if self.controls_visible else 0.0
            
        else:
            target_header = 1.0 if (in_content or self.config['sidebar_always_on']) else 0.0
            target_hover = 1.0 if (in_content or self.config['sidebar_always_on']) else 0.0
            self.controls_visible = False
            self.hover_time_acc = 0
            
            current_transparent = bool(self.windowFlags() & Qt.WindowType.WindowTransparentForInput)
            if current_transparent:
                self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, False)
                self.show()

        # ---------------------------------------------------------
        # 2. [鍘熸湁閫昏緫] 鍔ㄧ敾鎻掑€?(淇濇寔涓嶅彉)
        # ---------------------------------------------------------
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

        resize_speed = 0.18
        target_resize = 1.0 if self.state == InteractionState.ResizingDayBounds else 0.0
        resize_changed = False
        if abs(self.day_resize_anim - target_resize) > 0.001:
            self.day_resize_anim += (target_resize - self.day_resize_anim) * resize_speed
            resize_changed = True
            needs_repaint = True
        else:
            self.day_resize_anim = target_resize

        if needs_repaint:
            if resize_changed:
                self.force_refresh_max_geometry()
            else:
                self.update_layout_dynamic()
            self.update()

        if self.day_resize_cleanup_pending and self.day_resize_anim <= 0.01:
            self.day_resize_cleanup_pending = False
            self.day_resize_mode = None
            self.day_resize_initial_start = None
            self.day_resize_initial_end = None
            self.day_resize_candidate_times = []
            self.day_resize_candidate_offsets = []
            self.day_resize_candidates = []
            self.day_resize_selected_idx = -1

        # ---------------------------------------------------------
        # 3. [鍘熸湁閫昏緫] 鏃ユ湡鍙樻洿妫€鏌?(淇濇寔涓嶅彉)
        # ---------------------------------------------------------
        now_date = QDate.currentDate()
        if self.last_date_check != now_date:
            if self.current_view_date == self.last_date_check:
                self.current_view_date = now_date
                self.apply_current_day_time_range()
                self.force_refresh_max_geometry()
                self.update()
            self.last_date_check = now_date

        # ---------------------------------------------------------
        # 4. [淇鍚嶿 澹伴煶妫€鏌ラ€昏緫
        # ---------------------------------------------------------
        now = datetime.now()
        curr_min = now.minute

        if self.last_sound_min != curr_min:
            self.last_sound_min = curr_min
            
            # [淇] 姘歌繙鑾峰彇 "浠婂ぉ" 鐨勬暟鎹紝涓嶈褰撳墠瑙嗗浘鍦ㄧ湅鍝竴澶?
            today_str = now_date.toString(Qt.DateFormat.ISODate)
            
            if today_str in self.data_store:
                data = self.data_store[today_str]
                current_day_min = now.hour * 60 + now.minute
                today_start_time, _ = self.get_day_time_range(now_date)
                start_base = today_start_time.hour * 60 + today_start_time.minute
                
                # --- 妫€鏌?Segments ---
                for s in data['segments']:
                    if 'end_abs' in s:
                        end_min = s['end_abs']
                    else:
                        # [閲嶈淇] s['end'] 瀛樺偍鐨勬槸鍒嗛挓鏁帮紝涓嶆槸绱㈠紩锛屼笉闇€瑕佸啀涔?interval
                        # 涔嬪墠鐨勯敊璇叕寮忥細start_base + s['end'] * inv
                        # 淇鍚庣殑鍏紡锛歴tart_base + s['end']
                        end_min = start_base + s['end']
                    
                    if int(end_min) == current_day_min: 
                        play_sound_by_type(self.config['sound_timer'])
                
                # --- 妫€鏌?Notes ---
                inv = self.config['interval']
                # Note 妫€鏌ラ€昏緫锛氬綋鍓嶅垎閽熸濂芥槸 Interval 鐨勫€嶆暟
                if current_day_min % inv == 0:
                    if current_day_min >= start_base:
                        # s['end'] 鏄垎閽熸暟锛屽悓鐞?Note 鐨?key 涔熸槸鍒嗛挓鏁扮储寮?
                        curr_offset_min = int(current_day_min - start_base)
                        if str(curr_offset_min) in data['notes']:
                            play_sound_by_type(self.config['sound_note'])

        # ---------------------------------------------------------
        # 5. [鍘熸湁閫昏緫] 鐣岄潰寰绾у埛鏂?(淇濇寔涓嶅彉)
        # ---------------------------------------------------------
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
        
        # 缁樺埗 Header
        if self._header_val > 0.01:
            light_alpha = int(255 * self._header_val)
            r_rect, y_rect, g_rect = self.get_traffic_lights_rects()
            
            # [鏍稿績淇敼] 缁樺埗鍙充笂瑙掍俊鎭細浠呭湪闈為攣瀹氱姸鎬佷笅鏄剧ず
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
                
                # 鏅鸿兘瀵归綈璁＄畻
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

        # 缁樺埗缃戞牸
        if self._hover_val > 0.05:
            op = int(255 * self._hover_val)
            unified_font = pt.font()
            unified_font.setPixelSize(self.config['font_size'])
            unified_font.setWeight(self.config['font_weight'])
            pt.setFont(unified_font)
            pt.setPen(QColor(255, 255, 255, op))

            start_hour_abs_min = self.get_grid_base_start_minute()
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

        # 缁樺埗鐐归樀
        now = datetime.now()
        grid_base = self.get_grid_base_start_minute()
        view_dt = datetime.combine(self.current_view_date.toPyDate(), time((grid_base // 60) % 24, grid_base % 60))
        passed_mins = (now - view_dt).total_seconds() / 60
        is_today = (self.current_view_date == QDate.currentDate())
        curr_data = self.get_current_data()
        notes = curr_data['notes']
        grid_base = self.get_grid_base_start_minute()
        base_start_abs = self._time_to_minutes(self.config['start_time'])
        base_end_abs = self._time_to_minutes(self.config['end_time'])
        if base_end_abs <= base_start_abs:
            base_end_abs += 24 * 60
        base_s_off = base_start_abs - grid_base
        base_e_off = base_end_abs - grid_base
        candidate_offset_set = set(self.day_resize_candidate_offsets) if self.day_resize_anim > 0.01 else set()
        
        for r in range(rows):
            for c in range(cols):
                idx = r*rd + c*inv
                if idx < s_off or idx >= e_off: continue
                in_base_range = (base_s_off <= idx < base_e_off)
                if not in_base_range and idx not in candidate_offset_set:
                    continue
                cp = self.get_dot_abs_pos(r, c)
                r_real = rad
                if idx == self.hovered_dot_idx: r_real *= 1.3 
                if idx in candidate_offset_set and not in_base_range:
                    col = QColor(170, 170, 170, 175)
                    if 0 <= self.day_resize_selected_idx < len(self.day_resize_candidate_offsets) and idx == self.day_resize_candidate_offsets[self.day_resize_selected_idx]:
                        col = QColor(10, 132, 255, 245)
                        r_real *= 1.2
                else:
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
                if in_base_range and str(idx) in notes:
                    nc = notes[str(idx)]['color']
                    pt.setBrush(QBrush(QColor(*nc)))
                    pt.drawEllipse(cp, r_real*self.config.get('note_dot_scale', 0.4), r_real*self.config.get('note_dot_scale', 0.4))

        # 缁樺埗 Segment
        segs = curr_data['segments'][:]
        if self.preview_segment: segs.append(self.preview_segment)
        for s in segs:
            col = QColor(*s['color'])
            is_hovered = (s == self.hovered_segment)
            is_prev = (s == self.preview_segment)
            self.draw_segment(pt, s['start'], s['end'], col, s.get('layer', 0), passed_mins, is_today, is_hovered=is_hovered, is_preview=is_prev)

        if self.day_resize_anim > 0.01:
            self.draw_day_resize_overlay(pt)

        # 缁樺埗鏃ュ巻
        cal_show = self._hover_val * (1.0 - self.day_resize_anim)
        if cal_show > 0.01:
            dh = CALENDAR_HEIGHT
            cal_base = bg_rect.bottom() - BASE_MARGIN
            pt.save()
            path = QPainterPath()
            path.addRoundedRect(bg_rect, 16, 16)
            pt.setClipPath(path)
            old_hover = self._hover_val
            self._hover_val = cal_show
            self.draw_calendar_bar(pt, cal_base - dh/2, bg_rect.width(), dh, bg_rect.left())
            self._hover_val = old_hover
            pt.restore()

    def draw_segment(self, pt, start_idx, end_idx, color, layer, passed_mins, is_today, is_hovered=False, is_preview=False):
        rad, sp, sw = self.get_render_params()
        rd = self.config['row_duration']
        inv = self.config['interval']
        thickness = 2.5 
        if is_hovered or is_preview: thickness = 4.0
        
        offset_a = self.config.get('seg_base_offset', 6)
        step_b = self.config.get('seg_layer_step', 12)
        y_offset_from_center = rad + offset_a + (layer * step_b)

        # 瑙嗚闂撮殭 padding (淇濇寔涓嶅彉锛岀敤浜庤В鍐抽灏剧浉杩為噸鍙犻棶棰?
        seg_padding = 2.0 

        s_row = start_idx // rd
        e_row = end_idx // rd
        
        for r in range(s_row, e_row + 1):
            row_s = r * rd; row_e = (r+1) * rd
            d_s = max(start_idx, row_s); d_e = min(end_idx, row_e)
            if d_s >= d_e: continue 
            
            # --- 璁＄畻璧风偣 X1 ---
            c_s = (d_s % rd) // inv
            p1 = self.get_dot_abs_pos(r, c_s)
            # 璧风偣锛氬渾蹇?- 鍗婂緞 - 鍗婁釜闂磋窛 + padding
            x1 = p1.x() - rad - (sp/2) + seg_padding
            
            # --- 璁＄畻缁堢偣 X2 [鏍稿績淇敼] ---
            # 閫昏緫鍙樻洿锛氫笉鍐嶄娇鐢?d_e (涓嬩竴涓偣) 鐨勫乏杈圭紭锛岃€屾槸浣跨敤 d_e - 1 (褰撳墠娈垫渶鍚庝竴涓偣) 鐨勫彸杈圭紭銆?
            # 杩欐牱锛屾棤璁哄悗闈㈡槸鍚︽湁瀹介棿璺?Gap)鎴栨崲琛岋紝绾挎閮戒細绮剧‘鍋滃湪褰撳墠鐐圭殑缁撴潫浣嶇疆銆?
            last_dot_idx = d_e - 1
            c_e = (last_dot_idx % rd) // inv
            p_end = self.get_dot_abs_pos(r, c_e)
            
            # 缁堢偣锛氬渾蹇?+ 鍗婂緞 + 鍗婁釜闂磋窛 - padding
            x2 = p_end.x() + rad + (sp/2) - seg_padding

            # y鍧愭爣
            y = p1.y() + y_offset_from_center
            
            # 缁樺埗閫昏緫 (淇濇寔涓嶅彉)
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
        days_zh = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
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
            # 璁＄畻褰撳墠鍔ㄧ敾甯х殑閫忔槑搴?
            alpha = int(255 * self._hover_val)
            
            is_viewing = (d == self.current_view_date)
            is_today = (d == QDate.currentDate())
            
            # --- 1. 璁剧疆鍦嗙偣棰滆壊 ---
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
            
            # 璁剧疆鍛ㄦ湯绾㈠湀 (甯﹂€忔槑搴?
            if d.dayOfWeek() >= 6:
                red_pen_color = QColor(255, 80, 80)
                red_pen_color.setAlpha(alpha) 
                pt.setPen(QPen(red_pen_color, 1.5)) 
            else:
                pt.setPen(Qt.PenStyle.NoPen)
                
            pt.drawEllipse(QPointF(cx, cy), r, r)
            
            # --- 2. 缁樺埗鏂囧瓧 (鏄熸湡鍜屾棩鏈? ---
            # [鏍稿績淇] 绉婚櫎浜?"if self._hover_val > 0.8" 鐨勫垽鏂?
            # 鍙 alpha > 0 (绋嶅井鍙)锛屽氨闅忓渾鐐逛竴璧风粯鍒讹紝瀹炵幇鍚屾娣″叆
            if alpha > 0:
                txt_col = QColor(180, 180, 180, alpha)
                if d.dayOfWeek() >= 6: 
                    txt_col = QColor(255, 100, 100, alpha) 
                
                f = pt.font()
                f.setPixelSize(base_font_size) 
                pt.setFont(f)
                pt.setPen(txt_col)
                
                # 缁樺埗鏄熸湡 (鍦嗙偣涓婃柟)
                pt.drawText(QRectF(cx-20, cy-r-15, 40, 15), Qt.AlignmentFlag.AlignCenter, days_zh[d.dayOfWeek()-1])
                
                # 缁樺埗鏃ユ湡 (鍦嗙偣涓嬫柟锛屼粎闂撮殧鏄剧ず)
                dist = abs(i - mid_idx)
                should_show_date = (i == mid_idx) or (dist > 0 and dist % 3 == 0)
                if should_show_date:
                    pt.setPen(QColor(180, 180, 180, alpha))
                    date_str = f"{d.month()}/{d.day()}"
                    pt.drawText(QRectF(cx-20, cy+r+2, 40, 15), Qt.AlignmentFlag.AlignCenter, date_str)
        
        # --- 3. 缁樺埗宸﹀彸绠ご ---
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

    def get_last_dot_idx(self):
        _, _, s_off, e_off = self.get_grid_info()
        inv = self.config['interval']
        if inv <= 0 or e_off <= s_off:
            return -1
        return s_off + (((e_off - s_off) - 1) // inv) * inv

    def get_first_dot_idx(self):
        _, _, s_off, e_off = self.get_grid_info()
        if e_off <= s_off:
            return -1
        return s_off

    def _build_day_resize_candidates(self, mode):
        inv = max(1, self.config['interval'])
        rd = max(1, self.config['row_duration'])
        start_min = self._time_to_minutes(self.config['start_time'])
        end_min = self._time_to_minutes(self.config['end_time'])
        if end_min <= start_min:
            end_min += 24 * 60
        base_min = self.get_grid_base_start_minute()
        extra_side = 3 * rd

        if mode == 'start':
            lower = max(0, start_min - extra_side)
            upper = max(lower, end_min - inv)
            current_val = start_min
        else:
            lower = start_min
            upper = min((24 * 60) - inv, end_min + extra_side)
            current_val = max(start_min, end_min - inv)

        if upper < lower:
            lower, upper = current_val, current_val

        candidates = [c for c in range(lower, upper + 1, inv) if 0 <= c <= (24 * 60) - inv]
        if current_val not in candidates:
            current_clamped = max(0, min((24 * 60) - inv, current_val))
            candidates.append(current_clamped)
            candidates = sorted(set(candidates))

        self.day_resize_candidate_times = candidates
        self.day_resize_candidate_offsets = [c - base_min for c in candidates if c >= base_min]
        self.day_resize_selected_idx = candidates.index(current_val) if current_val in candidates else 0
        self.day_resize_candidates = []

    def _update_day_resize_hitboxes(self):
        if len(self.day_resize_candidate_offsets) == 0:
            self.day_resize_candidates = []
            return

        self.day_resize_candidates = []
        rd = self.config['row_duration']
        inv = max(1, self.config['interval'])
        for off in self.day_resize_candidate_offsets:
            row = off // rd
            col = (off % rd) // inv
            cp = self.get_dot_abs_pos(row, col)
            self.day_resize_candidates.append(QRectF(cp.x() - 11, cp.y() - 11, 22, 22))

    def _nearest_day_resize_candidate(self, pos):
        if not self.day_resize_candidates:
            return -1
        px = float(pos.x())
        py = float(pos.y())
        nearest_idx = -1
        nearest_dist = 1e18
        for i, rect in enumerate(self.day_resize_candidates):
            cx = rect.center().x()
            cy = rect.center().y()
            d = (cx - px) * (cx - px) + (cy - py) * (cy - py)
            if d < nearest_dist:
                nearest_dist = d
                nearest_idx = i
        if nearest_dist > 30 * 30:
            return -1
        return nearest_idx

    def _format_minutes_label(self, mins):
        mins = int(max(0, mins))
        hh = (mins // 60) % 24
        mm = mins % 60
        return f"{hh:02d}:{mm:02d}"

    def _get_resize_preview_minutes(self, candidate_min):
        if self.day_resize_mode == 'end':
            return candidate_min + max(1, self.config['interval'])
        return candidate_min

    def draw_day_resize_overlay(self, pt):
        self._update_day_resize_hitboxes()
        if not self.day_resize_candidates:
            return

        pt.save()
        alpha_scale = max(0.0, min(1.0, self.day_resize_anim))

        for i, rect in enumerate(self.day_resize_candidates):
            is_selected = (i == self.day_resize_selected_idx)
            c = QColor(10, 132, 255, int(240 * alpha_scale)) if is_selected else QColor(210, 210, 210, int(180 * alpha_scale))
            r = (6.0 if is_selected else 4.0) * (0.7 + 0.3 * alpha_scale)
            pt.setBrush(QBrush(c))
            pt.setPen(Qt.PenStyle.NoPen)
            pt.drawEllipse(rect.center(), r, r)

        if 0 <= self.day_resize_selected_idx < len(self.day_resize_candidate_times):
            selected_rect = self.day_resize_candidates[self.day_resize_selected_idx]
            preview_min = self._get_resize_preview_minutes(self.day_resize_candidate_times[self.day_resize_selected_idx])
            selected_label = self._format_minutes_label(preview_min)
            font = pt.font()
            font.setPixelSize(12)
            font.setBold(True)
            pt.setFont(font)
            pt.setPen(QColor(255, 255, 255, int(220 * alpha_scale)))
            rd = max(1, self.config['row_duration'])
            inv = max(1, self.config['interval'])
            sel_off = self.day_resize_candidate_offsets[self.day_resize_selected_idx]
            sel_row = sel_off // rd
            sel_col = (sel_off % rd) // inv
            sel_cp = self.get_dot_abs_pos(sel_row, sel_col)
            if sel_row > 0:
                upper_cp = self.get_dot_abs_pos(sel_row - 1, sel_col)
                label_y = (upper_cp.y() + sel_cp.y()) / 2.0 - 9.0
            else:
                # First row has no row above; show label slightly above the selected dot.
                label_y = sel_cp.y() - 34.0
            label_rect = QRectF(sel_cp.x() - 44, label_y, 88, 18)
            pt.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignCenter,
                selected_label
            )
        pt.restore()

    def _clear_pending_day_resize(self):
        self.boundary_hold_timer.stop()
        self.pending_boundary_idx = -1
        self.pending_boundary_mode = None
        self.pending_boundary_press_pos = QPoint()

    def _start_creating_segment(self, idx):
        self.state = InteractionState.CreatingSegment
        self.active_segment_idx = idx
        self.temp_end_idx = idx
        inv = self.config['interval']
        self.preview_segment = {
            'start': idx,
            'end': idx + inv,
            'color': [255, 255, 255],
            'layer': 0
        }
        self.force_refresh_max_geometry()
        self.update()

    def _activate_pending_day_resize(self):
        if self.pending_boundary_idx == -1 or self.pending_boundary_mode is None:
            return
        if not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            self._clear_pending_day_resize()
            return
        self.state = InteractionState.ResizingDayBounds
        self.day_resize_cleanup_pending = False
        self.day_resize_mode = self.pending_boundary_mode
        self.day_resize_initial_start = self.config['start_time']
        self.day_resize_initial_end = self.config['end_time']
        self._build_day_resize_candidates(self.day_resize_mode)
        self.force_refresh_max_geometry()
        self._update_day_resize_hitboxes()
        sel_idx = self._nearest_day_resize_candidate(self.pending_boundary_pos)
        if sel_idx >= 0:
            self.day_resize_selected_idx = sel_idx
        self._clear_pending_day_resize()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()

    def mousePressEvent(self, e: QMouseEvent):
        self.close_current_popup() 
        self._clear_pending_day_resize()
        if self.day_resize_cleanup_pending and self.day_resize_anim > 0.01:
            e.ignore()
            return
        
        # --- [淇] 閿佸畾鐘舵€佸鐞?---
        if self.is_locked:
            if self.controls_visible:
                r, y, g = self.get_traffic_lights_rects()
                pos_f = QPointF(e.pos())
                if r.contains(pos_f): self.quit_app(); return
                if y.contains(pos_f): self.hide(); return 
                if g.contains(pos_f): self.toggle_lock(); return
                
                # 鍏抽敭锛氶潪绾㈢豢鐏尯鍩熷拷鐣ョ偣鍑?
                e.ignore() 
                return
            else:
                e.ignore()
                return
        # ------------------------

        # Header 绾㈢豢鐏尯鍩?(闈為攣瀹?
        if self.cached_row_heights and self._header_val > 0.5:
             r, y, g = self.get_traffic_lights_rects()
             pos = e.pos()
             if r.contains(QPointF(pos)): self.quit_app(); return
             if y.contains(QPointF(pos)): self.hide(); return 
             if g.contains(QPointF(pos)): self.toggle_lock(); return
        
        # 鍙充笂瑙掕缃彍鍗?(闈為攣瀹?
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

        # 鏃ュ巻
        pos = e.pos()
        for key, rect in self.arrow_rects.items():
            if rect.contains(QPointF(pos)):
                self.current_view_date = QDate.currentDate()
                self.apply_current_day_time_range()
                self.force_refresh_max_geometry() 
                self.update()
                return
        
        date_at_pos = self.get_date_at_pos(pos)
        if date_at_pos:
            diff = self.current_view_date.daysTo(date_at_pos)
            self.scroll_date(diff)
            return
            
        # 鍙抽敭鑿滃崟
        if e.button() == Qt.MouseButton.RightButton:
            if seg := self.get_segment_at_pos(pos):
                self.show_segment_popup(seg, e.globalPosition().toPoint())
                return
            if (idx := self.get_idx_at_pos(pos)) != -1:
                self.show_popup(idx, e.globalPosition().toPoint())
                return
            return
            
        # 鍒涘缓 Segment / 鎷栨嫿绐楀彛
        if e.button() == Qt.MouseButton.LeftButton:
            idx = self.get_idx_at_pos(pos)
            if idx != -1:
                first_idx = self.get_first_dot_idx()
                last_idx = self.get_last_dot_idx()
                if idx == first_idx or idx == last_idx:
                    self.pending_boundary_idx = idx
                    self.pending_boundary_mode = 'start' if idx == first_idx else 'end'
                    self.pending_boundary_pos = e.pos()
                    self.pending_boundary_press_pos = e.pos()
                    self.boundary_hold_timer.start(260)
                    return
                self._start_creating_segment(idx)
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
        if self.day_resize_cleanup_pending and self.day_resize_anim > 0.01:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        
        # --- [淇] 閿佸畾鐘舵€佷笅鐨勪弗鏍间氦浜掓帶鍒?---
        if self.is_locked:
            # 濡傛灉鎺т欢鏈诞鐜?(绾?Locked)锛岀洿鎺ュ拷鐣?
            if not self.controls_visible:
                e.ignore()
                return

            # 濡傛灉鎺т欢宸叉诞鐜?(Locked-Hover)锛屽彧妫€娴嬬孩缁跨伅
            r, y, g = self.get_traffic_lights_rects()
            old_light = self.hovered_light_idx
            
            if r.contains(QPointF(pos)): self.hovered_light_idx = 0
            elif y.contains(QPointF(pos)): self.hovered_light_idx = 1
            elif g.contains(QPointF(pos)): self.hovered_light_idx = 2
            else: 
                self.hovered_light_idx = -1
                # [鍏抽敭] 濡傛灉涓嶅湪绾㈢豢鐏笂锛屽拷鐣ヤ簨浠讹紝灏濊瘯璁╅紶鏍囩┛閫?
                e.ignore()

            # 寮哄埗娓呯┖鍏朵粬鎵€鏈夊厓绱犵殑 Hover 鐘舵€侊紝闃叉鍑虹幇浜掑姩鐗规晥
            self.hovered_dot_idx = -1
            self.hovered_segment = None
            self.hovered_date = None
            self.hovered_arrow = None
            # 鍙充笂瑙掕缃尯涔熶笉鍏佽鍦ㄩ攣瀹氫笅浜や簰锛屾墍浠ヨ繖閲屼笉鍋氭娴?

            # 浠呭湪绾㈢豢鐏姸鎬佹敼鍙樻椂閲嶇粯
            if old_light != self.hovered_light_idx:
                self.update()
            
            # 鎵嬪瀷鍏夋爣浠呭湪绾㈢豢鐏笂鏄剧ず
            if self.hovered_light_idx != -1:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            
            return
        # --- [淇缁撴潫] ---

        if self.pending_boundary_idx != -1:
            self.pending_boundary_pos = pos
            if self.boundary_hold_timer.isActive():
                if (pos - self.pending_boundary_press_pos).manhattanLength() > 8:
                    idx = self.pending_boundary_idx
                    self._clear_pending_day_resize()
                    self._start_creating_segment(idx)
                else:
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                    return

        if self.state == InteractionState.ResizingDayBounds:
            self._update_day_resize_hitboxes()
            sel_idx = self._nearest_day_resize_candidate(pos)
            if sel_idx >= 0 and sel_idx != self.day_resize_selected_idx:
                self.day_resize_selected_idx = sel_idx
                if 0 <= sel_idx < len(self.day_resize_candidate_times):
                    tmin = self._get_resize_preview_minutes(self.day_resize_candidate_times[sel_idx])
                    QToolTip.showText(e.globalPosition().toPoint(), self._format_minutes_label(tmin), self)
                self.update()
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            return

        # --- 浠ヤ笅涓洪潪閿佸畾鐘舵€?(Normal) 鐨勫父瑙勯€昏緫 ---
        
        # [鏂板] 鍙充笂瑙掍氦浜掑尯 Hover 妫€娴?
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
        if self.day_resize_cleanup_pending and self.day_resize_anim > 0.01:
            return

        if self.pending_boundary_idx != -1:
            idx = self.pending_boundary_idx
            self._clear_pending_day_resize()
            self._start_creating_segment(idx)
        
        if self.state == InteractionState.ResizingDayBounds:
            QToolTip.hideText()
            new_start_time = None
            new_end_time = None
            if 0 <= self.day_resize_selected_idx < len(self.day_resize_candidate_times):
                sel = self.day_resize_candidate_times[self.day_resize_selected_idx]
                current_start = self._time_to_minutes(self.day_resize_initial_start)
                current_end = self._time_to_minutes(self.day_resize_initial_end)
                if current_end <= current_start:
                    current_end += 24 * 60

                if self.day_resize_mode == 'start':
                    new_start = min(sel, current_end - self.config['interval'])
                    new_start_time = self._minutes_to_time(new_start)
                    new_end_time = self._minutes_to_time(current_end)
                elif self.day_resize_mode == 'end':
                    new_end = max(sel + self.config['interval'], current_start + self.config['interval'])
                    new_start_time = self._minutes_to_time(current_start)
                    new_end_time = self._minutes_to_time(new_end)

            self.state = InteractionState.Idle
            self.day_resize_cleanup_pending = True
            if new_start_time is not None and new_end_time is not None:
                self.set_current_day_time_range(new_start_time, new_end_time, save=True)
            else:
                self.force_refresh_max_geometry()
                self.update()
            return
        
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

