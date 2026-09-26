from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from flowgraph.graph.model import Diagnostic, Edge, Graph, Node


IGNORED_DIRECTORIES = {
    ".flowgraph",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    ".svn",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
    "venv",
}
BUILTIN_NAMES = frozenset(dir(builtins))


class AnalysisError(RuntimeError):
    """Raised when a repository cannot be analyzed safely."""


@dataclass(frozen=True, slots=True)
class ImportBinding:
    kind: str
    module: str
    symbol: str | None = None
    line: int | None = None
    function_local: bool = False


@dataclass(slots=True)
class Symbol:
    node: Node
    module: str
    syntax: ast.FunctionDef | ast.AsyncFunctionDef
    class_qualname: str | None
    enclosing_functions: tuple[str, ...]
    imports: dict[str, ImportBinding]
    shadowed_names: set[str]


@dataclass(slots=True)
class ModuleInfo:
    name: str
    file: str
    is_package: bool
    tree: ast.Module
    imports: dict[str, ImportBinding]
    shadowed_names: set[str]


class _DefinitionCollector(ast.NodeVisitor):
    def __init__(self, file: str, module: str) -> None:
        self.file = file
        self.module = module
        self.scope: list[str] = []
        self.scope_kinds: list[str] = []
        self.classes: list[str] = []
        self.functions: list[str] = []
        self.symbols: list[Symbol] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.scope_kinds.append("class")
        self.classes.append(".".join(self.scope))
        for statement in node.body:
            self.visit(statement)
        self.classes.pop()
        self.scope_kinds.pop()
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        qualname = ".".join((*self.scope, node.name))
        kind = "method" if self.scope_kinds and self.scope_kinds[-1] == "class" else "function"
        if isinstance(node, ast.AsyncFunctionDef) and kind == "function":
            kind = "async_function"
        graph_node = Node(
            id=f"{self.file}:{qualname}",
            name=node.name,
            qualname=qualname,
            file=self.file,
            line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            kind=kind,
        )
        self.symbols.append(
            Symbol(
                node=graph_node,
                module=self.module,
                syntax=node,
                class_qualname=self.classes[-1] if self.classes else None,
                enclosing_functions=tuple(self.functions),
                imports={},
                shadowed_names=set(),
            )
        )

        self.scope.append(node.name)
        self.scope_kinds.append("function")
        self.functions.append(qualname)
        for statement in node.body:
            self.visit(statement)
        self.functions.pop()
        self.scope_kinds.pop()
        self.scope.pop()


