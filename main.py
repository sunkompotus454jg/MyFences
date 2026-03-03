import sys
import os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                             QLabel, QListView, QAbstractItemView)
from PyQt6.QtGui import QFileSystemModel, QDesktopServices, QDrag
from PyQt6.QtCore import Qt, QPoint, QSize, QUrl

class FenceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.drag_pos = QPoint()
        self.init_ui()

    def init_ui(self):
        self.setFixedSize(400, 550) # Немного увеличим для сетки
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Разрешаем окну принимать файлы
        self.setAcceptDrops(True)

        self.model = QFileSystemModel()
        path = os.getcwd() 
        self.model.setRootPath(path)

        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_view.setRootIndex(self.model.index(path))
        
        # --- НАСТРОЙКА СЕТКИ И ВЫТАСКИВАНИЯ ---
        self.list_view.setViewMode(QListView.ViewMode.IconMode)
        self.list_view.setIconSize(QSize(64, 64))
        self.list_view.setGridSize(QSize(100, 100)) # Вот она, наша сетка!
        self.list_view.setSpacing(10)
        self.list_view.setMovement(QListView.Movement.Static)
        
        # Включаем возможность вытаскивать файлы
        self.list_view.setDragEnabled(True)
        self.list_view.setAcceptDrops(True)
        self.list_view.setDropIndicatorShown(True)
        self.list_view.setDefaultDropAction(Qt.DropAction.MoveAction)
        
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
            QListView::item:hover {
                background-color: rgba(255, 255, 255, 20);
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout()
        self.container = QWidget()
        self.container.setObjectName("MainFrame")
        c_layout = QVBoxLayout(self.container)

        self.label = QLabel("🟦 Моя Сетка Приложений")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        c_layout.addWidget(self.label)
        c_layout.addWidget(self.list_view)
        layout.addWidget(self.container)
        self.setLayout(layout)

    def open_file(self, index):
        file_path = self.model.filePath(index)
        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    # ПРИЕМ ФАЙЛОВ (Вход в заборчик)
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for f in files:
            file_name = os.path.basename(f)
            destination = os.path.join(os.getcwd(), file_name)
            if f != destination: # Чтобы не переименовывать самого себя
                try:
                    os.rename(f, destination)
                except Exception as e:
                    print(f"Ошибка: {e}")
        event.accept()

    # ПЕРЕМЕЩЕНИЕ ОКНА
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FenceWindow()
    window.show()
    sys.exit(app.exec())