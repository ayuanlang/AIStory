import React, { useState, useEffect, useCallback } from 'react';
import { getUiLang, tUI, UI_LANG_EVENT } from '../lib/uiLang';

const FUNCTION_API_CHANGE_EVENT = 'aistory:function-api-changed';

const FunctionApiSelector = ({ functionName, configs, label = "AI 模型", className = '', onChange }) => {

    const apiList = configs?.[functionName] || [];
    const storageKey = 'func_api_' + functionName;
    const [value, setValue] = useState(Number(localStorage.getItem(storageKey)) || '');

    const applyValue = useCallback((nextValue, { persist = true } = {}) => {
        const normalized = Number(nextValue) || '';
        setValue(normalized);
        if (persist) {
            if (normalized) {
                localStorage.setItem(storageKey, String(normalized));
            } else {
                localStorage.removeItem(storageKey);
            }
            try {
                window.dispatchEvent(new CustomEvent(FUNCTION_API_CHANGE_EVENT, {
                    detail: { storageKey, value: normalized || null },
                }));
            } catch (_) {}
        }
        if (typeof onChange === 'function') {
            onChange(normalized || null);
        }
    }, [onChange, storageKey]);

    useEffect(() => {
        const stored = Number(localStorage.getItem(storageKey) || 0) || '';
        setValue(stored);
    }, [storageKey]);
    
    useEffect(() => {
        if (apiList.length > 0) {
            const isValid = apiList.some(a => Number(a.system_api_id) === Number(value));
            if (!value || !isValid) {
                const primary = apiList.find(a => !a.is_fallback) || apiList[0];
                if (primary && primary.system_api_id) {
                    applyValue(primary.system_api_id, { persist: true });
                }
            }
        }
    }, [apiList, value, applyValue]);

    useEffect(() => {
        if (typeof onChange === 'function') {
            onChange(Number(value) || null);
        }
    }, [onChange, value]);

    useEffect(() => {
        const handleStorage = (event) => {
            if (event?.key !== storageKey) return;
            const next = Number(event?.newValue || 0) || '';
            setValue(next);
        };
        const handleInternalSync = (event) => {
            const detailKey = String(event?.detail?.storageKey || '');
            if (detailKey !== storageKey) return;
            const next = Number(event?.detail?.value || 0) || '';
            setValue(next);
        };
        window.addEventListener('storage', handleStorage);
        window.addEventListener(FUNCTION_API_CHANGE_EVENT, handleInternalSync);
        return () => {
            window.removeEventListener('storage', handleStorage);
            window.removeEventListener(FUNCTION_API_CHANGE_EVENT, handleInternalSync);
        };
    }, [storageKey]);

    if (apiList.length === 0) return null;

    const handleChange = (val) => {
        applyValue(val, { persist: true });
    };

    return (
        <div className={`flex items-center gap-2 ${className}`}>

            <span className="text-xs text-white/50 whitespace-nowrap">{label}</span>

            <select
                value={value || ''}
                onChange={(e) => handleChange(Number(e.target.value))}
                onClick={(e) => e.stopPropagation()}
                className="w-full bg-[#111114] border border-white/10 rounded px-2 py-1 text-xs text-white outline-none focus:border-primary/50 min-w-[120px]"
            >
                      <option value="" disabled>{tUI('选择 API...', 'Select API...')}</option>
                {apiList.map((api, index) => (
                    <option key={`${api.system_api_id}-${index}`} value={api.system_api_id}>

                        {api.provider_alias ? `[${api.provider_alias}] ` : ""}{api.alias || (api.system_api_model || api.system_api_name || "API " + api.system_api_id)}{api.applicable_languages && api.applicable_languages.length > 0 ? " (" + api.applicable_languages.join(", ") + ")" : ""}{api.pricing_description ? " | " + api.pricing_description : ""}

                    </option>
                ))}
            </select>
        </div>
    );
};
export default FunctionApiSelector;
