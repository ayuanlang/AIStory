const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(filePath, 'utf-8');

const brokenBlock = `            cards.push({
                key: \\stage3-asset-\\\\,
                eyebrow: t('第三阶段局部', 'Stage 3 Partial'),
                title: t(cat.labelZh, cat.labelEn),
                status: catJson ? 'completed' : 'idle',
                badge: catJson ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending'),
                summary: t(\\局部的\\结果。\\, \\Stage 3 \\ result.\\),
                content: formatArtifactContent(catJson, 'json'),`;

const fixBlock = `            cards.push({
                key: \`stage3-asset-\${cat.key}\`,
                eyebrow: t('第三阶段局部', 'Stage 3 Partial'),
                title: t(cat.labelZh, cat.labelEn),
                status: catJson ? 'completed' : 'idle',
                badge: catJson ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending'),
                summary: t(\`局部的\${cat.labelZh}结果。\`, \`Stage 3 \${cat.labelEn} result.\`),
                content: formatArtifactContent(catJson, 'json'),`;

content = content.replace(brokenBlock, fixBlock);

const brokenBlock2 = `placeholder: t(\\尚未返回\\结果。\\, \\No \\ output yet.\\),`;
const fixBlock2 = `placeholder: t(\`尚未返回\${cat.labelZh}结果。\`, \`No \${cat.labelEn} output yet.\`),`;
content = content.replace(brokenBlock2, fixBlock2);

fs.writeFileSync(filePath, content, 'utf-8');
console.log('Fixed syntax errors.');
