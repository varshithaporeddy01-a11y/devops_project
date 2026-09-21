"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { AlertTriangle, Terminal, Code2, Activity, LineChart } from "lucide-react";
import {
  API_BASE,
  BOILERPLATE,
  ComplexityResult,
  LanguageId,
  TraceResult,
} from "@/lib/types";

// Monaco and Chart.js touch `window` at module init time, so they must be
// loaded client-side only.
const CodeEditor = dynamic(() => import("@/components/CodeEditor"), { ssr: false });
const EnhancedVisualizer = dynamic(() => import("@/components/EnhancedVisualizer"), { ssr: false });
const ComplexityChart = dynamic(() => import("@/components/ComplexityChart"), { ssr: false });

type ViewId = "code" | "visualizer" | "complexity";

const VIEWS: { id: ViewId; label: string; icon: typeof Code2 }[] = [
  { id: "code", label: "1. Code & Execution Config", icon: Code2 },
  { id: "visualizer", label: "2. Visual Memory & Step Inspector", icon: Activity },
  { id: "complexity", label: "3. Big-O Complexity Benchmark", icon: LineChart },
];

export default function Home() {
  const [view, setView] = useState<ViewId>("code");
  const [language, setLanguage] = useState<LanguageId>("python");
  const [code, setCode] = useState(BOILERPLATE.python);
  const [userInput, setUserInput] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [traceResult, setTraceResult] = useState<TraceResult | null>(null);
  const [complexityResult, setComplexityResult] = useState<ComplexityResult | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  function handleLanguageChange(next: LanguageId) {
    const isUntouched = Object.values(BOILERPLATE).includes(code);
    setLanguage(next);
    if (isUntouched) {
      setCode(BOILERPLATE[next]);
    }
  }

  async function handleRun() {
    setIsRunning(true);
    setConnectionError(null);
    try {
      const [traceRes, complexityRes] = await Promise.all([
        fetch(`${API_BASE}/api/trace`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, language, input: userInput }),
        }),
        fetch(`${API_BASE}/api/complexity`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, language, input: userInput }),
        }),
      ]);

      if (!traceRes.ok) throw new Error(`Trace request failed (${traceRes.status})`);
      if (!complexityRes.ok) throw new Error(`Complexity request failed (${complexityRes.status})`);

      setTraceResult(await traceRes.json());
      setComplexityResult(await complexityRes.json());
      // Smoothly move focus to the visualizer once results are in.
      setView("visualizer");
    } catch (err) {
      setConnectionError(
        err instanceof Error
          ? `${err.message}. Is the backend running on ${API_BASE}?`
          : "Unknown error contacting backend."
      );
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="flex h-screen flex-col bg-ink-950 text-paper">
      <header className="flex items-center justify-between border-b border-ink-700 px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold tracking-tight">GraphMind</span>
        </div>
        {connectionError && (
          <div className="flex items-center gap-1.5 text-xs text-node-condition">
            <AlertTriangle className="h-3.5 w-3.5" />
            {connectionError}
          </div>
        )}
      </header>

      {/* Tab bar */}
      <nav className="flex gap-1 border-b border-ink-700 bg-ink-900 px-4 pt-2">
        {VIEWS.map(({ id, label, icon: Icon }) => {
          const isActive = view === id;
          return (
            <button
              key={id}
              onClick={() => setView(id)}
              className={`flex items-center gap-2 rounded-t-lg border-b-2 px-4 py-2.5 text-sm font-medium transition ${
                isActive
                  ? "border-signal bg-ink-950 text-paper"
                  : "border-transparent text-paper/40 hover:text-paper/70"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          );
        })}
      </nav>

      {/* Views — only the active view is mounted, avoiding Monaco/Chart.js
          layout issues that display:none toggling can cause. */}
      <main className="min-h-0 flex-1">
        {view === "code" && (
          <div className="h-full">
            <CodeEditor
              code={code}
              language={language}
              isRunning={isRunning}
              onCodeChange={setCode}
              onLanguageChange={handleLanguageChange}
              onRun={handleRun}
              userInput={userInput}
              onInputChange={setUserInput}
            />
          </div>
        )}

        {view === "visualizer" && (
          <div className="h-full">
            <EnhancedVisualizer
              frames={traceResult?.frames ?? []}
              supported={traceResult?.supported ?? true}
              message={traceResult?.message ?? null}
              code={code}
              stdout={traceResult?.stdout ?? ""}
              error={traceResult?.error ?? null}
            />
          </div>
        )}

        {view === "complexity" && (
          <div className="h-full">
            <ComplexityChart result={complexityResult} />
          </div>
        )}
      </main>

      {traceResult && traceResult.supported && (
        <footer className="flex items-center gap-2 border-t border-ink-700 bg-ink-900 px-5 py-2 text-xs text-paper/60">
          <Terminal className="h-3.5 w-3.5" />
          <span className="font-mono">
            {traceResult.error ? traceResult.error : traceResult.stdout || "(no output)"}
          </span>
        </footer>
      )}
    </div>
  );
}
