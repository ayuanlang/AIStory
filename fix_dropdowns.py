import re
with open(r'c:\AS\AIStory\frontend\src\pages\ProjectList.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'<input list="list-([^"]+?)" className="([^"]+?)" value={([^}]+?)} onChange=\{\(e\) => ([^}]+?)\}\s*(?:placeholder=\{t\("[^"]+?", "[^"]+?"\)\}|placeholder="[^"]+?")?\s*/>\s*<datalist id="[^"]+?">\s*\{projectCreateOptions\.([a-zA-Z_]+?)\.map\(\(opt\) => <option key=\{opt\} value=\{opt\}>.*?</option>\)\}\s*</datalist>'

def repl(m):
    return f'''<select className="{m.group(2)}" value={{{m.group(3)}}} onChange={{(e) => {m.group(4)}}}>
                                                    <option value="" disabled hidden>{{t("请选择...", "Select...")}}</option>
                                                    {{projectCreateOptions.{m.group(5)}.map((opt) => <option key={{opt}} value={{opt}}>{{opt.includes('/') ? t(opt.split('/')[0].trim(), opt.split('/')[1]?.trim() || opt.split('/')[0].trim()) : opt}}</option>)}}
                                                </select>'''

new_content = re.sub(pattern, repl, content, flags=re.DOTALL)
with open(r'c:\AS\AIStory\frontend\src\pages\ProjectList.jsx', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Replaced dropdowns:', len(re.findall(r'<select', new_content)))
