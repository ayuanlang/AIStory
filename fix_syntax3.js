const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(filePath, 'utf-8');

const sIdx = content.indexOf('cards.push({\n                key: \\stage3-asset-\\\\,');
console.log(sIdx);
if (sIdx > -1) {
    let replaced = content.replace('key: \\stage3-asset-\\\\,', 'key: `stage3-asset-${cat.key}`,');
    replaced = replaced.replace('summary: t(\\局部的\\结果。\\, \\Stage 3 \\ result.\\),', 'summary: t(`局部的${cat.labelZh}结果。`, `Stage 3 ${cat.labelEn} result.`),');
    replaced = replaced.replace('key: \\\neimport-stage3-\\\\,', 'key: `reimport-stage3-${cat.key}-and-rerun`,');
    replaced = replaced.replace('label: \\stage3 \\ json\\,', 'label: `stage3 ${cat.key} json`,');
    replaced = replaced.replace('key: \\\nestart-stage3-\\\\,', 'key: `restart-stage3-${cat.key}`,');
    replaced = replaced.replace('placeholder: t(\\尚未返回\\结果。\\, \\No \\ output yet.\\),', 'placeholder: t(`尚未返回${cat.labelZh}结果。`, `No ${cat.labelEn} output yet.`),');
    
    fs.writeFileSync(filePath, replaced, 'utf-8');
    console.log('Fixed exactly.');
} else {
    // If exact string fails, try character logic
    const lines = content.split('\\n');
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes('key: \\\\stage3-asset-\\\\\\\\,') || lines[i].indexOf('stage3-asset-\\\\') > -1) {
             lines[i] = "                key: \`stage3-asset-\${cat.key}\`,";
        }
        if (lines[i].includes('summary: t(\\\\局部的')) {
             lines[i] = "                summary: t(\`局部的\${cat.labelZh}结果。\`, \`Stage 3 \${cat.labelEn} result.\`),";
        }
        if (lines[i].includes('placeholder: t(\\\\尚未返回')) {
             lines[i] = "                placeholder: t(\`尚未返回\${cat.labelZh}结果。\`, \`No \${cat.labelEn} output yet.\`),";
        }
        if (lines[i].includes('label: \\\\stage3 \\\\ json')) {
             lines[i] = "                            label: \`stage3 \${cat.key} json\`,";
        }
        if (lines[i].includes('eimport-stage3-')) {
             lines[i] = "                        key: \`reimport-stage3-\${cat.key}-and-rerun\`,";
        }
        if (lines[i].includes('estart-stage3-')) {
             lines[i] = "                        key: \`restart-stage3-\${cat.key}\`,";
        }
    }
    fs.writeFileSync(filePath, lines.join('\\n'), 'utf-8');
    console.log('Fixed via lines.');
}
