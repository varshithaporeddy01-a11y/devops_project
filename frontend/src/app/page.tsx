"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { AlertTriangle, Terminal, Code2, Activity, LineChart, GitBranch, FolderGit2, Save, X } from "lucide-react";
import {
  API_BASE,
  BOILERPLATE,
  ComplexityResult,
  LanguageId,
  TraceResult,
  GraphEdge,
  GraphNode,
} from "@/lib/types";

// Monaco and Chart.js touch `window` at module init time, so they must be
// loaded client-side only.
const CodeEditor = dynamic(() => import("@/components/CodeEditor"), { ssr: false });
const EnhancedVisualizer = dynamic(() => import("@/components/EnhancedVisualizer"), { ssr: false });
const ComplexityChart = dynamic(() => import("@/components/ComplexityChart"), { ssr: false });
const FlowCanvas = dynamic(() => import("@/components/FlowCanvas"), { ssr: false });

type ViewId = "code" | "visualizer" | "graph" | "complexity";

const VIEWS: { id: ViewId; label: string; icon: typeof Code2 }[] = [
  { id: "code", label: "1. Code & Execution Config", icon: Code2 },
  { id: "visualizer", label: "2. Visual Memory & Step Inspector", icon: Activity },
  { id: "graph", label: "3. Structure Graph", icon: GitBranch },
  { id: "complexity", label: "4. Big-O Complexity Benchmark", icon: LineChart },
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
  const [graph, setGraph] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [githubUrl, setGithubUrl] = useState("");
  const [githubFiles, setGithubFiles] = useState<{ path: string; size: number }[]>([]);
  const [panelError, setPanelError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showSessions, setShowSessions] = useState(false);
  const [sessions, setSessions] = useState<{ id: string; name: string; language: LanguageId; code: string }[]>([]);

  function languageForPath(path: string): LanguageId {
    const extension = path.split(".").pop()?.toLowerCase();
    return ({ py: "python", js: "javascript", ts: "typescript", tsx: "typescript", cpp: "cpp", h: "cpp", c: "c", java: "java", go: "go", r: "r" }[extension ?? ""] ?? "python") as LanguageId;
  }

  async function browseRepository() {
    setIsImporting(true); setPanelError(null);
    try {
      const response = await fetch(`${API_BASE}/api/github/import`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: githubUrl }) });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Could not browse repository");
      setGithubFiles((await response.json()).files);
    } catch (error) { setPanelError(error instanceof Error ? error.message : "Could not browse repository."); }
    finally { setIsImporting(false); }
  }

  async function importFile(path: string) {
    setIsImporting(true); setPanelError(null);
    try {
      const response = await fetch(`${API_BASE}/api/github/file`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: githubUrl, path }) });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Could not import file");
      const result = await response.json(); setCode(result.content); setLanguage(languageForPath(path)); setShowImport(false); setView("code");
    } catch (error) { setPanelError(error instanceof Error ? error.message : "Could not import file."); }
    finally { setIsImporting(false); }
  }

  async function saveSession() {
    setPanelError(null);
    try {
      const response = await fetch(`${API_BASE}/api/sessions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "Untitled analysis", language, code }) });
      if (!response.ok) throw new Error("Could not save session");
      await loadSessions();
    } catch (error) { setPanelError(error instanceof Error ? error.message : "Could not save session."); }
  }
  async function loadSessions() {
    const response = await fetch(`${API_BASE}/api/sessions`);
    if (!response.ok) throw new Error("Could not load sessions");
    setSessions(await response.json());
  }
  async function openSessions() { setShowSessions(true); try { await loadSessions(); } catch (error) { setPanelError(error instanceof Error ? error.message : "Could not load sessions."); } }

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
      const [traceRes, complexityRes, parseRes] = await Promise.all([
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
        fetch(`${API_BASE}/api/parse`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, language }),
        }),
      ]);

      if (!traceRes.ok) throw new Error(`Trace request failed (${traceRes.status})`);
      if (!complexityRes.ok) throw new Error(`Complexity request failed (${complexityRes.status})`);

      setTraceResult(await traceRes.json());
      setComplexityResult(await complexityRes.json());
      if (parseRes.ok) {
        const parsed = await parseRes.json();
        setGraph({ nodes: parsed.nodes, edges: parsed.edges });
        setParseError(parsed.hasError ? "The parser found a syntax error; the graph may be partial." : null);
      } else {
        setGraph(null);
        setParseError(`Structure analysis failed (${parseRes.status}).`);
      }
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
        <div className="flex items-center gap-2">
          <button onClick={() => setShowImport(true)} className="flex items-center gap-1 rounded border border-ink-700 px-2 py-1 text-xs text-paper/80 hover:bg-ink-800"><FolderGit2 className="h-3.5 w-3.5" /> Import GitHub</button>
          <button onClick={saveSession} className="flex items-center gap-1 rounded border border-ink-700 px-2 py-1 text-xs text-paper/80 hover:bg-ink-800"><Save className="h-3.5 w-3.5" /> Save</button>
          <button onClick={openSessions} className="rounded border border-ink-700 px-2 py-1 text-xs text-paper/80 hover:bg-ink-800">History</button>
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
            />
          </div>
        )}

        {view === "complexity" && (
          <div className="h-full">
            <ComplexityChart result={complexityResult} />
          </div>
        )}

        {view === "graph" && (
          <div className="relative h-full">
            {parseError && <div className="absolute left-4 top-4 z-10 rounded border border-node-condition bg-ink-900 px-3 py-2 text-xs text-node-condition">{parseError}</div>}
            <FlowCanvas nodes={graph?.nodes ?? []} edges={graph?.edges ?? []} activeLine={traceResult?.frames.at(-1)?.activeLine ?? null} />
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

      {(showImport || showSessions) && <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/60 p-4">
        <section className="max-h-[80vh] w-full max-w-xl overflow-auto rounded-xl border border-ink-700 bg-ink-950 p-5 shadow-2xl">
          <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">{showImport ? "Import public GitHub code" : "Saved sessions"}</h2><button onClick={() => { setShowImport(false); setShowSessions(false); }}><X className="h-5 w-5" /></button></div>
          {showImport ? <><div className="flex gap-2"><input aria-label="GitHub repository URL" value={githubUrl} onChange={(event) => setGithubUrl(event.target.value)} placeholder="https://github.com/owner/repository" className="min-w-0 flex-1 rounded border border-ink-700 bg-ink-900 px-3 py-2 text-sm" /><button onClick={browseRepository} disabled={isImporting || !githubUrl} className="rounded bg-signal px-3 text-sm text-ink-950 disabled:opacity-50">Browse</button></div>
            <p className="mt-2 text-xs text-paper/50">Public repositories only. Choose a supported source file below.</p>
            <div className="mt-4 space-y-1">{githubFiles.map((file) => <button key={file.path} onClick={() => importFile(file.path)} className="block w-full rounded px-2 py-1.5 text-left font-mono text-xs hover:bg-ink-800">{file.path} <span className="text-paper/40">({file.size} bytes)</span></button>)}</div></> : <div className="space-y-2">{sessions.length ? sessions.map((session) => <button key={session.id} onClick={() => { setCode(session.code); setLanguage(session.language); setShowSessions(false); setView("code"); }} className="block w-full rounded border border-ink-700 p-3 text-left hover:bg-ink-900"><div className="text-sm">{session.name}</div><div className="text-xs text-paper/50">{session.language}</div></button>) : <p className="text-sm text-paper/50">No saved sessions yet.</p>}</div>}
          {panelError && <p className="mt-3 text-sm text-node-condition">{panelError}</p>}
        </section>
      </div>}
    </div>
  );
}
