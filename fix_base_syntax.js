const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(filePath, 'utf-8');

let replaced = false;

if (content.includes('key: \\\\stage3-asset-\\\\\\\\,') || content.includes('key: \\\\stage3-asset-\\\\,')) {
   content = content.replace('key: \\\\stage3-asset-\\\\\\\\,', 'key: \`stage3-asset-\${cat.key}\`,');
   content = content.replace('key: \\\\stage3-asset-\\\\,', 'key: \`stage3-asset-\${cat.key}\`,');
   replaced = true;
}

if (content.includes('summary: t(\\\\局部的\\\\结果。\\\\, \\\\Stage 3 \\\\ result.\\\\),')) {
   content = content.replace('summary: t(\\\\局部的\\\\结果。\\\\, \\\\Stage 3 \\\\ result.\\\\),', 'summary: t(\`局部的\${cat.labelZh}结果。\`, \`Stage 3 \${cat.labelEn} result.\`),');
}

if (content.includes('placeholder: t(\\\\尚未返回\\\\结果。\\\\, \\\\No \\\\ output yet.\\\\),')) {
   content = content.replace('placeholder: t(\\\\尚未返回\\\\结果。\\\\, \\\\No \\\\ output yet.\\\\),', 'placeholder: t(\`尚未返回\${cat.labelZh}结果。\`, \`No \${cat.labelEn} output yet.\`),');
}

if (content.includes('label: \\\\stage3 \\\\ json\\\\,')) {
   content = content.replace('label: \\\\stage3 \\\\ json\\\\,', 'label: \`stage3 \${cat.key} json\`,');
}

if (content.includes('key: \\\\\neimport-stage3-\\\\\\\\,\n')) {
   content = content.replace('key: \\\\\neimport-stage3-\\\\\\\\,\n', 'key: \`reimport-stage3-\${cat.key}\`,\n');
} else if (content.includes('key: \\\\\nreimport-stage3-\\\\\\\\,\n')) {
   content = content.replace('key: \\\\\nreimport-stage3-\\\\\\\\,\n', 'key: \`reimport-stage3-\${cat.key}\`,\n');
} else if (content.match(/key:\s*\\+[\r\n]+eimport-stage3-\\+,/)) {
   content = content.replace(/key:\s*\\+[\r\n]+eimport-stage3-\\+,/, 'key: \`reimport-stage3-\${cat.key}\`,');
}

if (content.includes('key: \\\\\nestart-stage3-\\\\\\\\,\n')) {
   content = content.replace('key: \\\\\nestart-stage3-\\\\\\\\,\n', 'key: \`restart-stage3-\${cat.key}\`,\n');
} else if (content.includes('key: \\\\\nrestart-stage3-\\\\\\\\,\n')) {
   content = content.replace('key: \\\\\nrestart-stage3-\\\\\\\\,\n', 'key: \`restart-stage3-\${cat.key}\`,\n');
} else if (content.match(/key:\s*\\+[\r\n]+estart-stage3-\\+,/)) {
   content = content.replace(/key:\s*\\+[\r\n]+estart-stage3-\\+,/, 'key: \`restart-stage3-\${cat.key}\`,');
}


if (replaced) {
   fs.writeFileSync(filePath, content, 'utf-8');
   console.log('Fixed exactly.');
} else {
   console.log('Failed to find exactly.');
}
