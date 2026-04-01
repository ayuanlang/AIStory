import re

with open('src/pages/Editor.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r"\]\.map\(\(\{ key, label, title \}\) => \(\s*<button\s*key=\{key\}\s*onClick=\{[^}]+\}\s*className=\{[^}]+\}\s*title=\{title\}\s*>\s*\{label\} \(\{subjectCategoryStats\[key\] \|\| 0\}\)\s*</button>\s*\)\)"


replacement = """.map(({ key, label, title }) => {
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

content = re.sub(pattern, replacement, content)

with open('src/pages/Editor.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
