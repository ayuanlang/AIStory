import fs from 'fs';

let text = fs.readFileSync('c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx', 'utf-8');

text = text.replace(/`\[Stage 3 Asset Design\]/g, "'[Stage 3 Asset Design]' + `");
text = text.replace(/onLog\?\.\('/g, "onLog && onLog('");

fs.writeFileSync('c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx', text);