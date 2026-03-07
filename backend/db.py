import sqlite3
from contextlib import contextmanager

DB_PATH = "data.db"


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL REFERENCES questions(id),
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_answer(question_text: str, answer_text: str) -> dict:
    """Insert question if it doesn't exist, then add an answer. Returns the answer row."""
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO questions (text) VALUES (?)", (question_text,)
        )
        row = conn.execute(
            "SELECT id FROM questions WHERE text = ?", (question_text,)
        ).fetchone()
        question_id = row["id"]
        cursor = conn.execute(
            "INSERT INTO answers (question_id, text) VALUES (?, ?)",
            (question_id, answer_text),
        )
        answer = conn.execute(
            "SELECT * FROM answers WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(answer)


def get_questions() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM questions ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_answers(question_id: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM answers WHERE question_id = ? ORDER BY created_at ASC",
            (question_id,),
        ).fetchall()
        return [dict(r) for r in rows]
