import csv
import sqlite3
import uuid

DB_PATH = "data.db"
CSV_PATH = "responses.csv"

QUESTION_COLUMNS = [
    "Are you missing anyone right now? Do you think they are missing you too?",
    "What's the best compliment a stranger has ever given you?",
    "How are you, really?",
    "What lesson should you have learned by now?",
    "What made you happiest as a child?",
]

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Build question_text -> id map
question_ids = {}
for row in conn.execute("SELECT id, text FROM questions").fetchall():
    question_ids[row["text"]] = row["id"]

inserted = 0
skipped = 0

with open(CSV_PATH, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        for col in QUESTION_COLUMNS:
            text = row.get(col, "").strip()
            if not text:
                continue
            qid = question_ids.get(col)
            if qid is None:
                print(f"Warning: question not found in DB: {col}")
                continue
            try:
                conn.execute(
                    "INSERT INTO answers (uuid, question_id, text) VALUES (?, ?, ?)",
                    (str(uuid.uuid4()), qid, text),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1

conn.commit()
conn.close()
print(f"Done. Inserted {inserted} answers, skipped {skipped} duplicates.")
