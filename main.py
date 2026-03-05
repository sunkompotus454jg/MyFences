import sys
import os
import json
import shutil
import uuid
import ctypes
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QListView, QFrame, QMenu, QColorDialog, QDialog, QLabel, QPushButton, QSizePolicy)
from PyQt6.QtGui import QFileSystemModel, QDesktopServices, QCursor, QColor, QIcon, QPainter, QPen, QBrush
from PyQt6.QtCore import Qt, QPoint, QSize, QUrl, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty, QRect, QFileInfo
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

try:
    from PyQt6.QtWidgets import QFileIconProvider
except ImportError:
    try:
        from PyQt6.QtGui import QFileIconProvider
    except ImportError:
        from PyQt6.QtGui import QAbstractFileIconProvider as QFileIconProvider

USER_ROOT = os.path.expanduser("~")
MYFENCES_DIR = os.path.join(USER_ROOT, "MyFencesData")
os.makedirs(MYFENCES_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(MYFENCES_DIR, "fences_config.json")

HEADER_HEIGHT = 35 
BORDER_RADIUS = 5  

THEMES = {
    "Blue":   {"name": "Синий Неон",      "border": "#00d4ff", "bg": "#141419", "body": "#1a1a21", "title": "#00d4ff"},
    "Purple": {"name": "Фиолетовый Неон", "border": "#b82bf2", "bg": "#16101c", "body": "#1e1626", "title": "#b82bf2"},
    "Green":  {"name": "Зеленый Неон",    "border": "#00ff88", "bg": "#101c15", "body": "#16261c", "title": "#00ff88"},
    "Orange": {"name": "Оранжевый Неон",  "border": "#ffaa00", "bg": "#1c1610", "body": "#261e16", "title": "#ffaa00"},
    "Red":    {"name": "Красный Неон",    "border": "#ff0055", "bg": "#1c1014", "body": "#26161a", "title": "#ff0055"}
}

def qss(color_str):
    c = QColor(color_str)
    if not c.isValid(): 
        return color_str
    
    alpha = c.alpha()
    if alpha < 3: 
        alpha = 3 
        
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha / 255.0:.3f})"


