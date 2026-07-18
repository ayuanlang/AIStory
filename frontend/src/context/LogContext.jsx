import React, { createContext, useState, useContext, useCallback, useEffect, useRef } from 'react';
import { fetchUiSystemLogs, persistUiSystemLogs } from '../services/api';

const LogContext = createContext();

export const useLog = () => useContext(LogContext);

const FLUSH_DELAY_MS = 800;
const FLUSH_BATCH_SIZE = 20;
const MAX_LOGS = 100;

const hasAuthToken = () => Boolean(localStorage.getItem('token'));

/** Stable 24h clock for live lines (matches backend Beijing display). */
const formatHms = (date = new Date()) => {
    const d = date instanceof Date ? date : new Date(date);
    if (Number.isNaN(d.getTime())) return '--:--:--';
    const pad = (n) => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
};

const buildDisplayLine = (level, message, timeLabel) => (
    `[${timeLabel || '--:--:--'}] [${String(level || 'INFO').toUpperCase()}] ${String(message ?? '')}`
);

const toDisplayLines = (entries = []) => {
    const list = Array.isArray(entries) ? entries : [];
    // API returns oldest → newest; panel shows newest first.
    return list
        .map((entry) => {
            const message = String(entry?.message || '').trim();
            const display = String(entry?.display || '').trim();
            if (display) return display;
            if (!message) return '';
            const level = String(entry?.level || 'INFO').trim().toUpperCase() || 'INFO';
            let timeLabel = '';
            const clientTime = String(entry?.client_time || '').trim();
            if (clientTime) {
                const parsed = new Date(clientTime);
                if (!Number.isNaN(parsed.getTime())) timeLabel = formatHms(parsed);
            }
            if (!timeLabel) {
                const stamp = String(entry?.stamp || '').trim();
                timeLabel = stamp.length >= 19 ? stamp.slice(11, 19) : (stamp || '--:--:--');
            }
            return buildDisplayLine(level, message, timeLabel);
        })
        .filter(Boolean)
        .reverse()
        .slice(0, MAX_LOGS);
};

/** Dedupe key: level + message (ignore clock so UTC/local variants collapse). */
const lineDedupeKey = (line) => {
    const text = String(line || '');
    const match = text.match(/^\[[^\]]*\]\s*\[([^\]]+)\]\s*(.*)$/);
    if (!match) return text;
    return `${String(match[1] || '').toUpperCase()}|${String(match[2] || '').trim()}`;
};

export const LogProvider = ({ children }) => {
    const [logs, setLogs] = useState([]);
    const [isLogOpen, setLogOpenState] = useState(false);
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);
    const persistQueueRef = useRef([]);
    const flushTimerRef = useRef(null);
    const historyLoadedRef = useRef(false);
    const historyLoadingRef = useRef(false);
    const liveSeqRef = useRef(0);

    const flushPersistQueue = useCallback(() => {
        const batch = persistQueueRef.current.splice(0, persistQueueRef.current.length);
        if (!batch.length) return;
        if (!hasAuthToken()) return;

        void persistUiSystemLogs({ entries: batch }).catch(() => {});
    }, []);

    const schedulePersistFlush = useCallback(() => {
        if (flushTimerRef.current) return;
        flushTimerRef.current = setTimeout(() => {
            flushTimerRef.current = null;
            flushPersistQueue();
        }, FLUSH_DELAY_MS);
    }, [flushPersistQueue]);

    const loadPersistedLogs = useCallback(async ({ force = false } = {}) => {
        if (!hasAuthToken()) return;
        if (historyLoadingRef.current) return;
        if (historyLoadedRef.current && !force) return;

        historyLoadingRef.current = true;
        setIsLoadingHistory(true);
        const seqAtStart = liveSeqRef.current;
        try {
            // Flush pending local entries first so the read includes the latest writes.
            if (flushTimerRef.current) {
                clearTimeout(flushTimerRef.current);
                flushTimerRef.current = null;
            }
            flushPersistQueue();

            const result = await fetchUiSystemLogs(MAX_LOGS);
            const displayLines = toDisplayLines(result?.entries);
            historyLoadedRef.current = true;

            setLogs((prev) => {
                const persistedKeys = new Set(displayLines.map(lineDedupeKey));
                // Only keep lines added while this fetch was in flight (prepended by addLog).
                const liveCount = Math.max(0, liveSeqRef.current - seqAtStart);
                const liveWhileLoading = (Array.isArray(prev) ? prev : [])
                    .slice(0, liveCount)
                    .filter((line) => !persistedKeys.has(lineDedupeKey(line)));
                // Newest first: live (newest) → persisted history (already newest-first).
                return [...liveWhileLoading, ...displayLines].slice(0, MAX_LOGS);
            });
        } catch (_) {
            // Soft-fail: keep whatever is already in memory.
        } finally {
            historyLoadingRef.current = false;
            setIsLoadingHistory(false);
        }
    }, [flushPersistQueue]);

    const addLog = useCallback((msg, type = 'info') => {
        const message = String(msg ?? '');
        if (!message.trim()) return;

        liveSeqRef.current += 1;
        const now = new Date();
        const level = String(type || 'info').toLowerCase() || 'info';
        const line = buildDisplayLine(level, message, formatHms(now));
        setLogs((prev) => [line, ...prev].slice(0, MAX_LOGS));

        persistQueueRef.current.push({
            message,
            type: level,
            client_time: now.toISOString(),
        });

        if (persistQueueRef.current.length >= FLUSH_BATCH_SIZE) {
            if (flushTimerRef.current) {
                clearTimeout(flushTimerRef.current);
                flushTimerRef.current = null;
            }
            flushPersistQueue();
            return;
        }
        schedulePersistFlush();
    }, [flushPersistQueue, schedulePersistFlush]);

    const clearLogs = useCallback(() => {
        setLogs([]);
    }, []);

    const setIsLogOpen = useCallback((open = true) => {
        const nextOpen = typeof open === 'function' ? Boolean(open(isLogOpen)) : Boolean(open);
        setLogOpenState(nextOpen);
        if (nextOpen) {
            void loadPersistedLogs({ force: true });
        }
    }, [isLogOpen, loadPersistedLogs]);

    useEffect(() => {
        // Auto-load existing records as soon as the app has a login token.
        if (!hasAuthToken()) return undefined;
        void loadPersistedLogs({ force: false });

        const onStorage = (event) => {
            if (event.key === 'token' && event.newValue) {
                historyLoadedRef.current = false;
                void loadPersistedLogs({ force: true });
            }
        };
        window.addEventListener('storage', onStorage);
        return () => window.removeEventListener('storage', onStorage);
    }, [loadPersistedLogs]);

    useEffect(() => {
        const flushOnUnload = () => {
            if (flushTimerRef.current) {
                clearTimeout(flushTimerRef.current);
                flushTimerRef.current = null;
            }
            flushPersistQueue();
        };
        window.addEventListener('beforeunload', flushOnUnload);
        return () => {
            window.removeEventListener('beforeunload', flushOnUnload);
            if (flushTimerRef.current) {
                clearTimeout(flushTimerRef.current);
                flushTimerRef.current = null;
            }
            flushPersistQueue();
        };
    }, [flushPersistQueue]);

    return (
        <LogContext.Provider
            value={{
                logs,
                addLog,
                isLogOpen,
                setIsLogOpen,
                clearLogs,
                isLoadingHistory,
                reloadLogs: () => loadPersistedLogs({ force: true }),
            }}
        >
            {children}
        </LogContext.Provider>
    );
};
