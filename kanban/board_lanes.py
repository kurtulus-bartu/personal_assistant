from PyQt6 import QtCore, QtGui, QtWidgets
from theme.colors import COLOR_TEXT, COLOR_SECONDARY_BG

class TaskLane(QtWidgets.QListWidget):
    dropped = QtCore.pyqtSignal(int)  # task_id

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        # Dikey liste, tam genişlik kartlar
        self.setViewMode(QtWidgets.QListWidget.ViewMode.ListMode)
        self.setFlow(QtWidgets.QListView.Flow.TopToBottom)
        self.setWrapping(False)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setSpacing(6)

        # DnD
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.setMovement(QtWidgets.QListView.Movement.Snap)

        # Double click handled by board; disable default inline editing
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        self.setStyleSheet(
            f"color:{COLOR_TEXT}; background:{COLOR_SECONDARY_BG}; "
            f"border:1px solid #3a3a3a; border-radius:8px;"
        )

    def mimeTypes(self): return ['application/x-task-id']

    def startDrag(self, actions):
        item = self.currentItem()
        if not item: return
        mime = QtCore.QMimeData()
        mime.setData('application/x-task-id', str(item.data(QtCore.Qt.ItemDataRole.UserRole)).encode('utf-8'))
        drag = QtGui.QDrag(self); drag.setMimeData(mime)
        drag.exec(QtCore.Qt.DropAction.MoveAction)

    def dragEnterEvent(self, e: QtGui.QDragEnterEvent):
        e.acceptProposedAction() if e.mimeData().hasFormat('application/x-task-id') else e.ignore()

    def dropEvent(self, e: QtGui.QDropEvent):
        if not e.mimeData().hasFormat('application/x-task-id'):
            e.ignore(); return
        task_id = int(bytes(e.mimeData().data('application/x-task-id')).decode('utf-8'))

        # Kaynaktan çıkar
        src = e.source()
        if isinstance(src, TaskLane) and src is not self:
            for i in range(src.count()-1, -1, -1):
                it = src.item(i)
                if it.data(QtCore.Qt.ItemDataRole.UserRole) == task_id:
                    src.takeItem(i); break

        # Aynı şeritte mevcutsa ekleme
        for i in range(self.count()):
            if self.item(i).data(QtCore.Qt.ItemDataRole.UserRole) == task_id:
                e.acceptProposedAction(); return

        self._add_task_item(task_id)
        e.acceptProposedAction()
        self.dropped.emit(task_id)

    def _add_task_item(self, task_id: int, title: str | None = None):
        it = QtWidgets.QListWidgetItem(title or f"Task #{task_id}")
        it.setData(QtCore.Qt.ItemDataRole.UserRole, task_id)
        it.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft)
        it.setSizeHint(QtCore.QSize(self.viewport().width() - 12, 40))
        self.addItem(it)

    def remove_task(self, task_id: int):
        for i in range(self.count()-1, -1, -1):
            if self.item(i).data(QtCore.Qt.ItemDataRole.UserRole) == task_id:
                self.takeItem(i); return True
        return False

    def resizeEvent(self, e: QtGui.QResizeEvent):
        super().resizeEvent(e)
        w = self.viewport().width() - 12
        for i in range(self.count()):
            it = self.item(i)
            sz = it.sizeHint()
            if sz.width() != w:
                it.setSizeHint(QtCore.QSize(w, sz.height()))

class KanbanBoard(QtWidgets.QWidget):
    statusChanged = QtCore.pyqtSignal(int, str)  # (task_id, new_status)
    taskActivated = QtCore.pyqtSignal(int)       # task_id

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(8)

        self.todo   = TaskLane("Not Started", self)
        self.inprog = TaskLane("In Progress", self)
        self.done   = TaskLane("Done", self)

        self.todo.dropped.connect(lambda tid: self._on_lane_drop(tid, "not started"))
        self.inprog.dropped.connect(lambda tid: self._on_lane_drop(tid, "in progress"))
        self.done.dropped.connect(lambda tid: self._on_lane_drop(tid, "done"))

        for lane in (self.todo, self.inprog, self.done):
            lane.itemDoubleClicked.connect(self._emit_task_activated)

        def make_row(label: str, lane: TaskLane):
            row = QtWidgets.QVBoxLayout()
            lbl = QtWidgets.QLabel(label); lbl.setStyleSheet("color:#AEAEAE;")
            row.addWidget(lbl); row.addWidget(lane); return row

        lay.addLayout(make_row("Not Started", self.todo))
        lay.addLayout(make_row("In Progress", self.inprog))
        lay.addLayout(make_row("Done", self.done))

    # Public
    def set_tasks(self, tasks: list[dict]):
        for lane in (self.todo, self.inprog, self.done): lane.clear()
        for t in tasks:
            tid = int(t["id"]); title = t.get("title") or f"Task #{tid}"
            status = (t.get("status") or "not started").lower()
            lane = self.todo if status == "not started" else (self.inprog if status == "in progress" else self.done)
            lane._add_task_item(tid, title)

    def move_task(self, task_id: int, target: str):
        target = target.lower()
        lanes = {"not started": self.todo, "in progress": self.inprog, "done": self.done}
        lane = lanes.get(target); 
        if not lane: return False
        for l in lanes.values(): l.remove_task(task_id)
        lane._add_task_item(task_id)
        self.statusChanged.emit(task_id, target); return True

    def _on_lane_drop(self, task_id: int, new_status: str):
        self.statusChanged.emit(task_id, new_status)

    def _emit_task_activated(self, item: QtWidgets.QListWidgetItem):
        try:
            task_id = int(item.data(QtCore.Qt.ItemDataRole.UserRole))
            self.taskActivated.emit(task_id)
        except Exception:
            pass
