from PyQt6 import QtCore, QtGui, QtWidgets
from theme.colors import COLOR_TEXT, COLOR_SECONDARY_BG


class TaskList(QtWidgets.QListWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setStyleSheet(f"color:{COLOR_TEXT}; background:{COLOR_SECONDARY_BG}; border:1px solid #3a3a3a; border-radius:8px;")
        self.setSpacing(4)

    def mimeTypes(self):
        return ['application/x-task-id']

    def startDrag(self, actions):
        item = self.currentItem()
        if not item:
            return
        mime = QtCore.QMimeData()
        mime.setData('application/x-task-id', str(item.data(QtCore.Qt.ItemDataRole.UserRole)).encode('utf-8'))
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        drag.exec(actions)

    def dragEnterEvent(self, e: QtGui.QDragEnterEvent):
        if e.mimeData().hasFormat('application/x-task-id'):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e: QtGui.QDropEvent):
        if not e.mimeData().hasFormat('application/x-task-id'):
            e.ignore(); return
        task_id = int(bytes(e.mimeData().data('application/x-task-id')).decode('utf-8'))
        it = QtWidgets.QListWidgetItem(f"Task #{task_id}")
        it.setData(QtCore.Qt.ItemDataRole.UserRole, task_id)
        self.addItem(it)
        e.acceptProposedAction()


class KanbanBoard(QtWidgets.QWidget):
    statusChanged = QtCore.pyqtSignal(int, str)
    taskDroppedToCalendar = QtCore.pyqtSignal(int, tuple)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search tasks…")
        self.search.setStyleSheet("color:white; background:#1f1f1f; border:1px solid #3a3a3a; border-radius:8px; padding:6px 8px;")
        header.addWidget(self.search)
        lay.addLayout(header)

        cols = QtWidgets.QHBoxLayout()
        self.col_todo = TaskList("Not Started")
        self.col_prog = TaskList("In Progress")
        self.col_done = TaskList("Done")
        for w in (self.col_todo, self.col_prog, self.col_done):
            box = QtWidgets.QVBoxLayout()
            lbl = QtWidgets.QLabel(w.title)
            lbl.setStyleSheet("color:#AEAEAE;")
            box.addWidget(lbl)
            box.addWidget(w)
            cols.addLayout(box)
        lay.addLayout(cols)

        # Demo verisi
        for i in range(1, 6):
            it = QtWidgets.QListWidgetItem(f"Task #{i}")
            it.setData(QtCore.Qt.ItemDataRole.UserRole, i)
            self.col_todo.addItem(it)
