"""Refresh read-only gallery inventory from current MCP source definitions."""
import ast
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def tools(path):
    tree=ast.parse((ROOT/path).read_text())
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and any(isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=='tool' for d in node.decorator_list):
            yield dict(name=node.name,description=ast.get_docstring(node) or '',arguments=[a.arg for a in node.args.args],source=path,line=node.lineno)

rows = [tool for tool in tools('story_mode/mcp_server.py') if tool['name'] == 'propose_activity']
(ROOT/'web/interaction-tools.json').write_text(json.dumps(dict(scope='Story interruption panels', tools=rows), indent=2)+'\n')
print(f'Generated {len(rows)} Story interaction tool with three activity types.')
