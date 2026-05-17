import React from 'react';
import ReactMarkdown from 'react-markdown';
import { ChevronDown, Loader2, RefreshCw, PlayCircle } from 'lucide-react';

export default function LLMResultPanel({
    title, t, placeholder = '', stageCards = []
}) {
    const normalizedCards = React.useMemo(
        () => (Array.isArray(stageCards) ? stageCards.filter(Boolean) : []),
        [stageCards]
    );
    const [collapsedCards, setCollapsedCards] = React.useState(() => ({}));

    React.useEffect(() => {
        setCollapsedCards((prev) => {
            const next = {};
            let hasChanges = false;
            normalizedCards.forEach((card) => {
                const key = String(card.key || card.title || '');
                const value = Object.prototype.hasOwnProperty.call(prev, key) ? prev[key] : true;
                next[key] = value;
                if (!Object.prototype.hasOwnProperty.call(prev, key) || prev[key] !== value) {
                    hasChanges = true;
                }
            });

            if (!hasChanges && Object.keys(prev).length === normalizedCards.length) {
                return prev;
            }

            return next;
        });
    }, [normalizedCards]);

    return (
        <div className="flex flex-col gap-3 p-4 border border-white/10 rounded-lg bg-black/20 h-full overflow-y-auto custom-scrollbar">
            <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-bold text-white/90 tracking-wide flex items-center gap-2">{title}</h3>
            </div>
            {normalizedCards.length > 0 && (
                <div className="space-y-3 shrink-0">
                    {normalizedCards.map((card) => {
                        const cardKey = String(card.key || card.title);
                        const isCollapsed = collapsedCards[cardKey] !== false;
                        const cardStatus = String(card.status || '').trim();
                        const cardActions = Array.isArray(card.actions) ? card.actions.filter(Boolean) : [];
                        const toneClass = cardStatus === 'completed'
                            ? 'border-emerald-500/20 bg-emerald-500/5'
                            : cardStatus === 'running'
                                ? 'border-sky-500/20 bg-sky-500/5'
                                : cardStatus === 'warning'
                                    ? 'border-amber-500/20 bg-amber-500/5'
                                    : 'border-white/10 bg-white/5';
                        return (
                            <div key={cardKey} className={`rounded-xl border ${toneClass} overflow-hidden`}>
                                <div className={`px-4 py-3 flex items-center justify-between gap-3 ${isCollapsed ? '' : 'border-b border-white/10'}`}>
                                    <div>
                                        <div className="text-xs uppercase tracking-[0.18em] text-white/45 font-bold">{card.eyebrow || t('阶段输出', 'Stage Output')}</div>
                                        <div className="text-sm font-semibold text-white/90 mt-1">{card.title}</div>
                                    </div>
                                    <div className="flex items-center gap-2 flex-wrap justify-end">
                                        <button
                                            type="button"
                                            onClick={() => setCollapsedCards((prev) => ({ ...prev, [cardKey]: !isCollapsed }))}
                                            className="px-2 py-1 rounded-md bg-white/10 hover:bg-white/15 text-[11px] font-bold text-white/80 border border-white/10 flex items-center gap-1"
                                        >
                                            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isCollapsed ? '' : 'rotate-180'}`} />
                                            {isCollapsed ? t('展开', 'Expand') : t('折叠', 'Collapse')}
                                        </button>
                                        {card.badge && (
                                            <div className="px-2 py-1 rounded-full bg-white/10 text-[10px] font-bold text-white/70 uppercase tracking-wide">
                                                {card.badge}
                                            </div>
                                        )}
                                        {cardActions.map((action) => {
                                            const isDisabled = !!action.disabled;
                                            const isLoading = !!action.loading;
                                            const Icon = action.icon === 'play' ? PlayCircle : RefreshCw;
                                            return (
                                                <button
                                                    key={String(action.key || action.label || Math.random())}
                                                    type="button"
                                                    onClick={action.onClick}
                                                    disabled={isDisabled || isLoading}
                                                    className={`px-2.5 py-1.5 rounded-md text-[11px] font-bold border flex items-center gap-1.5 ${isDisabled || isLoading ? 'bg-white/5 text-muted-foreground border-white/10 cursor-not-allowed' : 'bg-white/10 hover:bg-white/15 border-white/15 text-white/90'}`}
                                                >
                                                    {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Icon className="w-3.5 h-3.5" />}
                                                    {action.label}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                                {!isCollapsed && (
                                    <>
                                        {(card.summary || card.meta) && (
                                            <div className="px-4 pt-3 pb-1 space-y-2">
                                                {card.summary && <div className="text-xs text-white/70">{card.summary}</div>}
                                                {card.meta && <div className="text-[11px] text-white/50">{card.meta}</div>}
                                            </div>
                                        )}
                                        <div className="px-4 pb-4 pt-3 prose prose-invert prose-p:my-1.5 prose-headings:my-2 prose-li:my-0.5 prose-pre:bg-black/40 prose-pre:border prose-pre:border-white/10 prose-code:text-amber-200 max-w-none text-sm text-white/85">
                                            {String(card.content || '').trim()
                                                ? <ReactMarkdown>{String(card.content || '')}</ReactMarkdown>
                                                : <div className="text-xs text-white/35 italic">{card.placeholder || placeholder || t('暂无阶段输出。', 'No stage output yet.')}</div>}
                                        </div>
                                    </>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}