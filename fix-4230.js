import fs from 'fs';

let text = fs.readFileSync('c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx', 'utf-8');
const lines = text.split('\n');

lines[4230] = "                    onLog && onLog('[Stage 3 Asset Design] Warning: AI did not return a valid asset-design JSON block. Skipping import to prevent overwriting the Stage 2 asset index.', 'warning');";

fs.writeFileSync('c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx', lines.join('\n'));