const fs = require('fs');
const p = 'C:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(p, 'utf8');
const s = content.indexOf('<table className=" w-full text-left border-collapse text-sm\>');
console.log(content.substring(s - 200, s));
