import sys
import os
import json
import shutil
import uuid
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QListView, QFrame, QPushButton)
from PyQt6.QtGui import QFileSystemModel, QDesktopServices, QCursor
from PyQt6.QtCore import Qt, QPoint, QSize, QUrl, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty, QRect
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

CONFIG_FILE = "fences_config.json"

# --- 1. ПОЛЗУНОК ДЛЯ ИЗМЕНЕНИЯ РАЗМЕРА ---
class ResizeHandle(QWidget):
    def __init__(self, parent_widget, instance):
        super().__init__(parent_widget)
        self.instance = instance
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setStyleSheet("""
            background-color: transparent;
            border-bottom: 3px solid rgba(0, 212, 255, 150);
            border-right: 3px solid rgba(0, 212, 255, 150);
            border-bottom-right-radius: 12px;
        """)
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
        self.setFixedHeight(55 + value)
        
    def __init__(self, manager, config):
        super().__init__()
        self.manager = manager
        self.config = config
        
        self.id = config.get("id", "default")
        self.title = config.get("title", "🟦 Новая Сетка")
        self.target_path = config.get("path", os.getcwd())
        
        os.makedirs(self.target_path, exist_ok=True)

        self.start_width = config.get("width", 500)
        self.full_height = config.get("height", 600)
        start_x = config.get("x", 100)
        start_y = config.get("y", 100)

        # 🌟 ИЗМЕНЕНО: Заменили WindowStaysOnTopHint на WindowStaysOnBottomHint
        # Теперь сетки всегда лежат на самом низу, как ярлыки рабочего стола!
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnBottomHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        
        self.setFixedWidth(self.start_width)
        self.setFixedHeight(55)
        self.move(start_x, start_y)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- ШАПКА ---
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(55)
        self.header_frame.setObjectName("HeaderFrame")
        
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(15, 0, 10, 0)
        
        self.title_edit = QLineEdit(self.title)
        self.title_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_edit.setReadOnly(True)
        self.title_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        h_layout.addWidget(self.title_edit)

        self.delete_btn = QPushButton("✖")
        self.delete_btn.setFixedSize(24, 24)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setObjectName("DeleteBtn")
        self.delete_btn.clicked.connect(self.delete_fence)
        h_layout.addWidget(self.delete_btn)

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
        b_layout.addWidget(self.list_view)

        self.main_layout.addWidget(self.header_frame)
        self.main_layout.addWidget(self.body_frame)

        # --- СТИЛИЗАЦИЯ ---
        self.setStyleSheet("""
            QFrame#BodyFrame {
                background-color: #1a1a21;
                border: 2px solid #00d4ff;
                border-top: none; 
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
            QLineEdit { color: #00d4ff; font-family: 'Segoe UI'; font-size: 16px; font-weight: bold; border: none; background: transparent; }
            QListView { background: transparent; border: none; color: white; outline: none; }
            
            QPushButton#DeleteBtn { background: transparent; color: rgba(255, 255, 255, 100); border: none; font-size: 14px; font-weight: bold; border-radius: 12px; }
            QPushButton#DeleteBtn:hover { background: rgba(255, 50, 50, 200); color: white; }
        """)
        self.set_header_style(expanded=False)

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

        self.show()

    def set_header_style(self, expanded):
        if expanded:
            self.header_frame.setStyleSheet("""
                QFrame#HeaderFrame {
                    background-color: #141419; border: 2px solid #00d4ff; border-bottom: none;
                    border-top-left-radius: 12px; border-top-right-radius: 12px;
                    border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;
                }
            """)
        else:
            self.header_frame.setStyleSheet("""
                QFrame#HeaderFrame { background-color: #141419; border: 2px solid #00d4ff; border-radius: 12px; }
            """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resizer.move(self.width() - 20, self.height() - 20)

    def check_mouse(self):
        if self.title_edit.hasFocus() or self.resizing: return

        mouse = QCursor.pos()
        over_window = self.geometry().contains(mouse)

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
        new_width = max(250, self.start_width + delta.x())
        new_height = max(150, self.start_height + delta.y())
        
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

    # 🌟 НОВОЕ: Логика магнитного прилипания
    def snap_to_edges(self, new_pos):
        snap_dist = 20 # Дистанция, на которой срабатывает магнит
        new_rect = QRect(new_pos.x(), new_pos.y(), self.width(), self.height())
        
        # Получаем рабочую область экрана (без учета панели задач Windows)
        screen = QApplication.primaryScreen().availableGeometry()
        
        snapped_x = False
        snapped_y = False
        
        # 1. Сначала проверяем другие сетки, чтобы они липли друг к другу
        for fence in self.manager.fences:
            if fence is self: continue
            other = fence.geometry()
            
            # Магнит по горизонтали (X)
            if not snapped_x:
                if abs(new_rect.left() - other.right()) < snap_dist:
                    new_pos.setX(other.right())
                    snapped_x = True
                elif abs(new_rect.right() - other.left()) < snap_dist:
                    new_pos.setX(other.left() - self.width())
                    snapped_x = True
                elif abs(new_rect.left() - other.left()) < snap_dist:
                    new_pos.setX(other.left())
                    snapped_x = True
                    
            # Магнит по вертикали (Y)
            if not snapped_y:
                if abs(new_rect.top() - other.bottom()) < snap_dist:
                    new_pos.setY(other.bottom())
                    snapped_y = True
                elif abs(new_rect.bottom() - other.top()) < snap_dist:
                    new_pos.setY(other.top() - self.height())
                    snapped_y = True
                elif abs(new_rect.top() - other.top()) < snap_dist:
                    new_pos.setY(other.top())
                    snapped_y = True

        # 2. Если не прилипли к другой сетке, липнем к краям экрана
        if not snapped_x:
            if abs(new_rect.left() - screen.left()) < snap_dist:
                new_pos.setX(screen.left())
            elif abs(new_rect.right() - screen.right()) < snap_dist:
                new_pos.setX(screen.right() - self.width())
                
        if not snapped_y:
            if abs(new_rect.top() - screen.top()) < snap_dist:
                new_pos.setY(screen.top())
            elif abs(new_rect.bottom() - screen.bottom()) < snap_dist:
                new_pos.setY(screen.bottom() - self.height())

        return new_pos

    def h_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def h_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.title_edit.hasFocus() and self.drag_pos:
            raw_new_pos = event.globalPosition().toPoint() - self.drag_pos
            
            # Пропускаем новые координаты через функцию прилипания
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
        self.config_data = {"fences": []}
        self.load_config()

        self.server = QLocalServer()
        self.server.removeServer("MyFencesApp")
        self.server.listen("MyFencesApp")
        self.server.newConnection.connect(self.handle_new_connection)

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
            "title": "🟦 Новая Сетка",
            "path": new_folder_path,
            "x": 100, "y": 100,
            "width": 400, "height": 300
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