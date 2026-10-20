"""All SQLite work. Winners are saved here so they survive refresh and restart."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import pandas as pd
from config import DB_PATH, DEFAULT_ROUNDS, DEFAULT_WINNERS_PER_ROUND

def _connect(path=None):
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn(path=None):
    conn = _connect(path)
    try:
        yield conn
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS draw_sessions (
    session_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    initial_count INTEGER NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active'   -- active | archived
);
CREATE TABLE IF NOT EXISTS employees (
    session_id  INTEGER NOT NULL REFERENCES draw_sessions(session_id),
    employee_id TEXT NOT NULL,
    name        TEXT NOT NULL,
    designation TEXT NOT NULL,
    department  TEXT NOT NULL,
    photo_path  TEXT DEFAULT '',
    PRIMARY KEY (session_id, employee_id)
);
CREATE TABLE IF NOT EXISTS draw_rounds (
    round_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES draw_sessions(session_id),
    round_number INTEGER NOT NULL,
    completed_at TEXT NOT NULL,
    UNIQUE (session_id, round_number)
);
CREATE TABLE IF NOT EXISTS winners (
    winner_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL,
    round_id    INTEGER NOT NULL REFERENCES draw_rounds(round_id),
    employee_id TEXT NOT NULL,
    UNIQUE (session_id, employee_id),            -- nobody can win twice
    FOREIGN KEY (session_id, employee_id) REFERENCES employees(session_id, employee_id)
);
"""


def init_db(path=None):
    with get_conn(path) as conn:
        conn.executescript(SCHEMA)
        # Add the two settings columns (also upgrades an older database safely)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(draw_sessions)")]
        if "total_rounds" not in cols:
            conn.execute("ALTER TABLE draw_sessions ADD COLUMN total_rounds INTEGER NOT NULL DEFAULT 5")
        if "winners_per_round" not in cols:
            conn.execute("ALTER TABLE draw_sessions ADD COLUMN winners_per_round INTEGER NOT NULL DEFAULT 2")
        conn.commit()


def create_session(df: pd.DataFrame, path=None,
                   total_rounds: int = DEFAULT_ROUNDS,
                   winners_per_round: int = DEFAULT_WINNERS_PER_ROUND) -> int:
    """Start a new draw from a validated employee table. Old session is archived."""
    with get_conn(path) as conn:
        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE draw_sessions SET status='archived' WHERE status='active'")
            cur = conn.execute(
                "INSERT INTO draw_sessions (created_at, initial_count, total_rounds, winners_per_round) "
                "VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(timespec="seconds"), len(df), total_rounds, winners_per_round))
            sid = cur.lastrowid
            conn.executemany(
                "INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?)",
                [(sid, r.Employee_ID, r.Name, r.Designation, r.Department, r.Photo)
                 for r in df.itertuples(index=False)])
            conn.commit()
            return sid
        except Exception:
            conn.rollback()
            raise


def get_active_session(path=None):
    with get_conn(path) as conn:
        row = conn.execute("SELECT * FROM draw_sessions WHERE status='active' "
                           "ORDER BY session_id DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def get_employees(session_id: int, path=None) -> pd.DataFrame:
    with get_conn(path) as conn:
        return pd.read_sql_query(
            "SELECT employee_id, name, designation, department, photo_path "
            "FROM employees WHERE session_id = ? ORDER BY employee_id",
            conn, params=(session_id,))


def get_eligible_ids(session_id: int, path=None) -> list:
    with get_conn(path) as conn:
        rows = conn.execute(
            "SELECT employee_id FROM employees WHERE session_id = ? AND employee_id NOT IN "
            "(SELECT employee_id FROM winners WHERE session_id = ?)",
            (session_id, session_id)).fetchall()
        return [r["employee_id"] for r in rows]


def rounds_completed(session_id: int, path=None) -> int:
    with get_conn(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM draw_rounds WHERE session_id = ?",
                            (session_id,)).fetchone()[0]


def save_round(session_id: int, winner_ids: list, path=None) -> int:
    """Save a round ATOMICALLY: all winners + the round, or nothing at all."""
    with get_conn(path) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")   # lock: stops double-clicks saving twice
            s = conn.execute("SELECT total_rounds, winners_per_round FROM draw_sessions "
                             "WHERE session_id = ?", (session_id,)).fetchone()
            if s is None:
                raise ValueError("Draw session not found.")
            per_round = s["winners_per_round"]
            if len(winner_ids) != per_round or len(set(winner_ids)) != per_round:
                raise ValueError(f"A round needs exactly {per_round} different winners.")
            done = conn.execute("SELECT COUNT(*) FROM draw_rounds WHERE session_id = ?",
                                (session_id,)).fetchone()[0]
            if done >= s["total_rounds"]:
                raise ValueError("All rounds are already completed.")
            round_no = done + 1
            cur = conn.execute(
                "INSERT INTO draw_rounds (session_id, round_number, completed_at) VALUES (?, ?, ?)",
                (session_id, round_no, datetime.now().isoformat(timespec="seconds")))
            round_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO winners (session_id, round_id, employee_id) VALUES (?, ?, ?)",
                [(session_id, round_id, e) for e in winner_ids])
            conn.commit()
            return round_no
        except Exception:
            conn.rollback()
            raise


def update_settings(session_id: int, total_rounds: int, winners_per_round: int, path=None):
    """Change rounds / winners-per-round. Only allowed before the first round is drawn."""
    with get_conn(path) as conn:
        done = conn.execute("SELECT COUNT(*) FROM draw_rounds WHERE session_id = ?",
                            (session_id,)).fetchone()[0]
        if done > 0:
            raise ValueError("Settings are locked once a round has been drawn. Reset the draw first.")
        conn.execute("UPDATE draw_sessions SET total_rounds = ?, winners_per_round = ? "
                     "WHERE session_id = ?", (total_rounds, winners_per_round, session_id))
        conn.commit()


def get_winners(session_id: int, path=None) -> pd.DataFrame:
    with get_conn(path) as conn:
        return pd.read_sql_query(
            "SELECT r.round_number AS Round, e.employee_id AS Employee_ID, e.name AS Name, "
            "e.designation AS Designation, e.department AS Department, "
            "e.photo_path AS Photo, r.completed_at AS Completed_At "
            "FROM winners w "
            "JOIN draw_rounds r ON r.round_id = w.round_id "
            "JOIN employees e ON e.session_id = w.session_id AND e.employee_id = w.employee_id "
            "WHERE w.session_id = ? ORDER BY r.round_number, w.winner_id",
            conn, params=(session_id,))


def reset_session(session_id: int, path=None):
    """Erase winners/rounds of this session (keeps the employee list)."""
    with get_conn(path) as conn:
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM winners WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM draw_rounds WHERE session_id = ?", (session_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
