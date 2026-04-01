const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

// 1. Fix "???"
content = content.replace(/t\('\?\?\?', 'Generator'\)/g, "t('生成器', 'Generator')");

// 2. Remove Add Entity Card
const addCardRegex = /<div\s+onClick=\{handleCreate\}\s+className="border-2 border-dashed border-white\/10 rounded-xl overflow-hidden text-muted-foreground hover:border-primary\/50 hover:text-primary cursor-pointer transition-all bg-black\/20 w-full min-h-\[240px\] flex flex-col"\s*>[\s\S]*?<span className="text-4xl"><Plus \/><\/span>[\s\S]*?\{t\('新建', 'New'\)\} \{subTab\}<\/span>[\s\S]*?<\/div>\s*<\/div>/;

if(addCardRegex.test(content)){
    content = content.replace(addCardRegex, "");
    console.log("Add Entity Card removed.");
} else {
    console.log("Failed to find Add Entity Card.");
}

// 3. Eval Stage Logic
const evalStageRegex = /const \[entities, scenes, episodes\] = await Promise\.all\(\[[\s\S]*?else \{\s*nextStage = 'script';\s*\}/;

const evalStageReplacement = `const [entities, episodes] = await Promise.all([
                fetchEntities(id).catch(() => []),
                fetchEpisodes(id).catch(() => [])
            ]);

            const hasAssets = entities && entities.length > 0;
            let hasScenes = false;
            
            if (episodes && episodes.length > 0) {
                const ep1Scenes = await fetchScenes(episodes[0].id).catch(() => []);
                hasScenes = ep1Scenes && ep1Scenes.length > 0;
            }

            let allAssetsReady = false;
            if (hasAssets) {
                // 如果所有的资产都有对应图片了，就应该进入分镜阶段
                allAssetsReady = entities.every(e => !!e.image_url);
            }

            let allVideosReady = false;
            let hasShots = false;
            if (allAssetsReady && episodes && episodes.length > 0) {
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
            } else if (hasAssets && allAssetsReady) {
                nextStage = 'shots';
            } else if (hasAssets || hasScenes) {
                nextStage = 'subjects';
            } else {
                nextStage = 'script';
            }`;

if (evalStageRegex.test(content)) {
    content = content.replace(evalStageRegex, evalStageReplacement);
    console.log("Stage logic replaced.");
} else {
    console.log("Failed to find Stage logic.");
}

fs.writeFileSync('frontend/src/pages/Editor.jsx', content, 'utf8');
