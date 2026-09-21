"""
Dynamic execution tracer and empirical Big-O benchmark engine.

Only Python is actually executed and traced in-process (via `sys.settrace`).
Other languages accepted by the API (JavaScript, C++, Java, C, Go, R) do not
have a real interpreter/debugger wired up in this build — rather than
fabricate fake variable traces for them (which would be actively
misleading), `trace_execution` and `run_complexity_benchmark` report
`supported: False` with an explanatory message for anything other than
Python. The Python engine is fully real: no synthetic/mocked data.

Each traced frame is enriched with:
  - operation: READ | WRITE | COMPARE | CALL | RETURN | LOOP | EXEC
  - description: a plain-English one-line narration of the step
  - loop: {var, iteration, total} when the step is a loop header re-visit
  - callInfo: {function, args} / {function, value} for CALL / RETURN steps

Public API:
    trace_execution(code, language) -> dict
    run_complexity_benchmark(code, language) -> dict
"""
from __future__ import annotations

import io
import math
import re
import sys
import time
from typing import Any

MAX_STEPS = 5000
SUPPORTED_EXECUTION_LANGUAGES = {"python"}

BENCHMARK_N_VALUES = [10, 50, 100, 500, 1000]
COMPLEXITY_STEP_CAP = 2_000_000


class ExecutionLimitError(RuntimeError):
    """Raised internally when a traced program exceeds MAX_STEPS lines."""


# --------------------------------------------------------------------------
# Value / variable helpers
# --------------------------------------------------------------------------

def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        if len(value) > 500:
            return f"<{type(value).__name__} of length {len(value)}>"
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in list(value.items())[:200]}
    text = repr(value)
    if len(text) > 200:
        text = text[:197] + "..."
    return text


