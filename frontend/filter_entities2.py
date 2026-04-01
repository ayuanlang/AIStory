import re

with open('src/pages/Editor.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the label rendering again if it failed
old_tab_render = '''].map(({ key, label, title }) => (
                            <button
                                key={key}
                                onClick={() => setSubTab(key)}
                                className={px-5 py-2.5 text-xs font-extrabold uppercase rounded-lg transition-all border }
                                title={title}
                            >
                                {label} ({subjectCategoryStats[key] || 0})
                            </button>
                        ))}'''

new_tab_render = '''].map(({ key, label, title }) => {
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
                        )})'''

content = content.replace(old_tab_render.strip(), new_tab_render.strip())

with open('src/pages/Editor.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
