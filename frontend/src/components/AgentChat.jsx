
import React, { useEffect, useRef, useState } from 'react';
import { sendAgentCommand, sendSystemManagementAgentCommand } from '../services/api';
import { Send, Bot, X } from 'lucide-react';

const AgentChat = ({ context, onClose, isSuperuser = false }) => {
    const [query, setQuery] = useState('');
    const [historyByMode, setHistoryByMode] = useState({ project: [], system_management: [] });
    const [loading, setLoading] = useState(false);
    const [mode, setMode] = useState('project');

    const activeHistory = Array.isArray(historyByMode?.[mode]) ? historyByMode[mode] : [];
    const scrollContainerRef = useRef(null);
    const endRef = useRef(null);

    const scrollToLatest = (behavior = 'smooth') => {
        if (endRef.current && typeof endRef.current.scrollIntoView === 'function') {
            endRef.current.scrollIntoView({ behavior, block: 'end' });
            return;
        }
        if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
        }
    };

    useEffect(() => {
        const behavior = loading ? 'auto' : 'smooth';
        scrollToLatest(behavior);
    }, [mode, loading, activeHistory.length]);

    const handleSend = async () => {
        if (!query.trim()) return;

        const updatedHistory = [...activeHistory, { role: 'user', content: query }];
        setHistoryByMode((prev) => ({
            ...(prev || {}),
            [mode]: updatedHistory,
        }));
        setLoading(true);
        setQuery('');

        try {
            const isSystemMode = mode === 'system_management';
            const runtimeContext = {
                ...(context || {}),
                agent_mode: isSystemMode ? 'system_management' : 'project',
            };
            const normalizedHistory = updatedHistory.map((msg) => ({
                role: String(msg?.role || 'user'),
                content: String(msg?.content || ''),
            }));
            const result = isSystemMode
                ? await sendSystemManagementAgentCommand(query, runtimeContext, normalizedHistory)
                : await sendAgentCommand(query, runtimeContext, normalizedHistory);
            
            const reply = result.reply;
            setHistoryByMode((prev) => ({
                ...(prev || {}),
                [mode]: [...updatedHistory, { role: 'assistant', content: reply, actions: result.actions }],
            }));
        } catch (error) {
            console.error(error);
            const errorMessage =
                error?.userMessage ||
                error?.response?.data?.detail ||
                error?.message ||
                'Error communicating with AI.';
            setHistoryByMode((prev) => ({
                ...(prev || {}),
                [mode]: [...updatedHistory, { role: 'system', content: errorMessage }],
            }));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-card rounded-lg border shadow-sm">
            <div className="p-4 border-b font-semibold flex items-center justify-between gap-2">
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
            <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4">
                {activeHistory.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[80%] rounded-lg p-3 ${msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                        </div>
                    </div>
                ))}
                {loading && <div className="text-sm text-muted-foreground animate-pulse p-2">Thinking...</div>}
                <div ref={endRef} />
            </div>
            <div className="p-4 border-t flex gap-2">
                <input 
                    className="flex-1 px-3 py-2 rounded-md border bg-background"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder={mode === 'system_management' ? 'Ask system agent to analyze/update provider pricing...' : 'Ask AI to analyze script, generate images...'}
                />
                <button 
                    onClick={handleSend}
                    disabled={loading}
                    className="p-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
                >
                    <Send className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
};

export default AgentChat;
