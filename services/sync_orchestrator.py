from __future__ import annotations
from typing import Optional
from PyQt6 import QtCore
from services.local_db import LocalDB
import services.supabase_api as api

class SyncOrchestrator(QtCore.QObject):
    tasksUpdated  = QtCore.pyqtSignal(list)
    eventsUpdated = QtCore.pyqtSignal(list)
    tagsUpdated   = QtCore.pyqtSignal(list)
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
            try:    events = api.fetch_events()
            except: events = []
            try:    tags   = api.fetch_tags()
            except: tags   = []
            self.db.replace_all("tasks", tasks)
            self.db.replace_all("events", events)
            self.db.replace_all("tags", tags)
        finally:
            self._emit_all_from_local()
            self._set_busy(False)

    def refresh(self):
        self._set_busy(True)
        try:
            tasks = self.db.get_all_tasks()
            events = self.db.get_events()
            tags = self.db.get_tags()
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
            for t in tasks:
                try:
                    api.upsert_task(t)
                except Exception:
                    pass
            for ev in events:
                try:
                    api.upsert_event({
                        "id": ev.get("id"),
                        "task_id": ev.get("task_id"),
                        "title": ev.get("title"),
                        "notes": ev.get("notes"),
                        "start_ts": ev.get("start_ts"),
                        "end_ts": ev.get("end_ts"),
                        "rrule": ev.get("rrule"),
                    })
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

    # ---------- TASKS ----------
    def upsert_task(self, task_id: Optional[int], title: str, notes: str,
                    due_date_iso: Optional[str], has_time: bool=False) -> int:
        tid = self.db.upsert_task(task_id, title, notes, due_date_iso, has_time=has_time)
        self.tasksUpdated.emit(self.db.get_tasks())
        return tid

    def delete_task(self, task_id: int):
        self.db.delete_task(task_id)
        self.tasksUpdated.emit(self.db.get_tasks())

    def set_task_status(self, task_id: int, status: str):
        # 🔒 Sadece status güncellenir — title asla değişmez
        self.db.set_task_status(task_id, status)
        self.tasksUpdated.emit(self.db.get_tasks())
        try:
            api.upsert_task({"id": int(task_id), "status": status})
        except Exception:
            pass

    # ---------- EVENTS ----------
    def create_event(self, task_id: int, start_iso: str, end_iso: str,
                     title: Optional[str]=None, notes: Optional[str]=None, rrule: Optional[str]=None) -> int:
        eid = self.db.create_event(task_id, start_iso, end_iso, title=title, notes=notes, rrule=rrule)
        self.db.mark_task_has_time(task_id, True)
        self._emit_all_from_local()
        return eid

    def update_event(self, event_id: int, start_iso: str, end_iso: str,
                     title: Optional[str]=None, notes: Optional[str]=None, rrule: Optional[str]=None):
        self.db.update_event(event_id, start_iso, end_iso, title=title, notes=notes, rrule=rrule)
        self.eventsUpdated.emit(self.db.get_events())

    def delete_event(self, event_id: int):
        ev = self.db.get_event_by_id(event_id)
        if ev and ev.get("task_id"):
            self.db.mark_task_has_time(int(ev["task_id"]), False)
        self.db.delete_event(event_id)
        self._emit_all_from_local()

    # ---------- helpers ----------
    def _emit_all_from_local(self):
        self.tasksUpdated.emit(self.db.get_tasks())
        self.eventsUpdated.emit(self.db.get_events())
        self.tagsUpdated.emit(self.db.get_tags())

    def _set_busy(self, b: bool):
        if self._busy != b:
            self._busy = b
            self.busyChanged.emit(b)
