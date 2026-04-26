import ast

with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

class V(ast.NodeVisitor):
    def visit_FunctionDef(self, node):
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and n.id == 'requests' and isinstance(n.ctx, ast.Store):
                print(f"Function {node.name} stores into `requests` at line {n.lineno}")
            elif isinstance(n, ast.Import):
                for alias in n.names:
                    if alias.name == 'requests' or alias.asname == 'requests':
                        print(f"Function {node.name} imports `requests` at line {n.lineno}")
            elif isinstance(n, ast.ImportFrom):
                for alias in n.names:
                    if alias.name == 'requests' or alias.asname == 'requests':
                        print(f"Function {node.name} imports from `requests` at line {n.lineno}")
        self.generic_visit(node)
    def visit_AsyncFunctionDef(self, node):
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and n.id == 'requests' and isinstance(n.ctx, ast.Store):
                print(f"AsyncFunction {node.name} stores into `requests` at line {n.lineno}")
            elif isinstance(n, ast.Import):
                for alias in n.names:
                    if alias.name == 'requests' or alias.asname == 'requests':
                        print(f"AsyncFunction {node.name} imports `requests` at line {n.lineno}")
        self.generic_visit(node)

V().visit(ast.parse(text))