class _BindingCollector(ast.NodeVisitor):
    def __init__(self, arguments: ast.arguments | None = None) -> None:
        self.non_import_names: set[str] = set()
        self.import_names: set[str] = set()
        if arguments:
            all_arguments = (
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
            )
            self.non_import_names.update(argument.arg for argument in all_arguments)
            if arguments.vararg:
                self.non_import_names.add(arguments.vararg.arg)
            if arguments.kwarg:
                self.non_import_names.add(arguments.kwarg.arg)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.non_import_names.add(node.id)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.import_names.add(alias.asname or alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self.import_names.add(alias.asname or alias.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


class _CallCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


def _module_name(relative_file: Path) -> tuple[str, bool]:
    parts = list(relative_file.with_suffix("").parts)
    is_package = bool(parts and parts[-1] == "__init__")
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def _absolute_from_module(
    current_module: str, is_package: bool, module: str | None, level: int
) -> str:
    if level == 0:
        return module or ""
    package = current_module.split(".") if is_package else current_module.split(".")[:-1]
    trim = level - 1
    if trim > len(package):
        return ""
    base = package[: len(package) - trim] if trim else package
    if module:
        base.extend(module.split("."))
    return ".".join(part for part in base if part)


def _bindings_for(
    import_nodes: Iterable[ast.Import | ast.ImportFrom],
    module: ModuleInfo,
    local_modules: set[str],
    *,
    function_local: bool = False,
) -> dict[str, ImportBinding]:
    bindings: dict[str, ImportBinding] = {}
    for node in import_nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".")[0]
                target = alias.name if alias.asname else alias.name.split(".")[0]
                kind = "module" if alias.name in local_modules else "external"
                bindings[bound_name] = ImportBinding(
                    kind, target, line=node.lineno, function_local=function_local
                )
            continue

        base = _absolute_from_module(
            module.name, module.is_package, node.module, node.level
        )
        for alias in node.names:
            bound_name = alias.asname or alias.name
            candidate_module = ".".join(part for part in (base, alias.name) if part)
            if alias.name == "*":
                bindings[bound_name] = ImportBinding(
                    "unsupported", base, line=node.lineno, function_local=function_local
                )
            elif candidate_module in local_modules:
                bindings[bound_name] = ImportBinding(
                    "module",
                    candidate_module,
                    line=node.lineno,
                    function_local=function_local,
                )
            elif base in local_modules:
                bindings[bound_name] = ImportBinding(
                    "symbol",
                    base,
                    alias.name,
                    node.lineno,
                    function_local,
                )
            else:
                bindings[bound_name] = ImportBinding(
                    "external",
                    base,
                    alias.name,
                    node.lineno,
                    function_local,
                )
    return bindings


def _collect_import_nodes(
    statements: list[ast.stmt],
) -> list[ast.Import | ast.ImportFrom]:
    return [
        statement
        for statement in statements
        if isinstance(statement, (ast.Import, ast.ImportFrom))
    ]


def _collect_bindings(
    statements: list[ast.stmt], arguments: ast.arguments | None = None
) -> _BindingCollector:
    collector = _BindingCollector(arguments)
    for statement in statements:
        collector.visit(statement)
    return collector


def _attribute_parts(node: ast.expr) -> list[str] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return list(reversed(parts))


def _call_expression(call: ast.Call) -> str:
    try:
        return ast.unparse(call.func)
    except Exception:
        return "<dynamic call>"


def analyze_repository(root: Path) -> Graph:
    root = root.resolve()
    if not root.is_dir():
        raise AnalysisError(f"repository is not a directory: {root}")

    paths = sorted(
        path
        for path in root.rglob("*.py")
        if not any(part in IGNORED_DIRECTORIES for part in path.relative_to(root).parts)
    )
    if not paths:
        raise AnalysisError(f"no Python files found under {root}")

    modules: dict[str, ModuleInfo] = {}
    for path in paths:
        relative = path.relative_to(root)
        file = relative.as_posix()
        module_name, is_package = _module_name(relative)
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=file)
        except (OSError, UnicodeError) as error:
            raise AnalysisError(f"cannot read {file}: {error}") from error
        except SyntaxError as error:
            location = f"{file}:{error.lineno or '?'}"
            raise AnalysisError(f"cannot parse {location}: {error.msg}") from error
        if module_name in modules:
            raise AnalysisError(f"duplicate module name {module_name!r}")
        modules[module_name] = ModuleInfo(
            name=module_name,
            file=file,
            is_package=is_package,
            tree=tree,
            imports={},
            shadowed_names=set(),
        )

    local_modules = set(modules)
    symbols: dict[str, Symbol] = {}
    by_module_qualname: dict[tuple[str, str], str] = {}
    for module in modules.values():
        module.imports = _bindings_for(
            _collect_import_nodes(module.tree.body), module, local_modules
        )
        module_bindings = _collect_bindings(module.tree.body)
        module.shadowed_names = module_bindings.non_import_names
        collector = _DefinitionCollector(module.file, module.name)
        collector.visit(module.tree)
        for symbol in collector.symbols:
            if symbol.node.id in symbols:
                raise AnalysisError(f"duplicate function identity {symbol.node.id}")
            local_imports = _bindings_for(
                _collect_import_nodes(symbol.syntax.body),
                module,
                local_modules,
                function_local=True,
            )
            symbol.imports = {**module.imports, **local_imports}
            local_bindings = _collect_bindings(symbol.syntax.body, symbol.syntax.args)
            direct_import_names = set(local_imports)
            symbol.shadowed_names = (
                module.shadowed_names
                | local_bindings.non_import_names
                | (local_bindings.import_names - direct_import_names)
            )
            symbols[symbol.node.id] = symbol
            by_module_qualname[(module.name, symbol.node.qualname)] = symbol.node.id

    graph = Graph(
        nodes={symbol_id: symbol.node for symbol_id, symbol in symbols.items()},
        metadata={
            "root": str(root),
            "python_files": len(paths),
            "analysis": "python-ast-static",
        },
    )

    for symbol in symbols.values():
        collector = _CallCollector()
        for statement in symbol.syntax.body:
            collector.visit(statement)
        for call in collector.calls:
            target, ignored = _resolve_call(
                call.func, symbol, by_module_qualname, local_modules
            )
            if target:
                graph.edges.append(
                    Edge(source=symbol.node.id, target=target, line=call.lineno)
                )
            elif not ignored:
                graph.diagnostics.append(
                    Diagnostic(
                        caller=symbol.node.id,
                        file=symbol.node.file,
                        line=call.lineno,
                        expression=_call_expression(call),
                        reason="dynamic or unresolved call target",
                    )
                )
    return graph


