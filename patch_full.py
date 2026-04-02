import re

with open("frontend/src/components/FunctionApiConfigTab.jsx", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Imports
content = content.replace(
    "import { getFunctionApiConfigs, updateFunctionApiConfig, getSystemSettingsManage } from '../services/api';",
    "import { getFunctionApiConfigs, updateFunctionApiConfig, getSystemSettingsManage, getApiRoutingConfig, updateApiRoutingConfig } from '../services/api';"
)

content = content.replace(
    "import { Plus, Trash2, Save, GripVertical } from 'lucide-react';",
    "import { Plus, Trash2, Save, GripVertical, Download, Upload } from 'lucide-react';"
)

content = content.replace(
    "import React, { useState, useEffect } from 'react';",
    "import React, { useState, useEffect, useRef } from 'react';"
)

# 2. Add Export/Import and States
state_code = """
export default function FunctionApiConfigTab() {
    const fileInputRef = useRef(null);
    const [configs, setConfigs] = useState({});
    const [systemApis, setSystemApis] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState({});
    const [routingConfig, setRoutingConfig] = useState({});
    const [savingRouting, setSavingRouting] = useState(false);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [configsData, sysApis, routingRes] = await Promise.all([
                getFunctionApiConfigs(),
                getSystemSettingsManage(),
                getApiRoutingConfig()
            ]);

            const configsMap = {};
            configsData.forEach(c => {
                configsMap[c.function_name] = c.api_settings || [];
            });
            setConfigs(configsMap);
            setRoutingConfig(routingRes || {});

            // Only keep non-deprecated APIs for the dropdowns
            const activeApis = sysApis.filter(api => !api.deprecated);
            setSystemApis(activeApis);
        } catch (error) {
            console.error('Failed to load function API configs', error);
            alert('获取失败');
        } finally {
            setLoading(false);
        }
    };

    const handleAddApi = (funcName) => {
        setConfigs(prev => {
            const existing = prev[funcName] || [];
            return {
                ...prev,
                [funcName]: [...existing, { system_api_id: '', priority: 0, is_fallback: true, explicit_selection: false, strict_provider: false }]
            };
        });
    };

    const handleRemoveApi = (funcName, index) => {
        setConfigs(prev => {
            const existing = [...prev[funcName]];
            existing.splice(index, 1);
            return {
                ...prev,
                [funcName]: existing
            };
        });
    };

    const handleChangeParams = (funcName, index, field, value) => {
        setConfigs(prev => {
            const existing = [...prev[funcName]];
            existing[index] = { ...existing[index], [field]: value };
            return {
                ...prev,
                [funcName]: existing
            };
        });
    };

    const handleExport = () => {
        const dataStr = JSON.stringify(configs, null, 2);
        const blob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'function_api_configs.json';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const handleImportClick = () => {
        if (fileInputRef.current) {
            fileInputRef.current.click();
        }
    };

    const handleImportFileChange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (evt) => {
            try {
                const importedConfigs = JSON.parse(evt.target.result);
                if (!window.confirm('确认要全量覆盖当前所有的功能API配置吗？此操作不可逆。')) {
                    e.target.value = '';
                    return;
                }

                setLoading(true);
                const allKeys = Object.keys(FUNCTION_LABELS);
                const mergedConfigs = { ...configs };

                for (let key of allKeys) {
                    const newItems = importedConfigs[key] || [];
                    
                    const itemsToSave = newItems.map(item => {
                        let langs = item.applicable_languages;
                        if (typeof langs === 'string') {
                            langs = langs.split(',').map(s => s.trim()).filter(Boolean);
                        }
                        
                        let fallbackAlias = null;
                        if (!item.alias && !!item.system_api_id) {
                            const defaultApi = systemApis.find(a => a.id === parseInt(item.system_api_id, 10));
                            if (defaultApi) fallbackAlias = defaultApi.model || defaultApi.name || ('API ' + defaultApi.id);
                        }

                        return {
                            system_api_id: parseInt(item.system_api_id, 10),
                            priority: parseInt(item.priority, 10) || 0,
                            is_fallback: Boolean(item.is_fallback),
                            alias: item.alias || fallbackAlias,
                            applicable_languages: langs && langs.length > 0 ? langs : null,
                            explicit_selection: Boolean(item.explicit_selection),
                            strict_provider: Boolean(item.strict_provider)
                        };
                    }).filter(item => !isNaN(item.system_api_id));

                    await updateFunctionApiConfig(key, { api_settings: itemsToSave });
                    mergedConfigs[key] = itemsToSave;
                }
                setConfigs(mergedConfigs);
                alert('配置全覆盖导入成功！');
            } catch (err) {
                console.error('Import failed', err);
                alert('解析导入文件失败或覆盖过程中发生错误！请检查文件格式。');
            } finally {
                setLoading(false);
                e.target.value = '';
            }
        };
        reader.readAsText(file);
    };

    const handleSave = async (funcName) => {
        setSaving(prev => ({ ...prev, [funcName]: true }));
        try {
            const items = configs[funcName].map(item => {
                let langs = item.applicable_languages;
                if (typeof langs === 'string') {
                    langs = langs.split(',').map(s => s.trim()).filter(Boolean);
                }
                
                let fallbackAlias = null;
                if (!item.alias && !!item.system_api_id) {
                    const defaultApi = systemApis.find(a => a.id === parseInt(item.system_api_id, 10));
                    if (defaultApi) fallbackAlias = defaultApi.model || defaultApi.name || ('API ' + defaultApi.id);
                }

                return {
                    system_api_id: parseInt(item.system_api_id, 10),
                    priority: parseInt(item.priority, 10) || 0,
                    is_fallback: Boolean(item.is_fallback),
                    alias: item.alias || fallbackAlias,
                    applicable_languages: langs && langs.length > 0 ? langs : null,
                    explicit_selection: Boolean(item.explicit_selection),
                    strict_provider: Boolean(item.strict_provider)
                };
            }).filter(item => !isNaN(item.system_api_id));

            const res = await updateFunctionApiConfig(funcName, { api_settings: items });
            setConfigs(prev => ({
                ...prev,
                [funcName]: res.api_settings || []
            }));
            alert('保存成功: ' + (FUNCTION_LABELS[funcName] || funcName));
        } catch (error) {
            console.error('Save failed', error);
            alert('保存失败');
        } finally {
            setSaving(prev => ({ ...prev, [funcName]: false }));
        }
    };
"""

content = re.sub(r'export default function FunctionApiConfigTab\(\) \{[\s\S]*?const handleSave = async \(funcName\) => \{[\s\S]*?setSaving\(prev => \(\{ \.\.\.prev, \[funcName\]: false \}\)\);\s*\}\s*\};', state_code, content)


header_block = """        <div className="space-y-8 pb-10">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 md:p-6 mb-6">
                <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-4">
                    <div>
                        <h3 className="text-xl font-medium text-white mb-2">功能专属 API 映射设置</h3>
                        <p className="text-gray-400 text-sm">
                            在此列表指定各功能执行的 API。支持为一个功能映射多 API （设定优先级）。<br/>当选择 API 失败时，会向同功能下勾选了 "作为备用 API（Fallback）" 的系统按优先级顺序重试。
                        </p>
                    </div>
                    <div className="flex items-center gap-3 mt-4 sm:mt-0">
                        <button
                            onClick={handleExport}
                            className="flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-white/10 whitespace-nowrap"
                        >
                            <Download size={16} /> 导出配置
                        </button>
                        <button
                            onClick={handleImportClick}
                            className="flex items-center justify-center gap-2 bg-primary/20 hover:bg-primary/30 text-primary px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-primary/20 whitespace-nowrap"
                        >
                            <Upload size={16} /> 导入覆盖
                        </button>
                        <input type="file" ref={fileInputRef} style={{ display: 'none' }} accept=".json" onChange={handleImportFileChange} />
                    </div>
                </div>

                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-medium text-white">全局路由控制</h3>
                    <div className="flex items-center">
"""

old_header_pattern = r'        <div className="space-y-8 pb-10">\s*<div className="bg-white/5 border border-white/10 rounded-xl p-4 md:p-6 mb-6">\s*<div className="flex items-center justify-between mb-4">\s*<h3 className="text-lg font-medium text-white">全局路由控制</h3>\s*<div className="flex items-center">'

content = re.sub(old_header_pattern, header_block, content)


# Inputs code block
inputs_block = """                                            <div className="flex-1">
                                                <select
                                                    value={item.system_api_id || ''}
                                                    onChange={(e) => {
                                                        const val = e.target.value;
                                                        setConfigs(prev => {
                                                            const existing = [...prev[funcName]];
                                                            const newItem = { ...existing[originalIndex], system_api_id: val };
                                                            if (val && !newItem.alias) {
                                                                const selectedApi = systemApis.find(a => a.id === parseInt(val, 10));
                                                                if (selectedApi) {
                                                                    newItem.alias = selectedApi.model || selectedApi.name || ('API ' + selectedApi.id);
                                                                }
                                                            }
                                                            existing[originalIndex] = newItem;
                                                            return { ...prev, [funcName]: existing };
                                                        });
                                                    }}
                                                    className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-primary/50"
                                                >
                                                    <option value="">-- 选择模型 API --</option>
                                                    {systemApis.map(api => (
                                                        <option key={api.id} value={api.id}>
                                                            ID:{api.id} | {api.name} ({api.model || 'N/A'}) - {api.provider || ''}
                                                        </option>
                                                    ))}
                                                    {/* If selected API is deprecated and missing from active list, inject it anyway */}
                                                    {item.system_api_id && !systemApis.some(a => a.id === item.system_api_id) && (
                                                        <option value={item.system_api_id}>
                                                            API [{item.system_api_name || item.system_api_id}] (已废弃/未验证)
                                                        </option>
                                                    )}
                                                </select>
                                            </div>

                                            <div className="flex-1 mt-2 md:mt-0">
                                                <input
                                                    type="text"
                                                    value={item.alias || ''}
                                                    onChange={(e) => handleChangeParams(funcName, originalIndex, 'alias', e.target.value)}
                                                    className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-primary/50"
                                                    placeholder="填写别名 (用于下拉框和Settings显示)"
                                                />
                                            </div>

                                            <div className="flex-1 mt-2 md:mt-0">
                                                <select
                                                    value={Array.isArray(item.applicable_languages) ? item.applicable_languages.join(',') : (item.applicable_languages || '')}
                                                    onChange={(e) => handleChangeParams(funcName, originalIndex, 'applicable_languages', e.target.value ? e.target.value.split(',') : null)}
                                                    className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-primary/50"
                                                >
                                                    <option value="">适用语言 (不限)</option>
                                                    <option value="zh">中文 (zh)</option>
                                                    <option value="en">英文 (en)</option>
                                                </select>
                                            </div>"""

# Match everything between `<div className="flex-1">` and `<div className="w-[100px]">`
content = re.sub(
    r'<div className="flex-1">\s*<select\s*value={item\.system_api_id \|\| \'\'}[\s\S]*?</select>\s*</div>',
    inputs_block,
    content
)

with open("frontend/src/components/FunctionApiConfigTab.jsx", "w", encoding="utf-8") as f:
    f.write(content)
