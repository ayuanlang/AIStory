const fs = require('fs');
let p = 'C:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let t = fs.readFileSync(p, 'utf8');

t = t.replace("onLog?.(`Storyboard generation trigger failed: , 'warning');", "onLog?.(`Storyboard generation trigger failed: ${e.message || e}`, 'warning');");

// Oh let's also check for asset rerun
t = t.replace("onLog?.(`Storyboard generation trigger failed: \`", "onLog?.(`Storyboard generation trigger failed: ${e.message || e}`");

fs.writeFileSync(p, t, 'utf8');
console.log('Fixed line 5439');