import re

with open('src/pages/Editor.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the stats mapping logic to include total and generated
old_stats_logic = '''    const subjectCategoryStats = useMemo(() => {
        return allEntities.reduce((stats, entity) => {
            const entityType = String(entity?.type || '').toLowerCase();
            if (Object.prototype.hasOwnProperty.call(stats, entityType)) {
                stats[entityType] += 1;
            }
            return stats;
        }, { character: 0, environment: 0, prop: 0, poster: 0 });
    }, [allEntities]);'''

new_stats_logic = '''    const subjectCategoryStats = useMemo(() => {
        return allEntities.reduce((stats, entity) => {
            const entityType = String(entity?.type || '').toLowerCase();
            if (Object.prototype.hasOwnProperty.call(stats, entityType)) {
                stats[entityType].total += 1;
                if (entity.image_url) {
                    stats[entityType].generated += 1;
                }
            }
            return stats;
        }, { 
            character: { total: 0, generated: 0 }, 
            environment: { total: 0, generated: 0 }, 
            prop: { total: 0, generated: 0 }, 
            poster: { total: 0, generated: 0 } 
        });
    }, [allEntities]);'''

content = content.replace(old_stats_logic, new_stats_logic)

# Replace the label rendering
old_tab_render = '''].map(({ key, label, title }) => (
                            <button
                                key={key}
                                onClick={() => setSubTab(key)}
                                className={px-5 py-2.5 text-xs font-extrabold uppercase rounded-lg transition-all border }
                                title={title}
                            >
                                {label} ({subjectCategoryStats[key] || 0})
                            </button>'''

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

content = content.replace(old_tab_render, new_tab_render)

with open('src/pages/Editor.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
