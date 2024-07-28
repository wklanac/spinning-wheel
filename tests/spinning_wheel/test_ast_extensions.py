import ast
import pytest
from assertpy import assert_that

from spinning_wheel.ast_extensions import (
    ImportNodeFlattener, ImportNodeDeduplicator, ClassAndFunctionDeduplicator,
    LineRangeRemover, CompositeNodeTransformer, union_and_deconflict_modules
)


@pytest.fixture
def sample_import_node():
    return ast.Import([ast.alias("os", None), ast.alias("sys", "system")])


@pytest.fixture
def sample_importfrom_node():
    return ast.ImportFrom("math", [ast.alias("sin", None), ast.alias("cos", "cosine")], 0)


@pytest.fixture
def sample_ast_module():
    return ast.parse("""import os, sys
from math import sin, cos
def func1(): pass
class Class1: pass
def func1(): pass
class Class1: pass
""")


class TestImportNodeFlattener:
    def test_visit_import(self, sample_import_node):
        flattener = ImportNodeFlattener()
        result = flattener.visit_Import(sample_import_node)
        assert_that(result).is_instance_of(list).is_length(2)
        for node in result:
            assert_that(node).is_instance_of(ast.Import)
        assert_that(result[0].names[0].name).is_equal_to("os")
        assert_that(result[1].names[0].name).is_equal_to("sys")
        assert_that(result[1].names[0].asname).is_equal_to("system")

    def test_visit_importfrom(self, sample_importfrom_node):
        flattener = ImportNodeFlattener()
        result = flattener.visit_ImportFrom(sample_importfrom_node)
        assert_that(result).is_instance_of(list).is_length(2)
        for node in result:
            assert_that(node).is_instance_of(ast.ImportFrom)
            assert_that(node.module).is_equal_to("math")
        assert_that(result[0].names[0].name).is_equal_to("sin")
        assert_that(result[1].names[0].name).is_equal_to("cos")
        assert_that(result[1].names[0].asname).is_equal_to("cosine")


class TestImportNodeDeduplicator:
    def test_remove_duplicate_aliases(self):
        deduplicator = ImportNodeDeduplicator()
        node1 = ast.Import([ast.alias("os", None), ast.alias("sys", "system")])
        node2 = ast.Import([ast.alias("os", None), ast.alias("datetime", None)])

        result1 = deduplicator.visit_Import(node1)
        assert_that(result1.names).is_length(2)

        result2 = deduplicator.visit_Import(node2)
        assert_that(result2.names).is_length(1)
        assert_that(result2.names[0].name).is_equal_to("datetime")


class TestClassAndFunctionDeduplicator:
    def test_deduplication(self, sample_ast_module):
        deduplicator = ClassAndFunctionDeduplicator()
        deduplicator.visit(sample_ast_module)

        func_defs = [node for node in sample_ast_module.body if isinstance(node, ast.FunctionDef)]
        class_defs = [node for node in sample_ast_module.body if isinstance(node, ast.ClassDef)]

        assert_that(func_defs).is_length(1)
        assert_that(class_defs).is_length(1)


class TestLineRangeRemover:
    def test_remove_range(self):
        code = """line1
line2
line3
line4
line5
"""
        tree = ast.parse(code)
        remover = LineRangeRemover(((2, 4),))
        remover.visit(tree)

        assert_that(tree.body).is_length(2)
        assert_that(tree.body[0]).is_instance_of(ast.Expr)
        assert_that(tree.body[1]).is_instance_of(ast.Expr)


class TestCompositeNodeTransformer:
    def test_composite_transformation(self, sample_ast_module):
        flattener = ImportNodeFlattener()
        deduplicator = ImportNodeDeduplicator()
        composite = CompositeNodeTransformer([flattener, deduplicator])

        composite.visit(sample_ast_module)

        imports = [node for node in sample_ast_module.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        assert_that(imports).is_length(4)  # 2 flattened imports + 2 flattened import froms


class TestUnionAndDeconflictModules:
    def test_union_and_deconflict(self):
        primary = ast.parse("""def func1(): pass
class Class1: pass
import os""")
        reference = ast.parse("""def func2(): pass
class Class1: pass
import sys""")

        result = union_and_deconflict_modules(primary, reference)

        assert_that(result.body).is_length(5)
        assert_that(result.body[0]).is_instance_of(ast.FunctionDef).has_name("func1")
        assert_that(result.body[1]).is_instance_of(ast.ClassDef).has_name("Class1")
        assert_that(result.body[2]).is_instance_of(ast.Import)
        assert_that(result.body[2].names[0].name).is_equal_to("os")
        assert_that(result.body[3]).is_instance_of(ast.FunctionDef).has_name("func2")

    def test_union_with_range_removal(self):
        primary = ast.parse("def func1(): pass")
        reference = ast.parse("""def func2(): pass
def func3(): pass
def func4(): pass""")

        result = union_and_deconflict_modules(primary, reference, ((2, 2),))

        assert_that(result.body).is_length(3)
        assert_that(result.body[0]).has_name("func1")
        assert_that(result.body[1]).has_name("func2")
        assert_that(result.body[2]).has_name("func4")