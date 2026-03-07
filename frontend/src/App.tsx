import { useState } from "react";
import "./App.css";

function App() {
  const [output, setOutput] = useState<string[]>([]);

  const log = (msg: string) => setOutput((prev) => [...prev, msg]);

  const testHealth = async () => {
    const res = await fetch("/api/health");
    const data = await res.json();
    log(`GET /health → ${JSON.stringify(data)}`);
  };

  const testAddAnswer = async () => {
    const res = await fetch("/api/answers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "What is the capital of France?", answer: "Paris" }),
    });
    const data = await res.json();
    log(`POST /answers → ${JSON.stringify(data)}`);
  };

  const testGetQuestions = async () => {
    const res = await fetch("/api/questions");
    const data = await res.json();
    log(`GET /questions → ${JSON.stringify(data)}`);
  };

  const testGetAnswers = async () => {
    const questionsRes = await fetch("/api/questions");
    const questions = await questionsRes.json();
    if (questions.length === 0) {
      log("No questions yet — add an answer first");
      return;
    }
    const id = questions[0].id;
    const res = await fetch(`/api/questions/${id}/answers`);
    const data = await res.json();
    log(`GET /questions/${id}/answers → ${JSON.stringify(data)}`);
  };

  return (
    <div style={{ padding: 24, fontFamily: "monospace" }}>
      <h2>API Tests</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button onClick={testHealth}>GET /health</button>
        <button onClick={testAddAnswer}>POST /answers</button>
        <button onClick={testGetQuestions}>GET /questions</button>
        <button onClick={testGetAnswers}>GET /questions/:id/answers</button>
        <button onClick={() => setOutput([])}>Clear</button>
      </div>
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
