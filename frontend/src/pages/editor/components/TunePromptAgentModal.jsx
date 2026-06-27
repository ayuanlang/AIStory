import React, { useEffect, useState } from 'react';
import { Loader2, Sparkles, X } from 'lucide-react';
import { tuneShotPrompt } from '../../../services/api';
import { resolveTuneShotPromptFromResponse } from '../../../lib/promptUtils';

export default function TunePromptAgentModal({
    isOpen,
    onClose,
    initialValue = '',
    promptLang = 'cn',
    uiLang = 'zh',
    onApply,
    onLog,
}) {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [instruction, setInstruction] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        if (isOpen) {
            setInstruction('');
            setIsSubmitting(false);
        }
    }, [isOpen, initialValue]);

    if (!isOpen) return null;

    const handleSubmit = async () => {
        const trimmedInstruction = String(instruction || '').trim();
        const originalPrompt = String(initialValue || '').trim();
        if (!trimmedInstruction) {
            onLog?.(t('请先填写修改意见', 'Please enter modification instructions first'), 'warning');
            return;
        }
        if (!originalPrompt) {
            onLog?.(t('当前提示词为空，无法修改', 'Current prompt is empty; nothing to modify'), 'warning');
            return;
        }

        setIsSubmitting(true);
        onLog?.(t('正在提交 LLM 修改提示词...', 'Submitting prompt modification to LLM...'), 'process');
        try {
            const res = await tuneShotPrompt({
                original_prompt: originalPrompt,
                instruction: trimmedInstruction,
                prompt_lang: promptLang,
            });
            const refined = resolveTuneShotPromptFromResponse(res);
            if (!refined) {
                throw new Error(t('未返回有效提示词', 'No valid refined prompt returned'));
            }
            await onApply?.(refined);
            onLog?.(t('提示词已更新', 'Prompt updated'), 'success');
            onClose?.();
        } catch (error) {
            const detail = error?.response?.data?.detail || error?.message || String(error);
            onLog?.(`${t('提示词修改失败', 'Prompt modification failed')}: ${detail}`, 'error');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-2xl shadow-2xl flex flex-col max-h-[85vh]">
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 shrink-0">
                    <div className="flex flex-col">
                        <h3 className="font-bold text-lg text-white flex items-center gap-2">
                            <Sparkles className="w-4 h-4 text-primary" />
                            {t('AI 提示词修改', 'AI Prompt Tuning')}
                        </h3>
                        <p className="text-xs text-white/50 mt-1">
                            {t('填写修改意见后提交，将按分镜提示词格式返回并覆盖当前提示词。', 'Submit your edit request; the refined prompt will follow the shot format and replace the current text.')}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={isSubmitting}
                        className="p-2 hover:bg-white/10 rounded-lg transition-colors disabled:opacity-40"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                    <div className="space-y-2">
                        <label className="text-xs font-bold text-muted-foreground uppercase">
                            {t('当前提示词（只读）', 'Current Prompt (Read-only)')}
                        </label>
                        <textarea
                            readOnly
                            value={initialValue || ''}
                            className="w-full h-40 bg-black/30 border border-white/10 rounded-md p-3 text-xs text-white/80 font-mono resize-none focus:outline-none"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-bold text-muted-foreground uppercase">
                            {t('修改意见', 'Modification Instructions')}
                        </label>
                        <textarea
                            value={instruction}
                            onChange={(e) => setInstruction(e.target.value)}
                            disabled={isSubmitting}
                            placeholder={t(
                                '例如：把 P2 的运镜改成缓慢推近；加强窗外冷光对比；让 Lin 的对白时视线更明确看向 Chen…',
                                'e.g. Change P2 camera move to a slow push-in; increase cold window-light contrast; make Lin look more clearly at Chen during dialogue…'
                            )}
                            className="w-full h-36 bg-black/30 border border-white/10 rounded-md p-3 text-sm text-white focus:outline-none focus:border-primary/50 resize-none disabled:opacity-60"
                        />
                    </div>
                </div>

                <div className="px-6 py-4 border-t border-white/10 flex justify-end gap-3 shrink-0 bg-black/20">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={isSubmitting}
                        className="px-4 py-2 rounded hover:bg-white/10 text-sm disabled:opacity-40"
                    >
                        {t('取消', 'Cancel')}
                    </button>
                    <button
                        type="button"
                        onClick={handleSubmit}
                        disabled={isSubmitting || !instruction.trim()}
                        className="px-6 py-2 bg-primary hover:bg-primary/90 text-primary-foreground rounded text-sm font-medium flex items-center gap-2 disabled:opacity-40"
                    >
                        {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                        {isSubmitting ? t('提交中...', 'Submitting...') : t('提交修改', 'Submit')}
                    </button>
                </div>
            </div>
        </div>
    );
}
