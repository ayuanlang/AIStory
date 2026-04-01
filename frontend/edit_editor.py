import re

with open('src/pages/Editor.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix duplicate poster
content = content.replace(
    "{ key: 'poster', label: t('海报', 'Poster'), title: t('封面海报', 'Cover Poster') },\n                            { key: 'poster', label: t('海报', 'Poster'), title: t('封面海报', 'Cover Poster') },",
    "{ key: 'poster', label: t('海报', 'Poster'), title: t('封面海报', 'Cover Poster') },"
)

# Pass workflowStage to ProjectStatusBar
content = content.replace(
    "<ProjectStatusBar \n                activeTab={activeTab} ",
    "<ProjectStatusBar \n                activeTab={activeTab} \n                workflowStage={project?.global_info?.workflow_stage}\n"
)

# Fix loading entities logic to mutate '封面海报'
loading_entities_block = '''                const data = await fetchEntities(resolvedProjectId);
                const nextEntities = Array.isArray(data) ? data : [];
                setEntities(nextEntities);'''

new_loading_entities_block = '''                const data = await fetchEntities(resolvedProjectId);
                const nextEntities = Array.isArray(data) ? data.map(item => {
                    if (item.type === 'environment' && (item.name === '封面海报' || item.name_en === 'Cover Poster')) {
                        return { ...item, type: 'poster' };
                    }
                    return item;
                }) : [];
                setEntities(nextEntities);'''

content = content.replace(loading_entities_block, new_loading_entities_block)

# Look for similar in the other loadEntities usage
loading_all_entities_block = '''            const data = await fetchEntities(projectId); // Fetch ALL types
            setAllEntities(data);
            return Array.isArray(data) ? data : [];'''

new_loading_all_entities_block = '''            const data = await fetchEntities(projectId); // Fetch ALL types
            const processedData = Array.isArray(data) ? data.map(item => {
                if (item.type === 'environment' && (item.name === '封面海报' || item.name_en === 'Cover Poster')) {
                    return { ...item, type: 'poster' };
                }
                return item;
            }) : [];
            setAllEntities(processedData);
            return processedData;'''

content = content.replace(loading_all_entities_block, new_loading_all_entities_block)

with open('src/pages/Editor.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
