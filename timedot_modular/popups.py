from PyQt6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QTextEdit
from PyQt6.QtCore import Qt, QPoint, QRect, QRectF, QPropertyAnimation, QEasingCurve, QPointF
from PyQt6.QtGui import QPainter, QBrush, QColor, QCursor, QFont, QPen, QFontMetrics, QGuiApplication

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
        self.text_edit.setPlaceholderText("Add note (optional)...")
        self.text_edit.setText(initial_text)
        self.text_edit.setFixedHeight(60)
        self.text_edit.setStyleSheet("QTextEdit { color: white; background-color: #444; border: 1px solid #555; border-radius: 4px; padding: 4px; }") 
        self.text_edit.textChanged.connect(self.handle_live_change)
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet("QPushButton { background-color: #444; color: #ff6666; border: 1px solid #555; border-radius: 4px; } QPushButton:hover { background-color: #555; }")
        del_btn.clicked.connect(self.handle_delete)
        save_btn = QPushButton("Save")
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
        
        # 甯冨眬璁＄畻
        self.item_height = 36
        self.w = 120
        self.h = len(items) * self.item_height + 10 # +padding
        self.resize(self.w, self.h)
        
        # 鍔ㄧ敾瀹瑰櫒
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(200)
        self.opacity_anim.setEasingCurve(QEasingCurve.Type.OutQuad)

    def show_at(self, global_pos):
        # 璋冩暣浣嶇疆锛屼娇鍏跺彸瀵归綈
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
        
        # 鑳屾櫙
        bg_rect = self.rect().adjusted(1, 1, -1, -1)
        pt.setBrush(QBrush(QColor(28, 28, 30, 250))) # iOS Secondary Background
        pt.setPen(QPen(QColor(60, 60, 60), 1))
        pt.drawRoundedRect(bg_rect, 12, 12)
        
        # 缁樺埗閫夐」
        f = pt.font()
        f.setPixelSize(14)
        f.setBold(True)
        pt.setFont(f)
        
        mouse_pos = self.mapFromGlobal(QCursor.pos())
        
        for i, val in enumerate(self.items):
            rect = QRectF(1, 5 + i * self.item_height, self.w - 2, self.item_height)
            
            # Hover 鏁堟灉
            if rect.contains(QPointF(mouse_pos)):
                pt.setBrush(QBrush(QColor(255, 255, 255, 30)))
                pt.setPen(Qt.PenStyle.NoPen)
                pt.drawRoundedRect(rect.adjusted(4, 2, -4, -2), 6, 6)
            
            # 鏂囧瓧涓庨€変腑鐘舵€?
            is_selected = (val == self.current_val)
            color = QColor(10, 132, 255) if is_selected else QColor(220, 220, 220)
            pt.setPen(color)
            
            # 缁樺埗鍦嗙偣绀烘剰 (宸︿晶)
            dot_cx = rect.left() + 20
            dot_cy = rect.center().y()
            pt.setBrush(QBrush(color))
            pt.setPen(Qt.PenStyle.NoPen)
            pt.drawEllipse(QPointF(dot_cx, dot_cy), 3, 3)
            
            # 缁樺埗鏂囧瓧
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
        self.update() # 鍒锋柊 Hover 鏁堟灉

