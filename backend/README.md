# Backend

## Setup

```bash
uv sync
```

## Run

```bash
uv run python app.py
```

Or with the Flask CLI:

```bash
uv run flask --app app run --debug
```

## API Endpoints

Base URL: `http://localhost:5000`

---

### `GET /health`

Health check.

**Response**
```json
{ "status": "ok" }
```

---

### `GET /questions`

Returns all questions.

**Response** — array of question objects:
```json
[
  {
    "id": 1,
    "text": "How are you, really?",
    "created_at": "2024-01-01 00:00:00"
  }
]
```

---

### `GET /questions/random`

Returns a single random question.

**Response**
```json
{
  "id": 3,
  "text": "What made you happiest as a child?",
  "created_at": "2024-01-01 00:00:00"
}
```

**Errors**
- `404` — no questions in the database

---

### `GET /questions/:question_id/answers`

Returns all answers for a question, ordered by creation time.

**Path params**
- `question_id` — integer

**Response** — array of answer objects:
```json
[
  {
    "id": 1,
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "question_id": 3,
    "text": "Playing outside with my dog.",
    "created_at": "2024-01-01 00:00:00"
  }
]
```

---

### `POST /questions/:question_id/answers`

Submits a new answer for a question.

**Path params**
- `question_id` — integer

**Request body**
```json
{
  "answer": "Playing outside with my dog.",
  "uuid": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response** `201` — the created answer object:
```json
{
  "id": 1,
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "question_id": 3,
  "text": "Playing outside with my dog.",
  "created_at": "2024-01-01 00:00:00"
}
```

---

### `GET /questions/:question_id/answers/:uuid/similar`

Finds the most semantically similar answer to the one identified by `uuid`, among all other answers for the same question.

**Path params**
- `question_id` — integer
- `uuid` — UUID string of the reference answer

**Response**
```json
{
  "answer": {
    "id": 2,
    "uuid": "661f9511-f3ac-52e5-b827-557766551111",
    "question_id": 3,
    "text": "Running around in the backyard.",
    "created_at": "2024-01-01 00:00:00"
  },
  "score": 0.87
}
```

**Errors**
- `404` — reference answer not found, or no other answers exist to compare

---

## WebSocket Events

Connects via Socket.IO at `ws://localhost:5000`.

| Event | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `connect` | server | — | Fired when a client connects |
| `disconnect` | server | — | Fired when a client disconnects |
| `message` | client → server | any | Broadcasts the payload back to the sender |
