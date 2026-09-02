import React from 'react';
import { AlertTriangle, Stethoscope, X } from 'lucide-react';

export default function FailedNodeInspectModal({
    open,
    payload = null,
    uiLang = 'zh',
    onClose,
    onDiagnose,
    onRerun,
    canRerun = false,
    rerunBusy = false,
}) {
    const t = React.useCallback((zh, en) => (uiLang === 'zh' ? zh : en), [uiLang]);

    if (!open || !payload) return null;

    const title = String(payload.label || t('失败节点', 'Failed node')).trim();
    const sceneLabel = String(payload.sceneLabel || payload.sceneId || '').trim();
    const reason = String(payload.reason || '').trim();
    const rawError = String(payload.rawError || '').trim();
    const errorCode = String(payload.errorCode || '').trim();
    const suggestions = Array.isArray(payload.suggestions) ? payload.suggestions.filter(Boolean) : [];

    return (
        <div
            className="fixed inset-0 z-[59] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
            onClick={() => onClose?.()}
        >
            <div
                className="bg-[#1a1a1a] border border-red-400/25 rounded-xl w-full max-w-xl max-h-[88vh] shadow-2xl overflow-hidden flex flex-col"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="flex items-start justify-between gap-3 p-4 border-b border-white/10 bg-red-500/10">
                    <div className="min-w-0">
                        <h3 className="text-lg font-bold flex items-center gap-2 text-red-100">
                            <AlertTriangle className="w-5 h-5 text-red-300 shrink-0" />
                            <span className="truncate">{title}</span>
                        </h3>
                        <p className="mt-1 text-xs text-white/50">
                            {sceneLabel
                                ? t(`场次 ${sceneLabel} · 点击节点可查看失败详情`, `Scene ${sceneLabel} · click a failed node for details`)
                                : t('全局节点 · 点击失败节点可查看原因与建议', 'Global node · click a failed node for the reason and next steps')}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => onClose?.()}
                        className="px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-bold transition-colors text-white shrink-0"
                        aria-label={t('关闭', 'Close')}
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
                    <section>
                        <div className="text-[11px] font-semibold tracking-wide text-white/45 mb-1.5">
                            {t('错误原因', 'Failure reason')}
                        </div>
                        <div className="rounded-lg border border-red-400/25 bg-red-500/10 px-3 py-2.5 text-sm text-red-50 leading-relaxed">
                            {reason || t('没有留下可读的失败原因。', 'No readable failure reason was stored.')}
                            {errorCode ? (
                                <div className="mt-1.5 text-[11px] text-red-100/60 font-mono break-all">
                                    {errorCode}
                                </div>
                            ) : null}
                        </div>
                    </section>

                    {rawError && rawError !== reason ? (
                        <section>
                            <div className="text-[11px] font-semibold tracking-wide text-white/45 mb-1.5">
                                {t('原始错误', 'Raw error')}
                            </div>
                            <pre className="rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-[11px] text-white/70 leading-relaxed whitespace-pre-wrap break-words max-h-36 overflow-y-auto">
                                {rawError}
                            </pre>
                        </section>
                    ) : null}

                    <section>
                        <div className="text-[11px] font-semibold tracking-wide text-white/45 mb-1.5">
                            {t('处理建议', 'What to do')}
                        </div>
                        {suggestions.length > 0 ? (
                            <ol className="list-decimal list-inside space-y-1.5 text-sm text-white/80 leading-relaxed">
                                {suggestions.map((item, index) => (
                                    <li key={`suggest-${index}`}>{item}</li>
                                ))}
                            </ol>
                        ) : (
                            <p className="text-sm text-white/55">
                                {t('可重跑该节点，或开 AI 诊断对照手册判断。', 'Rerun this node, or open AI Diagnosis for a guided next step.')}
                            </p>
                        )}
                    </section>
                </div>

                <div className="p-3 border-t border-white/10 bg-white/5 flex flex-wrap items-center justify-between gap-2">
                    <button
                        type="button"
                        onClick={() => onClose?.()}
                        className="px-3 py-2 rounded-lg text-sm font-bold border border-white/15 bg-white/5 hover:bg-white/10 text-white"
                    >
                        {t('关闭', 'Close')}
                    </button>
                    <div className="flex flex-wrap items-center gap-2">
                        {typeof onRerun === 'function' ? (
                            <button
                                type="button"
                                disabled={!canRerun || rerunBusy}
                                onClick={() => onRerun()}
                                className="px-3 py-2 rounded-lg text-sm font-bold border border-red-400/40 bg-red-500/15 hover:bg-red-500/25 text-red-100 disabled:opacity-40"
                            >
                                {t('重跑该节点', 'Rerun this node')}
                            </button>
                        ) : null}
                        <button
                            type="button"
                            onClick={() => onDiagnose?.()}
                            className="px-3 py-2 rounded-lg text-sm font-bold border border-emerald-400/40 bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-100 inline-flex items-center gap-1.5"
                        >
                            <Stethoscope className="w-4 h-4" />
                            {t('AI 诊断', 'AI Diagnosis')}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
