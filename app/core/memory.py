import sqlite3
import threading
from typing import Any, Dict, List, Optional

DB_PATH = "app_data.db"
_lock = threading.Lock()


def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                user_id TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (user_id, key)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                kind TEXT,
                payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()


def set_pref(user_id: str, key: str, value: str) -> None:
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO preferences (user_id, key, value) VALUES (?, ?, ?)",
            (user_id, key, value),
        )
        conn.commit()
        conn.close()


def get_pref(user_id: str, key: str) -> Optional[str]:
    with _lock:
        conn = _get_conn()
        cur = conn.execute("SELECT value FROM preferences WHERE user_id=? AND key=?", (user_id, key))
        row = cur.fetchone()
        conn.close()
        return row["value"] if row else None


def save_booking(user_id: str, kind: str, payload: str) -> int:
    with _lock:
        conn = _get_conn()
        cur = conn.execute("INSERT INTO bookings (user_id, kind, payload) VALUES (?, ?, ?)", (user_id, kind, payload))
        conn.commit()
        last = cur.lastrowid
        conn.close()
        return last


def list_bookings(user_id: str) -> List[Dict[str, Any]]:
    with _lock:
        conn = _get_conn()
        cur = conn.execute("SELECT id, kind, payload, created_at FROM bookings WHERE user_id=? ORDER BY created_at DESC", (user_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
