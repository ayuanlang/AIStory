import React, { useState, useEffect } from 'react';
import { getUiLang, tUI, UI_LANG_EVENT } from '../lib/uiLang';

const FunctionApiSelector = ({ functionName, configs, label = "AI 模型", className = '' }) => {

    const apiList = configs?.[functionName] || [];
    const storageKey = 'func_api_' + functionName;
    const [value, setValue] = useState(Number(localStorage.getItem(storageKey)) || '');
    
    useEffect(() => {
        if (apiList.length > 0) {
            const isValid = apiList.some(a => Number(a.system_api_id) === Number(value));
            if (!value || !isValid) {
                const primary = apiList.find(a => !a.is_fallback) || apiList[0];
                if (primary && primary.system_api_id) {
                    setValue(primary.system_api_id);
                    localStorage.setItem(storageKey, primary.system_api_id);
                }
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

                        {api.provider_alias ? `[${api.provider_alias}] ` : ""}{api.alias || (api.system_api_model || api.system_api_name || "API " + api.system_api_id)}{api.applicable_languages && api.applicable_languages.length > 0 ? " (" + api.applicable_languages.join(", ") + ")" : ""}

                    </option>
                ))}
            </select>
        </div>
    );
};
export default FunctionApiSelector;
