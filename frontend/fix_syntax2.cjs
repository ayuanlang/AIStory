const fs = require('fs');
let p = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let t = fs.readFileSync(p, 'utf8');
t = t.replace(/\\'/g, "'");
fs.writeFileSync(p, t, 'utf8');
console.log('Done');
