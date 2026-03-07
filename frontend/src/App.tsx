import { useState } from "react";
import "./App.css";

const TEST_QUESTION = "What is the capital of France?";
const TEST_ANSWERS = [
  "Paris is the capital city of France.",
  "The Eiffel Tower is in Paris.",
  "Berlin is the capital of Germany.",
  "France is a country in Western Europe.",
  "Lyon is a major city in France.",
];

function App() {
  const [output, setOutput] = useState<string[]>([]);
  const [similarityQuery, setSimilarityQuery] = useState("");

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
      body: JSON.stringify({ question: TEST_QUESTION, answer: "Paris" }),
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

  const seedAnswers = async () => {
    for (const answer of TEST_ANSWERS) {
      await fetch("/api/answers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: TEST_QUESTION, answer }),
      });
    }
    log(`Seeded ${TEST_ANSWERS.length} answers for "${TEST_QUESTION}"`);
  };

  const testSimilarity = async () => {
    if (!similarityQuery.trim()) {
      log("Enter a query first");
      return;
    }
    const questionsRes = await fetch("/api/questions");
    const questions = await questionsRes.json();
    const q = questions.find((q: { text: string }) => q.text === TEST_QUESTION);
    if (!q) {
      log(`Question not found — seed answers first`);
      return;
    }
    log(`Querying similarity for: "${similarityQuery}" (this may take a moment on first run)...`);
    const res = await fetch(`/api/questions/${q.id}/similar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer: similarityQuery }),
    });
    const data = await res.json();
    log(`Most similar → "${data.answer.text}" (score: ${data.score.toFixed(3)})`);
  };

  return (
    <div style={{ padding: 24, fontFamily: "monospace" }}>
      <h2>API Tests</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <button onClick={testHealth}>GET /health</button>
        <button onClick={testAddAnswer}>POST /answers</button>
        <button onClick={testGetQuestions}>GET /questions</button>
        <button onClick={testGetAnswers}>GET /questions/:id/answers</button>
        <button onClick={() => setOutput([])}>Clear</button>
      </div>

      <h2>Similarity Test</h2>
      <p style={{ margin: "4px 0 8px" }}>Question: <em>"{TEST_QUESTION}"</em></p>
      <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        <button onClick={seedAnswers}>Seed answers</button>
        <input
          value={similarityQuery}
          onChange={(e) => setSimilarityQuery(e.target.value)}
          placeholder="Type a query answer..."
          style={{ padding: "4px 8px", fontFamily: "monospace", width: 300 }}
        />
        <button onClick={testSimilarity}>Find most similar</button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 16 }}>
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