class VectorSearchButton(QPushButton):
    """Кастомная кнопка, которая сама рисует миниатюрную стильную лупу"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # --- УМЕНЬШИЛИ РАЗМЕР КНОПКИ ---
        self.setFixedSize(26, 26) 
        # ------------------------------
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Искать иконки")
        self._current_color = QColor("white")
        self._base_color = QColor("white")
        self._hover_color = QColor("white")
        self._pressed = False

    def set_theme_color(self, color_str):
        self._base_color = QColor(color_str)
        if not self.underMouse():
            self._current_color = self._base_color
        self.update()

    def enterEvent(self, event):
        self._current_color = self._hover_color
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._current_color = self._base_color
        self.update()
        super().leaveEvent(event)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        offset = 1 if self._pressed else 0
        
        pen = QPen(self._current_color)
        # --- УМЕНЬШИЛИ ТОЛЩИНУ ЛИНИИ ---
        pen.setWidthF(1.3) # Теперь линия тоньше
        # ------------------------------
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        w = self.width()
        h = self.height()
        
        # --- УМЕНЬШИЛИ ПАРАМЕТРЫ ЛУПЫ ---
        cx = w / 2 + offset
        cy = h / 2 + offset
        r = 5 # Радиус круга меньше
        # -------------------------------
        
        # Смещаем центр влево, чтобы ручка влезла
        draw_cx = cx - 2
        
        painter.drawEllipse(QPoint(int(draw_cx), int(cy)), r, r)
        
        handle_start_x = draw_cx + r * 0.707
        handle_start_y = cy + r * 0.707
        
        # --- УМЕНЬШИЛИ ДЛИНУ РУЧКИ ---
        handle_end_x = draw_cx + r * 1.5 
        handle_end_y = cy + r * 1.5
        # ----------------------------
        
        painter.drawLine(QPoint(int(handle_start_x), int(handle_start_y)), 
                         QPoint(int(handle_end_x), int(handle_end_y)))


class CustomIconProvider(QFileIconProvider):
    def icon(self, info):
        if isinstance(info, QFileInfo):
            path = info.absoluteFilePath()
            if path.lower().endswith('.url'):
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            line = line.strip()
                            if line.lower().startswith("iconfile="):
                                icon_path = line.split("=", 1)[1].strip().strip('"').strip("'")
                                if os.path.exists(icon_path):
                                    if icon_path.lower().endswith('.exe'):
                                        return super().icon(QFileInfo(icon_path))
                                    else:
                                        return QIcon(icon_path)
                except Exception:
                    pass
        return super().icon(info)

class CustomFileSystemModel(QFileSystemModel):
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            name = super().data(index, role)
            if name:
                return os.path.splitext(name)[0]
        return super().data(index, role)

class CustomThemeDialog(QDialog):
    def __init__(self, parent=None, default_border="#00d4ff", default_body="#1a1a21", default_title="#ffffff"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(380, 420)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QFrame(self)
        self.container.setObjectName("MainContainer")
        self.layout.addWidget(self.container)
        
        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(20, 20, 20, 20)
        c_layout.setSpacing(10)
        
        c_layout.addWidget(QLabel("Название пресета:"))
        self.name_input = QLineEdit("Мой цвет")
        c_layout.addWidget(self.name_input)
        
        c_layout.addWidget(QLabel("Цвет контура (HEX):"))
        border_layout = QHBoxLayout()
        self.border_input = QLineEdit(default_border)
        self.border_btn = QPushButton("🎨")
        self.border_btn.setFixedSize(32, 30)
        border_layout.addWidget(self.border_input)
        border_layout.addWidget(self.border_btn)
        c_layout.addLayout(border_layout)

        c_layout.addWidget(QLabel("Цвет текста заголовка (HEX):"))
        title_layout = QHBoxLayout()
        self.title_input = QLineEdit(default_title)
        self.title_btn = QPushButton("🎨")
        self.title_btn.setFixedSize(32, 30)
        title_layout.addWidget(self.title_input)
        title_layout.addWidget(self.title_btn)
        c_layout.addLayout(title_layout)
        
        c_layout.addWidget(QLabel("Основной цвет фона (HEX):"))
        body_layout = QHBoxLayout()
        self.body_input = QLineEdit(default_body)
        self.body_btn = QPushButton("🎨")
        self.body_btn.setFixedSize(32, 30)
        body_layout.addWidget(self.body_input)
        body_layout.addWidget(self.body_btn)
        c_layout.addLayout(body_layout)

        c_layout.addWidget(QLabel("Превью:"))
        self.preview_frame = QFrame()
        self.preview_frame.setFixedHeight(40)
        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        self.preview_label = QLabel("Моя Сетка")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_label)
        
        c_layout.addWidget(self.preview_frame)

        c_layout.addSpacing(10)
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Отмена")
        self.btn_ok = QPushButton("Сохранить")
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        c_layout.addLayout(btn_layout)
        
        self.border_btn.clicked.connect(lambda: self.pick_color(self.border_input))
        self.title_btn.clicked.connect(lambda: self.pick_color(self.title_input))
        self.body_btn.clicked.connect(lambda: self.pick_color(self.body_input))
        
        self.border_input.textChanged.connect(self.update_preview)
        self.title_input.textChanged.connect(self.update_preview)
        self.body_input.textChanged.connect(self.update_preview)
        
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.drag_pos = None
        self.update_preview() 
        
    def pick_color(self, line_edit):
        color = QColorDialog.getColor(QColor(line_edit.text()), self, "Выберите цвет", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            line_edit.setText(color.name(QColor.NameFormat.HexArgb) if color.alpha() < 255 else color.name())

    def update_preview(self):
        border = self.border_input.text().strip()
        body = self.body_input.text().strip()
        title = self.title_input.text().strip()
        
        border_qss = qss(border)
        body_qss = qss(body)
        title_qss = qss(title)
        
        self.preview_frame.setStyleSheet(f"QFrame {{ background-color: {body_qss}; border: 2px solid {border_qss}; border-radius: {BORDER_RADIUS}px; }}")
        self.preview_label.setStyleSheet(f"QLabel {{ color: {title_qss}; font-weight: bold; font-family: 'Segoe UI Variable', 'Segoe UI'; font-size: 14px; border: none; background: transparent; }}")
        
        c_border = QColor(border)
        preview_border = border_qss if c_border.isValid() and c_border.alpha() > 10 else "rgba(0, 212, 255, 1.0)"
        
        self.container.setStyleSheet(f"""
            QFrame#MainContainer {{ background-color: #1a1a21; border: 2px solid {preview_border}; border-radius: {BORDER_RADIUS}px; }}
            QLabel {{ color: white; border: none; font-family: 'Segoe UI'; font-size: 13px; }}
            QLineEdit {{ background-color: #141419; color: white; border: 1px solid #555; border-radius: 3px; padding: 6px; font-family: 'Segoe UI'; font-size: 13px; }}
            QPushButton {{ background-color: #141419; color: white; border: 1px solid #555; border-radius: 4px; padding: 6px 15px; font-family: 'Segoe UI'; }}
            QPushButton:hover {{ background-color: {preview_border}; color: black; border: 1px solid {preview_border}; }}
        """)

    def get_theme_data(self):
        border = self.border_input.text().strip()
        body = self.body_input.text().strip()
        title = self.title_input.text().strip()
        name = self.name_input.text().strip() or "Мой цвет"
        
        c_border = QColor(border) if QColor(border).isValid() else QColor("#00d4ff")
        c_body = QColor(body) if QColor(body).isValid() else QColor("#1a1a21")
        c_title = QColor(title) if QColor(title).isValid() else QColor("#ffffff")
        
        if c_border.alpha() < 3: c_border.setAlpha(3)
        if c_body.alpha() < 3: c_body.setAlpha(3)
        if c_title.alpha() < 3: c_title.setAlpha(3)
        
        border_hex = c_border.name(QColor.NameFormat.HexArgb)
        body_hex = c_body.name(QColor.NameFormat.HexArgb)
        title_hex = c_title.name(QColor.NameFormat.HexArgb)
        
        if c_body.alpha() <= 10:
            bg_hex = body_hex
        else:
            c_bg = c_body.darker(110)
            bg_hex = c_bg.name(QColor.NameFormat.HexArgb)
            
        return {"name": name, "border": border_hex, "bg": bg_hex, "body": body_hex, "title": title_hex}

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos: self.move(event.globalPosition().toPoint() - self.drag_pos)
    def mouseReleaseEvent(self, event):
        self.drag_pos = None


class ThemeMenu(QMenu):
    def __init__(self, title, parent_window):
        super().__init__(title, parent_window)
        self.parent_window = parent_window 
        
    def mouseReleaseEvent(self, event):
        action = self.actionAt(event.pos())
        if action and event.button() == Qt.MouseButton.RightButton:
            theme_key = action.data()
            if theme_key and str(theme_key).startswith("Custom_"):
                self.parent_window.manager.remove_custom_theme(theme_key)
                self.removeAction(action)
                self.close() 
                return
        super().mouseReleaseEvent(event)


class ResizeHandle(QWidget):
    def __init__(self, parent_widget, instance):
        super().__init__(parent_widget)
        self.instance = instance
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.instance.start_resizing(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.instance.do_resizing(event.globalPosition().toPoint())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.instance.stop_resizing()
            event.accept()


class FenceInstance(QWidget):
    
    @pyqtProperty(int)
    def current_body_height(self):
        return self.body_frame.maximumHeight()

    @current_body_height.setter
    def current_body_height(self, value):
        self.body_frame.setMinimumHeight(value)
        self.body_frame.setMaximumHeight(value)
        self.setFixedHeight(HEADER_HEIGHT + value)
        
    def __init__(self, manager, config):
        super().__init__()
        self.manager = manager
        self.config = config
        
        self.id = config.get("id", "default")
        self.title = config.get("title", "Новая Сетка") 
        self.target_path = config.get("path", os.getcwd())
        self.current_theme = config.get("theme", "Blue")
        self.is_locked = config.get("locked", False)
        
        os.makedirs(self.target_path, exist_ok=True)

        self.start_width = config.get("width", 500)
        self.full_height = config.get("height", 600)
        start_x = config.get("x", 100)
        start_y = config.get("y", 100)

        screen = QApplication.primaryScreen().availableGeometry()
        if start_x < screen.left() or start_x > screen.right() - 50:
            start_x = screen.left() + 50
        if start_y < screen.top() or start_y > screen.bottom() - HEADER_HEIGHT:
            start_y = screen.top() + 50

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnBottomHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        
        self.setFixedWidth(self.start_width)
        self.setFixedHeight(HEADER_HEIGHT)
        self.move(start_x, start_y)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(HEADER_HEIGHT)
        self.header_frame.setObjectName("HeaderFrame")
        
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(15, 0, 10, 0) 
        h_layout.setSpacing(0)
        
        self.title_edit = QLineEdit(self.title)
        self.title_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_edit.setReadOnly(True)
        self.title_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.title_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        self.search_btn = VectorSearchButton(self)
        self.search_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.search_btn.clicked.connect(self.toggle_search)

        # Пустышка слева для баланса
        dummy = QWidget()
        dummy.setFixedSize(self.search_btn.width(), self.search_btn.height())
        dummy.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        h_layout.addWidget(dummy)
        h_layout.addWidget(self.title_edit, 1) 
        h_layout.addWidget(self.search_btn)

        self.body_frame = QFrame()
        self.body_frame.setObjectName("BodyFrame")
        self.body_frame.setMinimumHeight(0)
        self.body_frame.setMaximumHeight(0)
        
        b_layout = QVBoxLayout(self.body_frame)
        b_layout.setContentsMargins(5, 5, 5, 5)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.hide()
        
        self.model = CustomFileSystemModel()
        self.model.setRootPath(self.target_path)
        self.model.setReadOnly(False)
        self.model.setNameFilterDisables(False) 
        
        self.icon_provider = CustomIconProvider()
        self.model.setIconProvider(self.icon_provider)
        
        self.search_input.textChanged.connect(self.apply_search)
        
        self.list_view = QListView()
        self.list_view.setModel(self.model) 
        
        self.model.directoryLoaded.connect(self.on_directory_loaded)
        self.list_view.setRootIndex(self.model.index(self.target_path))
        
        self.list_view.setViewMode(QListView.ViewMode.IconMode)
        self.list_view.setIconSize(QSize(32, 32)) 
        self.list_view.setGridSize(QSize(90, 80)) 
        self.list_view.setUniformItemSizes(True)  
        self.list_view.setLayoutMode(QListView.LayoutMode.Batched) 
        self.list_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_view.setWordWrap(True) 
        self.list_view.setEditTriggers(QListView.EditTrigger.EditKeyPressed | QListView.EditTrigger.SelectedClicked)

        self.list_view.doubleClicked.connect(self.open_file)
        self.list_view.setAcceptDrops(False)
        self.list_view.setMinimumHeight(0)
        
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self.show_context_menu)
        
        b_layout.addWidget(self.search_input)
        b_layout.addWidget(self.list_view)

        self.main_layout.addWidget(self.header_frame)
        self.main_layout.addWidget(self.body_frame)

        self.resizer = ResizeHandle(self, self)

        self.animation = QPropertyAnimation(self, b"current_body_height")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.drag_pos = None
        self.resizing = False
        self.is_expanded = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_mouse)
        self.timer.start(50)

        self.header_frame.mousePressEvent = self.h_press
        self.header_frame.mouseMoveEvent = self.h_move
        self.header_frame.mouseReleaseEvent = self.h_release
        self.header_frame.mouseDoubleClickEvent = self.enable_edit 
        
        self.title_edit.returnPressed.connect(self.disable_edit)
        self.title_edit.editingFinished.connect(self.disable_edit)

        self.apply_theme(self.current_theme)
        self.show()

    def apply_search(self, text):
        if text:
            self.model.setNameFilters([f"*{text}*"])
        else:
            self.model.setNameFilters([]) 

    def on_directory_loaded(self, path):
        if os.path.normpath(path) == os.path.normpath(self.target_path):
            self.list_view.setRootIndex(self.model.index(self.target_path))

    def toggle_search(self):
        if self.search_input.isVisible():
            self.search_input.hide()
            self.search_input.clear() 
        else:
            self.search_input.show()
            self.search_input.setFocus()

    def apply_theme(self, theme_key):
        all_themes = self.manager.get_all_themes()
        if theme_key not in all_themes:
            theme_key = "Blue"
            
        self.current_theme = theme_key
        theme = all_themes[theme_key]
        
        self.config["theme"] = theme_key
        self.manager.save_config()

        border_qss = qss(theme['border'])
        bg_qss = qss(theme['bg'])
        body_qss = qss(theme['body'])
        title_qss = qss(theme.get('title', theme['border']))

        self.title_edit.setStyleSheet(f"color: {title_qss}; font-family: 'Segoe UI Variable', 'Segoe UI'; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        self.resizer.setStyleSheet(f"background-color: transparent; border-bottom: 3px solid {border_qss}; border-right: 3px solid {border_qss}; border-bottom-right-radius: {BORDER_RADIUS}px;")
        
        self.search_btn.set_theme_color(theme.get('title', theme['border']))
        self.search_btn.update()
        
        self.search_input.setStyleSheet(f"QLineEdit {{ background: {bg_qss}; color: white; border: 1px solid {border_qss}; border-radius: 4px; padding: 4px; font-family: 'Segoe UI'; font-size: 12px; margin-bottom: 4px; }}")
        
        self.body_frame.setStyleSheet(f"""
            QFrame#BodyFrame {{ background-color: {body_qss}; border: 2px solid {border_qss}; border-top: none; border-bottom-left-radius: {BORDER_RADIUS}px; border-bottom-right-radius: {BORDER_RADIUS}px; }}
            QListView {{ background: transparent; border: none; color: white; outline: none; }}
            QListView::item:selected {{ background: rgba(255,255,255, 30); border-radius: 5px; }}
            QListView QLineEdit {{ background: {bg_qss}; color: white; border: 1px solid {border_qss}; }}
        """)
        
        self.set_header_style(expanded=self.is_expanded)

    def set_header_style(self, expanded):
        all_themes = self.manager.get_all_themes()
        theme = all_themes.get(self.current_theme, THEMES["Blue"])
        
        border_qss = qss(theme['border'])
        bg_qss = qss(theme['bg'])
            
        if expanded:
            self.header_frame.setStyleSheet(f"QFrame#HeaderFrame {{ background-color: {bg_qss}; border: 2px solid {border_qss}; border-bottom: none; border-top-left-radius: {BORDER_RADIUS}px; border-top-right-radius: {BORDER_RADIUS}px; border-bottom-left-radius: 0px; border-bottom-right-radius: 0px; }}")
        else:
            self.header_frame.setStyleSheet(f"QFrame#HeaderFrame {{ background-color: {bg_qss}; border: 2px solid {border_qss}; border-radius: {BORDER_RADIUS}px; }}")

    def prompt_custom_theme(self, apply_globally=False):
        all_themes = self.manager.get_all_themes()
        curr = all_themes.get(self.current_theme, THEMES["Blue"])
        
        default_title = curr.get('title', curr['border'])
        dialog = CustomThemeDialog(self, default_border=curr['border'], default_body=curr['body'], default_title=default_title)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            theme_data = dialog.get_theme_data()
            theme_id = self.manager.add_custom_theme(theme_data)

            if apply_globally: self.manager.apply_global_theme(theme_id)
            else: self.apply_theme(theme_id)

    def auto_fit_horizontal(self):
        if getattr(self, 'is_locked', False): return
        screen = QApplication.primaryScreen().availableGeometry()
        my_rect = self.geometry()
        
        min_x, max_x = screen.left(), screen.right()
        
        for fence in self.manager.fences:
            if fence is self: continue
            other = fence.geometry()
            if not (my_rect.bottom() < other.top() or my_rect.top() > other.bottom()):
                if other.right() <= my_rect.left() and other.right() > min_x:
                    min_x = other.right()
                if other.left() >= my_rect.right() and other.left() < max_x:
                    max_x = other.left()
        
        new_width = max_x - min_x
        if new_width > 200:
            self.move(min_x, self.y())
            self.setFixedWidth(new_width)
            self.config["x"] = min_x
            self.config["width"] = new_width
            self.manager.save_config()

    def toggle_lock(self):
        self.is_locked = not getattr(self, 'is_locked', False)
        self.config["locked"] = self.is_locked
        self.manager.save_config()

    def show_context_menu(self, pos):
        index = self.list_view.indexAt(pos) 
        all_themes = self.manager.get_all_themes()
        theme = all_themes.get(self.current_theme, THEMES["Blue"])
        
        c_menu_bg = QColor(theme['body'])
        if c_menu_bg.alpha() < 240: 
            c_menu_bg.setAlpha(240)
            
        menu_bg_qss = qss(c_menu_bg.name(QColor.NameFormat.HexArgb))
        border_qss = qss(theme['border'])
        
        menu_style = f"QMenu {{ background-color: {menu_bg_qss}; color: white; border: 1px solid {border_qss}; border-radius: 5px; font-family: 'Segoe UI'; font-size: 13px; }} QMenu::item {{ padding: 8px 20px; }} QMenu::item:selected {{ background-color: rgba(255, 255, 255, 20); }}"

        if index.isValid():
            file_menu = QMenu(self)
            file_menu.setStyleSheet(menu_style)
            
            open_action = file_menu.addAction("Открыть")
            rename_action = file_menu.addAction("Переименовать")
            folder_action = file_menu.addAction("Показать в папке")
            prop_action = file_menu.addAction("Свойства") 
            
            file_menu.addSeparator()
            del_action = file_menu.addAction("❌ Удалить файл")

            action = file_menu.exec(self.list_view.mapToGlobal(pos))
            if action == open_action:
                self.open_file(index)
            elif action == rename_action:
                self.list_view.edit(index)
            elif action == folder_action:
                path = self.model.filePath(index)
                os.system(f'explorer /select,"{os.path.normpath(path)}"')
            elif action == prop_action:
                path = self.model.filePath(index)
                ctypes.windll.shell32.ShellExecuteW(None, "properties", os.path.normpath(path), None, None, 1)
            elif action == del_action:
                self.model.remove(index)
            return

        menu = QMenu(self)
        menu.setStyleSheet(menu_style)
        
        manage_menu = QMenu("Управление сетками", self)
        manage_menu.setStyleSheet(menu_style)
        
        for f in self.manager.fences:
            fence_title = f.title_edit.text()
            f_menu = QMenu(fence_title, self)
            f_menu.setStyleSheet(menu_style)
            
            del_fence_action = f_menu.addAction("Удалить эту сетку")
            del_fence_action.triggered.connect(lambda checked, target_fence=f: target_fence.delete_fence())
            
            manage_menu.addMenu(f_menu)
            
        menu.addMenu(manage_menu)
        menu.addSeparator()
        
        lock_text = "Открепить сетку" if getattr(self, 'is_locked', False) else "Закрепить сетку"
        lock_action = menu.addAction(lock_text)
        lock_action.triggered.connect(self.toggle_lock)
        
        fit_action = menu.addAction("Заполнить свободное место")
        fit_action.triggered.connect(self.auto_fit_horizontal)
        
        search_action = menu.addAction("Поиск иконок")
        search_action.triggered.connect(self.toggle_search)
        menu.addSeparator()

        color_menu = ThemeMenu("Цвет этого окна", self)
        color_menu.setStyleSheet(menu_style)
        for key, data in all_themes.items():
            display_name = data["name"] + " (ПКМ - удалить)" if str(key).startswith("Custom_") else data["name"]
            action = color_menu.addAction(display_name)
            action.setData(key) 
            action.triggered.connect(lambda checked, k=key: self.apply_theme(k))
            
        color_menu.addSeparator()
        custom_action = color_menu.addAction("Создать свой пресет...")
        custom_action.triggered.connect(lambda: self.prompt_custom_theme(apply_globally=False))
        menu.addMenu(color_menu)

        global_color_menu = ThemeMenu("Цвет всех окон", self)
        global_color_menu.setStyleSheet(menu_style)
        for key, data in all_themes.items():
            display_name = data["name"] + " (ПКМ - удалить)" if str(key).startswith("Custom_") else data["name"]
            action = global_color_menu.addAction(display_name)
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self.manager.apply_global_theme(k))
            
        global_color_menu.addSeparator()
        global_custom_action = global_color_menu.addAction("Создать свой пресет...")
        global_custom_action.triggered.connect(lambda: self.prompt_custom_theme(apply_globally=True))
        menu.addMenu(global_color_menu)

        menu.addSeparator()
        delete_action = menu.addAction("Удалить сетку")
        delete_action.triggered.connect(self.delete_fence)

        menu.exec(self.list_view.mapToGlobal(pos))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resizer.move(self.width() - 20, self.height() - 20)

    def check_mouse(self):
        if self.title_edit.hasFocus() or self.search_input.hasFocus() or self.resizing: return

        mouse = QCursor.pos()
        over_window = self.geometry().contains(mouse)

        if QApplication.activePopupWidget(): return

        if over_window and not self.is_expanded:
            self.is_expanded = True
            self.animation.stop()
            try: self.animation.finished.disconnect(self.on_collapse_finished)
            except: pass
            
            self.set_header_style(expanded=True)
            self.animation.setStartValue(self.current_body_height)
            self.animation.setEndValue(self.full_height)
            self.resizer.show()
            self.animation.start()

        elif not over_window and self.is_expanded:
            self.is_expanded = False
            self.animation.stop()
            self.resizer.hide()
            
            if self.search_input.isVisible():
                self.search_input.hide()
                self.search_input.clear()
            
            self.animation.setStartValue(self.current_body_height)
            self.animation.setEndValue(0)
            self.animation.finished.connect(self.on_collapse_finished)
            self.animation.start()

    def on_collapse_finished(self):
        try: self.animation.finished.disconnect(self.on_collapse_finished)
        except: pass
        if self.current_body_height == 0:
            self.set_header_style(expanded=False)

    def start_resizing(self, global_pos):
        if getattr(self, 'is_locked', False): return
        self.resizing = True
        self.resize_start_pos = global_pos
        self.start_width = self.width()
        self.start_height = self.full_height
        self.animation.stop()

    def do_resizing(self, global_pos):
        if not self.resizing: return
        delta = global_pos - self.resize_start_pos
        new_width = max(200, self.start_width + delta.x())
        new_height = max(100, self.start_height + delta.y())
        
        self.setFixedWidth(new_width)
        self.full_height = new_height
        self.current_body_height = new_height

    def stop_resizing(self):
        self.resizing = False
        self.config["width"] = self.width()
        self.config["height"] = self.full_height
        self.manager.save_config()

    def delete_fence(self):
        desktop_dir = os.path.expanduser("~\\Desktop")
        if os.path.exists(self.target_path):
            for item in os.listdir(self.target_path):
                src_path = os.path.join(self.target_path, item)
                try: shutil.move(src_path, desktop_dir)
                except Exception as e: print(f"Файл {item} занят. ({e})")
            try: shutil.rmtree(self.target_path)
            except: pass

        self.manager.config_data["fences"] = [f for f in self.manager.config_data["fences"] if f["id"] != self.id]
        self.manager.save_config()
        self.manager.fences.remove(self)
        self.close()

    def snap_to_edges(self, new_pos):
        snap_dist = 20
        new_rect = QRect(new_pos.x(), new_pos.y(), self.width(), self.height())
        screen = QApplication.primaryScreen().availableGeometry()
        
        snapped_x = False; snapped_y = False
        
        for fence in self.manager.fences:
            if fence is self: continue
            other = fence.geometry()
            
            if not snapped_x:
                if abs(new_rect.left() - other.right()) < snap_dist: new_pos.setX(other.right()); snapped_x = True
                elif abs(new_rect.right() - other.left()) < snap_dist: new_pos.setX(other.left() - self.width()); snapped_x = True
                elif abs(new_rect.left() - other.left()) < snap_dist: new_pos.setX(other.left()); snapped_x = True
                    
            if not snapped_y:
                if abs(new_rect.top() - other.bottom()) < snap_dist: new_pos.setY(other.bottom()); snapped_y = True
                elif abs(new_rect.bottom() - other.top()) < snap_dist: new_pos.setY(other.top() - self.height()); snapped_y = True
                elif abs(new_rect.top() - other.top()) < snap_dist: new_pos.setY(other.top()); snapped_y = True

        if not snapped_x:
            if abs(new_rect.left() - screen.left()) < snap_dist: new_pos.setX(screen.left())
            elif abs(new_rect.right() - screen.right()) < snap_dist: new_pos.setX(screen.right() - self.width())
                
        if not snapped_y:
            if abs(new_rect.top() - screen.top()) < snap_dist: new_pos.setY(screen.top())
            elif abs(new_rect.bottom() - screen.bottom()) < snap_dist: new_pos.setY(screen.bottom() - self.height())

        if new_pos.y() < screen.top():
            new_pos.setY(screen.top())
        if new_pos.x() < screen.left():
            new_pos.setX(screen.left())
        if new_pos.x() + self.width() > screen.right():
            new_pos.setX(screen.right() - self.width())
        if new_pos.y() + HEADER_HEIGHT > screen.bottom():
            new_pos.setY(screen.bottom() - HEADER_HEIGHT)

        return new_pos

    def h_press(self, event):
        if getattr(self, 'is_locked', False): return 
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def h_move(self, event):
        if getattr(self, 'is_locked', False): return 
        if event.buttons() == Qt.MouseButton.LeftButton and not self.title_edit.hasFocus() and self.drag_pos:
            raw_new_pos = event.globalPosition().toPoint() - self.drag_pos
            snapped_pos = self.snap_to_edges(raw_new_pos)
            self.move(snapped_pos)

    def h_release(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_pos:
            self.drag_pos = None
            self.config["x"] = self.x()
            self.config["y"] = self.y()
            self.manager.save_config()

    def enable_edit(self, event):
        self.title_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.title_edit.setReadOnly(False)
        self.title_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def disable_edit(self):
        self.title_edit.setReadOnly(True)
        self.title_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.title_edit.clearFocus()
        self.title_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.config["title"] = self.title_edit.text()
        self.manager.save_config()

    def open_file(self, index):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.model.filePath(index)))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    src_path = url.toLocalFile()
                    file_name = os.path.basename(src_path)
                    dst_path = os.path.join(self.target_path, file_name)
                    try:
                        if src_path != dst_path: 
                            shutil.move(src_path, dst_path)
                            desktop_dir = os.path.expanduser("~\\Desktop")
                            ctypes.windll.shell32.SHChangeNotify(0x00001000, 0x0005, desktop_dir, None)
                    except Exception as e: print(f"Ошибка: {e}")
        else: event.ignore()


class FenceManager:
    def __init__(self):
        self.fences = []
        self.config_data = {"fences": [], "custom_themes": {}}
        self.load_config()

        self.server = QLocalServer()
        self.server.removeServer("MyFencesApp")
        self.server.listen("MyFencesApp")
        self.server.newConnection.connect(self.handle_new_connection)

    def get_all_themes(self):
        combined = THEMES.copy()
        customs = self.config_data.get("custom_themes", {})
        combined.update(customs)
        return combined

    def add_custom_theme(self, theme_data):
        theme_id = f"Custom_{uuid.uuid4().hex[:6]}"
        if "custom_themes" not in self.config_data:
            self.config_data["custom_themes"] = {}
        
        self.config_data["custom_themes"][theme_id] = theme_data
        self.save_config()
        return theme_id

    def remove_custom_theme(self, theme_id):
        if "custom_themes" in self.config_data and theme_id in self.config_data["custom_themes"]:
            del self.config_data["custom_themes"][theme_id]
            self.save_config()
            
            for fence in self.fences:
                if fence.current_theme == theme_id:
                    fence.apply_theme("Blue")

    def apply_global_theme(self, theme_key):
        for fence in self.fences:
            fence.apply_theme(theme_key)

    def handle_new_connection(self):
        socket = self.server.nextPendingConnection()
        if socket.waitForReadyRead(1000):
            message = socket.readAll().data().decode('utf-8')
            if message == "CREATE_NEW":
                self.create_new_fence()
        socket.disconnectFromServer()

    def create_new_fence(self):
        new_id = f"fence_{uuid.uuid4().hex[:6]}"
        
        new_folder_path = os.path.join(MYFENCES_DIR, new_id)
        os.makedirs(new_folder_path, exist_ok=True)

        new_config = {
            "id": new_id,
            "title": "Новая Сетка",
            "path": new_folder_path,
            "x": 100, "y": 100,
            "width": 400, "height": 300,
            "theme": "Blue"
        }
        self.config_data["fences"].append(new_config)
        self.save_config()
        
        fence = FenceInstance(self, new_config)
        self.fences.append(fence)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
            except Exception as e: pass

        if not self.config_data.get("fences"):
            self.create_new_fence()
        else:
            for fence_cfg in self.config_data["fences"]:
                fence = FenceInstance(self, fence_cfg)
                self.fences.append(fence)

    def save_config(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config_data, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    socket = QLocalSocket()
    socket.connectToServer("MyFencesApp")
    
    if socket.waitForConnected(500):
        if "--create" in sys.argv:
            socket.write(b"CREATE_NEW")
            socket.waitForBytesWritten(500)
        sys.exit(0)
    else:
        manager = FenceManager()
        if "--create" in sys.argv and len(manager.fences) > 0:
            manager.create_new_fence()
        sys.exit(app.exec())