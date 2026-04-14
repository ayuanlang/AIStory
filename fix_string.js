const fs = require('fs');
const path = 'frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(path, 'utf8');

content = content.replace("(?=\\n###|\\Z)", "(?=\\n###|$)");
content = content.split("(?=\\n###|\\\\Z)").join("(?=\\n###|$)");

fs.writeFileSync(path, content, 'utf8');

