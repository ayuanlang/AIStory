import React, { useState, useEffect } from 'react';
import { getFunctionApiConfigs } from '../services/api';

export const useFunctionApis = () => {
    const [configs, setConfigs] = useState({});
    
    useEffect(() => {
        const load = async () => {
            try {
                const res = await getFunctionApiConfigs();
                const map = {};
                res.forEach(item => {
                    map[item.function_name] = item.api_settings;
                });
                setConfigs(map);
            } catch (err) {}
        };
        load();
    }, []);
    return configs;
};

const FunctionApiSelector = ({ functionName, configs, className = '' }) => {
    const apiList = configs?.[functionName] || [];
    const storageKey = 'func_api_' + functionName;
    const [value, setValue] = useState(Number(localStorage.getItem(storageKey)) || '');
    
    useEffect(() => {
        if (!value && apiList.length > 0) {
            const primary = apiList.find(a => !a.is_fallback) || apiList[0];
            if (primary && primary.system_api_id) {
                setValue(primary.system_api_id);
                localStorage.setItem(storageKey, primary.system_api_id);
            }
        }
    }, [apiList, value, storageKey]);

    if (apiList.length === 0) return null;

    const handleChange = (val) => {
        setValue(val);
        localStorage.setItem(storageKey, val);
    };

    return (
        <div className={`flex items-center gap-2 ${className}`}>
            <span className="text-xs text-white/50 whitespace-nowrap">API:</span>
            <select
                value={value || ''}
                onChange={(e) => handleChange(Number(e.target.value))}
                onClick={(e) => e.stopPropagation()}
                className="bg-[#111114] border border-white/10 rounded px-2 py-1 text-xs text-white outline-none focus:border-primary/50 min-w-[120px]"
            >
                <option value="" disabled>Select API...</option>
                {apiList.map(api => (
                    <option key={api.system_api_id} value={api.system_api_id}>
                        {api.system_api_name} {api.is_fallback ? '(备用)' : ''}
                    </option>
                ))}
            </select>
        </div>
    );
};
export default FunctionApiSelector;
