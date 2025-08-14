from __future__ import annotations
import os, sqlite3, json, datetime as dt
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local.db")

def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat()

class LocalDB:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    # ---------------- Schema ----------------
    def _ensure_schema(self):
        c = self._conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'todo',
            tag_id INTEGER,
            project_id INTEGER,
            due_date TEXT,
            start_ts TEXT,
            end_ts   TEXT,
            has_time INTEGER DEFAULT 0,
            parent_id INTEGER,
            series_id INTEGER,
            deleted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
        # Existing DB'lerde kolon ekle
        try: c.execute("ALTER TABLE tasks ADD COLUMN start_ts TEXT")
        except sqlite3.OperationalError: pass
        try: c.execute("ALTER TABLE tasks ADD COLUMN end_ts TEXT")
        except sqlite3.OperationalError: pass
        try: c.execute("ALTER TABLE tasks ADD COLUMN parent_id INTEGER")
        except sqlite3.OperationalError: pass
        try: c.execute("ALTER TABLE tasks ADD COLUMN tag_id INTEGER")
        except sqlite3.OperationalError: pass
        try: c.execute("ALTER TABLE tasks ADD COLUMN project_id INTEGER")
        except sqlite3.OperationalError: pass
        try: c.execute("ALTER TABLE tasks ADD COLUMN series_id INTEGER")
        except sqlite3.OperationalError: pass
        c.execute("""
        CREATE TABLE IF NOT EXISTS tags(
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            tag_id INTEGER
        )""")
        try: c.execute("ALTER TABLE projects ADD COLUMN tag_id INTEGER")
        except sqlite3.OperationalError: pass
        c.execute("""
        CREATE TABLE IF NOT EXISTS sync_queue(
            id INTEGER PRIMARY KEY,
            table_name TEXT NOT NULL,
            op TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        self._conn.commit()

    # ---------------- Queue helpers ----------------
    def _enqueue(self, table: str, op: str, payload: Dict[str, Any]):
        self._conn.execute(
            "INSERT INTO sync_queue(table_name, op, payload) VALUES (?,?,?)",
            (table, op, json.dumps(payload)),
        )
        self._conn.commit()

    def dequeue_all(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, table_name, op, payload FROM sync_queue ORDER BY id ASC"
        ).fetchall()
        self._conn.execute("DELETE FROM sync_queue")
        self._conn.commit()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "table": r["table_name"],
                "op": r["op"],
                "payload": json.loads(r["payload"]),
            })
        return out

    # ---------------- Replace pulls ----------------
    def replace_all(self, table: str, rows: List[Dict[str, Any]]):
        if table == "tasks":
            self._conn.execute("DELETE FROM tasks")
            for t in rows or []:
                self._conn.execute("""
                    INSERT INTO tasks(id, title, notes, status, tag_id, project_id, due_date, start_ts, end_ts, has_time, parent_id, series_id, deleted, created_at, updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    t.get("id"),
                    t.get("title",""),
                    t.get("notes",""),
                    t.get("status","todo"),
                    t.get("tag_id"),
                    t.get("project_id"),
                    t.get("due_date"),
                    t.get("start_ts"),
                    t.get("end_ts"),
                    int(t.get("has_time",0)),
                    t.get("parent_id"),
                    t.get("series_id"),
                    int(t.get("deleted",0)) if "deleted" in t else 0,
                    t.get("created_at") or _now_iso(),
                    t.get("updated_at") or _now_iso(),
                ))

        elif table == "tags":
            self._conn.execute("DELETE FROM tags")
            for g in rows or []:
                self._conn.execute("INSERT OR IGNORE INTO tags(id, name) VALUES(?,?)", (g.get("id"), g.get("name")))

        elif table == "projects":
            self._conn.execute("DELETE FROM projects")
            for p in rows or []:
                self._conn.execute(
                    "INSERT OR IGNORE INTO projects(id, name, tag_id) VALUES(?,?,?)",
                    (p.get("id"), p.get("name"), p.get("tag_id"))
                )

        self._conn.commit()

    # ---------------- Getters ----------------
    def get_tasks(self) -> List[Dict[str, Any]]:
        rs = self._conn.execute("""
            SELECT * FROM tasks
            WHERE deleted=0 AND (has_time IS NULL OR has_time=0)
            ORDER BY created_at DESC
        """).fetchall()
        return [dict(r) for r in rs]

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        rs = self._conn.execute(
            "SELECT * FROM tasks WHERE deleted=0 ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rs]

    def get_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        r = self._conn.execute("SELECT * FROM tasks WHERE id=?", (int(task_id),)).fetchone()
        return dict(r) if r else None

    def get_events(self) -> List[Dict[str, Any]]:
        rs = self._conn.execute("""
            SELECT *, id as task_id FROM tasks
            WHERE deleted=0 AND has_time=1 AND start_ts IS NOT NULL AND end_ts IS NOT NULL
            ORDER BY start_ts ASC
        """).fetchall()
        return [dict(r) for r in rs]

    def get_tags(self) -> List[Dict[str, Any]]:
        rs = self._conn.execute("SELECT * FROM tags").fetchall()
        return [dict(r) for r in rs]

    def get_projects(self) -> List[Dict[str, Any]]:
        rs = self._conn.execute("SELECT * FROM projects").fetchall()
        return [dict(r) for r in rs]

    # ---------------- TAGS ops ----------------
    def add_tag_local(self, name: str) -> int:
        cur = self._conn.execute("INSERT INTO tags(name) VALUES(?)", (name,))
        tag_id = int(cur.lastrowid)
        self._enqueue("tags", "insert", {"name": name})
        self._conn.commit()
        return tag_id

    def delete_tag_local(self, tag_id: int):
        self._conn.execute("DELETE FROM tags WHERE id=?", (int(tag_id),))
        self._enqueue("tags", "delete", {"id": int(tag_id)})
        self._conn.commit()

    # ---------------- PROJECTS ops ----------------
    def add_project_local(self, name: str, tag_id: Optional[int] = None) -> int:
        existing = self._conn.execute(
            "SELECT id FROM projects WHERE name=?", (name,)
        ).fetchone()
        if existing:
            return int(existing["id"])
        cur = self._conn.execute(
            "INSERT INTO projects(name, tag_id) VALUES(?,?)",
            (name, tag_id)
        )
        pid = int(cur.lastrowid)
        self._enqueue("projects", "insert", {"name": name, "tag_id": tag_id})
        self._conn.commit()
        return pid

    def delete_project_local(self, project_id: int):
        self._conn.execute("DELETE FROM projects WHERE id=?", (int(project_id),))
        self._enqueue("projects", "delete", {"id": int(project_id)})
        self._conn.commit()

    # ---------------- TASKS ops ----------------
    def upsert_task(self, task_id: Optional[int], title: str, notes: str,
                    due_date_iso: Optional[str], start_iso: Optional[str]=None,
                    end_iso: Optional[str]=None, parent_id: Optional[int]=None,
                    series_id: Optional[int]=None,
                    tag_id: Optional[int]=None, project_id: Optional[int]=None) -> int:
        has_time = int(bool(start_iso and end_iso))
        if task_id:
            self._conn.execute("""
                UPDATE tasks SET title=?, notes=?, due_date=?, start_ts=?, end_ts=?, has_time=?, parent_id=?, series_id=?, tag_id=?, project_id=?, updated_at=?
                WHERE id=?
            """, (title, notes, due_date_iso, start_iso, end_iso, has_time, parent_id, series_id, tag_id, project_id, _now_iso(), int(task_id)))
            self._enqueue("tasks", "upsert", {
                "id": int(task_id),
                "title": title, "notes": notes,
                "due_date": due_date_iso,
                "start_ts": start_iso, "end_ts": end_iso,
                "has_time": bool(has_time),
                "parent_id": parent_id,
                "series_id": series_id,
                "tag_id": tag_id,
                "project_id": project_id,
            })
            tid = int(task_id)
        else:
            cur = self._conn.execute("""
                INSERT INTO tasks(title, notes, due_date, start_ts, end_ts, has_time, parent_id, series_id, tag_id, project_id, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """, (title, notes, due_date_iso, start_iso, end_iso, has_time, parent_id, series_id, tag_id, project_id, _now_iso(), _now_iso()))
            tid = int(cur.lastrowid)
            self._enqueue("tasks", "upsert", {
                "id": tid,
                "title": title, "notes": notes,
                "due_date": due_date_iso,
                "start_ts": start_iso, "end_ts": end_iso,
                "has_time": bool(has_time),
                "parent_id": parent_id,
                "series_id": series_id,
                "tag_id": tag_id,
                "project_id": project_id,
            })
        self._conn.commit()
        return tid

    def delete_task(self, task_id: int):
        self._conn.execute("UPDATE tasks SET deleted=1, updated_at=? WHERE id=?",
                           (_now_iso(), int(task_id)))
        self._enqueue("tasks", "delete", {"id": int(task_id)})
        self._conn.commit()

    def skip_task(self, task_id: int):
        self._conn.execute("UPDATE tasks SET deleted=1, updated_at=? WHERE id=?",
                           (_now_iso(), int(task_id)))
        self._enqueue("tasks", "delete", {"id": int(task_id)})
        self._conn.commit()

    def delete_future(self, task_id: int):
        row = self._conn.execute(
            "SELECT series_id, start_ts, due_date FROM tasks WHERE id=?",
            (int(task_id),)
        ).fetchone()
        if not row:
            return
        series_id = row["series_id"]
        base_ts = row["start_ts"] or row["due_date"]
        if series_id is None:
            self.delete_task(task_id)
            return
        rows = self._conn.execute(
            """
            SELECT id FROM tasks
            WHERE series_id=? AND (
                (start_ts IS NOT NULL AND start_ts>=?) OR
                (start_ts IS NULL AND due_date>=?)
            )
            """,
            (series_id, base_ts, base_ts)
        ).fetchall()
        now = _now_iso()
        for r in rows:
            tid = int(r["id"])
            self._conn.execute(
                "UPDATE tasks SET deleted=1, updated_at=? WHERE id=?",
                (now, tid)
            )
            self._enqueue("tasks", "delete", {"id": tid})
        self._conn.commit()

    def set_task_status(self, task_id: int, status: str):
        # 🔒 title'a dokunma — sadece status
        self._conn.execute("UPDATE tasks SET status=?, updated_at=? WHERE id=?",
                           (status, _now_iso(), int(task_id)))
        self._enqueue("tasks", "upsert", {"id": int(task_id), "status": status})
        self._conn.commit()

    def set_task_times(self, task_id: int, start_iso: Optional[str], end_iso: Optional[str]):
        has_time = int(bool(start_iso and end_iso))
        self._conn.execute("""
            UPDATE tasks SET start_ts=?, end_ts=?, has_time=?, updated_at=?
            WHERE id=?
        """, (start_iso, end_iso, has_time, _now_iso(), int(task_id)))
        payload = {
            "id": int(task_id),
            "start_ts": start_iso,
            "end_ts": end_iso,
            "has_time": bool(has_time),
        }
        row = self._conn.execute(
            "SELECT tag_id, project_id FROM tasks WHERE id=?",
            (int(task_id),),
        ).fetchone()
        if row:
            if row["tag_id"] is not None:
                payload["tag_id"] = int(row["tag_id"])
            if row["project_id"] is not None:
                payload["project_id"] = int(row["project_id"])
        self._enqueue("tasks", "upsert", payload)
        self._conn.commit()

    def set_task_parent(self, task_id: int, parent_id: Optional[int]):
        self._conn.execute(
            "UPDATE tasks SET parent_id=?, updated_at=? WHERE id=?",
            (parent_id, _now_iso(), int(task_id)),
        )
        self._enqueue("tasks", "upsert", {"id": int(task_id), "parent_id": parent_id})
        self._conn.commit()

    def set_task_tag(self, task_id: int, tag_id: Optional[int]):
        self._conn.execute(
            "UPDATE tasks SET tag_id=?, updated_at=? WHERE id=?",
            (tag_id, _now_iso(), int(task_id)),
        )
        self._enqueue("tasks", "upsert", {"id": int(task_id), "tag_id": tag_id})
        self._conn.commit()

    def set_task_project(self, task_id: int, project_id: Optional[int]):
        self._conn.execute(
            "UPDATE tasks SET project_id=?, updated_at=? WHERE id=?",
            (project_id, _now_iso(), int(task_id)),
        )
        self._enqueue("tasks", "upsert", {"id": int(task_id), "project_id": project_id})
        self._conn.commit()
