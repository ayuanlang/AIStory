const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'frontend/src/pages/editor/components/ScriptEditor.jsx');
let content = fs.readFileSync(filePath, 'utf8');

const oldMarkerSave = `            const payload = {
                taskId,
                startedAt: Number(marker?.startedAt || Date.now()),
            };`;
            
const newMarkerSave = `            const payload = {
                taskId,
                startedAt: Number(marker?.startedAt || Date.now()),
                phase: marker?.phase || 1,
            };`;

content = content.replace(oldMarkerSave, newMarkerSave);
fs.writeFileSync(filePath, content);
console.log('Fixed saveAnalysisTaskMarker definition');
