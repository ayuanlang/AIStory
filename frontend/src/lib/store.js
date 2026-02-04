import { useContext } from 'react';
import { StoreContext } from '../context/StoreContext';
import { useLog } from '../context/LogContext';

export const useStore = () => {
    const store = useContext(StoreContext);
    const log = useLog(); // returns { addLog, ... }
    return { ...store, ...log };
};
