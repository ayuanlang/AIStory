import React, { useState, useEffect } from 'react';
import { fetchSystemLogs } from '../services/api';
import { ArrowLeft, RefreshCw, Layers } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const SystemLogs = () => {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const navigate = useNavigate();

    const loadLogs = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await fetchSystemLogs(0, 200);
            setLogs(data);
        } catch (e) {
            console.error(e);
            setError("Failed to load logs. You might not have permission.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadLogs();
    }, []);

    return (
        <div className="flex flex-col h-full bg-[#121212] text-white">
            {/* Header */}
            <header className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#1e1e1e]">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/')} className="hover:bg-white/10 p-2 rounded-full">
                        <ArrowLeft size={20} />
                    </button>
                    <h1 className="text-xl font-bold flex items-center gap-2">
                        <Layers className="text-primary" />
                        System Logs
                    </h1>
                </div>
                <button 
                    onClick={loadLogs} 
                    className="p-2 hover:bg-white/10 rounded-full transition-colors"
                >
                    <RefreshCw size={20} className={loading ? "animate-spin" : ""} />
                </button>
            </header>

            {/* Content */}
            <div className="flex-1 overflow-auto p-6">
                {error && (
                    <div className="bg-red-500/20 text-red-200 p-4 rounded-lg mb-4 border border-red-500/30">
                        {error}
                    </div>
                )}

                <div className="bg-[#1e1e1e] rounded-xl border border-white/10 overflow-hidden">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-black/30 text-muted-foreground uppercase text-xs">
                            <tr>
                                <th className="px-6 py-3">Timestamp</th>
                                <th className="px-6 py-3">User</th>
                                <th className="px-6 py-3">Action</th>
                                <th className="px-6 py-3">Details</th>
                                <th className="px-6 py-3">IP</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {logs.map((log) => (
                                <tr key={log.id} className="hover:bg-white/5 transition-colors">
                                    <td className="px-6 py-3 text-white/60 whitespace-nowrap">
                                        {new Date(log.timestamp).toLocaleString()}
                                    </td>
                                    <td className="px-6 py-3 font-medium text-white">
                                        {log.user_name || `User #${log.user_id}`}
                                    </td>
                                    <td className="px-6 py-3">
                                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                                            log.action === 'LOGIN' ? 'bg-green-500/20 text-green-400' :
                                            log.action === 'LOGIN_FAILED' ? 'bg-red-500/20 text-red-400' :
                                            'bg-blue-500/20 text-blue-400'
                                        }`}>
                                            {log.action}
                                        </span>
                                    </td>
                                    <td className="px-6 py-3 text-white/80 max-w-md truncate" title={log.details}>
                                        {log.details || '-'}
                                    </td>
                                    <td className="px-6 py-3 text-white/40 font-mono text-xs">
                                        {log.ip_address || '-'}
                                    </td>
                                </tr>
                            ))}
                            {logs.length === 0 && !loading && (
                                <tr>
                                    <td colSpan={5} className="px-6 py-8 text-center text-muted-foreground">
                                        No logs found.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default SystemLogs;
