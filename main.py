import sys
import os
import json
import shutil
import uuid
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QListView, QFrame, QMenu, QColorDialog, QInputDialog)
from PyQt6.QtGui import QFileSystemModel, QDesktopServices, QCursor, QColor
from PyQt6.QtCore import Qt, QPoint, QSize, QUrl, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty, QRect
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

CONFIG_FILE = "fences_config.json"
HEADER_HEIGHT = 35 
BORDER_RADIUS = 5  

# --- БАЗОВЫЕ ПРЕСЕТЫ ЦВЕТОВ ---
THEMES = {
    "Blue":   {"name": "Синий Неон",      "border": "#00d4ff", "bg": "#141419", "body": "#1a1a21"},
    "Purple": {"name": "Фиолетовый Неон", "border": "#b82bf2", "bg": "#16101c", "body": "#1e1626"},
    "Green":  {"name": "Зеленый Неон",    "border": "#00ff88", "bg": "#101c15", "body": "#16261c"},
    "Orange": {"name": "Оранжевый Неон",  "border": "#ffaa00", "bg": "#1c1610", "body": "#261e16"},
    "Red":    {"name": "Красный Неон",    "border": "#ff0055", "bg": "#1c1014", "body": "#26161a"}
}

# --- КЛАСС ДЛЯ МЕНЮ ТЕМ (ЧТОБЫ РАБОТАЛ ПРАВЫЙ КЛИК) ---
class ThemeMenu(QMenu):
    def __init__(self, title, parent_window):
        super().__init__(title, parent_window)
        self.parent_window = parent_window # Сохраняем ссылку на окно сетки
        
    def mouseReleaseEvent(self, event):
        action = self.actionAt(event.pos())
        # Если кликнули ПРАВОЙ кнопкой по пункту меню
        if action and event.button() == Qt.MouseButton.RightButton:
            theme_key = action.data()
            # Проверяем, что это именно кастомная тема (базовые удалять нельзя)
            if theme_key and str(theme_key).startswith("Custom_"):
                self.parent_window.manager.remove_custom_theme(theme_key)
                self.close() # Закрываем меню после удаления
                return
        super().mouseReleaseEvent(event)


# --- 1. ПОЛЗУНОК ДЛЯ ИЗМЕНЕНИЯ РАЗМЕРА ---
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

