const fs = require('fs');
const filepath = 'frontend/src/pages/editor/components/SubjectLibrary.jsx';
let text = fs.readFileSync(filepath, 'utf8');

const start_str = 'const checkPoll = async () => {';
const end_str = 'updatesToApply.forEach(({ id, latest }) => {';

const def_index = text.indexOf(start_str);
const end_index = text.indexOf(end_str, def_index);

const old_block = text.substring(def_index, end_index + end_str.length);

const new_block = `const checkPoll = async () => {
            const currentAnalyzing = analyzingEntitiesRef.current;
            const analyzingIds = Object.keys(currentAnalyzing);
            if (analyzingIds.length === 0) return;

            try {
                const latestEntities = await fetchEntities(projectId, { include_project_null_episode: true });
                let changed = false;
                const updatesToApply = [];
                
                // Calculate updates BEFORE setAnalyzingEntities so we can iterate them!
                analyzingIds.forEach(id => {
                    const latest = latestEntities.find(e => String(e.id) === id);
                    const trackingData = currentAnalyzing[id];
                    if (!trackingData) return;

                    const initialAnalysisTime = trackingData?.initialAnalysisTime;
                    const startedAt = trackingData?.startedAt || Date.now();

                    if (!latest) {
                        changed = true;
                    } else if (getEntityAnalysisTime(latest) !== initialAnalysisTime) {
                        changed = true;
                        updatesToApply.push({ id, latest });
                    } else if (Date.now() - startedAt > 300000) {
                        changed = true;
                    }
                });

                if (changed) {
                    setAnalyzingEntities(prev => {
                        const next = { ...prev };
                        analyzingIds.forEach(id => {
                            const latest = latestEntities.find(e => String(e.id) === id);
                            const trackingData = next[id];
                            if (!trackingData) return;

                            const initialAnalysisTime = trackingData?.initialAnalysisTime;
                            const startedAt = trackingData?.startedAt || Date.now();

                            if (!latest) {
                                delete next[id];
                            } else if (getEntityAnalysisTime(latest) !== initialAnalysisTime) {
                                delete next[id];
                            } else if (Date.now() - startedAt > 300000) {
                                delete next[id];
                                if (onLog) onLog(\aSubject analysis timed out for \${latest.name}\`, 'warning');
                            }
                        });

                        if (subjectAnalyzingStorageKey) {
                            try {
                                if (Object.keys(next).length === 0) localStorage.removeItem(subjectAnalyzingStorageKey);
                                else localStorage.setItem(subjectAnalyzingStorageKey, JSON.stringify(next));
                            } catch {}
                        }
                        return next;
                    });
                }
                
                updatesToApply.forEach(/{ id, latest }) => {`;

if (text.includes(old_block)) {
    text = text.replace(old_block, new_block);
    fs.writeFileSync(filepath, text, 'utf8');
    console.log('Replaced successfully!');
} else {
    console.log('Could not find block!');
}