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


@app.route("/questions/random", methods=["GET"])
def random_question():
    question = db.get_random_question()
    if not question:
        return jsonify({"error": "No questions in database"}), 404
    return jsonify(question)


@app.route("/questions", methods=["GET"])
def get_questions():
    return jsonify(db.get_questions())


@app.route("/questions/<int:question_id>/answers", methods=["GET"])
def get_answers(question_id):
    return jsonify(db.get_answers(question_id))


@app.route("/questions/<int:question_id>/answers", methods=["POST"])
def add_answer(question_id):
    body = request.get_json()
    answer = db.add_answer(question_id, body["answer"], body["uuid"])
    return jsonify(answer), 201


@app.route("/questions/<int:question_id>/answers/<uuid>/similar", methods=["GET"])
def get_similar(question_id, uuid):
    target = db.get_answer_by_uuid(uuid)
    if not target:
        return jsonify({"error": "Answer not found"}), 404

    candidates = db.get_answers_excluding(question_id, uuid)
    if not candidates:
        return jsonify({"error": "No other answers to compare"}), 404

    best_idx, score = similarity.most_similar(target["text"], [a["text"] for a in candidates])
    return jsonify({"answer": candidates[best_idx], "score": score})


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
    socketio.run(app, host="0.0.0.0", debug=True, allow_unsafe_werkzeug=True)
