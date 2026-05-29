import React from 'react';
import AgentChat from '../../../components/AgentChat';
import { streamAnalyzeScene } from '../../../services/api';
import { X, Check } from 'lucide-react';


export default function TunePromptAgentModal({ isOpen, onClose, initialValue, onApply }) {
    const t = (zh, en) => zh;
    const systemPrompt = "你是一个提示词优化助手。你的任务是对用户给出的基础提示词进行扩展、修改、改写或优化。重要要求：必须严格保持原有的角色、道具或环境的标签格式（如 CHAR:[@Name] (描述)、PROP:[@Prop] 等），只返回修改后的提示词内容，不要有任何多余的废话或前缀。";

    if (!isOpen) return null;

    const handleSendCustom = async (queryText, history, callbacks) => {
        // Build payload for analyze_scene LLM api explicitly
        const payload = {
            script_text: `【修改要求】\n${queryText}\n\n【原始提示词】\n${initialValue}`,
            system_prompt: systemPrompt,
            project_metadata: {},
            reuse_subject_assets: []
        };
        return await streamAnalyzeScene(payload, callbacks);
    };

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-2xl h-[70vh] shadow-2xl flex flex-col">
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 shrink-0">
                    <div className="flex flex-col">
                        <h3 className="font-bold text-lg text-white">
                            {t('通过对话微调', 'Tune via Chat')}
                        </h3>
                        <p className="text-xs text-white/50 mt-1">
                            {t('对话生成的新提示词会自动更新到左侧文本框中。', 'Generated prompts will automatically apply to the text box.')}
                        </p>
                    </div>
                    <button 
                        onClick={onClose}
                        className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="flex-1 overflow-hidden">
                    <AgentChat
                        title={t('提示词调优助手', 'Prompt Tuning Assistant')}
                        agentRole={t('你可以告诉我你是想要增加具体的描述、设定某种风格、更改角色的情感状态，或者是让画面感更强等。', 'Tell me how you would like to modify the prompt (e.g., add details, change style, alter emotion).')}
                        onSend={handleSendCustom}
                        defaultInput={''}
                        enableQuickActions={false}
                        embeddedMode={true}
                        renderResult={(content, isTyping) => (
                            <div className="relative group">
                                <div className="p-3 bg-black/20 rounded-lg border border-white/5 text-sm font-mono whitespace-pre-wrap">
                                    {content}
                                </div>
                                {!isTyping && content && (
                                    <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
                                        <button
                                            onClick={() => {
                                                onApply(content);
                                            }}
                                            className="px-3 py-1.5 flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded text-xs transition-colors shadow-lg"
                                        >
                                            <Check className="w-3.5 h-3.5" />
                                            {t('应用该提示词', 'Apply Prompt')}
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}
                    />
                </div>
            </div>
        </div>
    );
}