"""Tree-sitter source-to-graph parser for the GraphMind editor languages."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tree_sitter_language_pack import get_parser, init

_CACHE_DIR = os.environ.get(
    "TREE_SITTER_CACHE_DIR",
    str(Path(__file__).resolve().parents[1] / ".tree-sitter-cache"),
)
init({"cache_dir": _CACHE_DIR})

_ALIASES = {"py": "python", "js": "javascript", "ts": "typescript", "c++": "cpp", "golang": "go"}
_LANGUAGES = {"python", "javascript", "typescript", "cpp", "java", "c", "go", "r"}

# Tree-sitter node names vary by grammar, so the mapping is explicit and keeps
# the output categories stable for the frontend.
_CATEGORIES: dict[str, str] = {}
for _category, _types in {
    "function": ("function_definition", "function_declaration", "function_item", "method_definition", "method_declaration", "function"),
    "class": ("class_definition", "class_declaration", "class_specifier", "struct_item", "interface_declaration", "struct_declaration"),
    "loop": ("for_statement", "for_in_statement", "for_expression", "while_statement", "while_expression", "do_statement"),
    "condition": ("if_statement", "if_expression", "elif_clause", "else_clause", "switch_statement", "match_statement", "try_statement", "catch_clause", "except_clause"),
    "variable": ("assignment", "assignment_expression", "augmented_assignment", "short_var_declaration", "variable_declaration", "lexical_declaration", "const_declaration"),
    "call": ("call", "call_expression", "method_invocation"),
    "return": ("return_statement",),
    "import": ("import_statement", "import_from_statement", "import_declaration", "preproc_include", "use_declaration"),
}.items():
    _CATEGORIES.update({node_type: _category for node_type in _types})

_DECLARATIONS = {"function", "class"}


def _language(language: str) -> str:
    name = _ALIASES.get((language or "").strip().lower(), (language or "").strip().lower())
    if name not in _LANGUAGES:
        raise ValueError(f"Unsupported language '{language}'. Supported: {sorted(_LANGUAGES)}")
    return name


def _value(node: Any, name: str) -> Any:
    value = getattr(node, name)
    return value() if callable(value) else value


def _children(node: Any, named: bool = False) -> list[Any]:
    attribute = "named_children" if named else "children"
    if hasattr(node, attribute):
        result = _value(node, attribute)
        return list(result)
    count_name = "named_child_count" if named else "child_count"
    child_name = "named_child" if named else "child"
    count = int(_value(node, count_name))
    child_accessor = getattr(node, child_name)
    return [child_accessor(index) for index in range(count)]


def _node_type(node: Any) -> str:
    return str(_value(node, "type" if hasattr(node, "type") else "kind"))


def _point(node: Any, kind: str) -> tuple[int, int]:
    point_name = "start_point" if kind == "start" else "end_point"
    position_name = "start_position" if kind == "start" else "end_position"
    point = _value(node, point_name) if hasattr(node, point_name) else _value(node, position_name)
    if isinstance(point, (tuple, list)):
        return int(point[0]), int(point[1])
    row = _value(point, "row") if hasattr(point, "row") else _value(point, "line")
    column = _value(point, "column")
    return int(row), int(column)


def _text(node: Any, source: bytes) -> str:
    start, end = int(_value(node, "start_byte")), int(_value(node, "end_byte"))
    return source[start:end].decode("utf-8", errors="replace")


def _identifier_names(node: Any, source: bytes) -> list[str]:
    identifier_types = {"identifier", "field_identifier", "property_identifier", "type_identifier", "name"}
    if _node_type(node) in identifier_types:
        return [_text(node, source).strip()]
    names: list[str] = []
    for child in _children(node):
        names.extend(_identifier_names(child, source))
    return names


def _field(node: Any, name: str) -> Any | None:
    try:
        return node.child_by_field_name(name)
    except AttributeError:
        return None


def _declaration_name(node: Any, source: bytes) -> str | None:
    # Most grammars expose a `name` field; C/C++ instead use a declarator
    # subtree, whose first identifier is the function being declared.
    name_node = _field(node, "name")
    if name_node is not None:
        names = _identifier_names(name_node, source)
        if names: return names[0]
    declarator = _field(node, "declarator")
    if declarator is not None:
        names = _identifier_names(declarator, source)
        if names: return names[0]
    names = _identifier_names(node, source)
    return names[0] if names else None


def _call_name(node: Any, source: bytes) -> str | None:
    """Resolve the callee name without mistaking a receiver for a method."""
    callee = None
    for field in ("function", "name"):
        callee = _field(node, field)
        if callee is not None:
            break
    if callee is None:
        callee = next((child for child in _children(node, named=True) if _node_type(child) not in {"arguments", "argument_list"}), None)
    if callee is None:
        return None
    names = _identifier_names(callee, source)
    return names[-1].split(".")[-1] if names else None


def parse_code_to_graph(code: str, language: str) -> dict[str, Any]:
    lang = _language(language)
    source = code.encode("utf-8")
    parser = get_parser(lang)
    try:
        tree = parser.parse(code)
    except TypeError:
        tree = parser.parse(source)
    root = _value(tree, "root_node")
    lines = max(1, len(code.splitlines()))
    nodes: list[dict[str, Any]] = [{
        "id": "n1", "type": "module", "category": "module", "label": "module",
        "startLine": 1, "endLine": lines,
    }]
    edges: list[dict[str, Any]] = []
    declarations: dict[str, str] = {}
    calls: list[tuple[str, str]] = []
    next_sibling: dict[str, str] = {}
    node_count = 0

    def add_edge(source_id: str, target_id: str, kind: str) -> None:
        edges.append({"id": f"e{len(edges) + 1}", "source": source_id, "target": target_id, "type": kind})

    def visit(node: Any, parent_id: str, owner_id: str) -> None:
        nonlocal node_count
        category = _CATEGORIES.get(_node_type(node))
        current_id, current_owner = parent_id, owner_id
        if category:
            # Bound graph size for large imported files while preserving parse status.
            if node_count >= 2_000:
                return
            node_count += 1
            current_id = f"n{len(nodes) + 1}"
            label = " ".join(_text(node, source).split())
            nodes.append({
                "id": current_id, "type": category, "category": category,
                "label": label[:60] or _node_type(node),
                "startLine": _point(node, "start")[0] + 1,
                "endLine": max(_point(node, "start")[0] + 1, _point(node, "end")[0] + (1 if _point(node, "end")[1] else 0)),
            })
            if category == "import":
                add_edge(parent_id, current_id, "import")
            else:
                add_edge(parent_id, current_id, "child")
            previous = next_sibling.get(parent_id)
            if previous:
                add_edge(previous, current_id, "flow")
            next_sibling[parent_id] = current_id
            if category in _DECLARATIONS:
                name = _declaration_name(node, source)
                if name:
                    declarations[name] = current_id
                current_owner = current_id
            elif category == "call":
                name = _call_name(node, source)
                if name:
                    calls.append((current_id, name))
        for child in _children(node):
            visit(child, current_id, current_owner)

    visit(root, "n1", "n1")
    for call_id, name in calls:
        target_id = declarations.get(name)
        if target_id and target_id != call_id:
            add_edge(call_id, target_id, "call")
    return {"nodes": nodes, "edges": edges, "hasError": bool(_value(root, "has_error"))}
