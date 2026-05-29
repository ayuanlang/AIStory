const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let lines = fs.readFileSync(filePath, 'utf-8').split('\\n');

let inBadBlock = false;
for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes('key: \\\\stage3-asset-\\\\\\\\,') || lines[i].indexOf(' stage3-asset-\\\\') > -1) {
        lines[i] = "                key: \`stage3-asset-\${cat.key}\`,";
    }
    else if (lines[i].includes('summary: t(\\\\局部的\\\\结果。\\\\, \\\\Stage 3 \\\\ result.\\\\),')) {
        lines[i] = "                summary: t(\`局部的\${cat.labelZh}结果。\`, \`Stage 3 \${cat.labelEn} result.\`),";
    }
    else if (lines[i].includes('key: \\\\')) {
        let nxt = lines[i+1];
        if (nxt && nxt.includes('eimport-stage3-\\\\\\\\,')) {
             lines[i] = "                        key: \`reimport-stage3-\${cat.key}\`,";
             lines[i+1] = "";
        }
        else if (nxt && nxt.includes('estart-stage3-\\\\\\\\,')) {
             lines[i] = "                        key: \`restart-stage3-\${cat.key}\`,";
             lines[i+1] = "";
        }
    }
    else if (lines[i].includes('label: \\\\stage3 \\\\ json\\\\,')) {
        lines[i] = "                            label: \`stage3 \${cat.key} json\`,";
    }
    else if (lines[i].includes('placeholder: t(\\\\尚未返回\\\\结果。\\\\, \\\\No \\\\ output yet.\\\\),')) {
        lines[i] = "                placeholder: t(\`尚未返回\${cat.labelZh}结果。\`, \`No \${cat.labelEn} output yet.\`),";
    }
}

fs.writeFileSync(filePath, lines.join('\\n'), 'utf-8');
console.log('Fixed syntax safely');
