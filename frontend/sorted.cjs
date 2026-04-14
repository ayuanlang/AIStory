const fs = require('fs');
let c = fs.readFileSync('C:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx', 'utf8');

const targetStr =     const sortedShots = useMemo(() => {
        return [...(shots || [])];
    }, [shots]);;

const replaceStr =     const sortedShots = useMemo(() => {
        return [...(shots || [])].sort((a, b) => {
            const sceneIdxA = (scenes || []).findIndex(s => String(s.id) === String(a.scene_id));
            const sceneIdxB = (scenes || []).findIndex(s => String(s.id) === String(b.scene_id));
            
            if (sceneIdxA !== -1 && sceneIdxB !== -1 && sceneIdxA !== sceneIdxB) {
                return sceneIdxA - sceneIdxB;
            }
            
            const sceneA = a.scene_no || a.scene_id || "";
            const sceneB = b.scene_no || b.scene_id || "";
            if (sceneA !== sceneB) {
                return String(sceneA).localeCompare(String(sceneB), undefined, {numeric: true, sensitivity: 'base'});
            }
            
            const shotA = a.shot_no || a.shot_id || a.id || "";
            const shotB = b.shot_no || b.shot_id || b.id || "";
            return String(shotA).localeCompare(String(shotB), undefined, {numeric: true, sensitivity: 'base'});
        });
    }, [shots, scenes]);;

c = c.replace(targetStr, replaceStr);
fs.writeFileSync('C:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx', c);
console.log('Replaced');
