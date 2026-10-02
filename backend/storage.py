"""Small SQLite repository kept separate from HTTP route definitions."""
from __future__ import annotations

import os
import sqlite3
import uuid
from pathlib import Path

DB_PATH = Path(os.environ.get("DATABASE_PATH", Path(__file__).with_name("graphmind.db")))

def _connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn=sqlite3.connect(DB_PATH); conn.row_factory=sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, name TEXT NOT NULL, language TEXT NOT NULL, code TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    return conn

def create_session(name: str, language: str, code: str) -> dict:
    session={"id":str(uuid.uuid4()),"name":name,"language":language,"code":code}
    conn=_connection()
    try: conn.execute("INSERT INTO sessions(id,name,language,code) VALUES(:id,:name,:language,:code)",session); conn.commit()
    finally: conn.close()
    return get_session(session["id"])
def get_session(session_id: str) -> dict | None:
    conn=_connection()
    try:
        row=conn.execute("SELECT id,name,language,code,created_at FROM sessions WHERE id=?",(session_id,)).fetchone()
    finally: conn.close()
    return dict(row) if row else None
def list_sessions() -> list[dict]:
    conn=_connection()
    try: rows=conn.execute("SELECT id,name,language,code,created_at FROM sessions ORDER BY created_at DESC").fetchall()
    finally: conn.close()
    return [dict(row) for row in rows]
def delete_session(session_id: str) -> bool:
    conn=_connection()
    try: deleted=conn.execute("DELETE FROM sessions WHERE id=?",(session_id,)).rowcount > 0; conn.commit(); return deleted
    finally: conn.close()
