const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ShotsView.jsx', 'utf8');

const regex = /if\s*\(phase\s*===\s*'queued'\s*\|\|\s*phase\s*===\s*'running'\)\s*\{\s*setShotGeneratingState\(stableShotId,\s*stableMediaKey,\s*true\);\s*return\s*\{\s*state:\s*'running',\s*jobId:\s*stableJobId,\s*source:\s*'local',\s*phase\s*\};\s*\}/;

const replace = `const isTerminal = ['succeeded', 'completed', 'failed', 'error', 'canceled', 'cancelled'].includes(phase) || Boolean(status?.result?.url || status?.result?.video_url || status?.url || status?.video_url);

                if (!isTerminal) {
                    setShotGeneratingState(stableShotId, stableMediaKey, true); 
                    return { state: 'running', jobId: stableJobId, source: 'local', phase };
                }`;

if (regex.test(text)) {
    text = text.replace(regex, replace);
    fs.writeFileSync('src/pages/editor/components/ShotsView.jsx', text);
    console.log("Success");
} else {
    console.log("Not found in regex");
}const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ShotsView.jsx', 'utf8');

const search = `                if (phase === 'queued' || phase === 'running') {
                    setShotGeneratingState(stableShotId, stableMediaKey, true); 
                    return { state: 'running', jobId: stableJobId, source: 'local', phase };
                }`;

const replace = `                const isTerminal = ['succeeded', 'completed', 'failed', 'error', 'canceled', 'cancelled'].includes(phase) || Boolean(status?.result?.url || status?.result?.video_url || status?.url || status?.video_url);

                if (!isTerminal) {
                    setShotGeneratingState(stableShotId, stableMediaKey, true); 
                    return { state: 'running', jobId: stableJobId, source: 'local', phase };
                }`;

if (text.includes(search)) {
    text = text.replace(search, replace);
    fs.writeFileSync('src/pages/editor/components/ShotsView.jsx', text);
    console.log("Success");
} else {
    console.log("Not found in text");
}