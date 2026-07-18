import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { X, BookOpen } from 'lucide-react';

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
            <h1 {...props} className="mt-0 mb-3 text-2xl sm:text-3xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white via-white to-primary/80">
                {children}
            </h1>
        ),
        h2: ({ children, ...props }) => (
            <h2 {...props} className="mt-10 mb-3 flex items-center gap-2 border-b border-white/10 pb-2.5 text-lg sm:text-xl font-bold text-white tracking-normal">
                <span className="inline-block h-5 w-1 rounded-full bg-primary/80 shrink-0" />
                <span>{children}</span>
            </h2>
        ),
        h3: ({ children, ...props }) => (
            <h3 {...props} className="mt-7 mb-2 text-[15px] font-bold text-amber-200/95 tracking-normal">
                {children}
            </h3>
        ),
        p: ({ children, ...props }) => (
            <p {...props} className="my-3 leading-7 text-white/80">
                {children}
            </p>
        ),
        blockquote: ({ children, ...props }) => (
            <blockquote {...props} className="my-5 rounded-xl border border-primary/25 border-l-[3px] border-l-primary bg-gradient-to-r from-primary/15 via-primary/5 to-transparent px-4 py-3.5 text-white/88 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
                {children}
            </blockquote>
        ),
        hr: ({ ...props }) => (
            <hr {...props} className="my-8 border-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
        ),
        strong: ({ children, ...props }) => (
            <strong {...props} className="font-bold text-white">
                {children}
            </strong>
        ),
        a: ({ children, ...props }) => (
            <a {...props} className="text-primary underline underline-offset-2 decoration-primary/40 hover:decoration-primary">
                {children}
            </a>
        ),
        table: ({ children, ...props }) => (
            <div className="my-5 overflow-x-auto rounded-xl border border-white/10 bg-black/30 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                <table {...props} className="w-full min-w-[620px] border-collapse text-sm">
                    {children}
                </table>
            </div>
        ),
        thead: ({ children, ...props }) => (
            <thead {...props} className="bg-white/[0.06]">
                {children}
            </thead>
        ),
        th: ({ children, ...props }) => (
            <th {...props} className="border-b border-white/15 px-3.5 py-2.5 text-left text-xs font-bold tracking-wide text-white/90">
                {children}
            </th>
        ),
        td: ({ children, ...props }) => (
            <td {...props} className="border-t border-white/[0.07] px-3.5 py-2.5 align-top text-white/78 leading-6">
                {children}
            </td>
        ),
        ul: ({ children, ...props }) => (
            <ul {...props} className="my-3 list-disc space-y-2 pl-5 text-white/82 marker:text-primary/70">
                {children}
            </ul>
        ),
        ol: ({ children, ...props }) => (
            <ol {...props} className="my-3 list-decimal space-y-2 pl-5 text-white/82 marker:text-primary/80">
                {children}
            </ol>
        ),
        li: ({ children, ...props }) => (
            <li {...props} className="leading-7 pl-0.5">
                {children}
            </li>
        ),
        pre: ({ children, ...props }) => (
            <pre {...props} className="my-4 overflow-x-auto rounded-xl border border-white/10 bg-black/45 px-4 py-3.5 text-[12px] leading-6 text-amber-100/90">
                {children}
            </pre>
        ),
        code: ({ inline, children, ...props }) => inline
            ? <code {...props} className="rounded-md bg-black/45 px-1.5 py-0.5 text-[12px] text-amber-200">{children}</code>
            : <code {...props} className="text-amber-100">{children}</code>,
    };

    return (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-3 sm:p-5 bg-black/80 backdrop-blur-sm" onClick={onClose}>
            <div
                className="w-full max-w-6xl h-[88vh] rounded-2xl border border-white/10 bg-[#121212] shadow-2xl overflow-hidden flex flex-col ring-1 ring-white/5"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="relative px-4 py-3.5 border-b border-white/10 overflow-hidden">
                    <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-primary/15 via-transparent to-emerald-500/10" />
                    <div className="relative flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                            <div className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-primary/30 bg-primary/15 text-primary shrink-0">
                                <BookOpen className="w-4.5 h-4.5 w-4 h-4" />
                            </div>
                            <div className="min-w-0">
                                <h3 className="text-base sm:text-lg font-bold text-white truncate">
                                    {t(activeManual.titleZh, activeManual.titleEn)}
                                </h3>
                                <div className="text-xs text-white/45 mt-0.5">
                                    {t('按章节浏览，边做边查。', 'Browse by section while you work.')}
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center gap-2 justify-between sm:justify-end">
                            <div className="flex items-center rounded-xl border border-white/10 bg-black/35 p-1">
                                {MANUALS.map((item) => {
                                    const active = item.key === activeManual.key;
                                    return (
                                        <button
                                            key={item.key}
                                            type="button"
                                            onClick={() => setActiveKey(item.key)}
                                            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${active ? 'bg-white text-black shadow-sm' : 'text-white/75 hover:bg-white/10 hover:text-white'}`}
                                        >
                                            {t(item.labelZh, item.labelEn)}
                                        </button>
                                    );
                                })}
                            </div>
                            <button
                                type="button"
                                onClick={onClose}
                                className="p-2 rounded-xl text-white/75 hover:text-white hover:bg-white/10 border border-white/10"
                                title={t('关闭', 'Close')}
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar bg-gradient-to-b from-black/10 via-black/25 to-black/40">
                    <div className="mx-auto max-w-5xl px-4 sm:px-8 py-6 sm:py-9">
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
