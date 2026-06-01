const fs = require('fs');
const path = 'C:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(path, 'utf8');

const oldStr = \        phase2GenerationInFlightRef.current = true;

        setAnalysisFlowStatus({
            phase: "assets_gen",
            message: t("✨ 正在执行第四阶段资产设计 (共 3 项并发推演)...", "Running Stage 4 asset design..."),
        });

        const targetAssetsCount = 3;
        let assetsGenCompletedCount = 0;

        try {
            onLog?.(\\\[Stage 3 Asset Design] Preparing to fetch 3 entity_design prompts\\\);
            
            const promptFiles = [
                { key: 'characters', path: 'skills/scene_analysis_feature_stack/entity_design_character.md' },
                { key: 'environments', path: 'skills/scene_analysis_feature_stack/entity_design_environment.md' },
                { key: 'props', path: 'skills/scene_analysis_feature_stack/entity_design_prop.md' }
            ].filter(p => !options.targetEntityTypes || options.targetEntityTypes.includes(p.key));

            const commonPromptRes = await fetchPrompt("skills/scene_analysis_feature_stack/entity_design_common.md").catch(() => null);\;

const newStr = \        phase2GenerationInFlightRef.current = true;

        const promptFilesRaw = [
            { key: 'characters', path: 'skills/scene_analysis_feature_stack/entity_design_character.md' },
            { key: 'environments', path: 'skills/scene_analysis_feature_stack/entity_design_environment.md' },
            { key: 'props', path: 'skills/scene_analysis_feature_stack/entity_design_prop.md' }
        ];
        
        let targetFilters = options.targetEntityTypes;
        if (targetFilters && targetFilters.includes('posters') && !targetFilters.includes('environments')) {
            targetFilters = [...targetFilters, 'environments'];
        }

        const promptFiles = promptFilesRaw.filter(p => !targetFilters || targetFilters.includes(p.key));
        const targetAssetsCount = promptFiles.length;

        setAnalysisFlowStatus({
            phase: "assets_gen",
            message: t(\\\✨ 正在执行第四阶段资产设计 (共 \\\ 项并发推演)...\\\, \\\Running Stage 4 asset design (\\\ tasks)...\\\),
        });

        let assetsGenCompletedCount = 0;

        try {
            onLog?.(\\\[Stage 3 Asset Design] Preparing to fetch \\\ entity_design prompts\\\);

            const commonPromptRes = await fetchPrompt("skills/scene_analysis_feature_stack/entity_design_common.md").catch(() => null);\;

if (content.includes(oldStr)) {
    content = content.replace(oldStr, newStr);
    fs.writeFileSync(path, content, 'utf8');
    console.log('Successfully patched ScriptEditor.jsx');
} else {
    console.log('String not found!');
}
