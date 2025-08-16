from PyQt6 import QtCore, QtGui, QtWidgets
from theme.colors import COLOR_TEXT, COLOR_SECONDARY_BG, COLOR_TEXT_MUTED
from typing import Dict, Tuple

class TaskLane(QtWidgets.QListWidget):
    dropped = QtCore.pyqtSignal(int, str, str, str)  # task_id, title, meta, due
    droppedOnTask = QtCore.pyqtSignal(int, int)  # child_id, parent_id

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
            f"border:none; border-radius:8px;"
        )

    def mimeTypes(self):
        return ['application/x-task-id', 'application/x-task-title',
                'application/x-task-meta', 'application/x-task-due']

    def startDrag(self, actions):
        item = self.currentItem()
        if not item: return
        mime = QtCore.QMimeData()
        mime.setData('application/x-task-id', str(item.data(QtCore.Qt.ItemDataRole.UserRole)).encode('utf-8'))
        title = item.data(QtCore.Qt.ItemDataRole.UserRole + 3) or item.text()
        mime.setData('application/x-task-title', str(title).encode('utf-8'))
        meta = item.data(QtCore.Qt.ItemDataRole.UserRole + 1) or ""
        due = item.data(QtCore.Qt.ItemDataRole.UserRole + 2) or ""
        mime.setData('application/x-task-meta', str(meta).encode('utf-8'))
        mime.setData('application/x-task-due', str(due).encode('utf-8'))
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        drag.exec(QtCore.Qt.DropAction.MoveAction)

    def dragEnterEvent(self, e: QtGui.QDragEnterEvent):
        e.acceptProposedAction() if e.mimeData().hasFormat('application/x-task-id') else e.ignore()

    def dropEvent(self, e: QtGui.QDropEvent):
        if not e.mimeData().hasFormat('application/x-task-id'):
            e.ignore(); return
        task_id = int(bytes(e.mimeData().data('application/x-task-id')).decode('utf-8'))
        title = None
        if e.mimeData().hasFormat('application/x-task-title'):
            try:
                title = bytes(e.mimeData().data('application/x-task-title')).decode('utf-8')
            except Exception:
                title = None
        meta = ""
        if e.mimeData().hasFormat('application/x-task-meta'):
            try:
                meta = bytes(e.mimeData().data('application/x-task-meta')).decode('utf-8')
            except Exception:
                meta = ""
        due = ""
        if e.mimeData().hasFormat('application/x-task-due'):
            try:
                due = bytes(e.mimeData().data('application/x-task-due')).decode('utf-8')
            except Exception:
                due = ""

        # Hedef item? (alt görev)
        target_item = self.itemAt(e.position().toPoint())
        parent_id = None
        if target_item and target_item.data(QtCore.Qt.ItemDataRole.UserRole) != task_id:
            parent_id = int(target_item.data(QtCore.Qt.ItemDataRole.UserRole))

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

        self._add_task_item(task_id, title, meta or None, due or None)
        e.acceptProposedAction()
        self.dropped.emit(task_id, title or f"Task #{task_id}", meta, due)
        if parent_id is not None:
            self.droppedOnTask.emit(task_id, parent_id)

    def _add_task_item(self, task_id: int, title: str | None = None,
                       meta: str | None = None, due: str | None = None):
        plain = title or f"Task #{task_id}"
        # Sol metin: TITLE (TAG>PROJECT>PARENT)
        if meta:
            left_html = f"{plain} <span style='color:{COLOR_TEXT_MUTED};'>({meta})</span>"
        else:
            left_html = plain

        it = QtWidgets.QListWidgetItem()
        it.setData(QtCore.Qt.ItemDataRole.UserRole, task_id)
        it.setData(QtCore.Qt.ItemDataRole.UserRole + 1, meta or "")
        it.setData(QtCore.Qt.ItemDataRole.UserRole + 2, due or "")
        it.setData(QtCore.Qt.ItemDataRole.UserRole + 3, plain)
        it.setFlags(it.flags() | QtCore.Qt.ItemFlag.ItemIsDragEnabled
                    | QtCore.Qt.ItemFlag.ItemIsSelectable
                    | QtCore.Qt.ItemFlag.ItemIsEnabled)

        # 2 eşit sütunlu widget
        w = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(w); row.setContentsMargins(8, 6, 8, 6); row.setSpacing(8)

        lbl_left = QtWidgets.QLabel()
        lbl_left.setTextFormat(QtCore.Qt.TextFormat.RichText)
        lbl_left.setWordWrap(True)
        lbl_left.setText(left_html)

        lbl_right = QtWidgets.QLabel(due or "")
        lbl_right.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight |
                               QtCore.Qt.AlignmentFlag.AlignVCenter)

        # İki sütun eşit genişlik
        row.addWidget(lbl_left, 1)
        row.addWidget(lbl_right, 1)

        self.addItem(it)
        self.setItemWidget(it, w)
        it.setSizeHint(QtCore.QSize(self.viewport().width() - 12,
                                    max(40, w.sizeHint().height())))

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
    taskReparented = QtCore.pyqtSignal(int, int)  # child_id, parent_id

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(8)

        self.todo   = TaskLane("Not Started", self)
        self.inprog = TaskLane("In Progress", self)
        self.done   = TaskLane("Done", self)

        self.todo.dropped.connect(lambda tid, title, meta, due: self._on_lane_drop(tid, "not started", title, meta, due))
        self.inprog.dropped.connect(lambda tid, title, meta, due: self._on_lane_drop(tid, "in progress", title, meta, due))
        self.done.dropped.connect(lambda tid, title, meta, due: self._on_lane_drop(tid, "done", title, meta, due))

        self._info_map: Dict[int, Tuple[str, str, str]] = {}

        for lane in (self.todo, self.inprog, self.done):
            lane.itemDoubleClicked.connect(self._emit_task_activated)
            lane.droppedOnTask.connect(self._emit_reparent)

        def make_row(label: str, lane: TaskLane):
            row = QtWidgets.QVBoxLayout()
            lbl = QtWidgets.QLabel(label); lbl.setStyleSheet("color:#AEAEAE;")
            row.addWidget(lbl); row.addWidget(lane); return row

        lay.addLayout(make_row("Not Started", self.todo))
        lay.addLayout(make_row("In Progress", self.inprog))
        lay.addLayout(make_row("Done", self.done))

    # Public
    def set_tasks(self, tasks: list[dict]):
        for lane in (self.todo, self.inprog, self.done):
            lane.clear()
        self._info_map.clear()
        for t in tasks:
            tid = int(t["id"])
            title = t.get("title") or f"Task #{tid}"
            status = (t.get("status") or "not started").lower()
            lane = self.todo if status == "not started" else (self.inprog if status == "in progress" else self.done)
            disp_title = "  ↳ " + title if t.get("parent_id") else title
            meta_parts = []
            if t.get("tag_name"): meta_parts.append(t["tag_name"])
            if t.get("project_name"): meta_parts.append(t["project_name"])
            if t.get("parent_title"): meta_parts.append(t["parent_title"])
            meta = ">".join(meta_parts)
            due = t.get("due") or t.get("due_date") or ""
            self._info_map[tid] = (disp_title, meta, due)
            lane._add_task_item(tid, disp_title, meta or None, due or None)

    def move_task(self, task_id: int, target: str):
        target = target.lower()
        lanes = {"not started": self.todo, "in progress": self.inprog, "done": self.done}
        lane = lanes.get(target); 
        if not lane: return False
        for l in lanes.values(): l.remove_task(task_id)
        info = self._info_map.get(task_id, (None, None, None))
        lane._add_task_item(task_id, info[0], info[1], info[2])
        self.statusChanged.emit(task_id, target); return True

    def _on_lane_drop(self, task_id: int, new_status: str, title: str, meta: str, due: str):
        self._info_map[task_id] = (title, meta, due)
        self.statusChanged.emit(task_id, new_status)

    def _emit_task_activated(self, item: QtWidgets.QListWidgetItem):
        try:
            task_id = int(item.data(QtCore.Qt.ItemDataRole.UserRole))
            self.taskActivated.emit(task_id)
        except Exception:
            pass

    def _emit_reparent(self, child_id: int, parent_id: int):
        self.taskReparented.emit(child_id, parent_id)
