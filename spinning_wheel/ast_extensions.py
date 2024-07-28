import ast
from copy import deepcopy

from typing import Union, List, Callable, TypeVar, Tuple

_AST_SUBTYPE = TypeVar("AstSubtype", bound=ast.AST)


class ImportNodeFlattener(ast.NodeTransformer):
    """
    Node transformer implementation which flattens Import and ImportFrom nodes into multiple single line entries.
    """
    _ImportTypes = Union[ast.Import, ast.ImportFrom]
    _FlattenerFunction = Callable[[_ImportTypes], List[_ImportTypes]]
    _DeduplicationFunction = Callable[[List[_ImportTypes]], List[_ImportTypes]]

    def visit_Import(self, node: ast.Import) -> List[ast.Import]:
        return list(map(lambda n: ast.Import([ast.alias(n.name, n.asname)]), node.names))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> List[ast.ImportFrom]:
        return list(map(lambda n: ast.ImportFrom(node.module, [ast.alias(n.name, n.asname)]), node.names))


class ImportNodeDeduplicator(ast.NodeTransformer):
    """
    Node transformer implementation which deduplicates Import and ImportFrom statements
    using alias as a basis.
    """

    def __init__(self):
        self._observed_name_tuples = set()

    def visit_Import(self, node: ast.Import) -> Union[ast.Import, None]:
        return self._remove_duplicate_aliases(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Union[ast.ImportFrom, None]:
        return self._remove_duplicate_aliases(node)

    def _remove_duplicate_aliases(self, node: Union[ast.Import, ast.ImportFrom]) \
            -> Union[ast.Import, ast.ImportFrom, None]:
        filtered_names = []

        for name in node.names:
            name_tuple = (name.name, name.asname)
            if name_tuple not in self._observed_name_tuples:
                filtered_names.append(name)
                self._observed_name_tuples.add(name_tuple)

        if filtered_names:
            node.names = filtered_names
            return node

        return None


class ClassAndFunctionDeduplicator(ast.NodeTransformer):
    """
    Node transformer implementation which removes duplicate class and function
    definitions on a first-come-first serve basis.
    """
    _ClassFunctionUnion = Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]

    def __init__(self):
        self._observed_names = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Union[ast.FunctionDef, None]:
        return self._node_or_none_if_exists(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Union[ast.AsyncFunctionDef, None]:
        return self._node_or_none_if_exists(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> Union[ast.ClassDef, None]:
        return self._node_or_none_if_exists(node)

    def _node_or_none_if_exists(self, node: _ClassFunctionUnion) -> Union[_ClassFunctionUnion, None]:
        if node.name in self._observed_names:
            return None
        self._observed_names.add(node.name)
        return node


class LineRangeRemover(ast.NodeTransformer):
    """
    Node transformer implementation which removes nodes based on
    a range of lines to be excised, including nodes exactly at the boundaries of the range.

    Nodes which cross the boundary of the range are removed in their entirety.
    """

    def __init__(self, removal_ranges: Tuple[Tuple[int, int]]):
        self._removal_ranges = removal_ranges

    def visit(self, node: ast.AST) -> Union[ast.AST, None]:
        node_start = getattr(node, "lineno", None)
        node_end = getattr(node, "end_lineno", None)

        if node_start or node_end:
            for removal_range in self._removal_ranges:
                if any(
                        map(
                            lambda boundary: removal_range[0] <= boundary <= removal_range[1] if boundary else False,
                            [node_start, node_end]
                        )
                ):
                    return None

        return self.generic_visit(node)


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

                if visitation_output:
                    if isinstance(visitation_output, list):
                        visitation_outputs.extend(visitation_output)
                    else:
                        visitation_outputs.append(visitation_output)

            collected_nodes = visitation_outputs

        return collected_nodes if len(collected_nodes) > 1 else collected_nodes[0]


def union_and_deconflict_modules(
        primary_module: ast.Module,
        reference_module: ast.Module,
        reference_ranges_to_remove: Tuple[Tuple[int, int]] = None) -> ast.Module:
    """
    Union two modules, treating one as primary and another as reference.
    Where name definitions overlap, the primary module takes priority
    as a source of truth for deduplication and other operations.

    Args:
        primary_module (ast.Module): Primary module to merge
        reference_module (ast.Module): Reference module to merge
        reference_ranges_to_remove: Line ranges (as tuples) to remove from reference before unioning

    Returns:
        ast.Module: Unioned module composed of the two input modules
    """
    # Create copies of both modules for mutation
    cloned_primary = deepcopy(primary_module)
    cloned_reference = deepcopy(reference_module)

    # Pre-process reference tree and remove any desired line ranges
    # Use sparingly when it is inconvenient to create significant additional functionality for deduplication
    if reference_ranges_to_remove:
        line_range_remover = LineRangeRemover(reference_ranges_to_remove)
        line_range_remover.visit(cloned_reference)

    # Create base unioned model after pre-processing
    unioned_module: ast.Module = ast.Module([], [])
    unioned_module.body.extend(cloned_primary.body)
    unioned_module.body.extend(cloned_reference.body)

    # Create composite node transformer which flattens and deduplicates imports,
    # and removes duplicate class and function definitions on a first come, first served basis,
    # using the identifer/name for deduplication
    import_node_flattener = ImportNodeFlattener()
    import_node_deduplicator = ImportNodeDeduplicator()
    class_and_function_deduplicator = ClassAndFunctionDeduplicator()
    transformers = [import_node_flattener, import_node_deduplicator, class_and_function_deduplicator]
    composite_transformer = CompositeNodeTransformer(transformers)
    composite_transformer.visit(unioned_module)

    return unioned_module