# --- 2. ЕДИНОЕ ОКНО СЕТКИ ---
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
        
        os.makedirs(self.target_path, exist_ok=True)

        self.start_width = config.get("width", 500)
        self.full_height = config.get("height", 600)
        start_x = config.get("x", 100)
        start_y = config.get("y", 100)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnBottomHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        
        self.setFixedWidth(self.start_width)
        self.setFixedHeight(HEADER_HEIGHT)
        self.move(start_x, start_y)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- ШАПКА ---
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(HEADER_HEIGHT)
        self.header_frame.setObjectName("HeaderFrame")
        
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(15, 0, 15, 0)
        
        self.title_edit = QLineEdit(self.title)
        self.title_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_edit.setReadOnly(True)
        self.title_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        h_layout.addWidget(self.title_edit)

        # --- ТЕЛО ---
        self.body_frame = QFrame()
        self.body_frame.setObjectName("BodyFrame")
        self.body_frame.setMinimumHeight(0)
        self.body_frame.setMaximumHeight(0)
        
        b_layout = QVBoxLayout(self.body_frame)
        b_layout.setContentsMargins(5, 5, 5, 5)
        
        self.model = QFileSystemModel()
        self.model.setRootPath(self.target_path)
        
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_view.setRootIndex(self.model.index(self.target_path))
        self.list_view.setViewMode(QListView.ViewMode.IconMode)
        self.list_view.setIconSize(QSize(72, 72))
        self.list_view.setGridSize(QSize(110, 110))
        self.list_view.doubleClicked.connect(self.open_file)
        self.list_view.setAcceptDrops(False)
        self.list_view.setMinimumHeight(0)
        
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self.show_context_menu)
        
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
        self.title_edit.mouseDoubleClickEvent = self.enable_edit
        self.title_edit.returnPressed.connect(self.disable_edit)
        self.title_edit.editingFinished.connect(self.disable_edit)

        self.apply_theme(self.current_theme)
        self.show()

    # --- ТЕМАТИКА И ВНЕШНИЙ ВИД ---
    def apply_theme(self, theme_key):
        all_themes = self.manager.get_all_themes()
        # Защита: если тема была удалена, откатываемся на синюю
        if theme_key not in all_themes:
            theme_key = "Blue"
            
        self.current_theme = theme_key
        theme = all_themes[theme_key]
        
        self.config["theme"] = theme_key
        self.manager.save_config()

        self.title_edit.setStyleSheet(f"color: {theme['border']}; font-family: 'Segoe UI Variable', 'Segoe UI'; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        self.resizer.setStyleSheet(f"background-color: transparent; border-bottom: 3px solid {theme['border']}; border-right: 3px solid {theme['border']}; border-bottom-right-radius: {BORDER_RADIUS}px;")
        
        self.body_frame.setStyleSheet(f"""
            QFrame#BodyFrame {{
                background-color: {theme['body']};
                border: 2px solid {theme['border']};
                border-top: none; 
                border-bottom-left-radius: {BORDER_RADIUS}px;
                border-bottom-right-radius: {BORDER_RADIUS}px;
            }}
            QListView {{ background: transparent; border: none; color: white; outline: none; }}
        """)
        
        self.set_header_style(expanded=self.is_expanded)

    def set_header_style(self, expanded):
        all_themes = self.manager.get_all_themes()
        theme = all_themes.get(self.current_theme, THEMES["Blue"])
            
        if expanded:
            self.header_frame.setStyleSheet(f"""
                QFrame#HeaderFrame {{
                    background-color: {theme['bg']}; 
                    border: 2px solid {theme['border']}; 
                    border-bottom: none;
                    border-top-left-radius: {BORDER_RADIUS}px; 
                    border-top-right-radius: {BORDER_RADIUS}px;
                    border-bottom-left-radius: 0px; 
                    border-bottom-right-radius: 0px;
                }}
            """)
        else:
            self.header_frame.setStyleSheet(f"""
                QFrame#HeaderFrame {{ 
                    background-color: {theme['bg']}; 
                    border: 2px solid {theme['border']}; 
                    border-radius: {BORDER_RADIUS}px; 
                }}
            """)

    # --- СОЗДАНИЕ СВОЕГО ПРЕСЕТА ---
    def prompt_custom_theme(self, apply_globally=False):
        border_color = QColorDialog.getColor(title="1/2: Выберите цвет контура и текста")
        if not border_color.isValid(): return
        
        body_color = QColorDialog.getColor(title="2/2: Выберите основной цвет фона")
        if not body_color.isValid(): return

        # Запрашиваем название для пресета
        name, ok = QInputDialog.getText(self, "Новый пресет", "Введите название для этого цвета:")
        if not ok or not name.strip():
            name = "Мой цвет"

        custom_theme_data = {
            "name": name,
            "border": border_color.name(),
            "bg": body_color.darker(110).name(),
            "body": body_color.name()
        }
        
        # Сохраняем в Менеджере и получаем ID
        theme_id = self.manager.add_custom_theme(custom_theme_data)

        # Применяем
        if apply_globally:
            self.manager.apply_global_theme(theme_id)
        else:
            self.apply_theme(theme_id)

    # --- КОНТЕКСТНОЕ МЕНЮ (ПКМ) ---
    def show_context_menu(self, pos):
        index = self.list_view.indexAt(pos)
        if index.isValid(): return 

        all_themes = self.manager.get_all_themes()
        theme = all_themes.get(self.current_theme, THEMES["Blue"])
        
        menu = QMenu(self)
        menu_style = f"""
            QMenu {{
                background-color: {theme['body']};
                color: white;
                border: 1px solid {theme['border']};
                border-radius: 5px;
                font-family: 'Segoe UI'; font-size: 13px;
            }}
            QMenu::item {{ padding: 8px 20px; }}
            QMenu::item:selected {{ background-color: rgba(255, 255, 255, 20); }}
        """
        menu.setStyleSheet(menu_style)

        # 1. Меню текущего окна (Используем кастомный ThemeMenu)
        color_menu = ThemeMenu("🎨 Цвет этого окна", self)
        color_menu.setStyleSheet(menu_style)
        for key, data in all_themes.items():
            display_name = data["name"] + " (ПКМ - удалить)" if str(key).startswith("Custom_") else data["name"]
            action = color_menu.addAction(display_name)
            action.setData(key) # Сохраняем ID темы в экшен
            action.triggered.connect(lambda checked, k=key: self.apply_theme(k))
            
        color_menu.addSeparator()
        custom_action = color_menu.addAction("➕ Создать свой пресет...")
        custom_action.triggered.connect(lambda: self.prompt_custom_theme(apply_globally=False))
        menu.addMenu(color_menu)

        # 2. Меню глобальное (Используем кастомный ThemeMenu)
        global_color_menu = ThemeMenu("🌍 Цвет всех окон", self)
        global_color_menu.setStyleSheet(menu_style)
        for key, data in all_themes.items():
            display_name = data["name"] + " (ПКМ - удалить)" if str(key).startswith("Custom_") else data["name"]
            action = global_color_menu.addAction(display_name)
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self.manager.apply_global_theme(k))
            
        global_color_menu.addSeparator()
        global_custom_action = global_color_menu.addAction("➕ Создать свой пресет...")
        global_custom_action.triggered.connect(lambda: self.prompt_custom_theme(apply_globally=True))
        menu.addMenu(global_color_menu)

        menu.addSeparator()
        delete_action = menu.addAction("❌ Удалить сетку")
        delete_action.triggered.connect(self.delete_fence)

        menu.exec(self.list_view.mapToGlobal(pos))

    # --- АНИМАЦИИ И СОБЫТИЯ ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resizer.move(self.width() - 20, self.height() - 20)

    def check_mouse(self):
        if self.title_edit.hasFocus() or self.resizing: return

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

        return new_pos

    def h_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def h_move(self, event):
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
        self.title_edit.setReadOnly(False)
        self.title_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def disable_edit(self):
        self.title_edit.setReadOnly(True)
        self.title_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.title_edit.clearFocus()
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
                        if src_path != dst_path: shutil.move(src_path, dst_path)
                    except Exception as e: print(f"Ошибка: {e}")
        else: event.ignore()


