"""Isolated execution facade. User code never runs in the FastAPI process."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

MAX_STEPS = 5_000
MAX_OUTPUT_BYTES = 64_000
EXECUTION_TIMEOUT_SECONDS = 3
NATIVE_EXECUTION_TIMEOUT_SECONDS = 15
SUPPORTED_EXECUTION_LANGUAGES = {"python", "py", "javascript", "js", "typescript", "ts", "c", "cpp", "c++", "java", "go", "r"}
PYTHON_LANGUAGES = {"python", "py"}
BENCHMARK_N_VALUES = [10, 50, 100, 500, 1_000]
_ENV_KEYS = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")


def _native_trace(code: str, language: str, input_text: str) -> dict[str, Any]:
    """Run a supported native runtime and translate its result to a trace response."""
    lang = language.strip().lower()
    aliases = {"js": "javascript", "ts": "typescript", "c++": "cpp"}
    lang = aliases.get(lang, lang)
    if lang not in {"javascript", "typescript", "c", "cpp", "java", "go", "r"}:
        return {"supported": False, "message": f"Execution is not configured for '{language}'. Choose one of the listed languages.", "frames": [], "stdout": "", "error": None}
    ext = {"javascript": ".js", "typescript": ".ts", "c": ".c", "cpp": ".cpp", "java": ".java", "go": ".go", "r": ".R"}[lang]
    required = {"javascript": "node", "typescript": "tsc", "c": "gcc", "cpp": "g++", "java": "javac", "go": "go", "r": "Rscript"}[lang]
    executable = shutil.which(required)
    if not executable:
        return {"supported": False, "message": f"Cannot run {lang}: '{required}' is not installed on the backend. Install that runtime or use the Docker image, which includes supported language tools.", "frames": [], "stdout": "", "error": None}

    env = {key: os.environ[key] for key in _ENV_KEYS if key in os.environ}
    trace_message = "Step-by-step variable tracing is available for Python. This run shows program output and compiler or runtime errors."
    frames: list[dict[str, Any]] = []
    stdout = ""
    error = None
    with tempfile.TemporaryDirectory(prefix="graphmind-native-") as folder:
        work = Path(folder)
        source = work / ("Main.java" if lang == "java" else f"program{ext}")
        source.write_text(code, encoding="utf-8")
        if lang == "javascript":
            command = [shutil.which("node") or "node", str(source)]
        elif lang == "typescript":
            try:
                built = subprocess.run([executable, "--target", "ES2022", "--module", "commonjs", "--skipLibCheck", "--outDir", str(work), str(source)], text=True, encoding="utf-8", capture_output=True, cwd=work, timeout=NATIVE_EXECUTION_TIMEOUT_SECONDS, env=env)
            except subprocess.TimeoutExpired:
                return {"supported": True, "message": trace_message, "frames": [], "stdout": "", "error": "TypeScript compilation timed out."}
            if built.returncode:
                error = (built.stderr or built.stdout).strip()[:MAX_OUTPUT_BYTES] or "TypeScript compilation failed."
                error_line = re.search(r"program\.ts\((\d+),", error)
                if error_line:
                    frames.append(_error_frame(int(error_line.group(1)), error, code))
                return {"supported": True, "message": trace_message, "frames": frames, "stdout": "", "error": error}
            command = [shutil.which("node") or "node", str(work / "program.js")]
        elif lang in ("c", "cpp"):
            binary = work / ("program.exe" if os.name == "nt" else "program")
            compiler = [executable, "-O0", str(source), "-o", str(binary)]
            try:
                built = subprocess.run(compiler, text=True, encoding="utf-8", capture_output=True, cwd=work, timeout=NATIVE_EXECUTION_TIMEOUT_SECONDS, env=env)
            except subprocess.TimeoutExpired:
                return {"supported": True, "message": trace_message, "frames": [], "stdout": "", "error": "Compilation timed out."}
            if built.returncode:
                stderr = (built.stderr or built.stdout).strip()[:MAX_OUTPUT_BYTES]
                match = re.search(r"(?:program\.(?:c|cpp)):(\d+)(?::\d+)?:\s*(?:fatal )?error", stderr)
                error = stderr or "Compilation failed."
                if match:
                    frames.append(_error_frame(int(match.group(1)), error, code))
                return {"supported": True, "message": trace_message, "frames": frames, "stdout": built.stdout[:MAX_OUTPUT_BYTES], "error": error}
            command = [str(binary)]
        elif lang == "java":
            match = re.search(r"\bpublic\s+class\s+(\w+)", code) or re.search(r"\bclass\s+(\w+)", code)
            class_name = match.group(1) if match else "Main"
            source = work / f"{class_name}.java"
            source.write_text(code, encoding="utf-8")
            try:
                built = subprocess.run([executable, str(source)], text=True, encoding="utf-8", capture_output=True, cwd=work, timeout=NATIVE_EXECUTION_TIMEOUT_SECONDS, env=env)
            except subprocess.TimeoutExpired:
                return {"supported": True, "message": trace_message, "frames": [], "stdout": "", "error": "Compilation timed out."}
            if built.returncode:
                error = (built.stderr or built.stdout).strip()[:MAX_OUTPUT_BYTES] or "Compilation failed."
                match_line = re.search(r"\.java:(\d+)(?:\)|:)", error)
                if match_line:
                    frames.append(_error_frame(int(match_line.group(1)), error, code))
                return {"supported": True, "message": trace_message, "frames": frames, "stdout": built.stdout[:MAX_OUTPUT_BYTES], "error": error}
            command = [shutil.which("java") or "java", "-cp", str(work), class_name]
        elif lang == "go":
            command = [executable, "run", str(source)]
        elif lang == "r":
            command = [executable, "--vanilla", str(source)]
        try:
            completed = subprocess.run(command, input=input_text, text=True, encoding="utf-8", capture_output=True, cwd=work, timeout=NATIVE_EXECUTION_TIMEOUT_SECONDS, env=env)
            stdout = completed.stdout[:MAX_OUTPUT_BYTES]
            stderr = completed.stderr[:MAX_OUTPUT_BYTES].strip()
            if completed.returncode:
                error = stderr or f"Program exited with status {completed.returncode}."
                match = re.search(r"(?:program\.(?:js|ts|go|R)|\.java):?(\d+)", error)
                if not match:
                    match = re.search(r"program\.(?:js|ts|go|R):(\d+)", error)
                if match:
                    frames.append(_error_frame(int(match.group(1)), error, code))
            elif stderr:
                # Compiler/runtime diagnostics sometimes use stderr while returning zero.
                error = stderr
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "")[:MAX_OUTPUT_BYTES] if isinstance(exc.stdout, str) else ""
            error = f"Execution timed out after {NATIVE_EXECUTION_TIMEOUT_SECONDS} seconds."
    return {"supported": True, "message": trace_message, "frames": frames, "stdout": stdout, "error": error}


def _error_frame(line: int, message: str, code: str) -> dict[str, Any]:
    return {"step": 1, "activeLine": line, "event": "exception", "operation": "ERROR", "description": message[:500], "callStack": [], "variables": {}, "arrayName": None, "arrayState": [], "pointers": {}, "loop": None, "callInfo": None}


def _run_worker(payload: dict[str, Any]) -> dict[str, Any]:
    worker = Path(__file__).with_name("worker.py")
    worker_env = {
        key: os.environ[key]
        for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
        if key in os.environ
    }
    worker_env.update({"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        with tempfile.TemporaryDirectory(prefix="graphmind-") as cwd:
            completed = subprocess.run(
                [sys.executable, "-I", str(worker)], input=json.dumps(payload), text=True,
                encoding="utf-8", capture_output=True, cwd=cwd, timeout=EXECUTION_TIMEOUT_SECONDS,
                env=worker_env,
            )
    except subprocess.TimeoutExpired:
        return {"error": f"Execution timed out after {EXECUTION_TIMEOUT_SECONDS} seconds."}
    except OSError as exc:
        return {"error": f"Could not start isolated execution worker: {exc}"}
    if completed.returncode:
        return {"error": f"Execution worker failed: {(completed.stderr or 'unexpected exit').strip()[:500]}"}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"error": "Execution worker returned an invalid response."}


def _unsupported(language: str, feature: str) -> dict[str, Any]:
    return {"supported": False, "message": f"{feature} currently supports Python only; '{language}' remains available for structural parsing."}


def trace_execution(code: str, language: str, input_text: str = "") -> dict[str, Any]:
    lang = (language or "").strip().lower()
    if lang not in PYTHON_LANGUAGES:
        return _native_trace(code, lang, input_text)
    result = _run_worker({"mode": "trace", "code": code, "input": input_text, "max_steps": MAX_STEPS, "max_output": MAX_OUTPUT_BYTES})
    return {"supported": True, "message": None, "frames": result.get("frames", []), "stdout": result.get("stdout", ""), "error": result.get("error")}


def run_complexity_benchmark(code: str, language: str, input_text: str = "") -> dict[str, Any]:
    if (language or "").strip().lower() not in PYTHON_LANGUAGES:
        return {**_unsupported(language, "Empirical Big-O benchmarking"), "n_values": [], "step_counts": [], "estimated_big_o": None, "error": None}
    result = _run_worker({"mode": "complexity", "code": code, "input": input_text, "n_values": BENCHMARK_N_VALUES, "max_steps": 2_000_000, "max_output": MAX_OUTPUT_BYTES})
    return {"supported": True, "message": None, "n_values": result.get("n_values", []), "step_counts": result.get("step_counts", []), "estimated_big_o": result.get("estimated_big_o"), "error": result.get("error")}
