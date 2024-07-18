import ast

from typing import Union, List, Callable


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


class DuplicateClassAndFunctionRemover(ast.NodeTransformer):
    """
    Node transformer implementation which removes duplicate class and function
    definitions on a first-come-first serve basis.
    """
    _ClassFunctionUnion = Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]

    def __init__(self):
        self._observed_names = set()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        return self._node_or_none_if_exists(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        return self._node_or_none_if_exists(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        return self._node_or_none_if_exists(node)

    def _node_or_none_if_exists(self, node: _ClassFunctionUnion):
        if node.name in self._observed_names:
            return None
        self._observed_names.add(node.name)
        return node


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
    unioned_module: ast.Module = ast.Module([], [])
    unioned_module.body.extend(primary_module.body)
    unioned_module.body.extend(reference_module.body)

    # Create composite node transformer which flattens and deduplicates imports,
    # and removes duplicate class and function definitions on a first come, first served basis,
    # using the identifer/name for deduplication
    import_node_flattener = ImportNodeFlattener()
    import_node_deduplicator = ImportNodeDeduplicator()
    duplicate_class_function_remover = DuplicateClassAndFunctionRemover()
    transformers = [import_node_flattener, import_node_deduplicator, duplicate_class_function_remover]
    composite_transformer = CompositeNodeTransformer(transformers)
    composite_transformer.visit(unioned_module)

    return unioned_module
