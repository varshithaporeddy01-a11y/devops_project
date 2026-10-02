"""Offline source-to-graph parser.

Python uses its authoritative standard-library AST. Other supported languages
receive a conservative structural graph from line-level syntax recognition;
this keeps parsing available without downloading native grammar binaries at
runtime and never pretends that a heuristic graph is executable.
"""
from __future__ import annotations

import ast
import re
from typing import Any

_ALIASES = {"py":"python", "js":"javascript", "ts":"typescript", "c++":"cpp", "golang":"go"}
_LANGUAGES = {"python", "javascript", "typescript", "cpp", "java", "c", "go", "r"}
_PATTERNS = [
    ("import", re.compile(r"^\s*(import|from|#include|package)\b")),
    ("class", re.compile(r"^\s*(class|struct|interface)\b")),
    ("function", re.compile(r"^\s*(def|func|function)\b|\w+\s+\w+\s*\([^)]*\)\s*\{|<-\s*function")),
    ("loop", re.compile(r"^\s*(for|while|do)\b")),
    ("condition", re.compile(r"^\s*(if|elif|else|switch|try|catch|except)\b")),
    ("return", re.compile(r"^\s*(return|break|continue)\b")),
    ("variable", re.compile(r"\b(let|const|var|int|float|double|char|string|boolean)\b|<-|(?<![=!<>])=(?!=)")),
    ("call", re.compile(r"\b\w+\s*\(")),
]


def _language(language: str) -> str:
    name = _ALIASES.get((language or "").strip().lower(), (language or "").strip().lower())
    if name not in _LANGUAGES:
        raise ValueError(f"Unsupported language '{language}'. Supported: {sorted(_LANGUAGES)}")
    return name


def _base() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return ([{"id":"n1","type":"module","category":"module","label":"module","startLine":1,"endLine":1}], [])


def _add(nodes: list[dict], edges: list[dict], category: str, label: str, start: int, end: int, parent="n1") -> str:
    node_id=f"n{len(nodes)+1}"; nodes.append({"id":node_id,"type":category,"category":category,"label":label[:60],"startLine":start,"endLine":end})
    edges.append({"id":f"e{len(edges)+1}","source":parent,"target":node_id,"type":"child"})
    siblings=[edge["target"] for edge in edges[:-1] if edge["source"]==parent and edge["type"]=="child"]
    if siblings: edges.append({"id":f"e{len(edges)+1}","source":siblings[-1],"target":node_id,"type":"flow"})
    return node_id


def _python(code: str) -> dict[str, Any]:
    nodes, edges = _base()
    try: tree=ast.parse(code)
    except SyntaxError: return _heuristic(code, True)
    end=max(1, len(code.splitlines())); nodes[0]["endLine"]=end
    categories={ast.FunctionDef:"function",ast.AsyncFunctionDef:"function",ast.ClassDef:"class",ast.For:"loop",ast.While:"loop",ast.If:"condition",ast.Try:"condition",ast.Assign:"variable",ast.AnnAssign:"variable",ast.AugAssign:"variable",ast.Call:"call",ast.Return:"return",ast.Import:"import",ast.ImportFrom:"import"}
    def visit(node: ast.AST, parent: str="n1") -> None:
        category=next((v for k,v in categories.items() if isinstance(node,k)),None)
        next_parent=parent
        if category:
            label=ast.get_source_segment(code,node) or type(node).__name__
            next_parent=_add(nodes,edges,category,label,(getattr(node,"lineno",1)),getattr(node,"end_lineno",getattr(node,"lineno",1)),parent)
        for child in ast.iter_child_nodes(node): visit(child,next_parent)
    visit(tree)
    return {"nodes":nodes,"edges":edges,"hasError":False}


def _heuristic(code: str, has_error: bool=False) -> dict[str, Any]:
    nodes, edges = _base(); lines=code.splitlines(); nodes[0]["endLine"]=max(1,len(lines))
    for index,line in enumerate(lines,1):
        stripped=line.strip()
        if not stripped or stripped.startswith(("//","# ")): continue
        for category,pattern in _PATTERNS:
            if pattern.search(stripped): _add(nodes,edges,category,stripped,index,index); break
    return {"nodes":nodes,"edges":edges,"hasError":has_error}


def parse_code_to_graph(code: str, language: str) -> dict[str, Any]:
    return _python(code) if _language(language)=="python" else _heuristic(code)
