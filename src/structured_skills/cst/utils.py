from dataclasses import dataclass

import libcst as cst

SECRET_VARIABLE = "__VALUE"


@dataclass
class ParameterInfo:
    name: str
    annotation: str | None
    default: str | None


@dataclass
class FunctionInfo:
    name: str
    parameters: list[ParameterInfo]
    return_type: str | None
    docstring: str | None


class FunctionNotFoundError(Exception):
    pass


def extract_function_info(source: str, function_name: str) -> FunctionInfo:
    module = cst.parse_module(source)

    class FunctionFinder(cst.CSTVisitor):
        def __init__(self):
            self.function_node = None

        def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
            if node.name.value == function_name:
                self.function_node = node
            super().visit_FunctionDef(node)

    finder = FunctionFinder()
    module.visit(finder)

    if finder.function_node is None:
        raise FunctionNotFoundError(f"Function '{function_name}' not found in source")

    func = finder.function_node

    params = []
    if func.params and func.params.params:
        for param in func.params.params:
            annotation = None
            if param.annotation and hasattr(param.annotation, "annotation"):
                try:
                    expr_value = param.annotation.annotation
                    code_val = getattr(expr_value, "code", None)
                    if isinstance(code_val, str):
                        annotation = code_val
                    elif isinstance(expr_value, cst.BaseExpression):
                        if hasattr(expr_value, "value"):
                            value_attr = getattr(expr_value, "value", None)
                            if callable(value_attr):
                                annotation = str(value_attr())
                            else:
                                annotation = str(value_attr)
                        else:
                            annotation = str(expr_value)
                    elif isinstance(expr_value, str):
                        annotation = expr_value
                except (AttributeError, TypeError):
                    pass

            default = None
            if param.default:
                expr_value = param.default
                value_attr = getattr(expr_value, "value", None)
                if callable(value_attr):
                    default = str(value_attr())
                elif isinstance(value_attr, str):
                    default = value_attr
                else:
                    code_attr = getattr(expr_value, "code", None)
                    if code_attr is not None:
                        default = str(code_attr)

            params.append(
                ParameterInfo(
                    name=param.name.value,
                    annotation=annotation,
                    default=default,
                )
            )

    return_type = None
    if func.returns:
        annotation_attr = getattr(func.returns, "annotation", None)
        if annotation_attr is not None:
            return_type = getattr(annotation_attr, "value", None)

    docstring = None
    if hasattr(func.body, "body") and func.body.body:
        first_stmt = func.body.body[0]
        if isinstance(first_stmt, cst.SimpleStatementLine):
            body_stmt = first_stmt.body[0] if first_stmt.body else None
            if isinstance(body_stmt, cst.Expr) and isinstance(
                body_stmt.value, cst.SimpleString
            ):
                docstring = (
                    body_stmt.value.value[3:-3]
                    if body_stmt.value.value.startswith('"""')
                    or body_stmt.value.value.startswith("'''")
                    else body_stmt.value.value[1:-1]
                )
        elif isinstance(first_stmt, cst.Expr) and isinstance(
            first_stmt.value, cst.SimpleString
        ):
            docstring = (
                first_stmt.value.value[3:-3]
                if first_stmt.value.value.startswith('"""')
                or first_stmt.value.value.startswith("'''")
                else first_stmt.value.value[1:-1]
            )

    return FunctionInfo(
        name=func.name.value,
        parameters=params,
        return_type=return_type,
        docstring=docstring,
    )


def update_code(source: str, new_call: str) -> str:
    module = cst.parse_module(source)

    class MainBlockFinder(cst.CSTVisitor):
        def __init__(self):
            self.main_block_positions = []

        def visit_If(self, node: cst.If) -> None:
            test = node.test
            if isinstance(test, cst.Comparison):
                if (
                    isinstance(test.left, cst.Name)
                    and test.left.value == "__name__"
                    and len(test.comparisons) == 1
                ):
                    comparison = test.comparisons[0]
                    if (
                        isinstance(comparison.operator, cst.Equal)
                        and isinstance(comparison.comparator, cst.SimpleString)
                        and comparison.comparator.value == '"__main__"'
                    ):
                        self.main_block_positions.append(node)
            super().visit_If(node)

    finder = MainBlockFinder()
    module.visit(finder)

    if not finder.main_block_positions:
        return source + "\n" + new_call + "\n"

    body = list(module.body)
    for node in finder.main_block_positions:
        body.remove(node)

    new_statement = cst.parse_statement(new_call)
    body.append(new_statement)

    new_module = cst.Module(body=body)
    return new_module.code


def execute_script(content, function_name, args):
    output = update_code(
        content, f"args={str(args)};{SECRET_VARIABLE} = {function_name}(**args)"
    )
    context: dict = {"__builtins__": __builtins__}
    exec(output, context, context)
    return context[SECRET_VARIABLE]
