"""Short-lived JSON worker with restricted builtins and bounded output."""
from __future__ import annotations

import builtins
import io
import json
import math
import re
import sys
import os
from typing import Any

# Enforced inside the short-lived worker on Unix containers. Windows does not
# expose rlimit, so the parent timeout and Docker compose limits remain active.
if os.name != "nt":
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))


class LimitError(RuntimeError): pass


class LimitedOutput(io.StringIO):
    def __init__(self, maximum: int): super().__init__(); self.maximum, self.count = maximum, 0
    def write(self, value: str) -> int:
        self.count += len(value.encode("utf-8", errors="replace"))
        if self.count > self.maximum: raise LimitError(f"Output exceeded {self.maximum} bytes.")
        return super().write(value)


def safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)): return value
    if isinstance(value, (list, tuple)): return [safe(v) for v in value[:500]]
    if isinstance(value, dict): return {str(k): safe(v) for k, v in list(value.items())[:200]}
    return repr(value)[:200]


def execute(payload: dict[str, Any]) -> dict[str, Any]:
    code, lines = payload.get("code", ""), payload.get("code", "").splitlines()
    input_lines = iter(str(payload.get("input", "")).splitlines())
    output, frames, steps = LimitedOutput(int(payload.get("max_output", 64000))), [], 0
    def input_fn(prompt: str = "") -> str:
        if prompt: output.write(str(prompt))
        try: return next(input_lines)
        except StopIteration as exc: raise EOFError("GraphMind input exhausted") from exc
    names = "abs all any bool chr dict enumerate float int isinstance len list max min pow print range reversed round set sorted str sum tuple zip"
    allowed = {name: getattr(builtins, name) for name in names.split()}; allowed["input"] = input_fn
    env: dict[str, Any] = {"__name__": "__main__", "__builtins__": allowed}
    old_stdout, old_trace = sys.stdout, sys.gettrace()
    def tracer(frame, event, arg):
        nonlocal steps
        if frame.f_code.co_filename != "<graphmind-user>" or event not in ("call", "line", "return"): return tracer
        steps += 1
        if steps > int(payload.get("max_steps", 5000)): raise LimitError(f"Execution exceeded {payload.get('max_steps')} traced steps; possible infinite loop.")
        local = {k: v for k, v in frame.f_locals.items() if not k.startswith("__")}
        arrays = [(k,v) for k,v in local.items() if isinstance(v,(list,tuple)) and len(v)<=500]
        array_name, array = arrays[0] if arrays else (None, [])
        pointers = {k:v for k,v in local.items() if k in {"i","j","k","idx","index","left","right","low","high"} and isinstance(v,int) and 0<=v<len(array)}
        line = frame.f_lineno; text = lines[line-1].strip() if 0<line<=len(lines) else ""
        operation = "LOOP" if re.match(r"(for|while)\\b",text) else "COMPARE" if re.match(r"(if|elif|while)\\b",text) else "WRITE" if re.search(r"(?<![=!<>])=(?!=)",text) else "RETURN" if text.startswith("return") or event=="return" else "CALL" if event=="call" else "EXEC"
        stack=[]; current=frame
        while current:
            if current.f_code.co_filename=="<graphmind-user>": stack.append(current.f_code.co_name)
            current=current.f_back
        stack.reverse()
        frames.append({"step":steps,"activeLine":line,"event":event,"operation":operation,"description":f"Step {steps}: {text or event}","callStack":stack,"variables":{k:safe(v) for k,v in local.items() if not isinstance(v,(list,tuple))},"arrayName":array_name,"arrayState":safe(array),"pointers":pointers,"loop":None,"callInfo":{"function":frame.f_code.co_name,"value":safe(arg)} if event=="return" else None})
        return tracer
    try:
        compile(code,"<graphmind-user>","exec")
        sys.stdout=output; sys.settrace(tracer); exec(compile(code,"<graphmind-user>","exec"),env,env)
        return {"frames":frames,"stdout":output.getvalue(),"error":None}
    except SyntaxError as exc: return {"frames":[],"stdout":output.getvalue(),"error":f"SyntaxError: {exc.msg} (line {exc.lineno})"}
    except Exception as exc: return {"frames":frames,"stdout":output.getvalue(),"error":f"{type(exc).__name__}: {exc}"}
    finally: sys.settrace(old_trace); sys.stdout=old_stdout


def variation(values: list[float]) -> float:
    mean=sum(values)/len(values); return math.sqrt(sum((v-mean)**2 for v in values)/len(values))/mean if mean else float("inf")
def benchmark(payload: dict[str, Any]) -> dict[str, Any]:
    ns=[]; counts=[]
    for n in payload["n_values"]:
        result=execute({**payload,"code":f"n = {n}\nN = {n}\n"+payload["code"]})
        if result["error"]: return {"n_values":ns,"step_counts":counts,"estimated_big_o":None,"error":f"{result['error']} (while benchmarking N={n})"}
        ns.append(n); counts.append(len(result["frames"]))
    models={"O(1)":lambda n:1,"O(log N)":lambda n:math.log2(max(n,2)),"O(N)":lambda n:n,"O(N log N)":lambda n:n*math.log2(max(n,2)),"O(N^2)":lambda n:n*n,"O(N^3)":lambda n:n*n*n}
    return {"n_values":ns,"step_counts":counts,"estimated_big_o":min(models,key=lambda name:variation([c/models[name](n) for n,c in zip(ns,counts)])),"error":None}
def main() -> None:
    try:
        payload=json.loads(sys.stdin.read()); result=benchmark(payload) if payload.get("mode")=="complexity" else execute(payload)
    except Exception as exc: result={"error":f"WorkerError: {type(exc).__name__}: {exc}"}
    sys.__stdout__.write(json.dumps(result,ensure_ascii=True))
if __name__ == "__main__": main()
