import sys, random

from pathlib import Path
from threading import Thread
from queue import LifoQueue

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QScrollBar, QHBoxLayout

from cutespam.db import picture_file_for_uid, get_all_uids

IMG_LOADING = QImage(str(Path(__file__).parent / "image_loading.png"))
IMG_SIZE = 150

class PictureViewer(QWidget):
    def __init__(self, uids, scrollbar, flags = QtCore.Qt.WindowFlags()):
        super().__init__(flags = flags)
        self.scrollbar = scrollbar
        self.set_uids(uids)

        def on_scroll():
            self.update()
        scrollbar.valueChanged.connect(on_scroll)

        self.image_queue = LifoQueue()

        def load_images():
            while True:
                uid = self.image_queue.get(block = True)
                image = QImage(str(picture_file_for_uid(uid))).scaled(
                    IMG_SIZE, IMG_SIZE, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.images[uid] = image
                self.update()

        image_loading_thread = Thread(target = load_images)
        image_loading_thread.setDaemon(True)
        image_loading_thread.start()

    def set_uids(self, uids):
        self.uids = uids
        self.images = {}

    def get_image(self, uid):
        if uid in self.images:
            uid = self.images[uid]
            if uid: return uid
            return IMG_LOADING

        self.images[uid] = None
        self.image_queue.put(uid, block = True)
        return IMG_LOADING

    def paintEvent(self, event):
        super().paintEvent(event)

        rect = event.rect()

        height = rect.height() // IMG_SIZE
        width = rect.width() // IMG_SIZE

        self.scrollbar.setMaximum(len(self.uids) // width)
        self.scrollbar.setPageStep(1)

        painter = QtGui.QPainter(self)
        for i in range(0, width):
            for j in range(0, height):
                x = i * IMG_SIZE
                y = j * IMG_SIZE
                index = i + ((j + self.scrollbar.value()) * width)
                if index < len(self.uids):
                    image = self.get_image(self.uids[index])
                    painter.drawImage(x, y, image)

        painter.end()

    def wheelEvent(self, wheel_event):
        self.scrollbar.wheelEvent(wheel_event)
        self.update()
        


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        layout = QHBoxLayout()
        frame = QWidget()
        frame.setLayout(layout)

        scrollbar = QScrollBar(QtCore.Qt.Vertical)
        image_pane = PictureViewer(get_all_uids(), scrollbar)
        
        layout.addWidget(image_pane)
        layout.addWidget(scrollbar)
        self.setCentralWidget(frame)
        self.setWindowTitle("Cutespam")

def main():
    app = QtWidgets.QApplication([])

    window = MainWindow()
    window.resize(800, 600)
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
   