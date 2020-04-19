import sys, random, atexit

from pathlib import Path
from threading import Thread
from queue import LifoQueue
from copy import deepcopy
from uuid import UUID

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QPixmap, QImage, QColor
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QScrollBar, QCompleter, QFrame, QHBoxLayout, QSplitter, QLineEdit, QSizePolicy, QPlainTextEdit, QComboBox, QFormLayout

from cutespam.db import picture_file_for_uid, get_all_uids, get_tab_complete_keywords, get_uids_from_keyword_list, get_meta, save_meta
from cutespam.xmpmeta import CuteMeta, Rating

IMG_LOADING = QImage(str(Path(__file__).parent / "image_loading.png"))
IMG_SIZE = 125

class PictureGrid(QWidget):
    def __init__(self, parent, uids, scrollbar, picture_viewer, meta_viewer):
        super().__init__(parent)
        self.scrollbar = scrollbar
        self.picture_viewer = picture_viewer
        self.meta_viewer = meta_viewer
        self.uids = uids
        self.images = {}
        self.selected_index = -1

        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        scrollbar.valueChanged.connect(lambda: self.update())

        self.image_queue = LifoQueue(20)

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

        if not self.image_queue.full():
            self.images[uid] = None
            self.image_queue.put(uid, block = True)
        return IMG_LOADING

    def get_selected_uid(self):
        if 0 <= self.selected_index < len(self.uids):
            return self.uids[self.selected_index]
        else: return None

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
        height = max(self.height() // IMG_SIZE, 1)
        width = max(self.width() // IMG_SIZE, 1)

        x = press_event.x() // IMG_SIZE
        y = press_event.y() // IMG_SIZE

        if x < width and y < height:
            self.selected_index = x + (y + self.scrollbar.value()) * width
            if self.selected_index >= len(self.uids):
                self.selected_index = -1
            self.update()

            uid = self.get_selected_uid()
            if uid:
                self.picture_viewer.set_image(uid)
                self.picture_viewer.update()
                self.meta_viewer.set_meta(get_meta(uid))

    def wheelEvent(self, wheel_event):
        self.scrollbar.wheelEvent(wheel_event)
        self.update()

class MetaViewer(QWidget):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.meta: CuteMeta = None

        self.uid = QLineEdit(self)
        self.uid.setDisabled(True)
        self.hash = QLineEdit(self)
        self.hash.setDisabled(True)
        self.caption = QPlainTextEdit(self)
        self.authors = QLineEdit(self)
        self.keywords = QLineEdit(self)
        self.source = QLineEdit(self)
        self.group_id = QLineEdit(self)
        self.collections = QLineEdit(self)
        self.rating = QComboBox(self)
        self.rating.addItems(["Safe", "Nudity", "Questionable", "Explicit"])
        self.date = QLineEdit(self)
        self.date.setDisabled(True)
        self.source_other = QPlainTextEdit(self)
        self.source_via = QPlainTextEdit(self)

        layout = QFormLayout()
        layout.addRow("uid", self.uid)
        layout.addRow("hash", self.hash)
        layout.addRow("caption", self.caption)
        layout.addRow("authors", self.authors)
        layout.addRow("keywords", self.keywords)
        layout.addRow("source", self.source)
        layout.addRow("group_id", self.group_id)
        layout.addRow("collections", self.collections)
        layout.addRow("rating", self.rating)
        layout.addRow("date", self.date)
        layout.addRow("source_other", self.source_other)
        layout.addRow("source_via", self.source_via)
        
        self.setLayout(layout)

    def save_meta(self):
        if self.meta:
            meta = deepcopy(self.meta)
            self.meta.caption = self.caption.toPlainText() or None
            self.meta.authors = self.authors.text().split(" ") if self.authors.text() else None
            self.meta.keywords = set(self.keywords.text().split(" ")) if self.keywords.text() else None
            self.meta.source = self.source.text() or None
            self.meta.group_id = UUID(self.group_id.text()) if self.group_id.text() else None
            self.meta.collections = set(self.collections.text().split(" ")) if self.collections.text() else None
            self.meta.rating = getattr(Rating, self.rating.currentText())
            self.meta.source_other = set(self.source_other.toPlainText().split("\n")) if self.source_other.toPlainText() else None
            self.meta.source_via = set(self.source_via.toPlainText().split("\n")) if self.source_via.toPlainText() else None

            if self.meta.as_dict() != meta.as_dict():
                self.meta.generate_keywords()
                save_meta(self.meta)

    def set_meta(self, meta: CuteMeta):
        self.save_meta()
        self.meta = meta
        
        self.uid.setText(str(meta.uid or ""))
        self.hash.setText(meta.hash or "")
        self.caption.setPlainText(meta.caption or "")
        self.authors.setText(" ".join(meta.authors or []))
        self.keywords.setText(" ".join(meta.keywords or []))
        self.source.setText(meta.source or "")
        self.group_id.setText(str(meta.group_id or ""))
        self.collections.setText(" ".join(meta.collections or []))
        if meta.rating: self.rating.setCurrentText(meta.rating.name)
        else: self.rating.setCurrentIndex(0)
        self.date.setText(str(meta.date or ""))
        self.source_other.setPlainText("\n".join(meta.source_other or []))
        self.source_via.setPlainText("\n".join(meta.source_via or []))

class PictureViewer(QFrame):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.image = None
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.setLineWidth(3)

    def set_image(self, uid):
        self.image = QImage(str(picture_file_for_uid(uid)))

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.image:
            painter = QtGui.QPainter(self)
            image = self.image.scaled(
                self.width() - self.frameWidth() * 2, self.height() - self.frameWidth() * 2, 
                QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            painter.drawImage(
                self.width() / 2 - image.width() / 2 + self.frameWidth() / 2, 
                self.height() / 2 - image.height() / 2 + self.frameWidth() / 2, image)
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
        image_splitter = QSplitter(QtCore.Qt.Vertical, self)
        picture_viewer = PictureViewer(image_splitter)
        meta_viewer = MetaViewer(image_splitter)
        atexit.register(lambda: meta_viewer.save_meta())

        picture_frame = QWidget(main_splitter)
        picture_frame.setLayout(layout)

        scrollbar = QScrollBar(QtCore.Qt.Vertical)
        image_pane = PictureGrid(picture_frame, uids, scrollbar, picture_viewer, meta_viewer)
        
        layout.addWidget(image_pane)
        layout.addWidget(scrollbar)

        image_splitter.addWidget(picture_viewer)
        image_splitter.addWidget(meta_viewer)
        image_splitter.setSizes([600, 200])

        main_splitter.addWidget(picture_frame)
        main_splitter.addWidget(image_splitter)
        main_splitter.setSizes([300, 200]) # TODO What do these numbers do?

        self.setCentralWidget(main_splitter)
        self.setWindowTitle("Cutespam")

        menu = self.menuBar()
        file = menu.addMenu("File")
        file.addAction("Import")

        search = TagLineEdit(self)
        completer = QCompleter([], search)
        search.setMultipleCompleter(completer)
        menu.setCornerWidget(search)

        def on_typed():
            words = search.text().split(" ")
            last_word = words[-1]
            completer.model().setStringList(get_tab_complete_keywords(last_word))

            if len(search.text()) == 0:
                image_pane.uids = get_all_uids()
            else:
                image_pane.uids = list(get_uids_from_keyword_list(words))
            
            image_pane.update()

        search.textChanged.connect(on_typed)

def main():
    app = QtWidgets.QApplication([])

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
   