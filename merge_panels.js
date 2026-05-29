const fs = require('fs');

const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(filePath, 'utf-8');

const oldBlock = `        <div className="flex gap-4 h-1/3 min-h-[250px] shrink-0 mt-4 border-t border-white/10 pt-4 px-6 pb-6">
        {/* Stage 1 Panel */}
        <div className="flex-1 overflow-hidden">
            <LLMResultPanel
                title={t('第一阶段：剧本修改说明 / 优化后剧本 / 全局风格', 'Stage 1: Script Notes / Optimized Script / Global Style')}
                t={t}
                stageCards={stage1StageCards}
                placeholder={t('第一阶段产物...', 'Stage 1 outputs...')}
            />
        </div>
        {/* Stage 2 Panel */}
        <div className="flex-1 overflow-hidden">
            <LLMResultPanel
                title={t('第二阶段：场景分析结果 / 资产清单', 'Stage 2: Scene Analysis Result / Asset Index')}
                t={t}
                stageCards={stage2StageCards}
                placeholder={t('第二阶段产物...', 'Stage 2 outputs...')}
            />
        </div>
        {/* Stage 3 Panel */}
        <div className="flex-1 overflow-hidden">
            <LLMResultPanel
                title={t('第三阶段：资产设计', 'Stage 3: Asset Design')}
                t={t}
                stageCards={stage3StageCards}
                placeholder={t('第三阶段产物...', 'Stage 3 outputs...')}
            />
        </div>
    </div>`;

const newBlock = `        <div className="flex gap-4 h-1/3 min-h-[250px] shrink-0 mt-4 border-t border-white/10 pt-4 px-6 pb-6">
        <div className="flex-1 overflow-hidden">
            <LLMResultPanel
                title={t('AI 拆解产物', 'AI Analysis Artifacts')}
                t={t}
                stageCards={[...stage1StageCards, ...stage2StageCards, ...stage3StageCards]}
                placeholder={t('流程产出...', 'Pipeline outputs...')}
            />
        </div>
    </div>`;

if (content.includes('第一阶段产物')) {
    content = content.replace(oldBlock, newBlock);
    fs.writeFileSync(filePath, content, 'utf-8');
    console.log('Merged LLMResultPanel successfully.');
} else {
    console.log('Could not find the block to replace.');
}