# --- 3. МЕНЕДЖЕР ОКНО ---
class FenceManager:
    def __init__(self):
        self.fences = []
        self.config_data = {"fences": [], "custom_themes": {}}
        self.load_config()

        self.server = QLocalServer()
        self.server.removeServer("MyFencesApp")
        self.server.listen("MyFencesApp")
        self.server.newConnection.connect(self.handle_new_connection)

    # Получить словарь ВСЕХ тем (базовые + пользовательские)
    def get_all_themes(self):
        combined = THEMES.copy()
        customs = self.config_data.get("custom_themes", {})
        combined.update(customs)
        return combined

    # Добавить новую пользовательскую тему
    def add_custom_theme(self, theme_data):
        theme_id = f"Custom_{uuid.uuid4().hex[:6]}"
        if "custom_themes" not in self.config_data:
            self.config_data["custom_themes"] = {}
        
        self.config_data["custom_themes"][theme_id] = theme_data
        self.save_config()
        return theme_id

    # Удалить пользовательскую тему
    def remove_custom_theme(self, theme_id):
        if "custom_themes" in self.config_data and theme_id in self.config_data["custom_themes"]:
            del self.config_data["custom_themes"][theme_id]
            self.save_config()
            
            # Если какие-то окна использовали эту удаленную тему, сбрасываем их на дефолт (Blue)
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
        
        documents_dir = os.path.expanduser("~/Documents")
        new_folder_path = os.path.join(documents_dir, "MyFencesData", new_id)
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