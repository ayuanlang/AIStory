import fs from 'fs';

let text = fs.readFileSync('c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx', 'utf-8');
const lines = text.split('\n');

lines[4177] = "                onLog?.(`[Stage 3 Asset Design] Reusing Stage 1 system_api_id=${phase1SystemApiId} for script_analysis routing.`, 'info');";

fs.writeFileSync('c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx', lines.join('\n'));
