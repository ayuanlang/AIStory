const fs = require('fs');
let p = 'C:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let t = fs.readFileSync(p, 'utf8');

t = t.replace("onLog?.(Storyboard generation trigger failed", "onLog?.(`Storyboard generation trigger failed");
t = t.replace(", 'warning');\n                    }\n            return;", "`, 'warning');\n                    }\n            return;");

// There are probably two of them!
t = t.replace(/onLog\?\.\(Storyboard generation trigger failed: /g, "onLog?.(`Storyboard generation trigger failed: ${e.message || e}`");

fs.writeFileSync(p, t, 'utf8');
console.log('Fixed quotes');