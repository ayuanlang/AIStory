import re

with open('frontend/src/pages/ProjectList.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to replace select with input + datalist
def replace_select_with_input(match):
    label = match.group(1)
    val_bind = match.group(2)
    change_bind = match.group(3)
    options_code = match.group(4)
    
    # We strip '>{opt}</option>' back to ' />' to match standard datalist options
    options_code = options_code.replace('>{opt}</option>', ' />').replace('></option>', ' />')
    
    # Generate list ID based on value bind
    list_id = val_bind.replace('new', '').lower() + '-options'
    
    return f'''<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">{{t({label})}}</label>
                                                <input list="{list_id}" className="w-full px-3 py-2.5 bg-background border rounded-lg" value={{{val_bind}}} onChange={{(e) => {change_bind}(e.target.value)}} />
                                                <datalist id="{list_id}">
                                                    {options_code}
                                                </datalist>'''

pattern = r'<label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">\{t\((.*?)\)\}</label>\s*<select className="w-full px-3 py-2.5 bg-background border rounded-lg appearance-none" value=\{([^}]+)\} onChange=\{\(e\) => ([^}]+)\(e\.target\.value\)\}>\s*(\{.*?\})\s*</select>'

new_content = re.sub(pattern, replace_select_with_input, content)

with open('frontend/src/pages/ProjectList.jsx', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Done")
