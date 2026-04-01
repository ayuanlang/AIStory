const fs = require('fs');
let file = 'frontend/src/pages/Editor.jsx';
let content = fs.readFileSync(file, 'utf8');

// 1. Remove the "New Scene" card from subjects panel
const newCardStart =                 <div\n                    onClick={handleCreate}\n                    className="border-2 border-dashed;
const newCardSnippetRegex = /<div\s+onClick=\{handleCreate\}\s+className="border-2 border-dashed border-white\/10 rounded-xl overflow-hidden text-muted-foreground hover:border-primary\/50 hover:text-primary cursor-pointer transition-all bg-black\/20 w-full min-h-\[240px\] flex flex-col"\s*>\s*<div className="aspect-video w-full flex items-center justify-center bg-black\/30 border-b border-white\/10">\s*<span className="text-4xl"><Plus \/><\/span>\s*<\/div>\s*<div className="flex-1 p-3 flex flex-col justify-center">\s*<span className="text-xs uppercase font-bold">\{t\('新建', 'New'\)\} \{subTab\}<\/span>\s*<span className="text-\[11px\] text-white\/40 mt-1">\{t\('创 建并管理主体信息', 'Create and manage subject info'\)\}<\/span>\s*<\/div>\s*<\/div>/g;

content = content.replace(
    /(<div\s+onClick=\{handleCreate\}\s+className="border-2 border-dashed border-white\/10 rounded-xl[^>]+>\s*<div className="aspect-video[^>]+>\s*<span className="text-4xl"><Plus \/><\/span>\s*<\/div>\s*<div className="flex-1 p-3[^>]+>\s*<span[^>]+>\{t\([^)]+\)\}\s*\{subTab\}<\/span>\s*<span[^>]+>\{t\([^)]+\)\}<\/span>\s*<\/div>\s*<\/div>)/g,
    "{/*  removed per user request */}"
);

// 2. FixevalProjectWorkflowStage 
// Original: const [entities, scenes, episodes] = ... fetchScenes(id)
const replaceStageLogicRegex = /const \[entities, scenes, episodes\] = await Promise\.all\(\[\s*fetchEntities\(id\)\.catch\(\(\) => \[\]\),\s*fetchScenes\(id\)\.catch\(\(\) => \[\]\),\s*fetchEpisodes\(id\)\.catch\(\(\) => \[\]\)\s*\]\);\s*const hasAssets = entities && entities\.length > 0;\s*const hasScenes = scenes && scenes\.length > 0;([\s\S]*?)if \(allVideosReady\) \{\s*nextStage = 'montage';\s*\} else if \(hasShots && allAssetsReady\) \{\s*nextStage = 'shots';\s*\} else if \(allAssetsReady && hasScenes\) \{\s*nextStage = 'shots';\s*\} else if \(hasAssets \|\| hasScenes\) \{\s*nextStage = 'subjects';\s*\} else \{\s*nextStage = 'script';\s*\}/m;

const newLogic = const [entities, episodes] = await Promise.all([
                fetchEntities(id).catch(() => []),
                fetchEpisodes(id).catch(() => [])
            ]);

            const hasAssets = entities && entities.length > 0;
            const hasEpisodes = episodes && episodes.length > 0;
            let allAssetsReady = false;
            
            if (hasAssets) {
                // 如果所有的资产都有对应图片了
                allAssetsReady = entities.every(e => !!e.image_url);
            }

            let allVideosReady = false;
            let hasShots = false;
            let hasScenes = false;

            if (hasEpisodes) {
                let anyActive = false;
                let allVids = true;
                
                for (const ep of episodes) {
                    const epShots = await fetchEpisodeShots(id, ep.id).catch(() => []);
                    if (epShots && epShots.length > 0) {
                        hasShots = true;
                        anyActive = true;
                        if (!epShots.every(s => !!s.video_url)) {
                            allVids = false;
                            break;
                        }
                    }
                }
                allVideosReady = anyActive && allVids;
            }

            if (allVideosReady) {
                nextStage = 'montage';
            } else if (allAssetsReady) {
                // According to requirements: "如果所有的资产都有对应图片了，就 应该进入分镜阶段"
                nextStage = 'shots';
            } else if (hasAssets || hasEpisodes) {
                nextStage = 'subjects';
            } else {
                nextStage = 'script';
            }
;

content = content.replace(replaceStageLogicRegex, newLogic);

fs.writeFileSync(file, content, 'utf8');
console.log('Patched editor');
