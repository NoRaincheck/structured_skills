import pytest

from structured_skills.cst.utils import (
    FunctionInfo,
    FunctionNotFoundError,
    ParameterInfo,
    execute_script,
    extract_function_info,
    update_code,
)


class TestExtractFunctionInfo:
    def test_simple_function(self):
        source = '''
def greet(name: str) -> str:
    """Greet a person."""
    return f"Hello, {name}!"
'''
        info = extract_function_info(source, "greet")
        assert info.name == "greet"
        assert len(info.parameters) == 1
        assert info.parameters[0].name == "name"
        assert info.parameters[0].annotation == "str"
        assert info.return_type == "str"
        assert "Greet a person" in (info.docstring or "")

    def test_function_with_multiple_params(self):
        source = '''
def add(a: int, b: int = 0) -> int:
    """Add two numbers."""
    return a + b
'''
        info = extract_function_info(source, "add")
        assert info.name == "add"
        assert len(info.parameters) == 2
        assert info.parameters[0].name == "a"
        assert info.parameters[0].annotation == "int"
        assert info.parameters[1].name == "b"
        assert info.parameters[1].default == "0"

    def test_function_without_annotations(self):
        source = """
def simple(x):
    return x
"""
        info = extract_function_info(source, "simple")
        assert info.name == "simple"
        assert len(info.parameters) == 1
        assert info.parameters[0].annotation is None
        assert info.return_type is None

    def test_function_not_found(self):
        source = "def foo(): pass"
        with pytest.raises(FunctionNotFoundError):
            extract_function_info(source, "nonexistent")

    def test_function_without_docstring(self):
        source = "def no_doc(x: int) -> int:\n    return x"
        info = extract_function_info(source, "no_doc")
        assert info.docstring is None

    def test_function_with_complex_types(self):
        source = '''
def process(data: dict[str, int], items: list[str] | None = None) -> bool:
    """Process data."""
    return True
'''
        info = extract_function_info(source, "process")
        assert info.name == "process"
        assert "dict" in (info.parameters[0].annotation or "")
        assert "list" in (info.parameters[1].annotation or "")


class TestExecuteScript:
    def test_simple_execution(self):
        source = """
def add(a: int, b: int) -> int:
    return a + b
"""
        result = execute_script(source, "add", {"a": 2, "b": 3})
        assert result == 5

    def test_string_return(self):
        source = """
def greet(name: str) -> str:
    return f"Hello, {name}!"
"""
        result = execute_script(source, "greet", {"name": "World"})
        assert result == "Hello, World!"

    def test_with_imports(self):
        source = """
import math

def compute(x: float) -> float:
    return math.sqrt(x)
"""
        result = execute_script(source, "compute", {"x": 4.0})
        assert result == 2.0


class TestUpdateCode:
    def test_adds_call_when_no_main(self):
        source = """
def foo():
    pass
"""
        new_call = "foo()"
        result = update_code(source, new_call)
        assert "foo()" in result

    def test_replaces_main_block(self):
        source = """
def main():
    print("old")

if __name__ == "__main__":
    main()
"""
        new_call = "args={};__VALUE = greet(**args)"
        result = update_code(source, new_call)
        assert 'if __name__ == "__main__"' not in result
        assert "__VALUE" in result


class TestParameterInfo:
    def test_parameter_info_creation(self):
        param = ParameterInfo(name="test", annotation="int", default="42")
        assert param.name == "test"
        assert param.annotation == "int"
        assert param.default == "42"

    def test_parameter_info_without_default(self):
        param = ParameterInfo(name="required", annotation="str", default=None)
        assert param.default is None


class TestFunctionInfo:
    def test_function_info_creation(self):
        params = [ParameterInfo(name="x", annotation="int", default=None)]
        info = FunctionInfo(
            name="test",
            parameters=params,
            return_type="bool",
            docstring="Test function",
        )
        assert info.name == "test"
        assert len(info.parameters) == 1
        assert info.return_type == "bool"
        assert info.docstring == "Test function"
