import sys
import os
import json
import shutil
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                             QLineEdit, QListView, QFrame)
from PyQt6.QtGui import QFileSystemModel, QDesktopServices, QCursor
from PyQt6.QtCore import Qt, QPoint, QSize, QUrl, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty

CONFIG_FILE = "fences_config.json"

# --- 1. ПОЛЗУНОК ДЛЯ ИЗМЕНЕНИЯ РАЗМЕРА ---
class ResizeHandle(QWidget):
    def __init__(self, parent, instance):
        super().__init__(parent)
        self.instance = instance
        self.setFixedSize(20, 20)
        # Меняем курсор на диагональную стрелочку
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        # Визуально выделяем уголок, чтобы было понятно, за что тянуть
        self.setStyleSheet("""
            background-color: transparent;
            border-bottom: 3px solid rgba(0, 212, 255, 100);
            border-right: 3px solid rgba(0, 212, 255, 100);
            border-bottom-right-radius: 12px;
        """)

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


# --- 2. ОКНО С ФАЙЛАМИ ---
class BodyWindow(QWidget):
    def __init__(self, instance):
        super().__init__()
        self.instance = instance
        self.header = instance.header
        self.target_path = instance.target_path
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QFrame()
        self.container.setObjectName("BodyContainer")
        main_layout.addWidget(self.container)

        self.setStyleSheet("""
            QFrame#BodyContainer {
                background-color: #1a1a21; 
                border: 2px solid #00d4ff;
                border-top: none;
                border-bottom-left-radius: 15px;
                border-bottom-right-radius: 15px;
            }
            QListView { background: transparent; border: none; color: white; outline: none; }
        """)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(5, 5, 5, 5)

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
        layout.addWidget(self.list_view)

        # Добавляем ползунок изменения размера
        self.resizer = ResizeHandle(self, self.instance)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Всегда держим ползунок в правом нижнем углу
        self.resizer.move(self.width() - 20, self.height() - 20)

    @pyqtProperty(int)
    def anim_height(self):
        return self.height()

    @anim_height.setter
    def anim_height(self, value):
        self.setFixedHeight(value)

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
                    except Exception as e:
                        print(f"Ошибка перемещения: {e}")
        else: event.ignore()


# --- 3. ЭКЗЕМПЛЯР СЕТКИ ---
class FenceInstance:
    def __init__(self, manager, config):
        self.manager = manager
        self.config = config
        
        self.id = config.get("id", "default_1")
        self.title = config.get("title", "🟦 Новая Сетка")
        self.target_path = config.get("path", os.getcwd())
        self.width = config.get("width", 500)
        self.full_height = config.get("height", 600)
        start_x = config.get("x", 200)
        start_y = config.get("y", 200)

        self.drag_pos = None
        self.resizing = False # Флаг: тянем ли мы сейчас за угол

        # --- ШАПКА ---
        self.header = QWidget()
        self.header.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.header.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.header.setFixedSize(self.width, 55)
        self.header.move(start_x, start_y)
        
        main_h_layout = QVBoxLayout(self.header)
        main_h_layout.setContentsMargins(0, 0, 0, 0)

        self.header_container = QFrame()
        self.header_container.setObjectName("HeaderContainer")
        main_h_layout.addWidget(self.header_container)

        h_layout = QVBoxLayout(self.header_container)
        h_layout.setContentsMargins(10, 0, 10, 0)

        self.title_edit = QLineEdit(self.title)
        self.title_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_edit.setReadOnly(True)
        self.title_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        self.header.setStyleSheet("""
            QFrame#HeaderContainer { background-color: #141419; border: 2px solid #00d4ff; border-radius: 12px; }
            QLineEdit { color: #00d4ff; font-family: 'Segoe UI'; font-size: 16px; font-weight: bold; border: none; background: transparent; }
        """)
        h_layout.addWidget(self.title_edit)

        # --- ТЕЛО ---
        self.body = BodyWindow(self)
        self.body.setFixedWidth(self.width)
        self.body.setFixedHeight(0)

        self.animation = QPropertyAnimation(self.body, b"anim_height")
        self.animation.setDuration(350)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.timer = QTimer()
        self.timer.timeout.connect(self.sync_and_check)
        self.timer.start(10)

        # События шапки
        self.header.mousePressEvent = self.h_press
        self.header.mouseMoveEvent = self.h_move
        self.header.mouseReleaseEvent = self.h_release
        self.title_edit.mouseDoubleClickEvent = self.enable_edit
        self.title_edit.returnPressed.connect(self.disable_edit)
        self.title_edit.editingFinished.connect(self.disable_edit)

        self.header.show()
        self.body.show()

    # --- МЕТОДЫ ИЗМЕНЕНИЯ РАЗМЕРА ---
    def start_resizing(self, global_pos):
        self.resizing = True
        self.resize_start_pos = global_pos
        self.start_width = self.width
        self.start_height = self.full_height

    def do_resizing(self, global_pos):
        if not self.resizing: return
        delta = global_pos - self.resize_start_pos
        
        # Минимальные размеры окна (чтобы не схлопнулось в ноль)
        new_width = max(250, self.start_width + delta.x())
        new_height = max(150, self.start_height + delta.y())
        
        self.width = new_width
        self.full_height = new_height
        
        # Мгновенно применяем новые размеры к окнам
        self.header.setFixedSize(self.width, 55)
        self.body.setFixedWidth(self.width)
        self.body.setFixedHeight(self.full_height)

    def stop_resizing(self):
        self.resizing = False
        # Сохраняем новые размеры в конфигурацию
        self.config["width"] = self.width
        self.config["height"] = self.full_height
        self.manager.save_config()

    # --- МЕТОДЫ ЛОГИКИ ---
    def sync_and_check(self):
        self.body.move(self.header.x(), self.header.y() + self.header.height() - 5)

        # Если тянем за угол или редактируем текст — прерываем логику сворачивания
        if self.title_edit.hasFocus() or self.resizing: return

        mouse = QCursor.pos()
        over_header = self.header.geometry().contains(mouse)
        over_body = self.body.geometry().contains(mouse) and self.body.height() > 10

        if over_header or over_body:
            if self.animation.endValue() != self.full_height:
                self.animation.stop()
                self.animation.setEndValue(self.full_height)
                self.animation.start()
        else:
            if self.animation.endValue() != 0:
                self.animation.stop()
                self.animation.setEndValue(0)
                self.animation.start()

    def h_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.header.frameGeometry().topLeft()

    def h_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.title_edit.hasFocus() and self.drag_pos:
            self.header.move(event.globalPosition().toPoint() - self.drag_pos)

    def h_release(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_pos:
            self.drag_pos = None
            self.config["x"] = self.header.x()
            self.config["y"] = self.header.y()
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


# --- 4. МЕНЕДЖЕР ---
class FenceManager:
    def __init__(self):
        self.fences = []
        self.config_data = {"fences": []}
        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
            except Exception as e:
                print(f"Ошибка чтения конфига: {e}")

        if not self.config_data.get("fences"):
            self.config_data["fences"] = [
                {
                    "id": "fence_1",
                    "title": "🟦 Рабочий Стол",
                    "path": os.getcwd(),
                    "x": 300, "y": 200,
                    "width": 500, "height": 600
                }
            ]
            self.save_config()

        for fence_cfg in self.config_data["fences"]:
            fence = FenceInstance(self, fence_cfg)
            self.fences.append(fence)

    def save_config(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config_data, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    manager = FenceManager()
    sys.exit(app.exec())