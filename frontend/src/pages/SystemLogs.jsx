import React, { useState, useEffect } from 'react';
import { fetchSystemLogs } from '../services/api';
import { ArrowLeft, RefreshCw, Layers, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getUiLang, tUI } from '../lib/uiLang';

const SystemLogs = () => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [selectedLog, setSelectedLog] = useState(null);
    const navigate = useNavigate();

    const loadLogs = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await fetchSystemLogs(0, 200);
            setLogs(data);
        } catch (e) {
            console.error(e);
            setError(t('日志加载失败，可能没有权限。', 'Failed to load logs. You might not have permission.'));
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
                        {t('系统日志', 'System Logs')}
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
                                <th className="px-6 py-3">{t('时间戳', 'Timestamp')}</th>
                                <th className="px-6 py-3">{t('用户', 'User')}</th>
                                <th className="px-6 py-3">{t('动作', 'Action')}</th>
                                <th className="px-6 py-3">{t('详情', 'Details')}</th>
                                <th className="px-6 py-3">{t('IP 地址', 'IP')}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {logs.map((log) => (
                                <tr
                                    key={log.id}
                                    className="hover:bg-white/5 transition-colors cursor-pointer"
                                    onClick={() => setSelectedLog(log)}
                                    title={t('点击查看详情', 'Click to view details')}
                                >
                                    <td className="px-6 py-3 text-white/60 whitespace-nowrap">
                                        {new Date(log.timestamp).toLocaleString()}
                                    </td>
                                    <td className="px-6 py-3 font-medium text-white">
                                        {log.user_name || `${t('用户', 'User')} #${log.user_id}`}
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
                                        {t('暂无日志。', 'No logs found.')}
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {selectedLog && (
                <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="w-full max-w-2xl bg-[#1e1e1e] border border-white/15 rounded-xl shadow-2xl overflow-hidden">
                        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
                            <h2 className="text-base font-semibold">
                                {t('日志详情', 'Log Details')} #{selectedLog.id}
                            </h2>
                            <button
                                onClick={() => setSelectedLog(null)}
                                className="p-1.5 rounded-md hover:bg-white/10 transition-colors"
                                title={t('关闭', 'Close')}
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div className="px-5 py-4 space-y-3 text-sm">
                            <div className="grid grid-cols-3 gap-3">
                                <span className="text-white/50">{t('时间戳', 'Timestamp')}</span>
                                <span className="col-span-2">{new Date(selectedLog.timestamp).toLocaleString()}</span>
                            </div>
                            <div className="grid grid-cols-3 gap-3">
                                <span className="text-white/50">{t('用户', 'User')}</span>
                                <span className="col-span-2">{selectedLog.user_name || `${t('用户', 'User')} #${selectedLog.user_id}`}</span>
                            </div>
                            <div className="grid grid-cols-3 gap-3">
                                <span className="text-white/50">{t('动作', 'Action')}</span>
                                <span className="col-span-2">{selectedLog.action}</span>
                            </div>
                            <div className="grid grid-cols-3 gap-3">
                                <span className="text-white/50">{t('IP 地址', 'IP')}</span>
                                <span className="col-span-2 font-mono text-xs">{selectedLog.ip_address || '-'}</span>
                            </div>
                            <div className="grid grid-cols-3 gap-3 items-start">
                                <span className="text-white/50">{t('详情', 'Details')}</span>
                                <pre className="col-span-2 whitespace-pre-wrap break-words bg-black/20 border border-white/10 rounded-md p-3 text-white/85 text-xs">
                                    {selectedLog.details || '-'}
                                </pre>
                            </div>
                        </div>

                        <div className="px-5 py-3 border-t border-white/10 flex justify-end">
                            <button
                                onClick={() => setSelectedLog(null)}
                                className="px-3 py-1.5 text-xs rounded-md bg-white/10 hover:bg-white/20 transition-colors"
                            >
                                {t('关闭', 'Close')}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default SystemLogs;