def _is_array_like(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and len(value) <= 500


def _pick_array_state(locals_snapshot: dict[str, Any]) -> tuple[str | None, list]:
    preferred_names = ("arr", "array", "nums", "data", "values", "lst", "list", "a")
    candidates = {k: v for k, v in locals_snapshot.items() if _is_array_like(v)}
    if not candidates:
        return None, []
    for name in preferred_names:
        if name in candidates:
            return name, list(candidates[name])
    name, value = next(iter(candidates.items()))
    return name, list(value)


_CONVENTIONAL_POINTER_NAMES = {
    "i", "j", "k", "l", "low", "high", "mid", "left", "right",
    "idx", "index", "ptr", "p", "q", "lo", "hi", "start", "end", "pos",
}


def _pick_pointers(
    locals_snapshot: dict[str, Any], array_len: int, known_loop_vars: set[str]
) -> dict[str, int]:
    if array_len == 0:
        return {}
    pointers = {}
    allowed_names = _CONVENTIONAL_POINTER_NAMES | known_loop_vars
    for key, value in locals_snapshot.items():
        if isinstance(value, bool):
            continue
        if key not in allowed_names:
            continue
        if isinstance(value, int) and 0 <= value < array_len:
            pointers[key] = value
    return pointers


def _fmt_value(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 40 else text[:37] + "..."


def _fmt_args(locals_snapshot: dict[str, Any]) -> str:
    items = [f"{k}={_fmt_value(v)}" for k, v in locals_snapshot.items() if not k.startswith("__")]
    return ", ".join(items)


# --------------------------------------------------------------------------
# Line classification (for operation type + plain-English description)
# --------------------------------------------------------------------------

_LOOP_RE = re.compile(r"^\s*(for|while)\b")
_FOR_HEADER_RE = re.compile(r"^\s*for\s+([\w, ]+?)\s+in\s+(.+?):\s*$")
_COMPARISON_RE = re.compile(r"(==|!=|<=|>=|(?<![=<>])<(?!=)|(?<![=<>])>(?!=))")
_ASSIGN_RE = re.compile(r"(?<![=<>!])=(?!=)")
_INDEX_RE = re.compile(r"\w+\s*\[")

_SAFE_BUILTINS = {"len": len, "range": range, "int": int, "min": min, "max": max}


def _safe_eval(expr: str, mapping: dict[str, Any]) -> Any:
    try:
        return eval(expr, {"__builtins__": _SAFE_BUILTINS}, mapping)  # noqa: S307
    except Exception:  # noqa: BLE001
        return None


def _estimate_loop_total(header_text: str, iterable_expr: str, mapping: dict[str, Any]) -> int | None:
    iterable_expr = iterable_expr.strip()
    range_match = re.match(r"^range\((.+)\)$", iterable_expr)
    if range_match:
        args_text = range_match.group(1)
        parts = [p.strip() for p in args_text.split(",")]
        values = [_safe_eval(p, mapping) for p in parts]
        if all(isinstance(v, int) for v in values):
            try:
                return len(range(*values))
            except Exception:  # noqa: BLE001
                return None
        return None
    value = _safe_eval(iterable_expr, mapping)
    if isinstance(value, (list, tuple, str)):
        return len(value)
    return None


def _classify_line(
    event: str,
    line_text: str,
    func_name: str,
    variables: dict[str, Any],
    array_name: str | None,
    return_value: Any,
    caller_name: str | None,
) -> tuple[str, str, dict | None, dict | None]:
    """Returns (operation, description, loop_info_partial, call_info)."""
    if event == "call":
        args = _fmt_args(variables)
        desc = f"Calling {func_name}({args})" + (f" from {caller_name}()" if caller_name else "")
        return "CALL", desc, None, {"function": func_name, "args": {k: _json_safe(v) for k, v in variables.items()}}

    if event == "return":
        desc = f"{func_name}() returns {_fmt_value(return_value)}"
        return "RETURN", desc, None, {"function": func_name, "value": _json_safe(return_value)}

    stripped = line_text.strip()
    if not stripped:
        return "EXEC", "(blank line)", None, None

    if _LOOP_RE.match(stripped):
        for_match = _FOR_HEADER_RE.match(stripped)
        loop_var = None
        if for_match:
            loop_var = for_match.group(1).strip()
        desc = f"Loop header: {stripped}"
        return "LOOP", desc, {"var": loop_var, "header": stripped}, None

    has_comparison = bool(_COMPARISON_RE.search(stripped))
    is_conditional = stripped.startswith(("if ", "elif ", "while ")) or stripped in ("else:",)
    if has_comparison and (is_conditional or "=" not in stripped):
        return "COMPARE", f"Comparing: {stripped}", None, None

    if _ASSIGN_RE.search(stripped):
        target = stripped.split("=")[0].strip()
        if array_name and array_name in target:
            return "WRITE", f"Updating {target} → {stripped}", None, None
        return "WRITE", f"Updating variable: {stripped}", None, None

    if _INDEX_RE.search(stripped):
        return "READ", f"Reading value: {stripped}", None, None

    if stripped.startswith("return"):
        return "RETURN", f"Preparing return: {stripped}", None, None

    return "EXEC", stripped, None, None


# --------------------------------------------------------------------------
# Python execution trace (real)
# --------------------------------------------------------------------------

def _run_traced(code: str) -> tuple[list[dict[str, Any]], str, str | None]:
    frames: list[dict[str, Any]] = []
    step_count = {"n": 0}
    error: str | None = None
    source_lines = code.splitlines()
    loop_hit_counts: dict[tuple[int, int], int] = {}
    known_loop_vars: set[str] = set()

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != "<graphmind-traced>":
            return tracer

        if event in ("line", "call", "return"):
            step_count["n"] += 1
            if step_count["n"] > MAX_STEPS:
                raise ExecutionLimitError(
                    f"Execution exceeded {MAX_STEPS} traced steps; possible infinite loop."
                )

            call_stack = []
            f = frame
            while f is not None:
                if f.f_code.co_filename == "<graphmind-traced>":
                    call_stack.append(f.f_code.co_name)
                f = f.f_back
            call_stack.reverse()
            caller_name = call_stack[-2] if len(call_stack) >= 2 else None

            local_items = {k: v for k, v in frame.f_locals.items() if not k.startswith("__")}
            array_name, array_state = _pick_array_state(local_items)
            pointers = _pick_pointers(local_items, len(array_state), known_loop_vars)
            variables = {k: _json_safe(v) for k, v in local_items.items() if not _is_array_like(v)}

            lineno = frame.f_lineno
            line_text = source_lines[lineno - 1] if 0 < lineno <= len(source_lines) else ""

            operation, description, loop_partial, call_info = _classify_line(
                event, line_text, frame.f_code.co_name, local_items, array_name, arg, caller_name
            )

            loop_info = None
            if operation == "LOOP":
                key = (id(frame), lineno)
                loop_hit_counts[key] = loop_hit_counts.get(key, 0) + 1
                iteration = loop_hit_counts[key]
                total = None
                loop_var = loop_partial.get("var") if loop_partial else None
                if loop_var:
                    known_loop_vars.add(loop_var)
                if loop_partial and loop_partial.get("header"):
                    for_match = _FOR_HEADER_RE.match(loop_partial["header"])
                    if for_match:
                        total = _estimate_loop_total(
                            loop_partial["header"], for_match.group(2), local_items
                        )
                if total is not None and iteration > total:
                    # CPython re-visits the for-header line once more to
                    # detect StopIteration; that revisit isn't a real
                    # iteration, so report it as the loop exiting instead.
                    operation = "EXEC"
                    description = f"Loop '{loop_var}' finished ({total} iterations)"
                else:
                    loop_info = {"var": loop_var, "iteration": iteration, "total": total}
                    if loop_var:
                        total_txt = f" of {total}" if total else ""
                        description = f"Loop '{loop_var}' — iteration {iteration}{total_txt}"

            frames.append({
                "step": step_count["n"],
                "activeLine": lineno,
                "event": event,
                "operation": operation,
                "description": f"Step {step_count['n']}: {description}",
                "callStack": call_stack,
                "variables": variables,
                "arrayName": array_name,
                "arrayState": _json_safe(array_state),
                "pointers": pointers,
                "loop": loop_info,
                "callInfo": call_info,
            })
        return tracer

    compiled = None
    try:
        compiled = compile(code, "<graphmind-traced>", "exec")
    except SyntaxError as exc:
        return frames, "", f"SyntaxError: {exc}"

    exec_globals: dict[str, Any] = {"__name__": "__main__"}

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    old_trace = sys.gettrace()
    try:
        sys.settrace(tracer)
        exec(compiled, exec_globals)
    except ExecutionLimitError as exc:
        error = str(exc)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    finally:
        sys.settrace(old_trace)
        stdout_text = sys.stdout.getvalue()
        sys.stdout = old_stdout

    return frames, stdout_text, error


def trace_execution(code: str, language: str) -> dict[str, Any]:
    """Return a step-by-step execution trace for `code`.

    Shape:
        {
          "supported": bool, "message": str | None,
          "frames": [{step, activeLine, event, operation, description,
                      callStack, variables, arrayName, arrayState,
                      pointers, loop, callInfo}, ...],
          "stdout": str, "error": str | None,
        }
    """
    lang = (language or "").strip().lower()
    if lang not in SUPPORTED_EXECUTION_LANGUAGES:
        return {
            "supported": False,
            "message": (
                f"Live execution tracing for '{language}' isn't wired up in this "
                "build (it requires a real per-language debugger/interpreter, e.g. "
                "gdb for C/C++, JDWP for Java, or Delve for Go). Python is fully "
                "supported. The editor and structural parser still work for this "
                "language."
            ),
            "frames": [], "stdout": "", "error": None,
        }

    frames, stdout_text, error = _run_traced(code)
    return {"supported": True, "message": None, "frames": frames, "stdout": stdout_text, "error": error}


# --------------------------------------------------------------------------
# Empirical Big-O benchmark engine (real, Python only)
# --------------------------------------------------------------------------

_REFERENCE_MODELS: dict[str, Any] = {
    "O(1)": lambda n: 1.0,
    "O(log N)": lambda n: math.log2(max(n, 2)),
    "O(N)": lambda n: float(n),
    "O(N log N)": lambda n: n * math.log2(max(n, 2)),
    "O(N^2)": lambda n: float(n) ** 2,
    "O(N^3)": lambda n: float(n) ** 3,
}


def _classify_growth(n_values: list[int], step_counts: list[int]) -> str:
    best_model = "O(N)"
    best_score = float("inf")
    for name, f in _REFERENCE_MODELS.items():
        ratios = []
        for n, steps in zip(n_values, step_counts):
            denom = f(n)
            if denom <= 0:
                continue
            ratios.append(steps / denom)
        if len(ratios) < 2:
            continue
        mean = sum(ratios) / len(ratios)
        if mean <= 0:
            continue
        variance = sum((r - mean) ** 2 for r in ratios) / len(ratios)
        coeff_of_variation = math.sqrt(variance) / mean
        if coeff_of_variation < best_score:
            best_score = coeff_of_variation
            best_model = name
    return best_model


def run_complexity_benchmark(code: str, language: str) -> dict[str, Any]:
    lang = (language or "").strip().lower()
    if lang not in SUPPORTED_EXECUTION_LANGUAGES:
        return {
            "supported": False,
            "message": (
                f"The empirical Big-O benchmark currently only executes Python "
                f"('{language}' isn't run in this build)."
            ),
            "n_values": [], "step_counts": [], "estimated_big_o": None, "error": None,
        }

    n_values: list[int] = []
    step_counts: list[int] = []
    error: str | None = None

    for n in BENCHMARK_N_VALUES:
        step_count = {"n": 0}

        def tracer(frame, event, arg, _step_count=step_count):
            if frame.f_code.co_filename != "<graphmind-benchmark>":
                return tracer
            if event == "line":
                _step_count["n"] += 1
                if _step_count["n"] > COMPLEXITY_STEP_CAP:
                    raise ExecutionLimitError("step cap exceeded")
            return tracer

        try:
            compiled = compile(code, "<graphmind-benchmark>", "exec")
        except SyntaxError as exc:
            error = f"SyntaxError: {exc}"
            break

        exec_globals: dict[str, Any] = {"__name__": "__main__", "n": n, "N": n}
        old_trace = sys.gettrace()
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        start = time.perf_counter()
        try:
            sys.settrace(tracer)
            exec(compiled, exec_globals)
        except ExecutionLimitError:
            sys.settrace(old_trace)
            sys.stdout = old_stdout
            error = f"Stopped benchmarking at N={n}: exceeded {COMPLEXITY_STEP_CAP} steps."
            break
        except Exception as exc:  # noqa: BLE001
            sys.settrace(old_trace)
            sys.stdout = old_stdout
            error = f"{type(exc).__name__}: {exc} (while benchmarking N={n})"
            break
        finally:
            sys.settrace(old_trace)
            sys.stdout = old_stdout
        elapsed = time.perf_counter() - start

        n_values.append(n)
        step_counts.append(step_count["n"])

        if elapsed > 2.0:
            break

    estimated = _classify_growth(n_values, step_counts) if len(n_values) >= 2 else None

    return {
        "supported": True, "message": None,
        "n_values": n_values, "step_counts": step_counts,
        "estimated_big_o": estimated, "error": error,
    }
