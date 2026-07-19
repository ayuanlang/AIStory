import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, Mail, Stethoscope, X } from 'lucide-react';
import scriptAnalysisManual from '../../../../../docs/script_analysis_user_manual.md?raw';
import assetPageManual from '../../../../../docs/asset_page_user_manual.md?raw';
import AgentChat from '../../../components/AgentChat';
import { runScriptAnalysisAiDiagnosis } from '../../../services/api';

const OPS_EMAIL = 'metawave@126.com';

const PAGE_PRESETS = {
    script_analysis: {
        pageScope: 'script_analysis',
        historyStorageKey: 'aistory.script_analysis.ai_diagnosis.history',
        manualText: scriptAnalysisManual,
        titleZh: 'AI 诊断（Agent）',
        titleEn: 'AI Diagnosis (Agent)',
        descriptionZh:
            'Agent 模式：可多轮对话。系统会带上操作手册、日志与本集工作区概况；你可追问细化建议。每轮对话按剧本分析接口计费；仅发送已有对话给运营不计费。',
        descriptionEn:
            'Agent mode: multi-turn chat with the manual, logs, and workspace summary. Follow-ups are supported. Each turn is billed via the script-analysis API; emailing an existing conversation to ops is free.',
    },
    assets: {
        pageScope: 'assets',
        historyStorageKey: 'aistory.assets.ai_diagnosis.history',
        manualText: assetPageManual,
        titleZh: '资产 AI 诊断（Agent）',
        titleEn: 'Assets AI Diagnosis (Agent)',
        descriptionZh:
            'Agent 模式：可多轮对话。系统会带上资产页操作手册、日志与当前资产工作区概况；你可追问细化建议。每轮对话按剧本分析接口计费；仅发送已有对话给运营不计费。',
        descriptionEn:
            'Agent mode: multi-turn chat with the assets manual, logs, and workspace summary. Follow-ups are supported. Each turn is billed via the script-analysis API; emailing an existing conversation to ops is free.',
    },
};

