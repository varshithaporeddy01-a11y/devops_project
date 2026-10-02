"""Isolated execution facade. User code never runs in the FastAPI process."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

MAX_STEPS = 5_000
MAX_OUTPUT_BYTES = 64_000
EXECUTION_TIMEOUT_SECONDS = 3
SUPPORTED_EXECUTION_LANGUAGES = {"python", "py"}
BENCHMARK_N_VALUES = [10, 50, 100, 500, 1_000]


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
    if (language or "").strip().lower() not in SUPPORTED_EXECUTION_LANGUAGES:
        return {**_unsupported(language, "Live execution tracing"), "frames": [], "stdout": "", "error": None}
    result = _run_worker({"mode": "trace", "code": code, "input": input_text, "max_steps": MAX_STEPS, "max_output": MAX_OUTPUT_BYTES})
    return {"supported": True, "message": None, "frames": result.get("frames", []), "stdout": result.get("stdout", ""), "error": result.get("error")}


def run_complexity_benchmark(code: str, language: str, input_text: str = "") -> dict[str, Any]:
    if (language or "").strip().lower() not in SUPPORTED_EXECUTION_LANGUAGES:
        return {**_unsupported(language, "Empirical Big-O benchmarking"), "n_values": [], "step_counts": [], "estimated_big_o": None, "error": None}
    result = _run_worker({"mode": "complexity", "code": code, "input": input_text, "n_values": BENCHMARK_N_VALUES, "max_steps": 2_000_000, "max_output": MAX_OUTPUT_BYTES})
    return {"supported": True, "message": None, "n_values": result.get("n_values", []), "step_counts": result.get("step_counts", []), "estimated_big_o": result.get("estimated_big_o"), "error": result.get("error")}
