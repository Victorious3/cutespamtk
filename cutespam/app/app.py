import sys, random
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QWidget, QScrollArea, QLayout, QStyle

from cutespam.db import picture_file_for_uid, get_all_uids

# https://stackoverflow.com/questions/41621354/pyqt-wrap-around-layout-of-widgets-inside-a-qscrollarea
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=-1, hspacing=-1, vspacing=-1):
        super().__init__(parent)
        self._hspacing = hspacing
        self._vspacing = vspacing
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        del self._items[:]

    def addItem(self, item):
        self._items.append(item)

    def horizontalSpacing(self):
        if self._hspacing >= 0:
            return self._hspacing
        else:
            return self.smartSpacing(
                QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self._vspacing >= 0:
            return self._vspacing
        else:
            return self.smartSpacing(
                QStyle.PM_LayoutVerticalSpacing)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)

    def expandingDirections(self):
        return QtCore.Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QtCore.QSize(left + right, top + bottom)
        return size

    def doLayout(self, rect, testonly):
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(+left, +top, -right, -bottom)
        x = effective.x()
        y = effective.y()
        lineheight = 0
        for item in self._items:
            widget = item.widget()
            hspace = self.horizontalSpacing()
            if hspace == -1:
                hspace = widget.style().layoutSpacing(
                    QtGui.QSizePolicy.PushButton,
                    QtGui.QSizePolicy.PushButton, QtCore.Qt.Horizontal)
            vspace = self.verticalSpacing()
            if vspace == -1:
                vspace = widget.style().layoutSpacing(
                    QtGui.QSizePolicy.PushButton,
                    QtGui.QSizePolicy.PushButton, QtCore.Qt.Vertical)
            nextX = x + item.sizeHint().width() + hspace
            if nextX - hspace > effective.right() and lineheight > 0:
                x = effective.x()
                y = y + lineheight + vspace
                nextX = x + item.sizeHint().width() + hspace
                lineheight = 0
            if not testonly:
                item.setGeometry(
                    QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            x = nextX
            lineheight = max(lineheight, item.sizeHint().height())
        return y + lineheight - rect.y() + bottom

    def smartSpacing(self, pm):
        parent = self.parent()
        if parent is None:
            return -1
        elif parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        else:
            return parent.spacing()

class MainWindow(QMainWindow):
    def __init__(self, uids):
        super().__init__()
        self.uids = uids

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)
        image_pane = QWidget()
        layout = FlowLayout()

        self.images = []
        for uid in uids:
            image = QLabel()

            image.setFixedWidth(150)
            image.setFixedHeight(150)
            image.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(image)
            self.images.append(image)

        image_pane.setLayout(layout)
        scroll_area.setWidget(image_pane)

        self.setCentralWidget(scroll_area)
        self.setWindowTitle("Cutespam")

    def on_scroll(self):
        print(self.sender().value())

from threading import Thread
import time

def main():
    app = QtWidgets.QApplication([])

    window = MainWindow(get_all_uids())
    window.resize(800, 600)
    window.show()

    def load_images():
        for i, image in enumerate(window.images):
            pixmap = QPixmap(str(picture_file_for_uid(window.uids[i])))
            image.setPixmap(pixmap.scaled(150, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            time.sleep(0.01)

    thread = Thread(target = load_images)
    thread.start()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
   