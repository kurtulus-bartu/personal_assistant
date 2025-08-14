from __future__ import annotations
from typing import Any, Dict, List
from PyQt6 import QtCore
import services.supabase_api as api

class SyncService(QtCore.QObject):
    tasksUpdated  = QtCore.pyqtSignal(list)
    eventsUpdated = QtCore.pyqtSignal(list)
    tagsUpdated   = QtCore.pyqtSignal(list)
    projectsUpdated = QtCore.pyqtSignal(list)
    onlineChanged = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None, poll_sec: int = 60):
        super().__init__(parent)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(int(poll_sec * 1000))
        self._timer.timeout.connect(self.pull_all)
        self._online = True

    def start(self):
        self.pull_all()
        self._timer.start()

    def stop(self):
        self._timer.stop()

    @QtCore.pyqtSlot()
    def pull_all(self):
        try:
            tasks = api.fetch_tasks()
            tags  = api.fetch_tags()
            projects = api.fetch_projects()
            events = [t for t in tasks if t.get("has_time") and t.get("start_ts") and t.get("end_ts")]
            self.tasksUpdated.emit(tasks)
            self.eventsUpdated.emit(events)
            self.tagsUpdated.emit(tags)
            self.projectsUpdated.emit(projects)
            if not self._online:
                self._online = True
                self.onlineChanged.emit(True)
        except Exception:
            if self._online:
                self._online = False
                self.onlineChanged.emit(False)

    # ---- CRUD: Upsert/Delete -> anında pull YAPMA (lag'i azalt) ----
    def upsert_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return api.upsert_task(task)

    def delete_task(self, task_id: int) -> bool:
        return api.delete_task(task_id)

    def upsert_tag(self, name: str, tag_id: int | None = None) -> Dict[str, Any]:
        return api.upsert_tag(name, tag_id)

    def delete_tag(self, tag_id: int) -> bool:
        return api.delete_tag(tag_id)

    def upsert_project(self, name: str, project_id: int | None = None, tag_id: int | None = None) -> Dict[str, Any]:
        return api.upsert_project(name, project_id, tag_id)

    def delete_project(self, project_id: int) -> bool:
        return api.delete_project(project_id)
