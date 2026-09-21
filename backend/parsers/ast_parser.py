"""
AST -> graph conversion using Tree-sitter.

Given source code and a language name, parses the code with the appropriate
Tree-sitter grammar and walks the resulting syntax tree, emitting a node for
every syntactically "interesting" construct (functions, loops, conditionals,
variable assignments, calls, returns, imports, classes) plus edges that
capture both the parent-child structure of the tree and the top-level
sequential "flow" between sibling statements.

Public API:
    parse_code_to_graph(code: str, language: str) -> dict
        Returns {"nodes": [...], "edges": [...]} or raises ValueError for
        unsupported languages / a SyntaxError-ish dict on parse failure.
"""
from __future__ import annotations

from typing import Any

from tree_sitter_languages import get_parser

# Map our public language identifiers to tree-sitter grammar names.
_LANGUAGE_ALIASES = {
    "python": "python",
    "py": "python",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "c++": "cpp",
    "cpp": "cpp",
    "java": "java",
    "c": "c",
    "go": "go",
    "golang": "go",
    "r": "r",
}

# Node types we consider "interesting" enough to surface as a graph node,
# grouped into a coarse category used for frontend styling/coloring.
_CATEGORY_BY_NODE_TYPE = {
    # functions / defs
    "function_definition": "function",
    "function_declaration": "function",
    "arrow_function": "function",
    "method_definition": "function",
    "lambda": "function",
    # classes
    "class_definition": "class",
    "class_declaration": "class",
    # loops
    "for_statement": "loop",
    "for_in_statement": "loop",
    "while_statement": "loop",
    "do_statement": "loop",
    # conditionals
    "if_statement": "condition",
    "elif_clause": "condition",
    "else_clause": "condition",
    "conditional_expression": "condition",
    "switch_statement": "condition",
    "try_statement": "condition",
    "except_clause": "condition",
    # variables / assignment
    "assignment": "variable",
    "augmented_assignment": "variable",
    "variable_declarator": "variable",
    "variable_declaration": "variable",
    "lexical_declaration": "variable",
    # calls
    "call": "call",
    "call_expression": "call",
    # returns
    "return_statement": "return",
    # imports
    "import_statement": "import",
    "import_from_statement": "import",
    "import_declaration": "import",
    "import_spec": "import",
    "preproc_include": "import",
    # C/C++/Java/Go additions
    "method_declaration": "function",
    "constructor_declaration": "function",
    "func_literal": "function",
    "class_specifier": "class",
    "struct_specifier": "class",
    "interface_declaration": "class",
    "declaration": "variable",
    "init_declarator": "variable",
    "short_var_declaration": "variable",
    "local_variable_declaration": "variable",
    "field_declaration": "variable",
}

NODE_TYPES_OF_INTEREST = set(_CATEGORY_BY_NODE_TYPE.keys())


def _resolve_language(language: str) -> str:
    key = (language or "").strip().lower()
    if key not in _LANGUAGE_ALIASES:
        supported = sorted(set(_LANGUAGE_ALIASES.values()))
        raise ValueError(
            f"Unsupported language '{language}'. Supported: {supported}"
        )
    return _LANGUAGE_ALIASES[key]


def _node_label(node, source_bytes: bytes) -> str:
    """Best-effort short human-readable label for a syntax node."""
    text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    first_line = text.strip().splitlines()[0] if text.strip() else node.type
    if len(first_line) > 60:
        first_line = first_line[:57] + "..."
    return first_line


def parse_code_to_graph(code: str, language: str) -> dict[str, Any]:
    """Parse `code` (written in `language`) into a {nodes, edges} graph."""
    lang_name = _resolve_language(language)
    parser = get_parser(lang_name)
    source_bytes = code.encode("utf-8")

    tree = parser.parse(source_bytes)
    root = tree.root_node

    if root.has_error:
        # Still attempt to extract whatever partial structure we can, but
        # flag it so the frontend can show a "syntax error" banner.
        partial = _walk(root, source_bytes)
        partial["hasError"] = True
        return partial

    result = _walk(root, source_bytes)
    result["hasError"] = False
    return result


def _walk(root, source_bytes: bytes) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    counter = {"n": 0}

    def next_id() -> str:
        counter["n"] += 1
        return f"n{counter['n']}"

    # id assigned to the nearest interesting ancestor, used to attach edges
    root_id = next_id()
    nodes.append({
        "id": root_id,
        "type": "module",
        "category": "module",
        "label": "module",
        "startLine": root.start_point[0] + 1,
        "endLine": root.end_point[0] + 1,
    })

    def recurse(ts_node, parent_graph_id: str, prev_sibling_id: dict[str, str | None]):
        for child in ts_node.children:
            local_prev_ref = {"id": None}
            if child.type in NODE_TYPES_OF_INTEREST:
                node_id = next_id()
                category = _CATEGORY_BY_NODE_TYPE[child.type]
                nodes.append({
                    "id": node_id,
                    "type": child.type,
                    "category": category,
                    "label": _node_label(child, source_bytes),
                    "startLine": child.start_point[0] + 1,
                    "endLine": child.end_point[0] + 1,
                })
                # structural edge: parent -> child
                edges.append({
                    "id": f"e{len(edges) + 1}",
                    "source": parent_graph_id,
                    "target": node_id,
                    "type": "child",
                })
                # sequential flow edge between siblings at this depth
                if prev_sibling_id["id"] is not None:
                    edges.append({
                        "id": f"e{len(edges) + 1}",
                        "source": prev_sibling_id["id"],
                        "target": node_id,
                        "type": "flow",
                    })
                prev_sibling_id["id"] = node_id
                recurse(child, node_id, {"id": None})
            else:
                recurse(child, parent_graph_id, prev_sibling_id)

    recurse(root, root_id, {"id": None})
    return {"nodes": nodes, "edges": edges}
