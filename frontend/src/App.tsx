import { useState } from "react";
import "./App.css";

interface Question {
  id: number;
  text: string;
  created_at: string;
}

interface Answer {
  id: number;
  uuid: string;
  question_id: number;
  text: string;
  created_at: string;
}

function App() {
  const [output, setOutput] = useState<string[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [answerUuid, setAnswerUuid] = useState("");
  const [storedAnswers, setStoredAnswers] = useState<Answer[]>([]);
  const [selectedUuid, setSelectedUuid] = useState("");

  const log = (msg: string) => setOutput((prev) => [...prev, msg]);

  const getRandomQuestion = async () => {
    const res = await fetch("/api/questions/random");
    const data = await res.json();
    if (!res.ok) { log(`GET /questions/random → error: ${data.error}`); return; }
    setCurrentQuestion(data);
    setStoredAnswers([]);
    setSelectedUuid("");
    log(`GET /questions/random → [${data.id}] "${data.text}"`);
  };

  const postAnswer = async () => {
    if (!currentQuestion) { log("Get a question first"); return; }
    if (!answerText.trim()) { log("Enter answer text"); return; }
    const uuid = answerUuid.trim() || crypto.randomUUID();
    const res = await fetch(`/api/questions/${currentQuestion.id}/answers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer: answerText, uuid }),
    });
    const data: Answer = await res.json();
    setStoredAnswers((prev) => [...prev, data]);
    log(`POST /questions/${currentQuestion.id}/answers → uuid=${data.uuid} "${data.text}"`);
    setAnswerText("");
    setAnswerUuid("");
  };

  const getSimilar = async () => {
    if (!currentQuestion) { log("Get a question first"); return; }
    if (!selectedUuid) { log("Select an answer to compare"); return; }
    const res = await fetch(`/api/questions/${currentQuestion.id}/answers/${selectedUuid}/similar`);
    const data = await res.json();
    if (!res.ok) { log(`GET .../similar → error: ${data.error}`); return; }
    log(`GET .../similar for uuid=${selectedUuid} → "${data.answer.text}" (score: ${data.score.toFixed(3)})`);
  };

  return (
    <div style={{ padding: 24, fontFamily: "monospace", maxWidth: 700 }}>
      <h2>1. Get a random question</h2>
      <button onClick={getRandomQuestion}>GET /questions/random</button>
      {currentQuestion && (
        <p style={{ marginTop: 8 }}>
          <strong>[{currentQuestion.id}]</strong> {currentQuestion.text}
        </p>
      )}

      <h2>2. Submit an answer</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: 400 }}>
        <input
          value={answerText}
          onChange={(e) => setAnswerText(e.target.value)}
          placeholder="Answer text"
          style={{ padding: "4px 8px", fontFamily: "monospace" }}
        />
        <input
          value={answerUuid}
          onChange={(e) => setAnswerUuid(e.target.value)}
          placeholder="UUID (leave blank to auto-generate)"
          style={{ padding: "4px 8px", fontFamily: "monospace" }}
        />
        <button onClick={postAnswer} style={{ alignSelf: "flex-start" }}>
          POST /questions/:id/answers
        </button>
      </div>

      {storedAnswers.length > 0 && (
        <>
          <h2>3. Find most similar answer</h2>
          <p style={{ margin: "4px 0 8px" }}>Select the answer to compare against:</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 8 }}>
            {storedAnswers.map((a) => (
              <label key={a.uuid} style={{ cursor: "pointer" }}>
                <input
                  type="radio"
                  name="uuid"
                  value={a.uuid}
                  checked={selectedUuid === a.uuid}
                  onChange={() => setSelectedUuid(a.uuid)}
                  style={{ marginRight: 8 }}
                />
                "{a.text}" <span style={{ color: "#888" }}>({a.uuid.slice(0, 8)}...)</span>
              </label>
            ))}
          </div>
          <button onClick={getSimilar}>GET /questions/:id/answers/:uuid/similar</button>
        </>
      )}

      <h2>Log</h2>
      <button onClick={() => setOutput([])} style={{ marginBottom: 8 }}>Clear</button>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {output.map((line, i) => (
          <div key={i} style={{ background: "#111", color: "#0f0", padding: "4px 8px", borderRadius: 4 }}>
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
