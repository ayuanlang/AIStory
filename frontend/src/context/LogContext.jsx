import React, { createContext, useState, useContext, useCallback, useEffect, useRef } from 'react';
import { persistUiSystemLogs } from '../services/api';

const LogContext = createContext();

export const useLog = () => useContext(LogContext);

const FLUSH_DELAY_MS = 800;
const FLUSH_BATCH_SIZE = 20;
const MAX_LOGS = 100;

export const LogProvider = ({ children }) => {
    const [logs, setLogs] = useState([]);
    const [isLogOpen, setIsLogOpen] = useState(false);
    const persistQueueRef = useRef([]);
    const flushTimerRef = useRef(null);

    const flushPersistQueue = useCallback(() => {
        const batch = persistQueueRef.current.splice(0, persistQueueRef.current.length);
        if (!batch.length) return;
        if (!localStorage.getItem('token')) return;

        void persistUiSystemLogs({ entries: batch }).catch(() => {});
    }, []);

    const schedulePersistFlush = useCallback(() => {
        if (flushTimerRef.current) return;
        flushTimerRef.current = setTimeout(() => {
            flushTimerRef.current = null;
            flushPersistQueue();
        }, FLUSH_DELAY_MS);
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
        <LogContext.Provider value={{ logs, addLog, isLogOpen, setIsLogOpen, clearLogs }}>
            {children}
        </LogContext.Provider>
    );
};
