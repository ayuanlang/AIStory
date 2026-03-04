import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { MessageSquare, X } from 'lucide-react';
import AgentChat from './AgentChat';
import { useLog } from '../context/LogContext';
import { fetchMe } from '../services/api';

const FLOAT_BUTTON_SIZE = 56;
const FLOAT_BUTTON_MARGIN = 16;
const LOG_PANEL_OPEN_OFFSET = 272;
const POS_STORAGE_KEY = 'aistory.ai.assistant.fab.position';

const clampFabPosition = (position, logPanelOffsetPx) => {
    if (!position || typeof window === 'undefined') return null;

    const maxX = Math.max(FLOAT_BUTTON_MARGIN, window.innerWidth - FLOAT_BUTTON_SIZE - FLOAT_BUTTON_MARGIN);
    const maxY = Math.max(FLOAT_BUTTON_MARGIN, window.innerHeight - FLOAT_BUTTON_SIZE - FLOAT_BUTTON_MARGIN - logPanelOffsetPx);

    const x = Math.min(maxX, Math.max(FLOAT_BUTTON_MARGIN, Number(position.x) || 0));
    const y = Math.min(maxY, Math.max(FLOAT_BUTTON_MARGIN, Number(position.y) || 0));
    return { x, y };
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
        };
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
    }, [logPanelOffsetPx, shouldRender]);

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

    const handlePointerMove = (e) => {
        const state = dragRef.current;
        if (!state.active) return;

        const dx = e.clientX - state.startClientX;
        const dy = e.clientY - state.startClientY;
        if (!state.moved && (Math.abs(dx) > 4 || Math.abs(dy) > 4)) {
            state.moved = true;
        }

        const next = clampFabPosition(
            {
                x: state.startX + dx,
                y: state.startY + dy,
            },
            logPanelOffsetPx,
        );
        if (!next) return;
        setButtonPosition(next);
    };

    const handlePointerUp = () => {
        dragRef.current.active = false;
    };

    useEffect(() => {
        if (!shouldRender) return;
        window.addEventListener('pointermove', handlePointerMove);
        window.addEventListener('pointerup', handlePointerUp);
        return () => {
            window.removeEventListener('pointermove', handlePointerMove);
            window.removeEventListener('pointerup', handlePointerUp);
        };
    }, [shouldRender]);

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

    const buttonBottomStyle = {
        bottom: `calc(20px + env(safe-area-inset-bottom, 0px) + ${logPanelOffsetPx}px)`,
    };
    const panelBottomStyle = {
        bottom: `calc(80px + env(safe-area-inset-bottom, 0px) + ${logPanelOffsetPx}px)`,
    };
    const buttonStyle = buttonPosition
        ? { left: `${buttonPosition.x}px`, top: `${buttonPosition.y}px` }
        : buttonBottomStyle;

    if (!shouldRender) {
        return null;
    }

    return (
        <>
            {isOpen && (
                <div style={panelBottomStyle} className="fixed right-4 w-[min(92vw,430px)] h-[70vh] max-h-[760px] z-[120]">
                    <AgentChat context={context} isSuperuser={isSuperuser} onClose={() => setIsOpen(false)} />
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
