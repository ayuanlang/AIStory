const fs = require('fs');
const content = `import React from 'react';
import { CheckCircle, AlertTriangle } from 'lucide-react';

function formatDurationMs(ms) {
    if (!ms) return '0s';
    const s = Math.floor(ms / 1000);
    return \${s}s\;
}

export default function LLMResultPanel({
    title, t, report, rawText, onRawTextChange, onRawTextBlur,
    isRawReadOnly = false, placeholder = '', extraContent = null
}) {
    return (
        <div className="flex flex-col gap-3 p-4 border border-white/10 rounded-lg bg-black/20 h-full overflow-y-auto custom-scrollbar">
            <h3 className="text-sm font-bold text-white/90 tracking-wide flex items-center gap-2">{title}</h3>
            {
                extraContent && (
                    <div className="mt-4 shrink-0">
                        {extraContent}
                    </div>
                )
            }
            {report && report.status !== 'running' && (
                <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm space-y-3 shrink-0">
                    <div className="font-bold text-white/90 text-base flex items-center gap-2">
                        <CheckCircle className="w-5 h-5 text-emerald-400" /> {t('run completed!', 'Execution Completed!')}
                    </div>
                    {report.warning && (
                        <div className="flex items-center gap-2 text-amber-400 text-xs mt-1 bg-amber-500/10 p-2 rounded">
                            <AlertTriangle className="w-4 h-4 shrink-0" />
                            {report.warning}
                        </div>
                    )}
                    {report.error && (
                        <div className="flex items-center gap-2 text-red-400 text-xs mt-1 bg-red-500/10 p-2 rounded">
                            <AlertTriangle className="w-4 h-4 shrink-0" />
                            {report.error}
                        </div>
                    )}
                </div>
            )}
            <div className="flex-1 flex flex-col min-h[300px]">
                <div className="px-1 pb-2 text-[10px] text-muted-foreground uppercase font-bold tracking-wide">
                    {t('LLM Raw Response', 'LLM Raw Response')}
                </div>
                <textarea
                    className="w-full flex-1 p-4 bg-black/40 text-white/80 font-mono text-[12px] leading-relaxed focus:outline-none custom-scrollbar border border-white/10 rounded-md"
                    placeholder={placeholder}
                    value={rawText || ''}
                    onChange={e => onRawTextChange?.(e.target.value)}
                    onBlur={onRawTextBlur}
                    readOnly={isRawReadOnly}
                />
            </div>
        </div>
    );
}`;
fs.writeFileSync('c:/AS/AIStory/frontend/src/pages/editor/components/LLMResultPanel.jsx', content);
console.log('Done');