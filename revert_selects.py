import re

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

# Pattern matches:
# <input\s+className="..."\s+value={...}\s+onChange={...}\s+list="..."\s*/>
# \s*<datalist id="...">
# \s*\{projectCreateOptions\....\.map\(\(opt\) => <option key=\{opt\} value=\{opt\}>\{...\}</option>\)\}
# \s*</datalist>

pattern = r'<input\s+(className="[^"]+")\s+value=\{([^}]+)\}\s+onChange=\{([^}]+)\}\s+list="[^"]+"\s*/>\s*<datalist id="[^"]+">\s*(\{projectCreateOptions\.[A-Za-z_]+\.map\(\(opt\) => <option key=\{opt\} value=\{opt\}>\{[^}]+\}</option>\)\})\s*</datalist>'

def repl(match):
    className = match.group(1)
    value = match.group(2)
    onChange = match.group(3)
    options = match.group(4)
    return f"""<select
                                                                {className}
                                                                value={{{value}}}
                                                                onChange={{{onChange}}}
                                                            >
                                                                {options}
                                                            </select>"""

new_text, count = re.subn(pattern, repl, text)
print(f"Replaced {count} instances.")

# Also let's move the Script Content and Project Description textareas.
# Wait, let's just do it in one go or manually.
with open("frontend/src/pages/ProjectList.jsx", "w", encoding="utf-8") as f:
    f.write(new_text)