def _resolve_call(
    function: ast.expr,
    caller: Symbol,
    index: dict[tuple[str, str], str],
    local_modules: set[str],
) -> tuple[str | None, bool]:
    if isinstance(function, ast.Name):
        name = function.id
        if name in caller.shadowed_names:
            return None, False
        binding = caller.imports.get(name)
        if binding:
            if not _binding_available(binding, function.lineno):
                return None, False
            if binding.kind == "symbol" and binding.symbol:
                return index.get((binding.module, binding.symbol)), binding.module not in local_modules
            return None, binding.kind in {"external", "module"}

        for parent in reversed(caller.enclosing_functions):
            target = index.get((caller.module, f"{parent}.{name}"))
            if target:
                return target, False
        nested = index.get((caller.module, f"{caller.node.qualname}.{name}"))
        if nested:
            return nested, False
        target = index.get((caller.module, name))
        if target:
            return target, False
        return None, name in BUILTIN_NAMES

    parts = _attribute_parts(function)
    if not parts:
        return None, False

    if parts[0] in {"self", "cls"} and caller.class_qualname:
        qualname = ".".join((caller.class_qualname, *parts[1:]))
        return index.get((caller.module, qualname)), False

    if parts[0] in caller.shadowed_names:
        return None, False

    binding = caller.imports.get(parts[0])
    if binding:
        if not _binding_available(binding, function.lineno):
            return None, False
        if binding.kind == "external":
            return None, True
        if binding.kind == "module":
            module_parts = binding.module.split(".")
            suffix = parts[1:]
            for split in range(len(suffix), -1, -1):
                module = ".".join((*module_parts, *suffix[:split]))
                qualname = ".".join(suffix[split:])
                if module in local_modules and qualname:
                    target = index.get((module, qualname))
                    if target:
                        return target, False
            return None, False
        if binding.kind == "symbol" and binding.symbol:
            qualname = ".".join((binding.symbol, *parts[1:]))
            return index.get((binding.module, qualname)), False
        return None, binding.kind == "unsupported"

    # Explicit same-module class calls such as Runner.run().
    target = index.get((caller.module, ".".join(parts)))
    if target:
        return target, False

    # `import package.module` binds `package`, so also honor the full call chain.
    for split in range(len(parts) - 1, 0, -1):
        module = ".".join(parts[:split])
        qualname = ".".join(parts[split:])
        if module in local_modules:
            target = index.get((module, qualname))
            if target:
                return target, False
    return None, False


def _binding_available(binding: ImportBinding, call_line: int) -> bool:
    return not binding.function_local or bool(binding.line and binding.line < call_line)
