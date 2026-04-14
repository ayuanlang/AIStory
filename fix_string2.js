const fs = require('fs');
const path = 'frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(path, 'utf8');

content = content.replace(/\\|\\\\Z\\)/g, "|$)");
// JS Regex issue, using string split
content = content.split("|\\\\Z)/").join("|$)/");

fs.writeFileSync(path, content, 'utf8');

