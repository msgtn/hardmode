import { useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";
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

const socket = io();

function App() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<number, Answer[]>>({});
  const [highlightedUuid, setHighlightedUuid] = useState<string | null>(null);
  const latestAnswerRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    const loadAll = async () => {
      const qRes = await fetch("/api/questions");
      const qs: Question[] = await qRes.json();
      setQuestions(qs);

      const answerMap: Record<number, Answer[]> = {};
      await Promise.all(
        qs.map(async (q) => {
          const aRes = await fetch(`/api/questions/${q.id}/answers`);
          const data: Answer[] = await aRes.json();
          answerMap[q.id] = data.reverse();
        }),
      );
      setAnswers(answerMap);
    };

    loadAll();

    socket.on("new_answer", (answer: Answer) => {
      setAnswers((prev) => ({
        ...prev,
        [answer.question_id]: [answer, ...(prev[answer.question_id] ?? [])],
      }));
      setHighlightedUuid(answer.uuid);
      setTimeout(
        () =>
          latestAnswerRef.current?.scrollIntoView({
            behavior: "smooth",
            block: "center",
          }),
        50,
      );
      setTimeout(() => setHighlightedUuid(null), 5000);
    });

    return () => {
      socket.off("new_answer");
    };
  }, []);

  return (
    <div style={{ padding: 24, fontFamily: "monospace", maxWidth: 700, margin: "0 auto" }}>
      <h1 style={{ color: "red" }}>
        <em>Close to the Fire</em>
      </h1>
      {questions.length === 0 && <p>Loading...</p>}
      {questions.map((q) => (
        <div key={q.id} style={{ marginBottom: 32 }}>
          <h2 style={{ marginBottom: 8 }}>{q.text}</h2>
          {(answers[q.id] ?? []).length === 0 ? (
            <p style={{ color: "#888" }}>No answers yet.</p>
          ) : (
            <ul style={{ paddingLeft: 20, margin: 0 }}>
              {(answers[q.id] ?? []).map((a, i) => (
                <li
                  key={a.uuid}
                  ref={i === 0 ? latestAnswerRef : null}
                  className={
                    a.uuid === highlightedUuid ? "answer-highlight" : undefined
                  }
                  style={{ marginBottom: 4 }}
                >
                  {a.text}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

export default App;
