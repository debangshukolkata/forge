"""LangGraph extractor (spec §11.3): StateGraph, nodes, edges, conditional routing, compile."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from forge.kb.python_index import ModuleFacts, dotted, string_value


@dataclass
class GraphFact:
    variable: str
    state_type: str
    state_fields: list[str]
    nodes: list[tuple[str, str]] = field(default_factory=list)  # (node name, function)
    edges: list[tuple[str, str]] = field(default_factory=list)
    conditional: list[tuple[str, str, dict[str, str]]] = field(
        default_factory=list
    )  # (source, router, mapping)
    compiled: bool = False
    builder: str = ""  # enclosing function, e.g. build_triage_graph
    path: str = ""
    line: int = 0


def extract_graphs(modules: list[ModuleFacts]) -> list[GraphFact]:
    graphs = []
    for facts in modules:
        typed_dicts = _typed_dicts(facts)
        for scope in [facts.tree, *[n for n in ast.walk(facts.tree) if isinstance(n, ast.FunctionDef)]]:
            graphs += _graphs_in(scope, facts, typed_dicts)
    return graphs


def _graphs_in(scope: ast.AST, facts: ModuleFacts, typed_dicts: dict[str, list[str]]) -> list[GraphFact]:
    graphs: dict[str, GraphFact] = {}
    body = scope.body if isinstance(scope, ast.Module | ast.FunctionDef) else []
    for statement in body:
        if not (isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call)):
            continue
        if dotted(statement.value.func).split(".")[-1] != "StateGraph":
            continue
        if not isinstance(statement.targets[0], ast.Name):
            continue
        state = ast.unparse(statement.value.args[0]) if statement.value.args else ""
        graphs[statement.targets[0].id] = GraphFact(
            variable=statement.targets[0].id,
            state_type=state,
            state_fields=typed_dicts.get(state, []),
            builder=scope.name if isinstance(scope, ast.FunctionDef) else "",
            path=facts.path,
            line=statement.lineno,
        )
    for node in ast.walk(scope) if graphs else []:
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        graph = graphs.get(dotted(node.func.value))
        if graph is None:
            continue
        method, args = node.func.attr, node.args
        if method == "add_node" and args:
            name = string_value(args[0]) or ast.unparse(args[0])
            graph.nodes.append((name, ast.unparse(args[1]) if len(args) > 1 else name))
        elif method == "add_edge" and len(args) == 2:
            graph.edges.append((_endpoint(args[0]), _endpoint(args[1])))
        elif method == "add_conditional_edges" and len(args) >= 2:
            mapping: dict[str, str] = {}
            if len(args) > 2 and isinstance(args[2], ast.Dict):
                mapping = {
                    ast.unparse(k).strip("'\""): _endpoint(v)
                    for k, v in zip(args[2].keys, args[2].values, strict=True)
                    if k
                }
            graph.conditional.append((_endpoint(args[0]), ast.unparse(args[1]), mapping))
        elif method in ("set_entry_point", "set_finish_point") and args:
            edge = (
                ("START", _endpoint(args[0])) if method == "set_entry_point" else (_endpoint(args[0]), "END")
            )
            graph.edges.append(edge)
        elif method == "compile":
            graph.compiled = True
    return list(graphs.values())


def _endpoint(node: ast.expr) -> str:
    return string_value(node) or ast.unparse(node)


def _typed_dicts(facts: ModuleFacts) -> dict[str, list[str]]:
    found = {}
    for node in ast.walk(facts.tree):
        if isinstance(node, ast.ClassDef) and any(
            ast.unparse(b).endswith(("TypedDict", "BaseModel")) for b in node.bases
        ):
            found[node.name] = [
                f"{item.target.id}: {ast.unparse(item.annotation)}"
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            ]
    return found
