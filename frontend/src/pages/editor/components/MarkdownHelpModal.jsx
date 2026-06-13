import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { X, Info } from 'lucide-react';

import scriptGenerationManual from '../../../../../docs/script_generation_user_manual.md?raw';
import scriptAnalysisManual from '../../../../../docs/script_analysis_user_manual.md?raw';
import assetPageManual from '../../../../../docs/asset_page_user_manual.md?raw';

const MANUALS = [
    {
        key: 'generation',
        labelZh: '生成剧本',
        labelEn: 'Script Generation',
        titleZh: '生成剧本操作手册',
        titleEn: 'Script Generation Manual',
        content: scriptGenerationManual,
    },
    {
        key: 'analysis',
        labelZh: '剧本分析',
        labelEn: 'Script Analysis',
        titleZh: 'AI 剧本分析操作手册',
        titleEn: 'AI Script Analysis Manual',
        content: scriptAnalysisManual,
    },
    {
        key: 'assets',
        labelZh: '资产页面',
        labelEn: 'Assets',
        titleZh: '资产页面操作手册',
        titleEn: 'Assets Manual',
        content: assetPageManual,
    },
];

export default function MarkdownHelpModal({ open, initialDocKey = 'generation', onClose, uiLang = 'zh' }) {
    const t = React.useCallback((zh, en) => (uiLang === 'zh' ? zh : en), [uiLang]);
    const [activeKey, setActiveKey] = React.useState(initialDocKey);

    React.useEffect(() => {
        if (open) setActiveKey(initialDocKey || 'generation');
    }, [initialDocKey, open]);

    if (!open) return null;

    const activeManual = MANUALS.find((item) => item.key === activeKey) || MANUALS[0];
    const markdownComponents = {
        h1: ({ children, ...props }) => (
            <h1 {...props} className="mt-0 mb-4 text-2xl sm:text-3xl font-black text-white tracking-normal">
                {children}
            </h1>
        ),
        h2: ({ children, ...props }) => (
            <h2 {...props} className="mt-8 mb-3 border-b border-white/10 pb-2 text-xl font-bold text-white tracking-normal">
                {children}
            </h2>
        ),
        h3: ({ children, ...props }) => (
            <h3 {...props} className="mt-6 mb-2 text-base font-bold text-primary tracking-normal">
                {children}
            </h3>
        ),
        p: ({ children, ...props }) => (
            <p {...props} className="my-3 leading-7 text-white/80">
                {children}
            </p>
        ),
        blockquote: ({ children, ...props }) => (
            <blockquote {...props} className="my-4 rounded-lg border border-primary/20 border-l-4 border-l-primary bg-primary/10 px-4 py-3 text-white/85">
                {children}
            </blockquote>
        ),
        table: ({ children, ...props }) => (
            <div className="my-4 overflow-x-auto rounded-lg border border-white/10 bg-black/25">
                <table {...props} className="w-full min-w-[620px] border-collapse text-sm">
                    {children}
                </table>
            </div>
        ),
        th: ({ children, ...props }) => (
            <th {...props} className="border-b border-white/15 bg-white/10 px-3 py-2 text-left text-xs font-bold text-white/90">
                {children}
            </th>
        ),
        td: ({ children, ...props }) => (
            <td {...props} className="border-t border-white/10 px-3 py-2 align-top text-white/78">
                {children}
            </td>
        ),
        ul: ({ children, ...props }) => (
            <ul {...props} className="my-3 list-disc space-y-1.5 pl-5 text-white/82">
                {children}
            </ul>
        ),
        ol: ({ children, ...props }) => (
            <ol {...props} className="my-3 list-decimal space-y-1.5 pl-5 text-white/82">
                {children}
            </ol>
        ),
        code: ({ inline, children, ...props }) => inline
            ? <code {...props} className="rounded bg-black/40 px-1 py-0.5 text-amber-200">{children}</code>
            : <code {...props} className="text-amber-100">{children}</code>,
    };

    return (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-3 sm:p-5 bg-black/80 backdrop-blur-sm" onClick={onClose}>
            <div
                className="w-full max-w-6xl h-[88vh] rounded-xl border border-white/10 bg-[#151515] shadow-2xl overflow-hidden flex flex-col ring-1 ring-white/5"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="px-4 py-3 border-b border-white/10 bg-white/5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                        <Info className="w-5 h-5 text-primary shrink-0" />
                        <div className="min-w-0">
                            <h3 className="text-base sm:text-lg font-bold text-white truncate">
                                {t(activeManual.titleZh, activeManual.titleEn)}
                            </h3>
                            <div className="text-xs text-white/45 mt-0.5">
                                {t('支持 Markdown 渲染，可滚动阅读。', 'Rendered as Markdown. Scroll to read.')}
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 justify-between sm:justify-end">
                        <div className="flex items-center rounded-lg border border-white/10 bg-black/25 p-1">
                            {MANUALS.map((item) => {
                                const active = item.key === activeManual.key;
                                return (
                                    <button
                                        key={item.key}
                                        type="button"
                                        onClick={() => setActiveKey(item.key)}
                                        className={`px-3 py-1.5 rounded-md text-xs font-bold transition-colors ${active ? 'bg-white text-black' : 'text-white/75 hover:bg-white/10 hover:text-white'}`}
                                    >
                                        {t(item.labelZh, item.labelEn)}
                                    </button>
                                );
                            })}
                        </div>
                        <button
                            type="button"
                            onClick={onClose}
                            className="p-2 rounded-lg text-white/75 hover:text-white hover:bg-white/10 border border-white/10"
                            title={t('关闭', 'Close')}
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar bg-black/20">
                    <div className="mx-auto max-w-5xl px-4 sm:px-8 py-6 sm:py-8">
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm, remarkBreaks]}
                            components={markdownComponents}
                        >
                            {String(activeManual.content || '')}
                        </ReactMarkdown>
                    </div>
                </div>
            </div>
        </div>
    );
}