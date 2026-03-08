import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { MessageSquare, X } from 'lucide-react';
import AgentChat from './AgentChat';
import { useLog } from '../context/LogContext';
import { fetchMe } from '../services/api';

const FLOAT_BUTTON_SIZE = 56;
const FLOAT_BUTTON_MARGIN = 16;
const LOG_PANEL_OPEN_OFFSET = 272;
const POS_STORAGE_KEY = 'aistory.ai.assistant.fab.position';
const PANEL_RECT_KEY = 'aistory.ai.assistant.panel.rect';
const MIN_PANEL_W = 340;
const MIN_PANEL_H = 320;
const DEFAULT_PANEL_W = 430;
const DEFAULT_PANEL_H = 560;

const clampFabPosition = (position, logPanelOffsetPx) => {
    if (!position || typeof window === 'undefined') return null;

    const maxX = Math.max(FLOAT_BUTTON_MARGIN, window.innerWidth - FLOAT_BUTTON_SIZE - FLOAT_BUTTON_MARGIN);
    const maxY = Math.max(FLOAT_BUTTON_MARGIN, window.innerHeight - FLOAT_BUTTON_SIZE - FLOAT_BUTTON_MARGIN - logPanelOffsetPx);

    const x = Math.min(maxX, Math.max(FLOAT_BUTTON_MARGIN, Number(position.x) || 0));
    const y = Math.min(maxY, Math.max(FLOAT_BUTTON_MARGIN, Number(position.y) || 0));
    return { x, y };
};

const clampPanelRect = (rect) => {
    if (typeof window === 'undefined') return rect;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let { x, y, w, h } = rect;
    w = Math.max(MIN_PANEL_W, Math.min(w, vw - 16));
    h = Math.max(MIN_PANEL_H, Math.min(h, vh - 16));
    x = Math.max(8, Math.min(x, vw - w - 8));
    y = Math.max(8, Math.min(y, vh - h - 8));
    return { x, y, w, h };
};

const loadPanelRect = () => {
    try {
        const raw = localStorage.getItem(PANEL_RECT_KEY);
        if (raw) {
            const p = JSON.parse(raw);
            if (p && Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.w) && Number.isFinite(p.h)) {
                return clampPanelRect(p);
            }
        }
    } catch { /* ignore */ }
    if (typeof window === 'undefined') return { x: 100, y: 100, w: DEFAULT_PANEL_W, h: DEFAULT_PANEL_H };
    return clampPanelRect({
        x: window.innerWidth - DEFAULT_PANEL_W - 16,
        y: window.innerHeight - DEFAULT_PANEL_H - 96,
        w: DEFAULT_PANEL_W,
        h: DEFAULT_PANEL_H,
    });
};

