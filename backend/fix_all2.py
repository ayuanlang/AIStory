import sys
import re

def fix(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    out = []
    lines = text.split('\n')
    in_block = False
    indent = ""
    for line in lines:
        if 'async for ' in line and 'in ' in line and not 'in_block' in line:
            m = re.match(r'^(\s*)async for (\w+) in (.*):', line)
            if m:
                indent = m.group(1)
                var = m.group(2)
                expr = m.group(3)
                out.append(indent + "from contextlib import aclosing")
                out.append(indent + f"async with aclosing({expr}) as _stream:")
                out.append(indent + "    async for " + var + " in _stream:")
                in_block = True
                continue
        
        if in_block:
            if line.strip() == "":
                out.append(line)
            else:
                curr_indent_m = re.match(r'^(\s*)', line)
                curr_indent = curr_indent_m.group(1) if curr_indent_m else ""
                
                # Check if it has dedented back or to a smaller scope
                if len(curr_indent) <= len(indent) and not (line.strip().startswith('except ') or line.strip().startswith('elif ') or line.strip().startswith('else:')):
                    in_block = False
                    out.append(line)
                elif line.strip().startswith('except ') or line.strip().startswith('elif ') or line.strip().startswith('else:') or line.strip().startswith('finally:'):
                     # keep exact indentation for these if they belong to parent, wait!
                     # if it belongs to try inside the block, it's fine.
                     # if it dedented back to exactly indent, it's outside.
                     if len(curr_indent) <= len(indent):
                         in_block = False
                         out.append(line)
                     else:
                         out.append("    " + line)
                else:
                    out.append("    " + line)
        else:
            out.append(line)

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))

fix('c:/AS/AIStory/backend/app/services/llm_service.py')
fix('c:/AS/AIStory/backend/app/api/endpoints.py')
fix('c:/AS/AIStory/backend/app/services/agent_service.py')

print('Done')
