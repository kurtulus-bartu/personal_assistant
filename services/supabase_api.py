# services/supabase_api.py
# Supabase PostgREST istemcisi (requests tabanlı)
# Ortam değişkenleri:
#   SUPABASE_URL (örn: https://xxxx.supabase.co)
#   SUPABASE_ANON_KEY (anon veya service key)

from __future__ import annotations
import os, requests, typing as t

SUPABASE_URL = "https://mfxykkgmsfqipmqpwnoj.supabase.co"         # <- senin URL
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1meHlra2dtc2ZxaXBtcXB3bm9qIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQ5NDgwNDIsImV4cCI6MjA3MDUyNDA0Mn0.2bbS-4khj1oFkEz-GsICBS15Nl1d-HVldxvE-nsYbLE"                       # <- senin anon key

def _headers(prefer: str | None = None) -> dict[str, str]:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h

def _ensure():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY tanımlı değil")

def _zfix_ts(s: str | None) -> str | None:
    """
    timestamptz stringine TZ yoksa 'Z' ekler.
    'YYYY-MM-DDTHH:MM:SS' gibi naive ISO'larda yardımcı olur.
    """
    if not s:
        return s
    if "Z" in s or "+" in s:   # zaten TZ içeriyor
        return s
    # en az 'YYYY-MM-DDTHH:MM:SS' uzunluğunda mı?
    if len(s) >= 19 and s[10] == "T":
        return s + "Z"
    return s

# ---------------- TAGS ----------------

def fetch_tags() -> list[dict]:
    _ensure()
    url = f"{SUPABASE_URL}/rest/v1/tags?select=*&order=updated_at.desc"
    r = requests.get(url, headers=_headers())
    r.raise_for_status()
    return r.json()

def upsert_tag(name: str, tag_id: int | None = None) -> dict:
    _ensure()
    url = f"{SUPABASE_URL}/rest/v1/tags?on_conflict=id"
    payload = {"name": name}
    if tag_id is not None:
        payload["id"] = int(tag_id)
    r = requests.post(
        url,
        headers=_headers("return=representation,resolution=merge-duplicates"),
        json=payload,
    )
    r.raise_for_status()
    out = r.json()
    return out[0] if isinstance(out, list) and out else out

def delete_tag(tag_id: int) -> bool:
    _ensure()
    url = f"{SUPABASE_URL}/rest/v1/tags?id=eq.{int(tag_id)}"
    r = requests.delete(url, headers=_headers())
    if r.status_code in (200, 204):
        return True
    r.raise_for_status()
    return True

# ---------------- TASKS ----------------

TASK_FIELDS = "id,title,notes,status,tag_id,has_time,due_date,updated_at"

def fetch_tasks() -> list[dict]:
    _ensure()
    url = f"{SUPABASE_URL}/rest/v1/tasks?select={TASK_FIELDS}&order=updated_at.desc"
    r = requests.get(url, headers=_headers())
    r.raise_for_status()
    return r.json()

def upsert_task(row: dict) -> dict:
    """
    Beklenen: id? | title | notes | status | tag_id | has_time | due_date
    due_date: 'YYYY-MM-DD' veya ISO ise sadece tarih kısmı gönderilir.
    """
    _ensure()
    url = f"{SUPABASE_URL}/rest/v1/tasks?on_conflict=id"
    payload: dict[str, t.Any] = {}

    if row.get("id"):
        payload["id"] = int(row["id"])

    if "title" in row:   payload["title"]   = row["title"]
    if "notes" in row:   payload["notes"]   = row["notes"]
    if "status" in row:  payload["status"]  = row["status"]
    if "tag_id" in row and row["tag_id"] is not None:
        payload["tag_id"] = int(row["tag_id"])
    if "has_time" in row:
        payload["has_time"] = bool(row["has_time"])
    if "due_date" in row and row["due_date"]:
        d = str(row["due_date"])
        payload["due_date"] = d.split("T", 1)[0]  # sadece tarih

    r = requests.post(
        url,
        headers=_headers("return=representation,resolution=merge-duplicates"),
        json=payload,
    )
    r.raise_for_status()
    out = r.json()
    return out[0] if isinstance(out, list) and out else out

def delete_task(task_id: int) -> bool:
    _ensure()
    url = f"{SUPABASE_URL}/rest/v1/tasks?id=eq.{int(task_id)}"
    r = requests.delete(url, headers=_headers())
    if r.status_code in (200, 204):
        return True
    r.raise_for_status()
    return True

# ---------------- EVENTS ----------------

EVENT_FIELDS = "id,task_id,title,notes,rrule,starts_at,ends_at,updated_at"

def fetch_events() -> list[dict]:
    _ensure()
    url = f"{SUPABASE_URL}/rest/v1/events?select={EVENT_FIELDS}&order=starts_at.asc"
    r = requests.get(url, headers=_headers())
    r.raise_for_status()
    return r.json()

def upsert_event(row: dict) -> dict:
    """
    Beklenen: id? | task_id | title? | notes? | rrule? | starts_at/start_ts | ends_at/end_ts
    """
    _ensure()
    url = f"{SUPABASE_URL}/rest/v1/events?on_conflict=id"
    payload: dict[str, t.Any] = {}

    if row.get("id"):
        payload["id"] = int(row["id"])

    # start_ts / starts_at ikisini de destekle
    starts = row.get("starts_at") or row.get("start_ts")
    ends   = row.get("ends_at")   or row.get("end_ts")

    if "task_id" in row: payload["task_id"] = int(row["task_id"])
    if "title" in row:   payload["title"]   = row["title"]
    if "notes" in row:   payload["notes"]   = row["notes"]
    if "rrule" in row:   payload["rrule"]   = row["rrule"]
    if starts:           payload["starts_at"] = _zfix_ts(str(starts))
    if ends:             payload["ends_at"]   = _zfix_ts(str(ends))

    r = requests.post(
        url,
        headers=_headers("return=representation,resolution=merge-duplicates"),
        json=payload,
    )
    r.raise_for_status()
    out = r.json()
    return out[0] if isinstance(out, list) and out else out

def delete_event(event_id: int) -> bool:
    _ensure()
    url = f"{SUPABASE_URL}/rest/v1/events?id=eq.{int(event_id)}"
    r = requests.delete(url, headers=_headers())
    if r.status_code in (200, 204):
        return True
    r.raise_for_status()
    return True
