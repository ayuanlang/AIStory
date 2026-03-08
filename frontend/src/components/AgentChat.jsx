
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import {
    sendAgentCommand,
    sendSystemManagementAgentCommand,
    streamAgentCommand,
    streamSystemManagementAgentCommand,
} from '../services/api';
import { Send, Bot, X, Trash2, History } from 'lucide-react';

/** Strip <think>...</think> blocks and unclosed <think> tails from streaming text. */
const stripThinkBlocks = (text) =>
    text.replace(/<think\b[^>]*>[\s\S]*?<\/think>/gi, '')
        .replace(/<think\b[^>]*>[\s\S]*$/gi, '')
        .trim();

/** Memoized message bubble — only re-renders when content/streaming flag changes. */
const MessageBubble = React.memo(({ role, content, streaming: isStreaming, actions, updatedData, onQuickAction }) => {
    if (role === 'user') {
        return (
            <div className="flex justify-end">
                <div className="max-w-[80%] rounded-lg p-3 bg-primary text-primary-foreground">
                    <p className="whitespace-pre-wrap">{content}</p>
                </div>
            </div>
        );
    }
    return (
        <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg p-3 bg-muted">
                <div className="agent-chat-md text-sm">
                    <ReactMarkdown>{content || ''}</ReactMarkdown>
                    {isStreaming && <span className="inline-block w-1.5 h-4 ml-0.5 bg-current animate-pulse align-text-bottom" />}
                </div>
                {!isStreaming && (() => {
                    const safeActions = Array.isArray(actions) ? actions : [];
                    if (!safeActions.length) return null;

                    const completed = safeActions.filter((a) => String(a?.status || '') === 'completed');
                    const failed = safeActions.filter((a) => String(a?.status || '') === 'failed');
                    const blocked = safeActions.filter((a) => String(a?.status || '') === 'blocked');

                    const hasWriteConfirm = (
                        String(updatedData?.type || '') === 'system_management_write_confirmation_required'
                        || blocked.some((a) => String(a?.tool || '') === 'upsert_system_api_pricing')
                    );

                    const previewItems = Array.isArray(updatedData?.items) ? updatedData.items : [];

                    return (
                        <div className="mt-3 space-y-2 border-t border-white/10 pt-2">
                            <div className="flex flex-wrap items-center gap-2 text-[11px]">
                                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">ok {completed.length}</span>
                                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">blocked {blocked.length}</span>
                                <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/30">failed {failed.length}</span>
                            </div>

                            {hasWriteConfirm && (
                                <div className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs space-y-2">
                                    <div className="text-amber-200 font-semibold">检测到写入确认步骤</div>
                                    {previewItems.length > 0 && (
                                        <div className="space-y-1 text-amber-100/90">
                                            {previewItems.slice(0, 6).map((item, idx) => (
                                                <div key={`${item?.provider || 'p'}-${item?.model || 'm'}-${idx}`} className="font-mono text-[11px]">
                                                    {idx + 1}. {item?.provider || '-'} / {item?.category || '-'} / {item?.model || '-'} | {item?.preview_action_label || '待确认'}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    <div className="flex items-center gap-2">
                                        <button
                                            type="button"
                                            onClick={() => onQuickAction?.('confirm_write')}
                                            className="px-2.5 py-1 rounded bg-amber-400 text-black hover:bg-amber-300 text-xs font-semibold"
                                        >
                                            确认并执行
                                        </button>
                                        <span className="text-[11px] text-amber-200/80">点击后会发送“确认执行以上更新”</span>
                                    </div>
                                </div>
                            )}

                            <div className="space-y-1">
                                {safeActions.slice(0, 8).map((a, idx) => (
                                    <div key={`${a?.tool || 'tool'}-${idx}`} className="text-[11px] text-muted-foreground bg-black/20 rounded px-2 py-1">
                                        <span className="font-mono">{a?.tool || 'unknown'}</span>
                                        <span className="mx-1">|</span>
                                        <span>{a?.status || '-'}</span>
                                        {a?.result && (
                                            <span className="ml-1">| {typeof a.result === 'string' ? a.result : JSON.stringify(a.result)}</span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    );
                })()}
            </div>
        </div>
    );
});

/**
 * Fully uncontrolled input – the browser handles all keystroke rendering natively
 * so typing is never blocked by React reconciliation on the main thread.
 */
const ChatInput = React.memo(({ onSend, loading, placeholder }) => {
    const inputRef = useRef(null);

    const submit = useCallback(() => {
        const el = inputRef.current;
        if (!el) return;
        const v = el.value.trim();
        if (!v) return;
        onSend(v);
        el.value = '';
    }, [onSend]);

    const handleKeyDown = useCallback((e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submit();
        }
    }, [submit]);

    return (
        <div className="p-4 border-t flex gap-2">
            <input
                ref={inputRef}
                className="flex-1 px-3 py-2 rounded-md border bg-background"
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={loading}
            />
            <button
                onClick={submit}
                disabled={loading}
                className="p-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
            >
                <Send className="w-5 h-5" />
            </button>
        </div>
    );
});

const STREAM_UI_INTERVAL = 50; // ms – throttle UI updates during streaming
const HISTORY_STORAGE_KEY = 'aistory.agent.chat.history';
const MAX_PERSISTED_MESSAGES = 100; // per mode, to cap localStorage size
const MAX_HISTORY_TO_SEND = 20;     // max messages sent to backend per request

/** Load saved history from localStorage. Returns default empty structure on failure. */
const loadPersistedHistory = () => {
    try {
        const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') {
            // Sanitise: keep only role + content, drop any leftover streaming flags
            const clean = (arr) =>
                (Array.isArray(arr) ? arr : []).slice(-MAX_PERSISTED_MESSAGES).map((m) => ({
                    role: String(m?.role || 'user'),
                    content: String(m?.content || ''),
                    ...(m?.actions ? { actions: m.actions } : {}),
                }));
            return {
                project: clean(parsed.project),
                system_management: clean(parsed.system_management),
            };
        }
    } catch { /* ignore corrupt data */ }
    return null;
};

const hasSavedHistory = () => {
    try {
        const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
        if (!raw) return false;
        const parsed = JSON.parse(raw);
        return !!((parsed?.project?.length) || (parsed?.system_management?.length));
    } catch { return false; }
};

const AgentChat = ({ context, onClose, isSuperuser = false, onHeaderPointerDown }) => {
    const [historyByMode, setHistoryByMode] = useState({ project: [], system_management: [] });
    const [loading, setLoading] = useState(false);
    const [streaming, setStreaming] = useState(false);
    const [mode, setMode] = useState('project');

    const activeHistory = Array.isArray(historyByMode?.[mode]) ? historyByMode[mode] : [];
    const scrollContainerRef = useRef(null);
    const endRef = useRef(null);
    // Accumulate streaming text via ref to avoid stale-closure issues
    const streamBufRef = useRef('');
    // Throttle: track whether a UI flush is already scheduled
    const streamFlushRef = useRef(null);
    const streamModeRef = useRef(mode);
    const historyRef = useRef(historyByMode);
    historyRef.current = historyByMode;

    // Persist history to localStorage whenever it changes (skip mid-stream placeholder messages)
    useEffect(() => {
        if (streaming) return; // don't persist partial streaming content
        try {
            const toSave = {
                project: (historyByMode.project || []).filter((m) => !m.streaming).slice(-MAX_PERSISTED_MESSAGES),
                system_management: (historyByMode.system_management || []).filter((m) => !m.streaming).slice(-MAX_PERSISTED_MESSAGES),
            };
            localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(toSave));
        } catch { /* quota exceeded – ignore */ }
    }, [historyByMode, streaming]);

    const handleClearHistory = useCallback(() => {
        setHistoryByMode((prev) => ({ ...(prev || {}), [mode]: [] }));
    }, [mode]);

    const handleLoadHistory = useCallback(() => {
        const saved = loadPersistedHistory();
        if (!saved) return;
        setHistoryByMode((prev) => ({
            ...(prev || {}),
            [mode]: saved[mode] || [],
        }));
    }, [mode]);

    const scrollToLatest = useCallback((behavior = 'smooth') => {
        if (endRef.current && typeof endRef.current.scrollIntoView === 'function') {
            endRef.current.scrollIntoView({ behavior, block: 'end' });
            return;
        }
        if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
        }
    }, []);

    useEffect(() => {
        const behavior = (loading || streaming) ? 'auto' : 'smooth';
        scrollToLatest(behavior);
    }, [mode, loading, streaming, activeHistory.length, scrollToLatest]);

    // Auto-scroll during streaming
    useEffect(() => {
        if (!streaming) return;
        const id = setInterval(() => scrollToLatest('auto'), 120);
        return () => clearInterval(id);
    }, [streaming, scrollToLatest]);

    const handleSend = useCallback(async (queryText) => {
        if (!queryText.trim()) return;
        const currentMode = mode;
        const currentHistory = Array.isArray(historyRef.current?.[currentMode]) ? historyRef.current[currentMode] : [];
        const updatedHistory = [...currentHistory, { role: 'user', content: queryText }];
        const withPlaceholder = [...updatedHistory, { role: 'assistant', content: '', streaming: true }];

        setHistoryByMode((prev) => ({ ...(prev || {}), [currentMode]: withPlaceholder }));
        setLoading(true);
        setStreaming(true);
        streamBufRef.current = '';

        const runtimeContext = {
            ...(context || {}),
            agent_mode: currentMode === 'system_management' ? 'system_management' : 'project',
        };
        const normalizedHistory = updatedHistory.slice(-MAX_HISTORY_TO_SEND).map((msg) => ({
            role: String(msg?.role || 'user'),
            content: String(msg?.content || ''),
        }));

        const isSystemMode = currentMode === 'system_management';
        streamModeRef.current = currentMode;

        // Flush accumulated stream buffer to React state (called at most once per STREAM_UI_INTERVAL)
        const flushStreamBuf = () => {
            streamFlushRef.current = null;
            const display = stripThinkBlocks(streamBufRef.current);
            const m = streamModeRef.current;
            setHistoryByMode((prev) => {
                const msgs = [...(prev[m] || [])];
                const last = msgs[msgs.length - 1];
                if (last && last.role === 'assistant') {
                    msgs[msgs.length - 1] = { ...last, content: display };
                }
                return { ...(prev || {}), [m]: msgs };
            });
        };

        try {
            const callbacks = {
                onToken: (text) => {
                    streamBufRef.current += text;
                    // Throttle: schedule a UI flush if one isn't pending
                    if (!streamFlushRef.current) {
                        streamFlushRef.current = setTimeout(flushStreamBuf, STREAM_UI_INTERVAL);
                    }
                },
            };

            const result = isSystemMode
                ? await streamSystemManagementAgentCommand(queryText, runtimeContext, normalizedHistory, callbacks)
                : await streamAgentCommand(queryText, runtimeContext, normalizedHistory, callbacks);

            setStreaming(false);

            // Flush any pending throttled update
            if (streamFlushRef.current) {
                clearTimeout(streamFlushRef.current);
                streamFlushRef.current = null;
            }

            // Replace with final clean reply from done event
            const finalReply = result.reply || stripThinkBlocks(streamBufRef.current) || '';
            setHistoryByMode((prev) => ({
                ...(prev || {}),
                [currentMode]: [...updatedHistory, { role: 'assistant', content: finalReply, actions: result.actions, updatedData: result.updated_data }],
            }));
        } catch (error) {
            console.error(error);
            setStreaming(false);
            if (streamFlushRef.current) {
                clearTimeout(streamFlushRef.current);
                streamFlushRef.current = null;
            }
            const errorMessage =
                error?.userMessage ||
                error?.response?.data?.detail ||
                error?.message ||
                'Error communicating with AI.';
            setHistoryByMode((prev) => ({
                ...(prev || {}),
                [currentMode]: [...updatedHistory, { role: 'system', content: errorMessage }],
            }));
        } finally {
            setLoading(false);
            setStreaming(false);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [mode, context]);

    const handleQuickAction = useCallback((actionType) => {
        if (actionType === 'confirm_write') {
            handleSend('确认执行以上更新');
        }
    }, [handleSend]);

    return (
        <div className="flex flex-col h-full bg-card rounded-lg border shadow-sm">
            <div className="p-4 border-b font-semibold flex items-center justify-between gap-2 cursor-grab active:cursor-grabbing select-none"
                 onPointerDown={onHeaderPointerDown}>
                <div className="flex items-center gap-2">
                    <Bot className="w-5 h-5 text-primary" />
                    {mode === 'system_management' ? 'System Management Agent' : 'AI Assistant'}
                </div>
                {isSuperuser && (
                    <div className="ml-auto mr-2 flex items-center gap-1 rounded-md border border-white/10 bg-black/20 p-1">
                        <button
                            type="button"
                            className={`px-2 py-1 text-xs rounded ${mode === 'project' ? 'bg-primary text-primary-foreground' : 'text-gray-300 hover:bg-white/10'}`}
                            onClick={() => setMode('project')}
                            disabled={loading}
                        >
                            Project
                        </button>
                        <button
                            type="button"
                            className={`px-2 py-1 text-xs rounded ${mode === 'system_management' ? 'bg-primary text-primary-foreground' : 'text-gray-300 hover:bg-white/10'}`}
                            onClick={() => setMode('system_management')}
                            disabled={loading}
                        >
                            System
                        </button>
                    </div>
                )}
                <div className="flex items-center gap-1">
                    {activeHistory.length > 0 && (
                        <button
                            onClick={handleClearHistory}
                            className="p-1 rounded-md hover:bg-white/10 text-muted-foreground hover:text-destructive"
                            aria-label="Clear chat history"
                            title="Clear history"
                            disabled={loading}
                        >
                            <Trash2 className="w-4 h-4" />
                        </button>
                    )}
                    {typeof onClose === 'function' && (
                        <button
                            onClick={onClose}
                            className="p-1 rounded-md hover:bg-white/10"
                            aria-label="Close AI Assistant"
                            title="Close"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    )}
                </div>
            </div>
            <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4">
                {activeHistory.length === 0 && !loading && hasSavedHistory() && (
                    <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
                        <button
                            onClick={handleLoadHistory}
                            className="flex items-center gap-2 px-4 py-2 rounded-md border border-white/10 hover:bg-white/10 transition-colors text-sm"
                        >
                            <History className="w-4 h-4" />
                            Load previous conversation
                        </button>
                    </div>
                )}
                {activeHistory.map((msg, idx) => (
                    <MessageBubble
                        key={idx}
                        role={msg.role}
                        content={msg.content}
                        streaming={msg.streaming}
                        actions={msg.actions}
                        updatedData={msg.updatedData}
                        onQuickAction={handleQuickAction}
                    />
                ))}
                {loading && !streaming && <div className="text-sm text-muted-foreground animate-pulse p-2">Thinking...</div>}
                <div ref={endRef} />
            </div>
            <ChatInput
                onSend={handleSend}
                loading={loading}
                placeholder={mode === 'system_management' ? 'Ask system agent to analyze/update provider pricing...' : 'Ask AI to analyze script, generate images...'}
            />
        </div>
    );
};

export default React.memo(AgentChat);
