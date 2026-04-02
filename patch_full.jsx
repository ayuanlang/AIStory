import React, { useState, useEffect, useRef } from 'react';
import { Plus, Trash2, Save, GripVertical, Download, Upload } from 'lucide-react';
import { getFunctionApiConfigs, updateFunctionApiConfig, getSystemSettingsManage, getApiRoutingConfig, updateApiRoutingConfig } from '../services/api';

const FUNCTION_LABELS = {
    "generate_subjects": "生成故事主题 (提取关键词/标签)",
    "generate_story": "生成故事主线 (核心文案)",
    "generate_sub_stories": "生成分页故事 (多段落)",
    "generate_image_prompts": "生成图片提示词 (绘图所需)",
    "generate_images": "生成图片 (调用绘图大模型)",
    "image_understanding": "理解上传的图片内容 (图片反推)",
    "voice_clone": "克隆声音 (音频API)",
    "text_to_speech": "文本转语音 (旁白生成)"
};

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

            const activeApis = sysApis.filter(api => !api.deprecated);
            setSystemApis(activeApis);
        } catch (error) {
            console.error('Failed to load function API configs', error);
            // alert('获取失败');
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
                            alias: item.alias || fallbackAlias || null,
                            applicable_languages: langs && langs.length > 0 ? langs : null,
                            explicit_selection: Boolean(item.explicit_selection),
                            strict_provider: Boolean(item.strict_provider)
                        };
                    }).filter(item => !isNaN(item.system_api_id));

                    await updateFunctionApiConfig(key, { api_settings: itemsToSave });
                    mergedConfigs[key] = itemsToSave;
                }
                setConfigs(mergedConfigs);
                alert('配置全量覆盖成功');
            } catch (err) {
                console.error('Import failed', err);
                alert('导入配置失败，请检查文件格式。');
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
                    alias: item.alias || fallbackAlias || null,
                    applicable_languages: langs && langs.length > 0 ? langs : null,
                    explicit_selection: Boolean(item.explicit_selection),
                    strict_provider: Boolean(item.strict_provider)
                };
            }).filter(item => !isNaN(item.system_api_id));

            const res = await updateFunctionApiConfig(funcName, { api_settings: items });
            
            // Set exact items returned by backend ensuring formatting matches expectations
            setConfigs(prev => ({
                ...prev,
                [funcName]: res.api_settings || []
            }));
            alert('保存成功');
        } catch (error) {
            console.error('Save failed', error);
            alert('保存失败');
        } finally {
            setSaving(prev => ({ ...prev, [funcName]: false }));
        }
    };

    const handleRoutingToggle = async () => {
        setSavingRouting(true);
        try {
            const newVal = !routingConfig.use_function_based_routing;
            await updateApiRoutingConfig({ use_function_based_routing: newVal });
            setRoutingConfig(prev => ({ ...prev, use_function_based_routing: newVal }));
        } catch (error) {
            console.error('Failed saving routing config', error);
            alert('路由设置保存失败');
        } finally {
            setSavingRouting(false);
        }
    };

    if (loading && Object.keys(configs).length === 0) {
        return <div className="text-white text-center py-10">加载配置中...</div>;
    }

    return (
        <div className="space-y-8 pb-10">
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

                <div className="flex items-center justify-between mb-4 mt-8 pb-4 border-b border-white/10">
                    <div>
                        <h3 className="text-lg font-medium text-white">全局路由控制</h3>
                        <p className="text-xs text-gray-500 mt-1">开启后生成环节自动采用此列表配置的模型</p>
                    </div>
                    <div className="flex items-center">
                        <label className="flex items-center cursor-pointer">
                            <div className="relative">
                                <input
                                    type="checkbox"
                                    className="sr-only"
                                    checked={!!routingConfig.use_function_based_routing}
                                    onChange={handleRoutingToggle}
                                    disabled={savingRouting}
                                />
                                <div className={`block w-10 h-6 rounded-full transition-colors ${routingConfig.use_function_based_routing ? 'bg-primary' : 'bg-white/20'}`}></div>
                                <div className={`absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform ${routingConfig.use_function_based_routing ? 'transform translate-x-4' : ''}`}></div>
                            </div>
                            <span className="ml-3 text-sm text-gray-300">
                                {routingConfig.use_function_based_routing ? '已启用按功能 API 模式' : '基础模式 (使用全局默认API)'}
                            </span>
                        </label>
                    </div>
                </div>
            </div>

            {Object.entries(FUNCTION_LABELS).map(([funcName, label]) => (
                <div key={funcName} className="bg-white/5 border border-white/10 rounded-xl p-4 md:p-6 overflow-hidden">
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <h3 className="text-lg font-medium text-white">{label}</h3>
                            <code className="text-xs text-primary/70">{funcName}</code>
                        </div>
                        <button
                            onClick={() => handleSave(funcName)}
                            disabled={saving[funcName]}
                            className="bg-primary hover:bg-primary/90 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 disabled:opacity-50"
                        >
                            <Save size={16} />
                            {saving[funcName] ? '保存中...' : '保存修改'}
                        </button>
                    </div>

                    <div className="bg-black/20 rounded-lg p-2 md:p-4 min-h-[100px] border border-white/5">
                        <div className="space-y-3">
                            {(!configs[funcName] || configs[funcName].length === 0) ? (
                                <p className="text-sm text-gray-500 text-center py-4">
                                    尚未配置任何 API ({funcName})
                                </p>
                            ) : null}

                            {[...(configs[funcName] || [])].sort((a, b) => (b.priority || 0) - (a.priority || 0)).map((item, sortedIndex) => {
                                // Find the actual index in the original array
                                const originalIndex = configs[funcName].indexOf(item);
                                
                                return (
                                    <div key={`${funcName}-${originalIndex}`} className="flex flex-col md:flex-row md:items-center gap-4 p-3 bg-white/5 border border-white/10 rounded-lg group hover:border-primary/30 transition-colors relative">
                                        <div className="cursor-move text-gray-600 hover:text-gray-300 md:block hidden">
                                            <GripVertical size={18} />
                                        </div>
                                        
                                        <div className="flex-1 min-w-0">
                                            <div className="flex flex-col md:flex-row gap-3 items-start md:items-center">
                                                <div className="flex-1 w-full md:w-auto">
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
                                                        {item.system_api_id && !systemApis.some(a => a.id === item.system_api_id) && (
                                                            <option value={item.system_api_id}>
                                                                API [{item.system_api_name || item.system_api_id}] (已废弃/未验证)
                                                            </option>
                                                        )}
                                                    </select>
                                                </div>

                                                <div className="w-full md:w-48">
                                                    <input
                                                        type="text"
                                                        value={item.alias || ''}
                                                        onChange={(e) => handleChangeParams(funcName, originalIndex, 'alias', e.target.value)}
                                                        className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-primary/50"
                                                        placeholder="显示别名(留空用模型名)"
                                                    />
                                                </div>
                                                
                                                <div className="w-full md:w-36">
                                                    <select
                                                        value={Array.isArray(item.applicable_languages) ? item.applicable_languages.join(',') : (item.applicable_languages || '')}
                                                        onChange={(e) => handleChangeParams(funcName, originalIndex, 'applicable_languages', e.target.value ? e.target.value.split(',') : null)}
                                                        className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-primary/50"
                                                    >
                                                        <option value="">语言 (不限)</option>
                                                        <option value="zh">中文 (zh)</option>
                                                        <option value="en">英文 (en)</option>
                                                    </select>
                                                </div>

                                                <div className="w-full md:w-28">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-xs text-gray-400">优先级:</span>
                                                        <input
                                                            type="number"
                                                            value={item.priority || 0}
                                                            onChange={(e) => handleChangeParams(funcName, originalIndex, 'priority', parseInt(e.target.value, 10))}
                                                            className="w-full bg-white/5 border border-white/10 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-primary/50"
                                                        />
                                                    </div>
                                                </div>
                                            </div>
                                            
                                            <div className="flex flex-wrap items-center gap-4 mt-3 ml-1">
                                                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer group-hover:text-white transition-colors">
                                                    <input
                                                        type="checkbox"
                                                        checked={!!item.is_fallback}
                                                        onChange={(e) => handleChangeParams(funcName, originalIndex, 'is_fallback', e.target.checked)}
                                                        className="rounded text-primary focus:ring-primary/50 bg-white/10 border-white/20"
                                                    />
                                                    允许作为备用(Fallback)
                                                </label>
                                                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer group-hover:text-white transition-colors">
                                                    <input
                                                        type="checkbox"
                                                        checked={!!item.explicit_selection}
                                                        onChange={(e) => handleChangeParams(funcName, originalIndex, 'explicit_selection', e.target.checked)}
                                                        className="rounded text-primary focus:ring-primary/50 bg-white/10 border-white/20"
                                                    />
                                                    前端可显式选择
                                                </label>
                                                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer group-hover:text-white transition-colors">
                                                    <input
                                                        type="checkbox"
                                                        checked={!!item.strict_provider}
                                                        onChange={(e) => handleChangeParams(funcName, originalIndex, 'strict_provider', e.target.checked)}
                                                        className="rounded text-primary focus:ring-primary/50 bg-white/10 border-white/20"
                                                    />
                                                    严格限制供应商
                                                </label>
                                            </div>
                                        </div>

                                        <button
                                            onClick={() => handleRemoveApi(funcName, originalIndex)}
                                            className="p-2 text-red-500/70 hover:text-red-500 hover:bg-red-500/10 rounded transition-colors"
                                            title="移除此处配置"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    </div>
                                );
                            })}
                        </div>
                        
                        <button
                            onClick={() => handleAddApi(funcName)}
                            className="mt-4 flex items-center gap-2 text-sm text-primary hover:text-primary-light transition-colors py-2 px-3 hover:bg-primary/10 rounded-lg w-full justify-center border border-dashed border-primary/30"
                        >
                            <Plus size={16} />
                            添加 API 映射
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}
