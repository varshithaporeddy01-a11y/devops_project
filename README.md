# GraphMind

> Interactive Code Execution Visualizer with Real-Time Animation and Complexity Analysis

GraphMind is a powerful visualization platform that transforms code execution into an interactive learning experience. Watch algorithms run step-by-step, observe data structure operations in real-time, and analyze algorithmic complexity with empirical benchmarking.

## Features

### Step-by-Step Execution Visualization
- Line-by-line code execution tracking with synchronized highlighting
- Adjustable playback speed (0.25x to 1.5x) for comfortable observation
- Frame-by-frame navigation with play, pause, and skip controls
- Auto-scroll to active line for seamless viewing experience

### Real-Time Data Structure Animation
- Dynamic array and list visualization with animated pointers
- Live variable tracking with instant value updates
- Interactive element highlighting during operations (READ, WRITE, COMPARE)
- Support for multiple pointer tracking and iteration visualization

### Call Stack Monitoring
- Hierarchical function call visualization
- Parameter and return value tracking
- Stack frame transitions with animated effects
- Nested function call representation

### Algorithmic Complexity Analysis
- Empirical Big-O time complexity measurement
- Visual complexity graphs with Chart.js
- Multiple input size benchmarking
- Performance metric tracking

### Multi-Language Support
- Python (full tracing support)
- JavaScript
- C++
- Java
- C
- Go
- R

### Interactive Input Terminal
- Built-in input panel for dynamic program execution
- Multi-line input support
- Real-time input processing during execution

## Tech Stack

### Frontend
- **Framework**: Next.js 16.3.5 with React 19
- **Language**: TypeScript 5
- **Styling**: TailwindCSS 4
- **Animation**: Framer Motion 11
- **Code Editor**: Monaco Editor (VS Code engine)
- **Visualization**: ReactFlow, Chart.js
- **Icons**: Lucide React

### Backend
- **Framework**: FastAPI 0.115.0
- **Language**: Python 3.10+
- **Server**: Uvicorn with WebSocket support
- **AST Parsing**: Tree-sitter with multi-language grammar support
- **Validation**: Pydantic 2.9

## Architecture

GraphMind follows a modern client-server architecture:

```
┌─────────────────────────────────────────────┐
│           Frontend (Next.js)                │
│  ┌─────────────┐  ┌──────────────────┐    │
│  │ Code Editor │  │ Visualizer Panel │    │
│  │  (Monaco)   │  │  - Call Stack    │    │
│  └─────────────┘  │  - Variables     │    │
│  ┌─────────────┐  │  - Array View    │    │
│  │   Input     │  │  - Code Panel    │    │
│  │  Terminal   │  └──────────────────┘    │
│  └─────────────┘  ┌──────────────────┐    │
│                   │ Complexity Chart │    │
│                   └──────────────────┘    │
└─────────────────────────────────────────────┘
                      │
                 HTTP/JSON API
                      │
┌─────────────────────────────────────────────┐
│           Backend (FastAPI)                 │
│  ┌─────────────────────────────────────┐   │
│  │         API Endpoints               │   │
│  │  /api/health                        │   │
│  │  /api/parse  - AST graph generation │   │
│  │  /api/trace  - Execution tracing    │   │
│  │  /api/complexity - Big-O analysis   │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │      Core Modules                   │   │
│  │  - AST Parser (Tree-sitter)         │   │
│  │  - Execution Tracer                 │   │
│  │  - Complexity Analyzer              │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Installation

### Prerequisites
- Node.js 20+ and npm
- Python 3.10+
- Git

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file (optional):
```bash
FRONTEND_ORIGIN=http://localhost:3000
```

5. Start the development server:
```bash
uvicorn main:app --reload --port 8000
```

The backend API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env.local` file:
```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

4. Start the development server:
```bash
npm run dev
```

The application will be available at `http://localhost:3000`

## Usage

### Basic Workflow

1. **Write Code**: Use the Monaco editor to write or paste your code
2. **Add Input**: (Optional) Provide input values in the input terminal
3. **Run**: Click "Run & Visualize" to execute
4. **Visualize**: Navigate to the "Visual Memory & Step Inspector" tab
5. **Control Playback**: Use play/pause controls to step through execution
6. **Analyze Complexity**: View the "Big-O Complexity Benchmark" tab for performance metrics

### Example: Bubble Sort Visualization

```python
def bubble_sort(arr):
    """Bubble sort with visual tracking"""
    n = len(arr)
    for i in range(n):
        for j in range(n - i - 1):
            if arr[j] > arr[j + 1]:
                # Swap elements
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

# Visualize sorting
numbers = [5, 2, 8, 1, 9, 3]
result = bubble_sort(numbers)
print("Sorted:", result)
```

This example demonstrates:
- Function call tracking
- Loop iteration visualization
- Array element comparison and swapping
- Variable state changes
- Return value display

### Playback Controls

- **Play/Pause**: Start or stop automatic step progression
- **Step Forward/Back**: Navigate one step at a time
- **First/Last**: Jump to the beginning or end
- **Speed Control**: Adjust playback speed from 0.25x to 1.5x
- **Progress Bar**: Scrub to any execution step

## API Reference

### POST /api/parse
Parse source code and generate an AST graph.

**Request:**
```json
{
  "code": "def add(a, b):\n    return a + b",
  "language": "python"
}
```

**Response:**
```json
{
  "nodes": [...],
  "edges": [...],
  "hasError": false
}
```

### POST /api/trace
Execute code and generate step-by-step execution trace.