export default function AiDiagnosisModal({
    open,
    onClose,
    uiLang = 'zh',
    pageKey = 'script_analysis',
    systemLogs = [],
    workspaceSummary = '',
    projectId = null,
    episodeId = null,
    episodeLabel = '',
    systemApiId = null,
    onLog = null,
}) {
    const t = useCallback((zh, en) => (uiLang === 'zh' ? zh : en), [uiLang]);
    const preset = PAGE_PRESETS[pageKey] || PAGE_PRESETS.script_analysis;
    const [sendingOnly, setSendingOnly] = useState(false);
    const [emailNotice, setEmailNotice] = useState('');
    const [emailError, setEmailError] = useState('');
    const [chatBusy, setChatBusy] = useState(false);
    const historyRef = useRef([]);
    const lastAdviceRef = useRef('');

    const logsText = useMemo(() => {
        const lines = Array.isArray(systemLogs) ? systemLogs : [];
        return lines.map((line) => String(line || '').trim()).filter(Boolean).join('\n');
    }, [systemLogs]);

    useEffect(() => {
        if (!open) return;
        setEmailNotice('');
        setEmailError('');
        setSendingOnly(false);
        setChatBusy(false);
    }, [open]);

    const handleHistoryChange = useCallback((history) => {
        historyRef.current = Array.isArray(history) ? history : [];
        const lastAssistant = [...historyRef.current].reverse().find((m) => m?.role === 'assistant' && String(m?.content || '').trim());
        if (lastAssistant) {
            lastAdviceRef.current = String(lastAssistant.content || '').trim();
        }
    }, []);

    const handleSendCustom = useCallback(async (queryText, normalizedHistory) => {
        setChatBusy(true);
        setEmailError('');
        try {
            const history = (Array.isArray(normalizedHistory) ? normalizedHistory : [])
                .filter((m) => m?.role === 'user' || m?.role === 'assistant')
                .map((m) => ({
                    role: String(m.role),
                    content: String(m.content || ''),
                }));
            const result = await runScriptAnalysisAiDiagnosis({
                page_scope: preset.pageScope,
                manual_text: String(preset.manualText || ''),
                system_logs: logsText,
                workspace_summary: String(workspaceSummary || ''),
                user_note: String(queryText || ''),
                history,
                project_id: projectId ? Number(projectId) : null,
                episode_id: episodeId ? Number(episodeId) : null,
                episode_label: episodeLabel,
                system_api_id: systemApiId ? Number(systemApiId) : null,
                send_to_ops: false,
            });
            const reply = String(result?.advice || '').trim();
            if (!reply) {
                throw new Error(t('AI 未返回有效诊断内容，请稍后重试。', 'AI returned empty diagnosis. Please retry.'));
            }
            lastAdviceRef.current = reply;
            onLog?.(t('AI 诊断已回复。', 'AI diagnosis replied.'), 'success');
            return { reply };
        } catch (err) {
            const message = err?.response?.data?.detail || err?.message || String(err);
            onLog?.(t(`AI 诊断失败：${message}`, `AI diagnosis failed: ${message}`), 'error');
            throw err;
        } finally {
            setChatBusy(false);
        }
    }, [
        episodeId,
        episodeLabel,
        logsText,
        onLog,
        preset.manualText,
        preset.pageScope,
        projectId,
        systemApiId,
        t,
        workspaceSummary,
    ]);

    const resendToOps = useCallback(async () => {
        const advice = String(lastAdviceRef.current || '').trim();
        if (!advice) {
            setEmailError(t('请先完成至少一轮诊断对话，再发送给运营。', 'Finish at least one diagnosis turn before emailing ops.'));
            return;
        }
        setSendingOnly(true);
        setEmailNotice('');
        setEmailError('');
        try {
            const history = (Array.isArray(historyRef.current) ? historyRef.current : [])
                .filter((m) => m?.role === 'user' || m?.role === 'assistant')
                .map((m) => ({
                    role: String(m.role),
                    content: String(m.content || ''),
                }));
            const lastUser = [...history].reverse().find((m) => m.role === 'user');
            const result = await runScriptAnalysisAiDiagnosis({
                page_scope: preset.pageScope,
                manual_text: String(preset.manualText || ''),
                system_logs: logsText,
                workspace_summary: String(workspaceSummary || ''),
                user_note: String(lastUser?.content || ''),
                history,
                existing_advice: advice,
                project_id: projectId ? Number(projectId) : null,
                episode_id: episodeId ? Number(episodeId) : null,
                episode_label: episodeLabel,
                system_api_id: systemApiId ? Number(systemApiId) : null,
                send_to_ops: true,
            });
            if (result?.emailed_to_ops) {
                setEmailNotice(t(
                    `已发送给运营人员（${result?.ops_email || OPS_EMAIL}）。`,
                    `Sent to ops (${result?.ops_email || OPS_EMAIL}).`
                ));
                onLog?.(t(`诊断内容已发送至 ${result?.ops_email || OPS_EMAIL}`, `Diagnosis emailed to ${result?.ops_email || OPS_EMAIL}`), 'success');
            } else {
                const mailErr = String(result?.email_error || '').trim() || t('邮件发送失败', 'Email failed');
                setEmailError(t(`邮件未发出：${mailErr}`, `Email failed: ${mailErr}`));
                onLog?.(t(`发送运营邮件失败：${mailErr}`, `Ops email failed: ${mailErr}`), 'warning');
            }
        } catch (err) {
            const message = err?.response?.data?.detail || err?.message || String(err);
            setEmailError(t(`发送失败：${message}`, `Send failed: ${message}`));
        } finally {
            setSendingOnly(false);
        }
    }, [
        episodeId,
        episodeLabel,
        logsText,
        onLog,
        preset.manualText,
        preset.pageScope,
        projectId,
        systemApiId,
        t,
        workspaceSummary,
    ]);

    if (!open) return null;

    return (
        <div
            className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
            onClick={() => {
                if (chatBusy || sendingOnly) return;
                onClose?.();
            }}
        >
            <div
                className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-3xl h-[88vh] max-h-[88vh] shadow-2xl overflow-hidden flex flex-col"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="px-4 pt-3 pb-2 border-b border-white/10 bg-white/5 space-y-2">
                    <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <Stethoscope className="w-5 h-5 text-emerald-300" />
                                {t(preset.titleZh, preset.titleEn)}
                            </h3>
                            <p className="mt-1 text-xs text-white/55 leading-relaxed">
                                {t(preset.descriptionZh, preset.descriptionEn)}
                            </p>
                        </div>
                        <button
                            type="button"
                            disabled={chatBusy || sendingOnly}
                            onClick={() => onClose?.()}
                            className="px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-bold transition-colors text-white shrink-0"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                    {(emailNotice || emailError) ? (
                        <div className={`rounded-lg border px-3 py-2 text-xs ${
                            emailError
                                ? 'border-red-400/40 bg-red-500/10 text-red-100'
                                : 'border-sky-400/30 bg-sky-500/10 text-sky-100'
                        }`}
                        >
                            {emailError || emailNotice}
                        </div>
                    ) : null}
                </div>

                <div className="flex-1 min-h-0 overflow-hidden [&_.bg-card]:bg-transparent [&_.bg-card]:border-0 [&_.bg-card]:rounded-none [&_.bg-card]:shadow-none">
                    <AgentChat
                        customModeOnly
                        hideHeader
                        customPlaceholder={t(
                            '描述卡住的问题，或继续追问……',
                            'Describe the blocker, or ask a follow-up…'
                        )}
                        loadHistoryLabel={t('加载上次诊断对话', 'Load previous diagnosis chat')}
                        historyStorageKey={preset.historyStorageKey}
                        onSendCustom={handleSendCustom}
                        onHistoryChange={handleHistoryChange}
                    />
                </div>

                <div className="p-3 border-t border-white/10 bg-white/5 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[11px] text-white/40">
                        {episodeLabel || t('当前分集', 'Current episode')}
                    </span>
                    <button
                        type="button"
                        disabled={chatBusy || sendingOnly}
                        onClick={resendToOps}
                        className="px-3 py-2 rounded-lg text-sm font-bold border border-white/15 bg-white/5 hover:bg-white/10 text-white inline-flex items-center gap-1.5 disabled:opacity-40"
                    >
                        {sendingOnly ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                        {t('发送对话给运营', 'Email chat to ops')}
                    </button>
                </div>
            </div>
        </div>
    );
}
