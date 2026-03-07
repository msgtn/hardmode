import sqlite3
from contextlib import contextmanager

DB_PATH = "data.db"


QUESTIONS = [
    "Are you missing anyone right now? Do you think they are missing you too?",
    "What's the best compliment a stranger has ever given you?",
    "How are you, really?",
    "What lesson should you have learned by now?",
    "What made you happiest as a child?",
]


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
                uuid TEXT NOT NULL UNIQUE,
                question_id INTEGER NOT NULL REFERENCES questions(id),
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.executemany(
            "INSERT OR IGNORE INTO questions (text) VALUES (?)",
            [(q,) for q in QUESTIONS],
        )


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_random_question() -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM questions ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def add_answer(question_id: int, text: str, uuid: str) -> dict:
    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO answers (uuid, question_id, text) VALUES (?, ?, ?)",
            (uuid, question_id, text),
        )
        row = conn.execute(
            "SELECT * FROM answers WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)


def get_answer_by_uuid(uuid: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM answers WHERE uuid = ?", (uuid,)
        ).fetchone()
        return dict(row) if row else None


def get_answers_excluding(question_id: int, exclude_uuid: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM answers WHERE question_id = ? AND uuid != ? ORDER BY created_at ASC",
            (question_id, exclude_uuid),
        ).fetchall()
        return [dict(r) for r in rows]


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
