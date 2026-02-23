
import React, { createContext, useState, useContext, useCallback } from 'react';

const LogContext = createContext();

export const useLog = () => useContext(LogContext);

export const LogProvider = ({ children }) => {
    const [logs, setLogs] = useState([]);
    const [isLogOpen, setIsLogOpen] = useState(false);

    const addLog = useCallback((msg, type='info') => {
        const timestamp = new Date().toLocaleTimeString();
        setLogs(prev => [`[${timestamp}] [${type.toUpperCase()}] ${msg}`, ...prev]);
    }, []);

    const clearLogs = useCallback(() => {
        setLogs([]);
    }, []);

    return (
        <LogContext.Provider value={{ logs, addLog, isLogOpen, setIsLogOpen, clearLogs }}>
            {children}
        </LogContext.Provider>
    );
};
