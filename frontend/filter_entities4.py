import re

with open('src/pages/Editor.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r"\]\.map\(\(\{ key, label, title \}\) => \(\s*<button\s*key=\{key\}\s*onClick=\{[^}]+\}\s*className=\{[^}]+\}\s*title=\{title\}\s*>\s*\{label\} \(\{subjectCategoryStats\[key\] \|\| 0\}\)\s*</button>\s*\)\)"

# Fallback string replace with literal approach to circumvent regex edgecases
pos_start = content.find("].map(({ key, label, title }) => (")
if pos_start != -1:
    pos_end = content.find("</button>", pos_start) + len("</button>")
    pos_end_parens = content.find("\n                        ))", pos_end) + len("\n                        ))")
    
    orig_str = content[pos_start:pos_end_parens]
    
    new_str = """.map(({ key, label, title }) => {
                            const stat = subjectCategoryStats[key] || { total: 0, generated: 0 };
                            return (
                            <button
                                key={key}
                                onClick={() => setSubTab(key)}
                                className={px-5 py-2.5 text-xs font-extrabold uppercase rounded-lg transition-all border }
                                title={title}
                            >
                                {label} ({stat.generated}/{stat.total})
                            </button>
                        )})"""
    
    content = content[:pos_start] + "]" + new_str + content[pos_end_parens:]

with open('src/pages/Editor.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
