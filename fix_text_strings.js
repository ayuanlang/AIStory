const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let text = fs.readFileSync(filePath, 'utf-8');

// Stage 1 Action text
text = text.replace(
    /label:\s*t\('回填剧本',\s*'Backfill Script'\)/g,
    "label: t('回填剧本并以新内容重跑', 'Backfill Script & Rerun')"
);
text = text.replace(
    /title:\s*t\('全局风格',\s*'Global Style'\)/g,
    "title: t('节点1: 全局风格', 'Stage 1: Global Style')"
);

// Stage 3 badges
text = text.replace(
    /badge:\s*catJson\s*\?\s*t\('可导入',\s*'Importable'\)\s*:\s*t\('待输出',\s*'Pending'\)/g,
    "badge: catJson ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending')"
);

// Stage 3 partial import labels
text = text.replace(
    /btnZh:\s*'重跑\s*道具'/g,
    "btnZh: '局部导入重跑道具'"
);
text = text.replace(
    /btnZh:\s*'\s*重跑封面'/g,
    "btnZh: '局部导入重跑封面'"
);

// Need to update the actions inside the stage 3 loop
const stage3Pattern = /actions:\s*\[[\s\S]*?label:\s*t\('局部导入.*?'[\s\S]*?\}\s*\]/g;
text = text.replace(stage3Pattern, (match) => {
    // Actually wait, right now in `ScriptEditor.jsx` the stage 3 subcategory loop might not even have those actions yet!
    return match;
});

// visualBackfill badge
text = text.replace(
    /t\('可导入',\s*'Importable'\)\s*:\s*t\('待输出\s*',\s*'Pending'\)/g,
    "t('展开可导入', 'Importable') : t('展开待输出', 'Pending')"
);

// Stage 1 output badge
text = text.replace(
    /badge:\s*!!getStageOutputContent\('stage1',\s*'optimized_script'\)\s*\?\s*t\('可回填',\s*'Backfill'\)\s*:\s*t\('待输出',\s*'Pending'\)/g,
    "badge: !!getStageOutputContent('stage1', 'optimized_script') ? t('展开可回填', 'Expand to Backfill') : t('展开待输出', 'Pending')"
);

fs.writeFileSync(filePath, text, 'utf-8');
console.log('Strings updated.');