**Request:**
```json
{
  "code": "x = 5\ny = 10\nprint(x + y)",
  "language": "python",
  "input": "5\n10"
}
```

**Response:**
```json
{
  "supported": true,
  "message": null,
  "frames": [
    {
      "step": 1,
      "activeLine": 1,
      "operation": "WRITE",
      "description": "Assigning x = 5",
      "variables": {"x": 5},
      "arrayState": [],
      "callStack": ["<module>"],
      ...
    }
  ],
  "stdout": "15\n",
  "error": null
}
```

### POST /api/complexity
Analyze algorithmic complexity with empirical benchmarking.

**Request:**
```json
{
  "code": "def linear_search(arr, target):\n    for i in range(len(arr)):\n        if arr[i] == target:\n            return i\n    return -1",
  "language": "python"
}
```

**Response:**
```json
{
  "supported": true,
  "message": null,
  "n_values": [10, 100, 1000, 10000],
  "step_counts": [15, 150, 1500, 15000],
  "estimated_big_o": "O(n)",
  "error": null
}
```

## Project Structure

```
graphmind/
├── backend/
│   ├── parsers/
│   │   └── ast_parser.py      # AST parsing with Tree-sitter
│   ├── tracer/
│   │   └── execution.py       # Execution tracing and complexity analysis
│   ├── main.py                # FastAPI application and routes
│   ├── requirements.txt       # Python dependencies
│   └── .env                   # Environment variables
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx     # Root layout
│   │   │   ├── page.tsx       # Main page component
│   │   │   └── globals.css    # Global styles
│   │   ├── components/
│   │   │   ├── CodeEditor.tsx           # Monaco code editor wrapper
│   │   │   ├── EnhancedVisualizer.tsx   # Main visualization component
│   │   │   ├── ComplexityChart.tsx      # Complexity graph component
│   │   │   └── ...
│   │   └── lib/
│   │       └── types.ts       # TypeScript type definitions
│   ├── package.json           # Node dependencies
│   ├── next.config.ts         # Next.js configuration
│   ├── tailwind.config.js     # Tailwind CSS configuration
│   └── .env.local             # Environment variables
└── README.md
```

## Configuration

### Backend Configuration

Edit `backend/.env`:
```bash
FRONTEND_ORIGIN=http://localhost:3000  # Allowed CORS origin
```

### Frontend Configuration

Edit `frontend/.env.local`:
```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000  # Backend API URL
```

## Development

### Running Tests

Backend:
```bash
cd backend
pytest
```

Frontend:
```bash
cd frontend
npm test
```

### Building for Production

Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Frontend:
```bash
cd frontend
npm run build
npm start
```

### Code Quality

Backend linting:
```bash
cd backend
pylint **/*.py
black .
```

Frontend linting:
```bash
cd frontend
npm run lint
```

## Roadmap

- [ ] Additional language support (Rust, TypeScript, Swift)
- [ ] Graph and tree data structure visualization
- [ ] Collaborative debugging sessions
- [ ] Export visualization as video/GIF
- [ ] Custom theme support
- [ ] Breakpoint support
- [ ] Memory usage visualization
- [ ] Integration with popular IDEs

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure your code:
- Follows the existing code style
- Includes appropriate tests
- Updates documentation as needed
- Passes all linting checks

## Acknowledgments

- Tree-sitter for robust AST parsing
- Monaco Editor for the VS Code editing experience
- FastAPI for the high-performance backend framework
- Next.js and React teams for the excellent frontend framework
- The open-source community for various libraries and tools

## Contact

For questions, suggestions, or issues, please open an issue on GitHub or contact the maintainers.

---

Built with care for developers and learners everywhere.
﻿# GraphMind

GraphMind is a browser-based code inspector: edit code, map its structure,
trace Python state step-by-step, and estimate empirical complexity.

## Run locally

In one PowerShell window:

```powershell
cd backend
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:FRONTEND_ORIGIN = "http://localhost:3000"
uvicorn main:app --reload --port 8000
```

In another:

```powershell
cd frontend
npm install
"NEXT_PUBLIC_API_BASE=http://localhost:8000" | Set-Content .env.local
npm run dev
```

Open http://localhost:3000. Python has real isolated tracing. The other editor
languages have structural graphs only; GraphMind reports that distinction in
the API rather than fabricating execution results.

## Safety and deployment

Every Python run is executed in a short-lived subprocess with a three-second
timeout, restricted builtins, bounded stdin/stdout, a step cap, and an empty
working directory. For a public deployment, run the backend in a container
sandbox with an unprivileged user, no network egress, CPU/memory limits, and a
read-only filesystem; restricted Python is defense-in-depth, not a complete
security boundary.

`render.yaml` and `vercel.json` provide deployment entry points. Set
`NEXT_PUBLIC_API_BASE` on Vercel and `FRONTEND_ORIGIN` on Render to the actual
public origins. The backend has SQLite session endpoints and a public GitHub
repository file-tree endpoint; a GitHub token is optional but avoids low
unauthenticated rate limits. Render's local filesystem is ephemeral, so set
`DATABASE_PATH` to a mounted persistent disk if history must survive deploys.

### Docker API runtime

For a local production-like backend, install Docker Desktop and run:

```powershell
docker compose up --build api
```

The API image runs as an unprivileged user with no Linux capabilities, a
read-only root filesystem, a bounded temporary directory, and CPU/memory
limits. The SQLite database is the named `graphmind-data` volume. Keep the
GitHub token in the deployment environment, never in compose files or source.
