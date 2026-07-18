import React, { useCallback, useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { Loader2, Mail, Stethoscope, X } from 'lucide-react';
import scriptAnalysisManual from '../../../../../docs/script_analysis_user_manual.md?raw';
import { runScriptAnalysisAiDiagnosis } from '../../../services/api';

const OPS_EMAIL = 'metawave@126.com';

export default function AiDiagnosisModal({
    open,
    onClose,
    uiLang = 'zh',
    systemLogs = [],
    workspaceSummary = '',
    projectId = null,
    episodeId = null,
    episodeLabel = '',
    systemApiId = null,
    onLog = null,
}) {
    const t = useCallback((zh, en) => (uiLang === 'zh' ? zh : en), [uiLang]);
    const [userNote, setUserNote] = useState('');
    const [sendToOps, setSendToOps] = useState(false);
    const [running, setRunning] = useState(false);
    const [sendingOnly, setSendingOnly] = useState(false);
    const [advice, setAdvice] = useState('');
    const [error, setError] = useState('');
    const [emailNotice, setEmailNotice] = useState('');

    const logsText = useMemo(() => {
        const lines = Array.isArray(systemLogs) ? systemLogs : [];
        return lines.map((line) => String(line || '').trim()).filter(Boolean).join('\n');
    }, [systemLogs]);

    useEffect(() => {
        if (!open) return;
        setUserNote('');
        setSendToOps(false);
        setAdvice('');
        setError('');
        setEmailNotice('');
    }, [open]);

    const runDiagnosis = useCallback(async ({ forceSendToOps = null } = {}) => {
        const shouldSend = forceSendToOps == null ? sendToOps : Boolean(forceSendToOps);
        setRunning(true);
        setError('');
        setEmailNotice('');
        try {
            const result = await runScriptAnalysisAiDiagnosis({
                manual_text: String(scriptAnalysisManual || ''),
                system_logs: logsText,
                workspace_summary: String(workspaceSummary || ''),
                user_note: userNote,
                project_id: projectId ? Number(projectId) : null,
                episode_id: episodeId ? Number(episodeId) : null,
                episode_label: episodeLabel,
                system_api_id: systemApiId ? Number(systemApiId) : null,
                send_to_ops: shouldSend,
            });
            const nextAdvice = String(result?.advice || '').trim();
            setAdvice(nextAdvice);
            onLog?.(t('AI 诊断已完成。', 'AI diagnosis finished.'), 'success');
            if (shouldSend) {
                if (result?.emailed_to_ops) {
                    setEmailNotice(t(
                        `已发送给运营人员（${result?.ops_email || OPS_EMAIL}）。`,
                        `Sent to ops (${result?.ops_email || OPS_EMAIL}).`
                    ));
                    onLog?.(t(`诊断内容已发送至 ${result?.ops_email || OPS_EMAIL}`, `Diagnosis emailed to ${result?.ops_email || OPS_EMAIL}`), 'success');
                } else {
                    const mailErr = String(result?.email_error || '').trim() || t('邮件发送失败', 'Email failed');
                    setEmailNotice(t(`诊断完成，但邮件未发出：${mailErr}`, `Diagnosis done, but email failed: ${mailErr}`));
                    onLog?.(t(`发送运营邮件失败：${mailErr}`, `Ops email failed: ${mailErr}`), 'warning');
                }
            }
        } catch (err) {
            const message = err?.response?.data?.detail || err?.message || String(err);
            setError(String(message));
            onLog?.(t(`AI 诊断失败：${message}`, `AI diagnosis failed: ${message}`), 'error');
        } finally {
            setRunning(false);
        }
    }, [
        episodeId,
        episodeLabel,
        logsText,
        onLog,
        projectId,
        sendToOps,
        systemApiId,
        t,
        userNote,
        workspaceSummary,
    ]);

    const resendToOps = useCallback(async () => {
        if (!advice.trim()) return;
        setSendingOnly(true);
        setEmailNotice('');
        try {
            const result = await runScriptAnalysisAiDiagnosis({
                manual_text: String(scriptAnalysisManual || ''),
                system_logs: logsText,
                workspace_summary: String(workspaceSummary || ''),
                user_note: userNote,
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
                setEmailNotice(t(
                    `邮件未发出：${result?.email_error || '未知错误'}`,
                    `Email failed: ${result?.email_error || 'unknown error'}`
                ));
            }
        } catch (err) {
            const message = err?.response?.data?.detail || err?.message || String(err);
            setEmailNotice(t(`发送失败：${message}`, `Send failed: ${message}`));
        } finally {
            setSendingOnly(false);
        }
    }, [
        advice,
        episodeId,
        episodeLabel,
        logsText,
        onLog,
        projectId,
        systemApiId,
        t,
        userNote,
        workspaceSummary,
    ]);

    if (!open) return null;

    return (
        <div
            className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
            onClick={() => {
                if (running || sendingOnly) return;
                onClose?.();
            }}
        >
            <div
                className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-3xl max-h-[88vh] shadow-2xl overflow-hidden flex flex-col"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                    <h3 className="text-lg font-bold flex items-center gap-2">
                        <Stethoscope className="w-5 h-5 text-emerald-300" />
                        {t('AI 诊断', 'AI Diagnosis')}
                    </h3>
                    <button
                        type="button"
                        disabled={running || sendingOnly}
                        onClick={() => onClose?.()}
                        className="px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-bold transition-colors text-white"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                <div className="p-4 overflow-y-auto custom-scrollbar flex-1 min-h-0 space-y-3 text-sm">
                    <p className="text-xs text-white/55 leading-relaxed">
                        {t(
                            '将把操作手册、系统日志、本集工作区概况提交给 AI，给出下一步操作建议。你也可以选择把材料与建议发给运营人员。开始诊断会按剧本分析接口计费；余额不足时会提示充值。仅发送已有建议给运营时不计费。',
                            'Submits the manual, system logs, and this episode’s workspace summary to AI for next-step advice. You can also email the package to ops. Starting diagnosis is billed via the script-analysis API; insufficient balance prompts a recharge. Resending existing advice to ops is not billed.'
                        )}
                    </p>

                    <div>
                        <label className="text-[11px] font-semibold text-white/70">
                            {t('您希望解决什么问题', 'What problem do you want to solve?')}
                        </label>
                        <textarea
                            className="mt-1 w-full min-h-[72px] rounded-md border border-white/15 bg-black/40 px-3 py-2 text-sm text-white/90 outline-none focus:border-emerald-400/50 resize-y"
                            placeholder={t(
                                '例如：场景编排已完成，但分镜一直不开始；或资产清单改过还没重跑。',
                                'e.g. Scene orchestration is done but storyboard never starts; or inventory was edited but downstream not rerun.'
                            )}
                            value={userNote}
                            disabled={running || sendingOnly}
                            onChange={(e) => setUserNote(e.target.value)}
                        />
                    </div>

                    <label className="flex items-start gap-2 text-xs text-white/75 cursor-pointer select-none">
                        <input
                            type="checkbox"
                            className="mt-0.5"
                            checked={sendToOps}
                            disabled={running || sendingOnly}
                            onChange={(e) => setSendToOps(e.target.checked)}
                        />
                        <span>
                            {t(
                                `诊断完成后，把提交材料与 AI 建议发送给运营人员（${OPS_EMAIL}）`,
                                `After diagnosis, email the package and AI advice to ops (${OPS_EMAIL})`
                            )}
                        </span>
                    </label>

                    {error ? (
                        <div className="rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-xs text-red-100">
                            {error}
                        </div>
                    ) : null}
                    {emailNotice ? (
                        <div className="rounded-lg border border-sky-400/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-100">
                            {emailNotice}
                        </div>
                    ) : null}

                    {advice ? (
                        <div className="rounded-lg border border-white/10 bg-black/30 px-4 py-3 prose prose-invert prose-p:my-1.5 prose-headings:my-2 max-w-none text-sm text-white/85">
                            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                                {advice}
                            </ReactMarkdown>
                        </div>
                    ) : (
                        <div className="rounded-lg border border-dashed border-white/10 px-4 py-8 text-center text-xs text-white/35">
                            {running
                                ? t('正在诊断，请稍候…', 'Diagnosing, please wait…')
                                : t('点击下方「开始诊断」生成建议。', 'Click Start Diagnosis below to generate advice.')}
                        </div>
                    )}
                </div>

                <div className="p-4 border-t border-white/10 bg-white/5 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[11px] text-white/40">
                        {episodeLabel || t('当前分集', 'Current episode')}
                    </span>
                    <div className="flex flex-wrap items-center gap-2">
                        {advice ? (
                            <button
                                type="button"
                                disabled={running || sendingOnly}
                                onClick={resendToOps}
                                className="px-3 py-2 rounded-lg text-sm font-bold border border-white/15 bg-white/5 hover:bg-white/10 text-white inline-flex items-center gap-1.5 disabled:opacity-40"
                            >
                                {sendingOnly ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                                {t('发送给运营', 'Email ops')}
                            </button>
                        ) : null}
                        <button
                            type="button"
                            disabled={running || sendingOnly}
                            onClick={() => runDiagnosis()}
                            className={`px-4 py-2 rounded-lg text-sm font-bold inline-flex items-center gap-2 ${
                                running || sendingOnly
                                    ? 'bg-white/5 text-white/35 cursor-not-allowed'
                                    : 'bg-emerald-600 hover:bg-emerald-500 text-white'
                            }`}
                        >
                            {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Stethoscope className="w-4 h-4" />}
                            {running ? t('诊断中…', 'Diagnosing…') : t('开始诊断', 'Start Diagnosis')}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
