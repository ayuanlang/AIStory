const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(filePath, 'utf-8');

// The file has literal ONE backslash: `\\stage3-asset-\\\\,` (in JS terms, '\\stage3-asset-\\,')
content = content.replace(/key: \\stage3-asset-\\\\,/g, 'key: \`stage3-asset-\${cat.key}\`,');
content = content.replace(/summary: t\(\\局部的\\结果。\\, \\Stage 3 \\ result\.\\\),/g, 'summary: t(\`局部的\${cat.labelZh}结果。\`, \`Stage 3 \${cat.labelEn} result.\`),');
content = content.replace(/placeholder: t\(\\尚未返回\\结果。\\, \\No \\ output yet\.\\\),/g, 'placeholder: t(\`尚未返回\${cat.labelZh}结果。\`, \`No \${cat.labelEn} output yet.\`),');
content = content.replace(/label: \\stage3 \\ json\\,/g, 'label: \`stage3 \${cat.key} json\`,');

content = content.replace(/key: \\\neimport-stage3-\\\\,/g, 'key: \`reimport-stage3-\${cat.key}\`,');
content = content.replace(/key: \\\nestart-stage3-\\\\,/g, 'key: \`restart-stage3-\${cat.key}\`,');

fs.writeFileSync(filePath, content, 'utf-8');
console.log('Fixed exactly using RegExp.');
