# GraphMind

GraphMind is a browser-based code inspector for structural code graphs,
step-by-step Python tracing, and empirical complexity estimates. It combines a
Monaco editor, a React Flow canvas, a variable and call-stack inspector, and a
Chart.js benchmark view.

## What it supports

- **Editor and structural graph:** Python, JavaScript, TypeScript, C, C++, Java,
  Go, and R, parsed with Tree-sitter.
- **Execution trace and complexity benchmark:** Python. Other languages remain
  available for structural inspection and are reported as unsupported for
  execution instead of returning fabricated traces.
- **Repository import:** Browse supported source files in public GitHub
  repositories and load a selected file into the editor.
- **Saved sessions:** Store and reopen code and language selections in SQLite.
- **Graph navigation:** Select a function or call to highlight its resolved
  callers and dependencies where the source contains resolvable function calls.

The first parse for a language may download its Tree-sitter grammar. The backend
therefore needs outbound access to the grammar package's release host on first
use of each language.

## Run locally

Requirements: Python 3.10+, Node.js 20+, and npm.

Start the backend in one terminal:

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:FRONTEND_ORIGIN = "http://localhost:3000"
uvicorn main:app --reload --port 8000
```

Start the frontend in another terminal:

```powershell
cd frontend
npm ci
"NEXT_PUBLIC_API_BASE=http://localhost:8000" | Set-Content .env.local
npm run dev
```

Open <http://localhost:3000>. The backend API is available at
<http://localhost:8000/docs>.

## Main API endpoints

- `GET /api/health` - backend health check.
- `POST /api/parse` - Tree-sitter structure nodes and relationships.
- `POST /api/trace` - Python execution frames, output, and captured errors.
- `POST /api/complexity` - Python step counts for N = 10, 50, 100, 500, and
  1,000 with a best-fit Big-O estimate.
- `POST /api/github/import` and `/api/github/file` - public repository listing
  and source-file import.
- `/api/sessions` - SQLite session create, list, load, and delete operations.

Complexity results are empirical estimates based on the selected sample sizes;
they are useful for comparison and may be inconclusive for small or
input-dependent programs.

## Deployment

The repository includes `vercel.json` for the Next.js frontend and `render.yaml`
for the FastAPI backend. Configure `NEXT_PUBLIC_API_BASE` in Vercel with the
backend URL and `FRONTEND_ORIGIN` in Render with the frontend origin. The Render
manifest mounts a persistent disk at `/var/data` and stores SQLite at
`/var/data/graphmind.db`. Set `GITHUB_TOKEN` on Render if you need higher GitHub
API rate limits. Render persistent disks require a paid compute plan; the
manifest selects Render's smallest paid plan so the SQLite volume is available.

The local Docker Compose setup uses a named volume for SQLite and applies
container resource limits. The execution worker has a short timeout, bounded
output and step counts, and restricted builtins. This is defense in depth, not
a complete security boundary for running arbitrary hostile code; keep the API
private or add a stronger operating-system sandbox before exposing it publicly.

## Project layout

```text
backend/
  main.py                 FastAPI routes and request models
  parsers/ast_parser.py   Tree-sitter graph generation
  tracer/                 Isolated Python tracing and benchmarking
  storage.py              SQLite sessions
  github_import.py        GitHub repository browsing
frontend/src/
  app/                    Next.js application shell
  components/             Editor, graph, trace, and complexity views
  lib/types.ts            API and UI types
```
