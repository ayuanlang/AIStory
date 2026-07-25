const fs = require('fs');
let p = 'C:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let t = fs.readFileSync(p, 'utf8');

t = t.replace(/prev !== '\\\\'\) \{/g, \"prev !== '\\\\\\\\'\) \{\");
fs.writeFileSync(p, t, 'utf8');
console.log('Fixed syntax error');