import React from 'react';
import { X } from 'lucide-react';
import { getUiLang, tUI } from '../lib/uiLang';

const InfoCard = ({ label, value }) => (
	<div className="bg-white/5 p-3 rounded-xl">
		<div className="text-gray-500 text-xs">{label}</div>
		<div>{value || '-'}</div>
	</div>
);

const LlmLogViewer = ({ log, onClose }) => {
	const uiLang = getUiLang();
	const t = (zh, en) => tUI(uiLang, zh, en);

	if (!log) {
		return null;
	}

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
			<div className="bg-gray-900 border border-white/10 rounded-2xl w-full max-w-4xl shadow-2xl flex flex-col max-h-[85vh]">
				<div className="flex justify-between items-center p-4 border-b border-white/10">
					<h3 className="text-lg font-bold">{t('LLM 调用日志详情', 'LLM Call Log Details')} #{log.id}</h3>
					<button onClick={onClose} className="text-gray-400 hover:text-white" aria-label={t('关闭日志详情', 'Close log details')}>
						<X className="w-5 h-5" />
					</button>
				</div>
				<div className="flex-1 overflow-y-auto p-4 space-y-4 text-sm">
					<div className="grid grid-cols-2 md:grid-cols-4 gap-4">
						<InfoCard label="Provider" value={log.provider} />
						<InfoCard label="Model" value={log.model} />
						<InfoCard label="Tag" value={log.tag} />
						<InfoCard label="Latency" value={log.latency_ms ? `${log.latency_ms}ms` : '-'} />
					</div>
					<div className="space-y-1">
						<div className="text-gray-500 text-xs">API URL</div>
						<div className="bg-white/5 p-3 rounded-xl break-all">{log.api_url || '-'}</div>
					</div>
					{log.error_msg && (
						<div className="space-y-1">
							<div className="text-red-400 text-xs">{t('错误信息', 'Error Message')}</div>
							<div className="bg-red-500/10 text-red-200 border border-red-500/20 p-3 rounded-xl whitespace-pre-wrap break-words">{log.error_msg}</div>
						</div>
					)}
					<div className="space-y-1">
						<div className="text-gray-500 text-xs">Payload JSON</div>
						<pre className="bg-black/50 p-3 rounded-xl whitespace-pre-wrap break-words overflow-x-auto border border-white/5 text-xs text-gray-300">{log.payload_json || '-'}</pre>
					</div>
					<div className="space-y-1">
						<div className="text-gray-500 text-xs">Response JSON</div>
						<pre className="bg-black/50 p-3 rounded-xl whitespace-pre-wrap break-words overflow-x-auto border border-white/5 text-xs text-gray-300">{log.response_json || '-'}</pre>
					</div>
				</div>
			</div>
		</div>
	);
};

export default LlmLogViewer;
