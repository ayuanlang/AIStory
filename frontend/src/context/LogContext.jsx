import React, { createContext, useState, useContext, useCallback, useEffect, useRef } from 'react';
import { fetchUiSystemLogs, persistUiSystemLogs } from '../services/api';

const LogContext = createContext();

export const useLog = () => useContext(LogContext);

const FLUSH_DELAY_MS = 800;
const FLUSH_BATCH_SIZE = 20;
const MAX_LOGS = 100;

const hasAuthToken = () => Boolean(localStorage.getItem('token'));

const toDisplayLines = (entries = []) => {
    const list = Array.isArray(entries) ? entries : [];
    // API returns oldest → newest; panel shows newest first.
    return list
        .map((entry) => {
            const display = String(entry?.display || '').trim();
            if (display) return display;
            const message = String(entry?.message || '').trim();
            if (!message) return '';
            const level = String(entry?.level || 'INFO').trim().toUpperCase() || 'INFO';
            const stamp = String(entry?.stamp || '').trim();
            const time = stamp.length >= 19 ? stamp.slice(11, 19) : (stamp || '--:--:--');
            return `[${time}] [${level}] ${message}`;
        })
        .filter(Boolean)
        .reverse()
        .slice(0, MAX_LOGS);
};

export const LogProvider = ({ children }) => {
    const [logs, setLogs] = useState([]);
    const [isLogOpen, setLogOpenState] = useState(false);
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);
    const persistQueueRef = useRef([]);
    const flushTimerRef = useRef(null);
    const historyLoadedRef = useRef(false);
    const historyLoadingRef = useRef(false);

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
                // Keep any brand-new local lines that are not yet in persisted history.
                const persistedSet = new Set(displayLines);
                const pendingLocal = (Array.isArray(prev) ? prev : []).filter((line) => !persistedSet.has(line));
                return [...pendingLocal, ...displayLines].slice(0, MAX_LOGS);
            });
        } catch (_) {
            // Soft-fail: keep whatever is already in memory.
        } finally {
            historyLoadingRef.current = false;
            setIsLoadingHistory(false);
        }
    }, [flushPersistQueue]);

    const addLog = useCallback((msg, type = 'info') => {
        const timestamp = new Date().toLocaleTimeString();
        const level = String(type || 'info').toLowerCase() || 'info';
        const message = String(msg ?? '');
        setLogs(prev => [`[${timestamp}] [${level.toUpperCase()}] ${message}`, ...prev].slice(0, MAX_LOGS));

        persistQueueRef.current.push({
            message,
            type: level,
            client_time: new Date().toISOString(),
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
