from __future__ import annotations
from typing import Optional
from PyQt6 import QtCore
from services.local_db import LocalDB
import services.supabase_api as api

class SyncOrchestrator(QtCore.QObject):
    tasksUpdated  = QtCore.pyqtSignal(list)
    eventsUpdated = QtCore.pyqtSignal(list)
    tagsUpdated   = QtCore.pyqtSignal(list)
    projectsUpdated = QtCore.pyqtSignal(list)
    busyChanged   = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = LocalDB()
        self._busy = False

    # ---------- lifecycle ----------
    def bootstrap(self):
        self._set_busy(True)
        try:
            try:    tasks  = api.fetch_tasks()
            except: tasks = []
            try:    tags   = api.fetch_tags()
            except: tags   = []
            try:    projects = api.fetch_projects()
            except: projects = []
            self.db.replace_all("tasks", tasks)
            self.db.replace_all("tags", tags)
            self.db.replace_all("projects", projects)
        finally:
            self._emit_all_from_local()
            self._set_busy(False)

    def refresh(self):
        self._set_busy(True)
        try:
            tasks = self.db.get_all_tasks()
            tags = self.db.get_tags()
            projects = self.db.get_projects()
            try:
                self.db.dequeue_all()
            except Exception:
                pass
            try:
                api.wipe_all()
            except Exception as e:
                print("wipe error:", e)
            for g in tags:
                try:
                    api.upsert_tag(g.get("name", ""), g.get("id"))
                except Exception:
                    pass
            for p in projects:
                try:
                    api.upsert_project(p.get("name", ""), p.get("id"), p.get("tag_id"))
                except Exception:
                    pass
            for t in tasks:
                try:
                    api.upsert_task(t)
                except Exception:
                    pass
            self.bootstrap()
        except Exception as e:
            print("refresh error:", e)
            self._emit_all_from_local()
        finally:
            self._set_busy(False)

    # ---------- TAGS ----------
    def add_tag(self, name: str):
        self.db.add_tag_local(name)
        self.tagsUpdated.emit(self.db.get_tags())

    def delete_tag(self, tag_id: int):
        self.db.delete_tag_local(int(tag_id))
        self.tagsUpdated.emit(self.db.get_tags())

    # ---------- PROJECTS ----------
    def add_project(self, name: str, tag_id: Optional[int] = None):
        pid = self.db.add_project_local(name, tag_id)
        try:
            api.upsert_project(name, pid, tag_id)
        except Exception:
            pass
        self.projectsUpdated.emit(self.db.get_projects())

    def delete_project(self, project_id: int):
        self.db.delete_project_local(int(project_id))
        self.projectsUpdated.emit(self.db.get_projects())

    # ---------- TASKS ----------
    def upsert_task(self, task_id: Optional[int], title: str, notes: str,
                    due_date_iso: Optional[str], start_iso: Optional[str]=None,
                    end_iso: Optional[str]=None, parent_id: Optional[int]=None,
                    tag_id: Optional[int]=None, project_id: Optional[int]=None) -> int:
        tid = self.db.upsert_task(task_id, title, notes, due_date_iso, start_iso=start_iso, end_iso=end_iso, parent_id=parent_id, tag_id=tag_id, project_id=project_id)
        self._emit_all_from_local()
        return tid

    def delete_task(self, task_id: int):
        self.db.delete_task(task_id)
        self._emit_all_from_local()

    def set_task_status(self, task_id: int, status: str):
        # 🔒 Sadece status güncellenir — title asla değişmez
        self.db.set_task_status(task_id, status)
        self.tasksUpdated.emit(self.db.get_tasks())
        try:
            api.upsert_task({"id": int(task_id), "status": status})
        except Exception:
            pass

    def set_task_times(self, task_id: int, start_iso: Optional[str], end_iso: Optional[str]):
        self.db.set_task_times(task_id, start_iso, end_iso)
        self._emit_all_from_local()

    def set_task_parent(self, task_id: int, parent_id: Optional[int]):
        self.db.set_task_parent(task_id, parent_id)
        self.tasksUpdated.emit(self.db.get_tasks())
        try:
            api.upsert_task({"id": int(task_id), "parent_id": parent_id})
        except Exception:
            pass

    # ---------- helpers ----------
    def _emit_all_from_local(self):
        self.tasksUpdated.emit(self.db.get_tasks())
        self.eventsUpdated.emit(self.db.get_events())
        self.tagsUpdated.emit(self.db.get_tags())
        self.projectsUpdated.emit(self.db.get_projects())

    def _set_busy(self, b: bool):
        if self._busy != b:
            self._busy = b
            self.busyChanged.emit(b)
