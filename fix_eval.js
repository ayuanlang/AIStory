const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

// Insert a function evalProjectWorkflowStage inside the Editor component
const editorFuncStart = content.indexOf('const Editor = ({');
const endOfEditorHooks = content.indexOf('useEffect(() => {', editorFuncStart);

const stageEvalCode = `
    const evalProjectWorkflowStage = async () => {
        if (!id) return;
        try {
            const currentProj = await fetchProject(id);
            const currentStage = currentProj?.global_info?.workflow_stage || 'script';
            let nextStage = 'script';

            const [entities, scenes, episodes] = await Promise.all([
                fetchEntities(id).catch(() => []),
                fetchScenes(id).catch(() => []),
                fetchEpisodes(id).catch(() => [])
            ]);

            const hasAssets = entities && entities.length > 0;
            const hasScenes = scenes && scenes.length > 0;
            let allAssetsReady = false;
            if (hasAssets) {
                // Ignore missing images only if strictly required. The instruction: "资产图片全部都生成好后进入分镜阶段"
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
            } else if (hasShots && allAssetsReady) {
                nextStage = 'shots';
            } else if (allAssetsReady && hasScenes) {
                nextStage = 'shots';
            } else if (hasAssets || hasScenes) {
                nextStage = 'subjects';
            } else {
                nextStage = 'script';
            }

            if (nextStage !== currentStage) {
                console.log(\`Advancing project stage: \${currentStage} => \${nextStage}\`);
                await updateProject(id, { 
                    global_info: { 
                        ...(currentProj?.global_info || {}), 
                        workflow_stage: nextStage 
                    } 
                });
                setProject(prev => ({ 
                    ...prev, 
                    global_info: { 
                        ...(prev?.global_info || {}), 
                        workflow_stage: nextStage 
                    } 
                }));
            }
        } catch (e) {
            console.error("Failed to eval project stage", e);
        }
    };

    useEffect(() => {
        // Poll every 10s to see if stage changes
        const interval = setInterval(() => {
            evalProjectWorkflowStage();
        }, 10000);
        return () => clearInterval(interval);
    }, [id]);

`;

content = content.slice(0, endOfEditorHooks) + stageEvalCode + content.slice(endOfEditorHooks);

// Expose wait wait. Is fetchEntities imported? We checked earlier, YES. 
// However, the `ProjectOverview` component receives `project.global_info`!
// Wait! ProjectOverview sets its `info` state at initialization but does it sync when `project` updates?
// `info` state inside ProjectOverview:
const infoSyncCode = `useEffect(() => { if (project?.global_info) setInfo(prev => ({...prev, workflow_stage: project.global_info.workflow_stage})) }, [project?.global_info?.workflow_stage]);`;

content = content.replace('setInfo(prev => ({ ...prev, ...merged }));\n        }\n    }, [project]);', 'setInfo(prev => ({ ...prev, ...merged }));\n        }\n    }, [project]);\n    ' + infoSyncCode);

fs.writeFileSync('frontend/src/pages/Editor.jsx', content);
console.log('Eval stage logic added');
