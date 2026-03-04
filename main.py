import sys
import os
import shutil
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                             QLineEdit, QListView, QFrame)
from PyQt6.QtGui import QFileSystemModel, QDesktopServices, QCursor
from PyQt6.QtCore import Qt, QPoint, QSize, QUrl, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty

class BodyWindow(QWidget):
    def __init__(self, parent_header):
        super().__init__()
        self.header = parent_header
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
            QListView { 
                background: transparent; 
                border: none; 
                color: white; 
                outline: none; 
            }
        """)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(5, 5, 5, 5)

        self.model = QFileSystemModel()
        self.target_path = os.getcwd() 
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

    @pyqtProperty(int)
    def anim_height(self):
        return self.height()

    @anim_height.setter
    def anim_height(self, value):
        self.setFixedHeight(value)

    def open_file(self, index):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.model.filePath(index)))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        # Меняем курсор на "Перемещение"
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

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
                        # Проверяем, что не пытаемся переместить файл сам в себя
                        if src_path != dst_path:
                            # Перемещаем файл или папку (оригинал)
                            shutil.move(src_path, dst_path)
                    except Exception as e:
                        print(f"Ошибка перемещения: {e}")
        else:
            event.ignore()

class FenceApp:
    def __init__(self):
        self.width = 500
        self.full_height = 600
        self.drag_pos = QPoint()

        self.header = QWidget()
        self.header.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.header.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.header.setFixedSize(self.width, 55)
        
        main_h_layout = QVBoxLayout(self.header)
        main_h_layout.setContentsMargins(0, 0, 0, 0)

        self.header_container = QFrame()
        self.header_container.setObjectName("HeaderContainer")
        main_h_layout.addWidget(self.header_container)

        h_layout = QVBoxLayout(self.header_container)
        h_layout.setContentsMargins(10, 0, 10, 0)

        self.title_edit = QLineEdit("🟦 Моя Сетка Приложений")
        self.title_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_edit.setReadOnly(True)
        self.title_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        self.header.setStyleSheet("""
            QFrame#HeaderContainer { 
                background-color: #141419; 
                border: 2px solid #00d4ff; 
                border-radius: 12px; 
            }
            QLineEdit { 
                color: #00d4ff; 
                font-family: 'Segoe UI'; 
                font-size: 16px; 
                font-weight: bold; 
                border: none; 
                background: transparent; 
            }
        """)
        h_layout.addWidget(self.title_edit)

        self.body = BodyWindow(self.header)
        self.body.setFixedWidth(self.width)
        self.body.setFixedHeight(0)

        self.animation = QPropertyAnimation(self.body, b"anim_height")
        self.animation.setDuration(350)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.timer = QTimer()
        self.timer.timeout.connect(self.sync_and_check)
        self.timer.start(10)

        self.header.mousePressEvent = self.h_press
        self.header.mouseMoveEvent = self.h_move
        self.title_edit.mouseDoubleClickEvent = self.enable_edit
        self.title_edit.returnPressed.connect(self.disable_edit)

        self.header.show()
        self.body.show()

    def sync_and_check(self):
        self.body.move(self.header.x(), self.header.y() + self.header.height() - 5)

        if self.title_edit.hasFocus(): return

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
        if event.buttons() == Qt.MouseButton.LeftButton and not self.title_edit.hasFocus():
            self.header.move(event.globalPosition().toPoint() - self.drag_pos)

    def enable_edit(self, event):
        self.title_edit.setReadOnly(False)
        self.title_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def disable_edit(self):
        self.title_edit.setReadOnly(True)
        self.title_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.title_edit.clearFocus()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    fence = FenceApp()
    sys.exit(app.exec())