from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import db
import similarity

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
db.init_db()


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/questions", methods=["GET"])
def get_questions():
    return jsonify(db.get_questions())


@app.route("/questions/<int:question_id>/answers", methods=["GET"])
def get_answers(question_id):
    return jsonify(db.get_answers(question_id))


@app.route("/answers", methods=["POST"])
def add_answer():
    body = request.get_json()
    answer = db.add_answer(body["question"], body["answer"])
    return jsonify(answer), 201


@app.route("/questions/<int:question_id>/similar", methods=["POST"])
def get_similar(question_id):
    body = request.get_json()
    query = body["answer"]

    answers = db.get_answers(question_id)
    candidates = [a["text"] for a in answers]

    if not candidates:
        return jsonify({"error": "No answers for this question"}), 404

    best_idx, score = similarity.most_similar(query, candidates)
    return jsonify({"answer": answers[best_idx], "score": score})


@socketio.on("connect")
def on_connect():
    print("Client connected")


@socketio.on("disconnect")
def on_disconnect():
    print("Client disconnected")


@socketio.on("message")
def on_message(data):
    emit("message", data)


if __name__ == "__main__":
    socketio.run(app, debug=True)
