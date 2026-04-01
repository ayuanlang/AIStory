import re

with open('frontend/src/pages/ProjectList.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace typical select block
pattern = re.compile(
    r'<select\s+className="([^"]+)"\s+value=\{([^}]+)\}\s+onChange=\{([^}]+)\}\s*>\s*<option value="">.*?<\/option>\s*\{(.*?)\.map\(\(([^,]+).*?\}\)\s*<\/select>',
    re.DOTALL
)

def replacer(match):
    class_name = match.group(1)
    if 'text-white' not in class_name:
        class_name = class_name.replace('text-gray-400', 'text-white/80')
    value = match.group(2)
    on_change = match.group(3)
    options_array = match.group(4)
    item_var = match.group(5)
    
    datalist_id = f"{value}-options"
    
    res = f'''<input
                        list="{datalist_id}"
                        className="{class_name}"
                        value={{{value}}}
                        onChange={{{on_change}}}
                        placeholder="Select or enter custom value..."
                      />
                      <datalist id="{datalist_id}">
                        {{{options_array}.map(({item_var}) => (
                          <option key={{{item_var}}} value={{{item_var}}} />
                        ))}}
                      </datalist>'''
    return res

new_content = pattern.sub(replacer, content)

with open('frontend/src/pages/ProjectList.jsx', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Selects converted back.")