const GlobalAIAssistant = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [isSuperuser, setIsSuperuser] = useState(false);
    const [buttonPosition, setButtonPosition] = useState(() => {
        try {
            const raw = localStorage.getItem(POS_STORAGE_KEY);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== 'object') return null;
            if (!Number.isFinite(Number(parsed.x)) || !Number.isFinite(Number(parsed.y))) return null;
            return { x: Number(parsed.x), y: Number(parsed.y) };
        } catch {
            return null;
        }
    });
    const [panelRect, setPanelRect] = useState(loadPanelRect);

    const location = useLocation();
    const { isLogOpen } = useLog();
    const dragRef = useRef({
        active: false,
        moved: false,
        startClientX: 0,
        startClientY: 0,
        startX: 0,
        startY: 0,
    });
    // Panel drag/resize state
    const panelDragRef = useRef({ active: false, type: null, startX: 0, startY: 0, startRect: null });

    const isAuthed = useMemo(() => {
        try {
            return !!localStorage.getItem('token');
        } catch {
            return false;
        }
    }, []);

    const context = useMemo(() => {
        const pathname = String(location?.pathname || '');
        const matched = pathname.match(/^\/editor\/([^/]+)/i);
        const projectId = matched && matched[1] ? decodeURIComponent(matched[1]) : null;
        return projectId ? { projectId } : {};
    }, [location?.pathname]);
    const shouldRender = isAuthed && location?.pathname !== '/auth';

    const logPanelOffsetPx = isLogOpen ? LOG_PANEL_OPEN_OFFSET : 0;

    useEffect(() => {
        if (!shouldRender) return;
        if (!buttonPosition) return;
        const clamped = clampFabPosition(buttonPosition, logPanelOffsetPx);
        if (!clamped) return;
        if (clamped.x !== buttonPosition.x || clamped.y !== buttonPosition.y) {
            setButtonPosition(clamped);
        }
    }, [buttonPosition, logPanelOffsetPx, shouldRender]);

    useEffect(() => {
        if (!shouldRender) return;
        if (!buttonPosition) return;
        try {
            localStorage.setItem(POS_STORAGE_KEY, JSON.stringify(buttonPosition));
        } catch {
            // ignore persistence failures
        }
    }, [buttonPosition, shouldRender]);

    // Persist panel rect
    useEffect(() => {
        try { localStorage.setItem(PANEL_RECT_KEY, JSON.stringify(panelRect)); } catch { /* ignore */ }
    }, [panelRect]);

    useEffect(() => {
        if (!shouldRender) return;
        const onResize = () => {
            setButtonPosition((prev) => {
                if (!prev) return prev;
                const clamped = clampFabPosition(prev, logPanelOffsetPx);
                if (!clamped) return prev;
                if (clamped.x === prev.x && clamped.y === prev.y) return prev;
                return clamped;
            });
            setPanelRect((prev) => clampPanelRect(prev));
        };
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
    }, [logPanelOffsetPx, shouldRender]);

    // --- FAB drag handlers ---
    const handlePointerDown = (e) => {
        if (e.button !== 0) return;
        const base = buttonPosition || {
            x: window.innerWidth - FLOAT_BUTTON_SIZE - 20,
            y: window.innerHeight - FLOAT_BUTTON_SIZE - 20 - logPanelOffsetPx,
        };
        dragRef.current = {
            active: true,
            moved: false,
            startClientX: e.clientX,
            startClientY: e.clientY,
            startX: base.x,
            startY: base.y,
        };
    };

    const handlePointerMove = useCallback((e) => {
        // FAB drag
        const state = dragRef.current;
        if (state.active) {
            const dx = e.clientX - state.startClientX;
            const dy = e.clientY - state.startClientY;
            if (!state.moved && (Math.abs(dx) > 4 || Math.abs(dy) > 4)) {
                state.moved = true;
            }
            const next = clampFabPosition(
                { x: state.startX + dx, y: state.startY + dy },
                logPanelOffsetPx,
            );
            if (next) setButtonPosition(next);
        }
        // Panel drag/resize
        const ps = panelDragRef.current;
        if (ps.active && ps.startRect) {
            const dx = e.clientX - ps.startX;
            const dy = e.clientY - ps.startY;
            const r = ps.startRect;
            let next;
            if (ps.type === 'move') {
                next = clampPanelRect({ x: r.x + dx, y: r.y + dy, w: r.w, h: r.h });
            } else {
                let { x, y, w, h } = r;
                if (ps.type.includes('e')) w = r.w + dx;
                if (ps.type.includes('s')) h = r.h + dy;
                if (ps.type.includes('w')) { w = r.w - dx; x = r.x + dx; }
                if (ps.type.includes('n')) { h = r.h - dy; y = r.y + dy; }
                next = clampPanelRect({ x, y, w, h });
            }
            setPanelRect(next);
        }
    }, [logPanelOffsetPx]);

    const handlePointerUp = useCallback(() => {
        dragRef.current.active = false;
        panelDragRef.current.active = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }, []);

    useEffect(() => {
        if (!shouldRender) return;
        window.addEventListener('pointermove', handlePointerMove);
        window.addEventListener('pointerup', handlePointerUp);
        return () => {
            window.removeEventListener('pointermove', handlePointerMove);
            window.removeEventListener('pointerup', handlePointerUp);
        };
    }, [shouldRender, handlePointerMove, handlePointerUp]);

    useEffect(() => {
        if (!shouldRender) return;
        let cancelled = false;
        (async () => {
            try {
                const me = await fetchMe();
                if (!cancelled) {
                    setIsSuperuser(!!me?.is_superuser);
                }
            } catch {
                if (!cancelled) setIsSuperuser(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [shouldRender]);

    const handleButtonClick = () => {
        if (dragRef.current.moved) {
            dragRef.current.moved = false;
            return;
        }
        setIsOpen((prev) => !prev);
    };

    const handleClose = useCallback(() => setIsOpen(false), []);

    // --- Panel drag (header) ---
    const onPanelHeaderPointerDown = (e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        panelDragRef.current = {
            active: true,
            type: 'move',
            startX: e.clientX,
            startY: e.clientY,
            startRect: { ...panelRect },
        };
        document.body.style.cursor = 'grabbing';
        document.body.style.userSelect = 'none';
    };

    // --- Panel resize (edges/corners) ---
    const onResizePointerDown = (type) => (e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        e.stopPropagation();
        panelDragRef.current = {
            active: true,
            type,
            startX: e.clientX,
            startY: e.clientY,
            startRect: { ...panelRect },
        };
        document.body.style.userSelect = 'none';
    };

    const buttonBottomStyle = {
        bottom: `calc(20px + env(safe-area-inset-bottom, 0px) + ${logPanelOffsetPx}px)`,
    };
    const buttonStyle = buttonPosition
        ? { left: `${buttonPosition.x}px`, top: `${buttonPosition.y}px` }
        : buttonBottomStyle;

    if (!shouldRender) {
        return null;
    }

    const resizeHandleBase = 'absolute z-10';
    const EDGE = 5;

    return (
        <>
            {isOpen && (
                <div
                    style={{
                        position: 'fixed',
                        left: panelRect.x,
                        top: panelRect.y,
                        width: panelRect.w,
                        height: panelRect.h,
                        zIndex: 120,
                    }}
                    className="flex flex-col"
                >
                    {/* Resize handles */}
                    <div className={`${resizeHandleBase} top-0 left-[${EDGE}px] right-[${EDGE}px] h-[${EDGE}px] cursor-n-resize`}
                         style={{ top: 0, left: EDGE, right: EDGE, height: EDGE, cursor: 'n-resize' }}
                         onPointerDown={onResizePointerDown('n')} />
                    <div className={resizeHandleBase}
                         style={{ bottom: 0, left: EDGE, right: EDGE, height: EDGE, cursor: 's-resize' }}
                         onPointerDown={onResizePointerDown('s')} />
                    <div className={resizeHandleBase}
                         style={{ top: EDGE, left: 0, bottom: EDGE, width: EDGE, cursor: 'w-resize' }}
                         onPointerDown={onResizePointerDown('w')} />
                    <div className={resizeHandleBase}
                         style={{ top: EDGE, right: 0, bottom: EDGE, width: EDGE, cursor: 'e-resize' }}
                         onPointerDown={onResizePointerDown('e')} />
                    {/* Corner handles */}
                    <div className={resizeHandleBase}
                         style={{ top: 0, left: 0, width: EDGE * 2, height: EDGE * 2, cursor: 'nw-resize' }}
                         onPointerDown={onResizePointerDown('nw')} />
                    <div className={resizeHandleBase}
                         style={{ top: 0, right: 0, width: EDGE * 2, height: EDGE * 2, cursor: 'ne-resize' }}
                         onPointerDown={onResizePointerDown('ne')} />
                    <div className={resizeHandleBase}
                         style={{ bottom: 0, left: 0, width: EDGE * 2, height: EDGE * 2, cursor: 'sw-resize' }}
                         onPointerDown={onResizePointerDown('sw')} />
                    <div className={resizeHandleBase}
                         style={{ bottom: 0, right: 0, width: EDGE * 2, height: EDGE * 2, cursor: 'se-resize' }}
                         onPointerDown={onResizePointerDown('se')} />

                    {/* Chat panel with draggable header */}
                    <div className="flex flex-col h-full">
                        <AgentChat
                            context={context}
                            isSuperuser={isSuperuser}
                            onClose={handleClose}
                            onHeaderPointerDown={onPanelHeaderPointerDown}
                        />
                    </div>
                </div>
            )}

            <button
                onPointerDown={handlePointerDown}
                onClick={handleButtonClick}
                style={buttonStyle}
                className={`fixed ${buttonPosition ? '' : 'right-5'} z-[121] h-14 w-14 rounded-full bg-primary text-black shadow-lg hover:opacity-90 transition-opacity flex items-center justify-center cursor-grab active:cursor-grabbing touch-none select-none`}
                title={isOpen ? 'Close AI Assistant' : 'Open AI Assistant'}
                aria-label={isOpen ? 'Close AI Assistant' : 'Open AI Assistant'}
            >
                {isOpen ? <X className="w-6 h-6" /> : <MessageSquare className="w-6 h-6" />}
            </button>
        </>
    );
};

export default GlobalAIAssistant;
