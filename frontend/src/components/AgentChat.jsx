
import React, { useState } from 'react';
import { sendAgentCommand } from '../services/api';
import { Send, Bot, User } from 'lucide-react';

const AgentChat = ({ context }) => {
    const [query, setQuery] = useState('');
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);

    const handleSend = async () => {
        if (!query.trim()) return;

        const updatedHistory = [...history, { role: 'user', content: query }];
        setHistory(updatedHistory);
        setLoading(true);
        setQuery('');

        try {
            const result = await sendAgentCommand(query, context, history); // Mock history format needs adaptation for API
            
            const reply = result.reply;
            setHistory([...updatedHistory, { role: 'assistant', content: reply, actions: result.actions }]);
        } catch (error) {
            console.error(error);
            setHistory([...updatedHistory, { role: 'system', content: "Error communicating with AI." }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-card rounded-lg border shadow-sm">
            <div className="p-4 border-b font-semibold flex items-center gap-2">
                <Bot className="w-5 h-5 text-primary" />
                AI Assistant
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {history.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[80%] rounded-lg p-3 ${msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                            {msg.actions && msg.actions.length > 0 && (
                                <div className="mt-2 text-xs border-t pt-2 opacity-70">
                                    {msg.actions.map((act, i) => (
                                        <div key={i}>Action: {act.tool} ({act.status})</div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                ))}
                {loading && <div className="text-sm text-muted-foreground animate-pulse p-2">Thinking...</div>}
            </div>
            <div className="p-4 border-t flex gap-2">
                <input 
                    className="flex-1 px-3 py-2 rounded-md border bg-background"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Ask AI to analyze script, generate images..."
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
