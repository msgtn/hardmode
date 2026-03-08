import { useState, useEffect, useCallback, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { ForceGraphMethods } from "react-force-graph-2d";

interface Question {
  id: number;
  text: string;
  created_at: string;
}

interface Answer {
  id: number;
  question_id: number;
  text: string;
  created_at: string;
}

interface GraphLink {
  source: number;
  target: number;
  score: number;
}

interface GraphData {
  nodes: Answer[];
  links: GraphLink[];
}

const MIN_THRESHOLD = 0.1;
const MAX_THRESHOLD = 0.95;
const DEFAULT_THRESHOLD = 0.5;

// Palette
const C = {
  bg: "#111111",
  surface: "rgba(255,255,255,0.04)",
  border: "rgba(179,179,179,0.14)",
  nodeFill: "#ffffff",
  nodeSelected: "#DD4343",
  nodeGlow: "rgba(255,255,255,0.6)",
  nodeGlowSelected: "rgba(221,67,67,0.9)",
  link: (score: number) => `rgba(255,255,255,${(0.06 + score * 0.45).toFixed(2)})`,
  textPrimary: "#ffffff",
  textSecondary: "#B3B3B3",
  textMuted: "rgba(179,179,179,0.45)",
  accent: "#DD4343",
  accentStrong: "#DD4343",
};

function App() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [selectedQuestion, setSelectedQuestion] = useState<Question | null>(null);
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [selectedNode, setSelectedNode] = useState<Answer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<ForceGraphMethods<any, any>>(undefined);

  useEffect(() => {
    fetch("/api/questions")
      .then((r) => r.json())
      .then((data: Question[]) => {
        setQuestions(data);
        if (data.length > 0) setSelectedQuestion(data[0]);
      })
      .catch(() => setError("Could not reach backend"));
  }, []);

  useEffect(() => {
    if (!selectedQuestion) return;
    setLoading(true);
    setSelectedNode(null);
    fetch(`/api/questions/${selectedQuestion.id}/similarity-graph?threshold=${threshold}`)
      .then((r) => r.json())
      .then((data: GraphData) => {
        setGraphData(data);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load graph");
        setLoading(false);
      });
  }, [selectedQuestion, threshold]);

  const handleNodeClick = useCallback((node: Answer) => {
    setSelectedNode((prev) => (prev?.id === node.id ? null : node));
    const n = node as Answer & { x?: number; y?: number };
    if (n.x != null && n.y != null) {
      graphRef.current?.centerAt(n.x, n.y, 900);
      graphRef.current?.zoom(3, 900);
    }
  }, []);

  const handleZoomToFit = () => graphRef.current?.zoomToFit(600, 60);

  // Precompute degree (connection count) per node id
  const degreeMap = useCallback(() => {
    const map: Record<number, number> = {};
    for (const l of graphData.links) {
      const src = typeof l.source === "object" ? (l.source as Answer).id : l.source;
      const tgt = typeof l.target === "object" ? (l.target as Answer).id : l.target;
      map[src] = (map[src] ?? 0) + 1;
      map[tgt] = (map[tgt] ?? 0) + 1;
    }
    return map;
  }, [graphData.links])();

  const drawNode = useCallback(
    (node: object, ctx: CanvasRenderingContext2D) => {
      const n = node as Answer & { x: number; y: number };
      const isSelected = selectedNode?.id === n.id;
      const degree = degreeMap[n.id] ?? 0;
      const r = isSelected ? 8 : 3.5 + Math.sqrt(degree) * 1.2;

      ctx.save();
      ctx.shadowBlur = isSelected ? 18 : 10;
      ctx.shadowColor = isSelected ? C.nodeSelected : C.nodeGlow;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = C.nodeFill;
      ctx.fill();
      ctx.restore();
    },
    [selectedNode, degreeMap]
  );

  const connectedLinks = graphData.links.filter((l) => {
    const src = typeof l.source === "object" ? (l.source as Answer).id : l.source;
    const tgt = typeof l.target === "object" ? (l.target as Answer).id : l.target;
    return src === selectedNode?.id || tgt === selectedNode?.id;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: C.bg, color: C.textPrimary, fontFamily: "'DM Sans', system-ui, sans-serif" }}>

      {/* Header */}
      <div style={{
        padding: "14px 24px",
        borderBottom: `1px solid ${C.border}`,
        display: "flex",
        alignItems: "center",
        gap: 12,
        background: "rgba(17,17,17,0.85)",
        backdropFilter: "blur(12px)",
      }}>
        <span style={{ fontSize: 13, fontWeight: 500, letterSpacing: "0.08em", color: C.accentStrong }}>community light</span>
        <span style={{ width: 1, height: 14, background: C.border }} />
        <span style={{ fontSize: 12, color: C.textMuted, letterSpacing: "0.05em" }}>response map</span>
      </div>

      {/* Question toggles */}
      <div style={{
        padding: "10px 24px",
        borderBottom: `1px solid ${C.border}`,
        display: "flex",
        gap: 6,
        flexWrap: "wrap",
        alignItems: "center",
        background: "rgba(17,17,17,0.7)",
        backdropFilter: "blur(8px)",
      }}>
        {questions.length === 0 && !error && (
          <span style={{ fontSize: 12, color: C.textMuted }}>loading…</span>
        )}
        {questions.map((q, i) => {
          const active = selectedQuestion?.id === q.id;
          return (
            <button
              key={q.id}
              onClick={() => setSelectedQuestion(q)}
              title={q.text}
              style={{
                padding: "5px 14px",
                fontSize: 12,
                fontFamily: "inherit",
                fontWeight: active ? 500 : 400,
                background: active ? "rgba(221,67,67,0.12)" : "rgba(255,255,255,0.04)",
                color: active ? C.accentStrong : C.textSecondary,
                border: `1px solid ${active ? "rgba(221,67,67,0.4)" : C.border}`,
                borderRadius: 20,
                cursor: "pointer",
                transition: "all 0.18s ease",
                whiteSpace: "nowrap",
                maxWidth: 240,
                overflow: "hidden",
                textOverflow: "ellipsis",
                boxShadow: active ? "0 0 14px rgba(221,67,67,0.18)" : "none",
              }}
            >
              <span style={{ opacity: 0.45, marginRight: 6, fontSize: 10 }}>{i + 1}</span>
              {q.text.length > 42 ? q.text.slice(0, 40) + "…" : q.text}
            </button>
          );
        })}
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden", position: "relative" }}>

        {/* Graph canvas */}
        <div style={{ flex: 1, position: "relative" }}>
          {(loading || error || (!loading && graphData.nodes.length === 0 && selectedQuestion)) && (
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
              <span style={{ fontSize: 13, color: C.textMuted, letterSpacing: "0.04em" }}>
                {error ?? (loading ? "computing embeddings…" : "no answers yet")}
              </span>
            </div>
          )}

          {graphData.nodes.length > 0 && (
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData as unknown as { nodes: Answer[]; links: GraphLink[] }}
              nodeId="id"
              nodeLabel={(node) => (node as Answer).text}
              nodeCanvasObject={drawNode}
              nodeCanvasObjectMode={() => "replace"}
              linkSource="source"
              linkTarget="target"
              linkWidth={(link) => (link as GraphLink).score * 2.5}
              linkColor={(link) => C.link((link as GraphLink).score)}
              linkLabel={(link) => `${((link as GraphLink).score * 100).toFixed(0)}% similar`}
              onNodeClick={(node) => handleNodeClick(node as Answer)}
              onBackgroundClick={() => {
                setSelectedNode(null);
                graphRef.current?.zoomToFit(900, 60);
              }}
              backgroundColor={C.bg}
              onEngineStop={handleZoomToFit}
              onRenderFramePre={(ctx, globalScale) => {
                // Translucent grey grid
                const gridSize = 40 / globalScale;
                const w = (ctx.canvas.width / globalScale);
                const h = (ctx.canvas.height / globalScale);
                const transform = ctx.getTransform();
                const ox = -transform.e / globalScale;
                const oy = -transform.f / globalScale;
                const startX = Math.floor(ox / gridSize) * gridSize;
                const startY = Math.floor(oy / gridSize) * gridSize;
                ctx.save();
                ctx.strokeStyle = "rgba(179,179,179,0.07)";
                ctx.lineWidth = 1 / globalScale;
                ctx.beginPath();
                for (let x = startX; x < ox + w; x += gridSize) {
                  ctx.moveTo(x, oy);
                  ctx.lineTo(x, oy + h);
                }
                for (let y = startY; y < oy + h; y += gridSize) {
                  ctx.moveTo(ox, y);
                  ctx.lineTo(ox + w, y);
                }
                ctx.stroke();
                ctx.restore();
              }}
            />
          )}

          {/* Threshold control */}
          <div style={{
            position: "absolute",
            bottom: 20,
            left: 20,
            padding: "12px 16px",
            background: "rgba(17,17,17,0.8)",
            backdropFilter: "blur(16px)",
            border: `1px solid ${C.border}`,
            borderRadius: 14,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 11, color: C.textSecondary, letterSpacing: "0.04em" }}>connection threshold</span>
              <span style={{ fontSize: 12, color: C.accentStrong, fontVariantNumeric: "tabular-nums" }}>{threshold.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min={MIN_THRESHOLD}
              max={MAX_THRESHOLD}
              step={0.05}
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              style={{ width: 160, accentColor: C.accent, cursor: "pointer" }}
            />
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: C.textMuted }}>
              <span>more edges</span>
              <span>fewer edges</span>
            </div>
          </div>
        </div>

        {/* Detail panel */}
        {selectedNode && (
          <div style={{
            width: 300,
            borderLeft: `1px solid ${C.border}`,
            padding: "20px 18px",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 16,
            background: "rgba(17,17,17,0.82)",
            backdropFilter: "blur(20px)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <span style={{ fontSize: 10, letterSpacing: "0.1em", color: C.textMuted, textTransform: "uppercase" }}>response</span>
              <button
                onClick={() => setSelectedNode(null)}
                style={{ background: "none", border: "none", color: C.textMuted, cursor: "pointer", fontSize: 18, lineHeight: 1, padding: "0 2px" }}
              >
                ×
              </button>
            </div>

            <p style={{ fontSize: 14, lineHeight: 1.75, color: C.textPrimary, fontWeight: 300 }}>
              {selectedNode.text}
            </p>

            <span style={{ fontSize: 11, color: C.textMuted }}>
              #{selectedNode.id} · {new Date(selectedNode.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
            </span>

            {/* Connections */}
            <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 16, display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 10, letterSpacing: "0.1em", color: C.textMuted, textTransform: "uppercase", marginBottom: 8 }}>
                connections
              </span>

              {connectedLinks.length === 0 && (
                <span style={{ fontSize: 12, color: C.textMuted }}>none above threshold</span>
              )}

              {connectedLinks
                .sort((a, b) => b.score - a.score)
                .map((l, i) => {
                  const src = typeof l.source === "object" ? (l.source as Answer).id : l.source;
                  const tgt = typeof l.target === "object" ? (l.target as Answer).id : l.target;
                  const otherId = src === selectedNode.id ? tgt : src;
                  const other = graphData.nodes.find((n) => n.id === otherId);
                  return (
                    <div
                      key={i}
                      onClick={() => other && setSelectedNode(other)}
                      style={{
                        padding: "8px 10px",
                        borderRadius: 10,
                        cursor: "pointer",
                        background: "rgba(139,92,246,0.05)",
                        border: `1px solid ${C.border}`,
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                        transition: "background 0.15s",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.07)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.04)")}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 12, color: C.textSecondary, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                          {other?.text.slice(0, 48)}{(other?.text.length ?? 0) > 48 ? "…" : ""}
                        </span>
                        <span style={{ fontSize: 11, color: C.accentStrong, flexShrink: 0 }}>
                          {(l.score * 100).toFixed(0)}%
                        </span>
                      </div>
                      {/* Score bar */}
                      <div style={{ height: 2, background: "rgba(167,139,250,0.1)", borderRadius: 1, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${l.score * 100}%`, background: `linear-gradient(90deg, #b83232, #DD4343)`, borderRadius: 1 }} />
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
