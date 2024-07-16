import ast
from _ast import Module

from typing import Union, List

from ordered_set import OrderedSet


class ImportNodeFlattener(ast.NodeTransformer):
    """
    Node transformer implementation which flattens Import and ImportFrom nodes into multiple single line entries.
    Duplicate flattened entries are not included.
    """

    def __init__(self):
        self._observed_import_set = OrderedSet()
        self._observed_import_from_set = OrderedSet()

    def visit_Import(self, node: ast.Import) -> List[ast.Import]:
        flattened_imports = list(map(lambda n: ast.Import([ast.alias(n.name, n.asname)]), node.names))
        self._observed_import_set.update(flattened_imports)
        return list(self._observed_import_set.difference(flattened_imports))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> List[ast.ImportFrom]:
        flattened_from_imports = list(
            map(lambda n: ast.ImportFrom(node.module,
                                         [ast.alias(n.name, n.asname)],
                                         node.level),
                node.names))
        self._observed_import_from_set.update(flattened_from_imports)
        return list(self._observed_import_from_set.difference(flattened_from_imports))


class DuplicateClassAndFunctionRemover(ast.NodeTransformer):
    """
    Node transformer implementation which removes duplicate class and function
    definitions on a first-come-first serve basis.
    """
    ClassFunctionUnion = Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]

    def __init__(self):
        self._observed_names = set()

    def _node_or_none_if_exists(self, node: ClassFunctionUnion):
        if node.name in self._observed_names:
            return None
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        return self._node_or_none_if_exists(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        return self._node_or_none_if_exists(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        return self._node_or_none_if_exists(node)


class CompositeNodeTransformer(ast.NodeTransformer):
    """
    Node transformer composed of one or more node transformers.
    This is intended to reduce the overhead of visiting and transforming
    the same nodes for isolated operations which can be executed in sequence.
    Each transformer is expected to return a single node or a list of nodes,
    all of which will be processed by the next transformers in the sequence.
    """

    def __init__(self, node_visitors: List[ast.NodeTransformer]):
        self._node_visitors = node_visitors

    def visit(self, node: ast.AST) -> Union[List[ast.AST], ast.AST]:
        collected_nodes = [node]

        for node_visitor in self._node_visitors:
            visitation_outputs = []

            for collected_node in collected_nodes:
                visitation_output = node_visitor.visit(collected_node)

                if isinstance(visitation_output, list):
                    visitation_outputs.extend(visitation_output)
                else:
                    visitation_outputs.append(visitation_output)

            collected_nodes = visitation_outputs

        return collected_nodes if len(collected_nodes) > 1 else collected_nodes[0]


def union_and_deconflict_modules(primary_module: ast.Module, reference_module: ast.Module) -> ast.Module:
    """
    Union two modules, treating one as primary and another as reference.
    Where name definitions overlap, the primary module takes priority
    as a source of truth for deduplication and other operations.

    Args:
        primary_module (ast.Module): Primary module to merge
        reference_module (ast.Module): Reference module to merge

    Returns:
        ast.Module: Unioned module composed of the two input modules
    """
    # Create base unioned module with no modifications using the body of primary and reference modules
    unioned_module: Module = ast.Module([], [])
    unioned_module.body.extend(primary_module.body)
    unioned_module.body.extend(reference_module.body)

    # Create composite node transformer which flattens and deduplicates imports,
    # and removes duplicate class and function definitions on a first come, first served basis,
    # using the identifer/name for deduplication
    flattener_transformer = ImportNodeFlattener()
    duplicate_class_function_remover = DuplicateClassAndFunctionRemover()
    composite_transformer = CompositeNodeTransformer([flattener_transformer, duplicate_class_function_remover])
    composite_transformer.visit(unioned_module)

    return unioned_module
