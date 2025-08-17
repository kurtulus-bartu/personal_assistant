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
        # Pomodoro session table migration
        self.migrate_add_pomodoro_sessions()

    # ---------------- Schema ----------------
    def _ensure_schema(self):
        c = self._conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'todo',
            due_date TEXT,
            has_time INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY,
            task_id INTEGER,
            title TEXT,
            notes TEXT DEFAULT '',
            start_ts TEXT NOT NULL,
            end_ts   TEXT NOT NULL,
            rrule TEXT,
            deleted INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS tags(
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS sync_queue(
            id INTEGER PRIMARY KEY,
            table_name TEXT NOT NULL,
            op TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        self._conn.commit()

    def migrate_add_pomodoro_sessions(self):
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                ended_at   TEXT NOT NULL,
                planned_secs INTEGER NOT NULL,
                actual_secs  INTEGER NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );
            """
        )
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
                    INSERT INTO tasks(id, title, notes, status, due_date, has_time, deleted, created_at, updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?)
                """, (
                    t.get("id"),
                    t.get("title",""),
                    t.get("notes",""),
                    t.get("status","todo"),
                    t.get("due_date"),
                    int(t.get("has_time",0)),
                    int(t.get("deleted",0)) if "deleted" in t else 0,
                    t.get("created_at") or _now_iso(),
                    t.get("updated_at") or _now_iso(),
                ))

        elif table == "events":
            self._conn.execute("DELETE FROM events")
            for e in rows or []:
                start_ts = e.get("start_ts") or e.get("starts_at")
                end_ts   = e.get("end_ts")   or e.get("ends_at")
                self._conn.execute("""
                    INSERT INTO events(id, task_id, title, notes, start_ts, end_ts, rrule, deleted, updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?)
                """, (
                    e.get("id"),
                    e.get("task_id"),
                    e.get("title"),
                    e.get("notes",""),
                    start_ts,
                    end_ts,
                    e.get("rrule"),
                    int(e.get("deleted",0)) if "deleted" in e else 0,
                    e.get("updated_at") or _now_iso(),
                ))

        elif table == "tags":
            self._conn.execute("DELETE FROM tags")
            for g in rows or []:
                self._conn.execute("INSERT OR IGNORE INTO tags(id, name) VALUES(?,?)", (g.get("id"), g.get("name")))

        self._conn.commit()

    # ---------------- Getters ----------------
    def get_tasks(self) -> List[Dict[str, Any]]:
        rs = self._conn.execute("""
            SELECT * FROM tasks
            WHERE deleted=0 AND (has_time IS NULL OR has_time=0)
            ORDER BY created_at DESC
        """).fetchall()
        return [dict(r) for r in rs]

    def get_task_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        r = self._conn.execute("SELECT * FROM tasks WHERE id=?", (int(task_id),)).fetchone()
        return dict(r) if r else None

    def get_events(self) -> List[Dict[str, Any]]:
        rs = self._conn.execute("""
            SELECT * FROM events
            WHERE deleted=0
            ORDER BY start_ts ASC
        """).fetchall()
        return [dict(r) for r in rs]

    def get_event_by_id(self, ev_id: int) -> Optional[Dict[str, Any]]:
        r = self._conn.execute("SELECT * FROM events WHERE id=?", (int(ev_id),)).fetchone()
        return dict(r) if r else None

    def get_tags(self) -> List[Dict[str, Any]]:
        rs = self._conn.execute("SELECT * FROM tags").fetchall()
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

    # ---------------- TASKS ops ----------------
    def upsert_task(self, task_id: Optional[int], title: str, notes: str,
                    due_date_iso: Optional[str], has_time: bool=False) -> int:
        if task_id:
            self._conn.execute("""
                UPDATE tasks SET title=?, notes=?, due_date=?, has_time=?, updated_at=?
                WHERE id=?
            """, (title, notes, due_date_iso, int(has_time), _now_iso(), int(task_id)))
            self._enqueue("tasks", "upsert", {
                "id": int(task_id),
                "title": title, "notes": notes,
                "due_date": due_date_iso, "has_time": bool(has_time)
            })
            tid = int(task_id)
        else:
            cur = self._conn.execute("""
                INSERT INTO tasks(title, notes, due_date, has_time, created_at, updated_at)
                VALUES(?,?,?,?,?,?)
            """, (title, notes, due_date_iso, int(has_time), _now_iso(), _now_iso()))
            tid = int(cur.lastrowid)
            self._enqueue("tasks", "upsert", {
                "id": tid,
                "title": title, "notes": notes,
                "due_date": due_date_iso, "has_time": bool(has_time)
            })
        self._conn.commit()
        return tid

    def delete_task(self, task_id: int):
        self._conn.execute("UPDATE tasks SET deleted=1, updated_at=? WHERE id=?",
                           (_now_iso(), int(task_id)))
        self._enqueue("tasks", "delete", {"id": int(task_id)})
        self._conn.commit()

    def set_task_status(self, task_id: int, status: str):
        # 🔒 title'a dokunma — sadece status
        self._conn.execute("UPDATE tasks SET status=?, updated_at=? WHERE id=?",
                           (status, _now_iso(), int(task_id)))
        self._enqueue("tasks", "upsert", {"id": int(task_id), "status": status})
        self._conn.commit()

    def mark_task_has_time(self, task_id: int, has_time: bool):
        self._conn.execute("UPDATE tasks SET has_time=?, updated_at=? WHERE id=?",
                           (int(has_time), _now_iso(), int(task_id)))
        self._enqueue("tasks", "upsert", {"id": int(task_id), "has_time": bool(has_time)})
        self._conn.commit()

    # ---------------- Events ops ----------------
    def create_event(self, task_id: int, start_iso: str, end_iso: str,
                     title: Optional[str]=None, notes: Optional[str]=None,
                     rrule: Optional[str]=None) -> int:
        cur = self._conn.execute("""
            INSERT INTO events(task_id, title, notes, start_ts, end_ts, rrule, updated_at)
            VALUES(?,?,?,?,?,?,?)
        """, (int(task_id), title, notes or "", start_iso, end_iso, rrule, _now_iso()))
        eid = int(cur.lastrowid)
        self._enqueue("events", "upsert", {
            "id": eid, "task_id": int(task_id), "title": title,
            "notes": notes or "", "start_ts": start_iso, "end_ts": end_iso, "rrule": rrule
        })
        self._conn.commit()
        return eid

    def update_event(self, event_id: int, start_iso: str, end_iso: str,
                     title: Optional[str]=None, notes: Optional[str]=None,
                     rrule: Optional[str]=None):
        self._conn.execute("""
            UPDATE events SET start_ts=?, end_ts=?, title=?, notes=?, rrule=?, updated_at=?
            WHERE id=?
        """, (start_iso, end_iso, title, notes or "", rrule, _now_iso(), int(event_id)))
        self._enqueue("events", "upsert", {
            "id": int(event_id), "start_ts": start_iso, "end_ts": end_iso,
            "title": title, "notes": notes or "", "rrule": rrule
        })
        self._conn.commit()

    def delete_event(self, event_id: int):
        self._conn.execute("UPDATE events SET deleted=1, updated_at=? WHERE id=?",
                           (_now_iso(), int(event_id)))
        self._enqueue("events", "delete", {"id": int(event_id)})
        self._conn.commit()

    # ---------------- Pomodoro sessions ----------------
    def insert_pomodoro_session(
        self,
        task_id: int,
        started_at_iso: str,
        ended_at_iso: str,
        planned_secs: int,
        actual_secs: int,
        note: str,
    ) -> int:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO pomodoro_sessions (task_id, started_at, ended_at, planned_secs, actual_secs, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, started_at_iso, ended_at_iso, planned_secs, actual_secs, note),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def list_pomodoro_sessions_for_task(self, task_id: int) -> list[dict]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT id, task_id, started_at, ended_at, planned_secs, actual_secs, note, created_at
            FROM pomodoro_sessions
            WHERE task_id = ?
            ORDER BY datetime(ended_at) DESC
            """,
            (task_id,),
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "id": r[0],
                    "task_id": r[1],
                    "started_at": r[2],
                    "ended_at": r[3],
                    "planned_secs": r[4],
                    "actual_secs": r[5],
                    "note": r[6],
                    "created_at": r[7],
                }
            )
        return out
