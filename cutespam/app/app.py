import sys, random

from pathlib import Path
from threading import Thread
from queue import LifoQueue

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QPixmap, QImage, QColor
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QScrollBar, QHBoxLayout, QSplitter, QLineEdit, QSizePolicy, QCompleter

from cutespam.db import picture_file_for_uid, get_all_uids, get_tab_complete_keywords

IMG_LOADING = QImage(str(Path(__file__).parent / "image_loading.png"))
IMG_SIZE = 125

class PictureGrid(QWidget):
    def __init__(self, parent, uids, scrollbar, picture_viewer, flags = QtCore.Qt.WindowFlags()):
        super().__init__(parent, flags = flags)
        self.scrollbar = scrollbar
        self.picture_viewer = picture_viewer
        self.uids = uids
        self.images = {}
        self.selected_index = -1

        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        scrollbar.valueChanged.connect(lambda: self.update())

        self.image_queue = LifoQueue() # TODO Use max size

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

    def get_image(self, uid):
        if uid in self.images:
            uid = self.images[uid]
            if uid: return uid
            return IMG_LOADING

        self.images[uid] = None
        self.image_queue.put(uid, block = True)
        return IMG_LOADING

    def get_selected_uid(self):
        return self.uids[self.selected_index]

    def paintEvent(self, event):
        super().paintEvent(event)

        height = max(self.height() // IMG_SIZE, 1)
        width = max(self.width() // IMG_SIZE, 1)

        self.scrollbar.setMaximum(len(self.uids) // width)
        self.scrollbar.setPageStep(1)

        painter = QtGui.QPainter(self)
        for i in range(0, width):
            for j in range(0, height):
                x = i * IMG_SIZE
                y = j * IMG_SIZE
                index = i + (j + self.scrollbar.value()) * width
                if index < len(self.uids):
                    if index == self.selected_index:
                        painter.fillRect(x, y, IMG_SIZE, IMG_SIZE, QColor.fromRgb(0xCCE8FF))

                    image = self.get_image(self.uids[index])
                    painter.drawImage(x + IMG_SIZE / 2 - image.width() / 2, y + IMG_SIZE / 2 - image.height() / 2, image)

                    if index == self.selected_index:
                        painter.setPen(QColor.fromRgb(0x99D1FF))
                        painter.drawRect(x, y, IMG_SIZE - 1, IMG_SIZE - 1)

        painter.end()

    def mousePressEvent(self, press_event):
        width = max(self.width() // IMG_SIZE, 1)

        x = press_event.x() // IMG_SIZE
        y = press_event.y() // IMG_SIZE

        self.selected_index = x + (y + self.scrollbar.value()) * width
        self.update()

        self.picture_viewer.set_image(self.get_selected_uid())
        self.picture_viewer.update()

    def wheelEvent(self, wheel_event):
        self.scrollbar.wheelEvent(wheel_event)
        self.update()

class PictureViewer(QWidget):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.image = None

    def set_image(self, uid):
        self.image = QImage(str(picture_file_for_uid(uid)))

    def paintEvent(self, event):
        if self.image:
            painter = QtGui.QPainter(self)
            image = self.image.scaled(self.width(), self.height(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            painter.drawImage(self.width() / 2 - image.width() / 2, self.height() / 2 - image.height() / 2, image)
            painter.end()

# https://stackoverflow.com/questions/47832971/qcompleter-supporting-multiple-items-like-stackoverflow-tag-field
class TagLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.multipleCompleter = None

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if not self.multipleCompleter:
            return
        c = self.multipleCompleter
        if self.text() == "":
            return
        c.setCompletionPrefix(self.cursorWord(self.text()))
        if len(c.completionPrefix()) < 1:
            c.popup().hide()
            return
        c.complete()

    def cursorWord(self, sentence):
        p = sentence.rfind(" ")
        if p == -1:
            return sentence
        return sentence[p + 1:]

    def insertCompletion(self, text):
        p = self.text().rfind(" ")
        if p == -1:
            self.setText(text)
        else:
            self.setText(self.text()[:p+1]+ text)

    def setMultipleCompleter(self, completer):
        self.multipleCompleter = completer
        self.multipleCompleter.setWidget(self)
        completer.activated.connect(self.insertCompletion)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        uids = get_all_uids()
        
        layout = QHBoxLayout()
        main_splitter = QSplitter(self)
        picture_viewer = PictureViewer(main_splitter)

        picture_frame = QWidget(main_splitter)
        picture_frame.setLayout(layout)

        scrollbar = QScrollBar(QtCore.Qt.Vertical)
        image_pane = PictureGrid(picture_frame, uids, scrollbar, picture_viewer)
        
        layout.addWidget(image_pane)
        layout.addWidget(scrollbar)

        main_splitter.addWidget(picture_frame)
        main_splitter.addWidget(picture_viewer)
        main_splitter.setSizes([300, 200]) # TODO What do these numbers do?

        self.setCentralWidget(main_splitter)
        self.setWindowTitle("Cutespam")

        menu = self.menuBar()
        file = menu.addMenu("File")
        file.addAction("Import")

        search = TagLineEdit(self)
        completer = QCompleter(["foo", "bar", "baz"], search)
        search.setMultipleCompleter(completer)
        menu.setCornerWidget(search)

        def on_typed():
            last_word = search.text().split(" ")[-1]
            completer.model().setStringList(get_tab_complete_keywords(last_word))

        search.textChanged.connect(on_typed)

def main():
    app = QtWidgets.QApplication([])

    # TODO Proper style
    app.setStyleSheet("""
        QSplitter::handle {
            background-color: #333;
        }
    """)

    window = MainWindow()
    window.resize(800, 650)
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
   