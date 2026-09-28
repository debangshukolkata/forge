"""flask-smorest extractor (spec §11.3): blueprints, routes, MethodViews, schemas, registrations."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from forge.kb.python_index import ModuleFacts, dotted, string_value

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


@dataclass
class BlueprintFact:
    variable: str
    name: str
    url_prefix: str
    module: str
    path: str
    line: int
    registered_in: list[str] = field(default_factory=list)  # "module:line"


@dataclass
class Endpoint:
    method: str
    path: str
    blueprint: str
    view: str
    style: str  # MethodView | function
    arguments: list[str] = field(default_factory=list)  # "ClaimQuerySchema (query)"
    responses: list[str] = field(default_factory=list)  # "200 ClaimPageSchema"
    other_decorators: list[str] = field(default_factory=list)  # e.g. auth
    file: str = ""
    line: int = 0


def extract_blueprints(modules: list[ModuleFacts]) -> list[BlueprintFact]:
    found = []
    for facts in modules:
        for node in facts.tree.body:
            if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
                continue
            if dotted(node.value.func).split(".")[-1] != "Blueprint" or not isinstance(
                node.targets[0], ast.Name
            ):
                continue
            call = node.value
            name = string_value(call.args[0], facts.constants) if call.args else None
            prefix = next(
                (string_value(k.value, facts.constants) for k in call.keywords if k.arg == "url_prefix"), ""
            )
            found.append(
                BlueprintFact(
                    node.targets[0].id,
                    name or node.targets[0].id,
                    prefix or "",
                    facts.module,
                    facts.path,
                    node.lineno,
                )
            )
    _find_registrations(modules, found)
    return found


def _find_registrations(modules: list[ModuleFacts], blueprints: list[BlueprintFact]) -> None:
    for facts in modules:
        for node in ast.walk(facts.tree):
            if not (
                isinstance(node, ast.Call) and dotted(node.func).endswith("register_blueprint") and node.args
            ):
                continue
            alias = dotted(node.args[0])
            imported = facts.imported_as(alias)
            source = resolve_import(facts, imported.module) if imported else None
            for blueprint in blueprints:
                same_module = blueprint.module == facts.module and blueprint.variable == alias
                via_import = (
                    imported is not None
                    and imported.name == blueprint.variable
                    and source == blueprint.module
                )
                if same_module or via_import:
                    blueprint.registered_in.append(f"{facts.path}:{node.lineno}")


def resolve_import(facts: ModuleFacts, module: str) -> str:
    """Absolute dotted module for an import made in facts (handles `from .routes import blp`)."""
    if not module.startswith("."):
        return module
    level = len(module) - len(module.lstrip("."))
    package = facts.module.split(".")
    if not facts.path.endswith("__init__.py"):
        package = package[:-1]  # a plain module's package is its parent
    base = package[: len(package) - (level - 1)] if level > 1 else package
    rest = module.lstrip(".")
    return ".".join([*base, rest] if rest else base)


def extract_endpoints(modules: list[ModuleFacts], blueprints: list[BlueprintFact]) -> list[Endpoint]:
    by_module = {(b.module, b.variable): b for b in blueprints}
    endpoints: list[Endpoint] = []
    for facts in modules:
        for node in facts.tree.body:
            if not isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for decorator in node.decorator_list:
                route = _route(decorator, facts, by_module)
                if route is None:
                    continue
                blueprint, route_path, methods = route
                full_path = (blueprint.url_prefix.rstrip("/") + "/" + route_path.lstrip("/")) or "/"
                if isinstance(node, ast.ClassDef):
                    endpoints += _methodview_endpoints(node, blueprint, full_path, facts)
                else:
                    endpoints += [
                        _endpoint(node, method, full_path, blueprint, node.name, "function", facts)
                        for method in methods
                    ]
    return sorted(endpoints, key=lambda e: (e.path, HTTP_METHODS.index(e.method.lower())))


def _route(
    decorator: ast.expr, facts: ModuleFacts, by_module: dict[tuple[str, str], BlueprintFact]
) -> tuple[BlueprintFact, str, list[str]] | None:
    if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)):
        return None
    if decorator.func.attr != "route":
        return None
    variable = dotted(decorator.func.value)
    blueprint = by_module.get((facts.module, variable))
    if blueprint is None:
        return None
    path = string_value(decorator.args[0], facts.constants) if decorator.args else "/"
    methods = ["GET"]
    for keyword in decorator.keywords:
        if keyword.arg == "methods" and isinstance(keyword.value, ast.List | ast.Tuple):
            methods = [string_value(e) or "?" for e in keyword.value.elts]
    return blueprint, path or "/", methods


def _methodview_endpoints(
    node: ast.ClassDef, blueprint: BlueprintFact, path: str, facts: ModuleFacts
) -> list[Endpoint]:
    return [
        _endpoint(item, item.name.upper(), path, blueprint, f"{node.name}.{item.name}", "MethodView", facts)
        for item in node.body
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and item.name in HTTP_METHODS
    ]


def _endpoint(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    method: str,
    path: str,
    blueprint: BlueprintFact,
    view: str,
    style: str,
    facts: ModuleFacts,
) -> Endpoint:
    endpoint = Endpoint(
        method=method.upper(),
        path=path,
        blueprint=blueprint.name,
        view=view,
        style=style,
        file=facts.path,
        line=function.lineno,
    )
    for decorator in function.decorator_list:
        call = decorator if isinstance(decorator, ast.Call) else None
        target = dotted(call.func if call else decorator)
        if target == f"{blueprint.variable}.arguments" and call and call.args:
            location = next((string_value(k.value) for k in call.keywords if k.arg == "location"), "json")
            endpoint.arguments.append(f"{ast.unparse(call.args[0])} ({location})")
        elif target == f"{blueprint.variable}.response" and call and len(call.args) >= 2:
            endpoint.responses.append(f"{ast.unparse(call.args[0])} {ast.unparse(call.args[1])}")
        elif target == f"{blueprint.variable}.response" and call and call.args:
            endpoint.responses.append(ast.unparse(call.args[0]))
        elif not target.startswith(f"{blueprint.variable}."):
            endpoint.other_decorators.append(ast.unparse(decorator))
    return endpoint
