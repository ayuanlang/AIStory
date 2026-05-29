const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(filePath, 'utf-8');

content = content.replace(/key:\s*\\\\[\r\n]+eimport-stage3-\\\\,/g, 'key: \`reimport-stage3-\${cat.key}\`,');
content = content.replace(/key:\s*\\\\[\r\n]+estart-stage3-\\\\,/g, 'key: \`restart-stage3-\${cat.key}\`,');

fs.writeFileSync(filePath, content, 'utf-8');
console.log('Fixed exactly using RegExp CRLF.');
