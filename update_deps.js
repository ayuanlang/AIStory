const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'frontend/src/pages/editor/components/ScriptEditor.jsx');
let content = fs.readFileSync(filePath, 'utf8');

// The new deps block we want to add
const oldDepsRegex = /(const resumeAnalysisFromTaskMarker = useCallback[\s\S]*?^    \}, \[)([\s\S]*?)(\]\);)/m;
const match = content.match(oldDepsRegex);

if (match) {
    let deps = match[2];
    if (!deps.includes('doImportText')) {
        deps = deps + '        doImportText,\n';
    }
    if (!deps.includes('setLlmAssetRawResultContent')) {
        deps = deps + '        setLlmAssetRawResultContent,\n';
    }
    if (!deps.includes('setIsRetryingPhase2')) {
        deps = deps + '        setIsRetryingPhase2,\n';
    }
    if (!deps.includes('projectId')) {
        deps = deps + '        projectId,\n';
    }
    if (!deps.includes('onLog')) {
        deps = deps + '        onLog,\n';
    }
    
    const newContent = content.replace(oldDepsRegex, `$1${deps}$3`);
    fs.writeFileSync(filePath, newContent);
    console.log("Dependencies updated.");
} else {
    console.error("Dependencies block not found.");
}
