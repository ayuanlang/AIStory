import fs from 'fs';

const text = fs.readFileSync('c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx', 'utf-8');
const lines = text.split('\n');

for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes('Stage 3 Asset') && lines[i].includes('onLog')) {
        console.log(`${i+1}: ${lines[i]}`);
    }
}
