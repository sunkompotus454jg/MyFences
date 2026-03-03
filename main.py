import sys
import os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                             QLabel, QListView)
from PyQt6.QtGui import QFileSystemModel, QDesktopServices, QCursor
from PyQt6.QtCore import Qt, QPoint, QSize, QUrl, QPropertyAnimation, QEasingCurve, QTimer

class FenceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.drag_pos = QPoint()
        
        # Размеры
        self.full_height = 550
        self.collapsed_height = 60 
        
        self.init_ui()
        
        # Анимация
        self.animation = QPropertyAnimation(self, b"minimumHeight")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # ТАЙМЕР ДЛЯ ПРОВЕРКИ МЫШИ (Решает проблему зависания в развернутом виде)
        self.check_timer = QTimer()
        self.check_timer.setInterval(100) # Проверка каждые 100мс
        self.check_timer.timeout.connect(self.check_mouse_position)
        self.check_timer.start()

    def init_ui(self):
        self.setFixedWidth(400)
        self.setMinimumHeight(self.collapsed_height)
        self.setMaximumHeight(self.full_height)
        
        # Tool — чтобы не было в таскбаре, Frameless — без рамок
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)

        self.model = QFileSystemModel()
        path = os.getcwd() 
        self.model.setRootPath(path)

        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_view.setRootIndex(self.model.index(path))
        self.list_view.setViewMode(QListView.ViewMode.IconMode)
        self.list_view.setIconSize(QSize(64, 64))
        self.list_view.setGridSize(QSize(100, 100))
        self.list_view.setSpacing(10)
        
        # Отключаем фокус, чтобы не мешать событиям окна
        self.list_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_view.doubleClicked.connect(self.open_file)

        self.setStyleSheet("""
            QWidget#MainFrame {
                background-color: rgba(20, 20, 25, 230);
                border: 1px solid rgba(0, 212, 255, 50);
                border-radius: 20px;
            }
            QLabel {
                color: #00d4ff;
                font-family: 'Segoe UI Variable';
                font-size: 16px;
                background: transparent;
                padding: 10px;
            }
            QListView {
                background: transparent;
                border: none;
                color: white;
                outline: none;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.container = QWidget()
        self.container.setObjectName("MainFrame")
        c_layout = QVBoxLayout(self.container)
        self.label = QLabel("🟦 Моя Сетка Приложений")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(self.label)
        c_layout.addWidget(self.list_view)
        layout.addWidget(self.container)
        self.setLayout(layout)

    # --- ГЛАВНАЯ ЛОГИКА ПРОВЕРКИ ---
    def check_mouse_position(self):
        # Получаем позицию мыши относительно окна
        local_pos = self.mapFromGlobal(QCursor.pos())
        is_over = self.rect().contains(local_pos)

        if is_over and self.height() < self.full_height - 5:
            # Если мышь наведена, а окно закрыто — открываем
            self.expand_window()
        elif not is_over and self.height() > self.collapsed_height + 5:
            # Если мышь ушла, а окно открыто — закрываем
            self.collapse_window()

    def expand_window(self):
        if self.animation.state() != QPropertyAnimation.State.Running:
            self.animation.stop()
            self.animation.setEndValue(self.full_height)
            self.animation.start()

    def collapse_window(self):
        if self.animation.state() != QPropertyAnimation.State.Running:
            self.animation.stop()
            self.animation.setEndValue(self.collapsed_height)
            self.animation.start()

    # Файловые методы
    def open_file(self, index):
        file_path = self.model.filePath(index)
        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for f in files:
            dest = os.path.join(os.getcwd(), os.path.basename(f))
            if f != dest:
                try: os.rename(f, dest)
                except: pass
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FenceWindow()
    window.show()
    sys.exit(app.exec())