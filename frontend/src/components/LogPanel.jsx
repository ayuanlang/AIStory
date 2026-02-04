
import React from 'react';
import { ScrollText, X, ChevronUp, ChevronDown, Trash2 } from 'lucide-react';
import { useLog } from '../context/LogContext';

const LogPanel = () => {
    const { logs, isLogOpen, setIsLogOpen, clearLogs } = useLog();

    return (
        <>
            {/* Toggle Button (Visible when closed) */}
            <div 
                className={`fixed bottom-0 left-1/2 -translate-x-1/2 z-[99] transition-transform duration-300 ${isLogOpen ? 'translate-y-full' : 'translate-y-0'}`}
            >
                <button 
                    onClick={() => setIsLogOpen(true)}
                    className="flex items-center gap-2 px-4 py-1.5 bg-[#09090b] border border-b-0 border-white/10 rounded-t-lg text-xs font-mono text-muted-foreground hover:text-primary hover:border-primary/50 transition-colors shadow-lg"
                >
                    <ChevronUp size={14} />
                    <span className="opacity-75">SysLog</span>
                    {logs.length > 0 && <span className="ml-1 w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />}
                </button>
            </div>

            {/* Main Panel */}
            <div 
                className={`fixed bottom-0 left-0 right-0 border-t border-white/10 bg-[#09090b]/95 backdrop-blur-md flex flex-col z-[100] transition-all duration-300 ease-in-out shadow-[0_-10px_40px_rgba(0,0,0,0.5)] ${isLogOpen ? 'h-64 translate-y-0' : 'h-0 translate-y-0 overflow-hidden'}`}
            >
                <div className="flex items-center justify-between px-4 py-2 border-b border-white/5 bg-white/5 shrink-0 h-10">
                    <span className="text-xs font-bold text-muted-foreground uppercase flex items-center gap-2">
                        <ScrollText className="w-3 h-3" /> System Logs <span className="text-[10px] opacity-50">({logs.length})</span>
                    </span>
                    <div className="flex gap-2 items-center">
                            <button onClick={clearLogs} className="p-1 hover:bg-white/10 rounded text-muted-foreground hover:text-red-400 transition-colors" title="Clear Logs">
                                <Trash2 size={14} />
                            </button>
                            <div className="h-4 w-[1px] bg-white/10 mx-1"></div>
                            <button onClick={() => setIsLogOpen(false)} className="p-1 hover:bg-white/10 rounded text-muted-foreground hover:text-white transition-colors">
                                <ChevronDown size={16} />
                            </button>
                    </div>
                </div>
                <div className="flex-1 overflow-auto p-3 font-mono text-[11px] leading-relaxed text-muted-foreground custom-scrollbar space-y-1.5">
                    {logs.length === 0 && (
                        <div className="h-full flex items-center justify-center text-muted-foreground/30 italic">
                            No active logs.
                        </div>
                    )}
                    {logs.map((log, i) => (
                        <div key={i} className="flex gap-3 hover:bg-white/5 px-2 py-0.5 rounded break-all group">
                            <span className="text-white/20 select-none w-6 text-right shrink-0">{i + 1}</span>
                            <span className="text-white/80 group-hover:text-white transition-colors">{log}</span>
                        </div>
                    ))}
                </div>
            </div>
        </>
    );
};


export default LogPanel;
