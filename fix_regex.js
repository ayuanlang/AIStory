const fs = require('fs');
const path = 'frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(path, 'utf8');

content = content.replace(/\\|\\\\Z\\)/g, "|$)");

fs.writeFileSync(path, content, 'utf8');

