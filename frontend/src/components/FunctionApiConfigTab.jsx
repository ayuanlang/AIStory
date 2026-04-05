import React, { useState, useEffect, useRef } from 'react';
import { Plus, Trash2, Save, GripVertical, Download, Upload } from 'lucide-react';
import { getFunctionApiConfigs, updateFunctionApiConfig, getSystemSettingsManage, getApiRoutingConfig, updateApiRoutingConfig } from '../services/api';

const FUNCTION_LABELS = {
    generate_subjects: '文生文 (角色/道具/环境文本)',
generate_subjects_t2i: '文生图 (角色/道具/环境)',
generate_subjects_i2i: '图生图 (角色/道具/环境)',
    generate_cover: '生成封面',
    generate_shot_images: '生成分镜图片',
    generate_videos: '生成视频',
    script_analysis: '剧本分析',
    subject_image_analysis: '实体图片分析'
};

export default function FunctionApiConfigTab() {
    const fileInputRef = useRef(null);
    const [configs, setConfigs] = useState({});
    const [systemApis, setSystemApis] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState({});
    const [routingConfig, setRoutingConfig] = useState({
        use_function_based_routing: false,
        explicit_selection: false,
        strict_provider: false
    });
    const [savingRouting, setSavingRouting] = useState(false);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [configsData, sysApis, routingData] = await Promise.all([
                getFunctionApiConfigs(),
                getSystemSettingsManage(),
                getApiRoutingConfig()
            ]);

            setRoutingConfig(routingData || {
                use_function_based_routing: false,
                explicit_selection: false,
                strict_provider: false
            });

            const configsMap = {};
            configsData.forEach(c => {
                configsMap[c.function_name] = c.api_settings || [];
            });
            setConfigs(configsMap);
            
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
                [funcName]: [...existing, { system_api_id: '', priority: 0, is_fallback: true, alias: '', applicable_languages: null }]
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

    const handleSave = async (funcName) => {
        setSaving(prev => ({ ...prev, [funcName]: true }));
        try {
            const items = configs[funcName].map(item => ({
                system_api_id: parseInt(item.system_api_id, 10),
                priority: parseInt(item.priority, 10) || 0,
                is_fallback: Boolean(item.is_fallback),
                alias: item.alias || '',
                applicable_languages: item.applicable_languages || null
            })).filter(item => !isNaN(item.system_api_id));

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

    const handleExport = () => {
        const dataStr = JSON.stringify(configs, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
        const exportFileDefaultName = 'function_api_configs.json';
        
        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();
    };

    const handleImportClick = () => {
        fileInputRef.current?.click();
    };

    const handleImportFileChange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (event) => {
            try {
                const json = JSON.parse(event.target.result);
                // Upload each function config
                for (const funcName of Object.keys(json)) {
                    await updateFunctionApiConfig(funcName, { api_settings: json[funcName] });
                }
                setConfigs(json);
                alert("导入成功！");
            } catch (error) {
                console.error("Error parsing JSON file:", error);
                alert("导入的文件格式不正确或保存失败！");
            }
        };
        reader.readAsText(file);
        e.target.value = null; // Reset input
    };

    if (loading) return <div className="text-gray-400 p-4">Loading configurations...</div>;

    const handleSaveRouting = async () => {
        setSavingRouting(true);
        try {
            await updateApiRoutingConfig(routingConfig);
            alert('全局开关设置保存成功');
        } catch (error) {
            console.error('Failed to save routing config', error);
            alert('保存失败');
        } finally {
            setSavingRouting(false);
        }
    };

    const functionNames = Object.keys(FUNCTION_LABELS);

    return (
        <div className="space-y-8 pb-10">
            <div>
                <div className="flex justify-between items-center mb-2">
                    <h3 className="text-xl font-medium text-white mb-2">功能专属 API 映射设置</h3>
                    <div className="flex gap-2">
                        <button
                            onClick={handleExport}
                            className="bg-white/5 hover:bg-white/10 text-white px-3 py-1.5 rounded-lg text-sm transition-colors border border-white/10 flex items-center gap-2"
                        >
                            <Download size={16} />
                            导出配置
                        </button>
                        <button
                            onClick={handleImportClick}
                            className="bg-white/5 hover:bg-white/10 text-white px-3 py-1.5 rounded-lg text-sm transition-colors border border-white/10 flex items-center gap-2"
                        >
                            <Upload size={16} />
                            导入配置
                            <input
                                type="file"
                                ref={fileInputRef}
                                style={{ display: 'none' }}
                                accept=".json"
                                onChange={handleImportFileChange}
                            />
                        </button>
                    </div>
                </div>
                <p className="text-gray-400 text-sm mb-4">
                    在此列表指定各功能执行的 API。支持为一个功能映射多 API （设 定优先级）。<br/>当选择 API 失败时，会向同功能下勾选了 "作为备用 API（Fallback）" 的系统按优先级顺序重试。
                </p>

                <div className="bg-[#111114] border border-white/10 rounded-xl p-4 md:p-6 mb-6">
                    <div className="flex items-center justify-between mb-4">
                        <h4 className="text-lg font-medium text-white/90">全局路由开关设定</h4>
                        <button
                            onClick={handleSaveRouting}
                            disabled={savingRouting}
                            className="bg-primary/20 hover:bg-primary/30 text-primary px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-primary/20 flex items-center gap-2"
                        >
                            <Save size={16} />
                            {savingRouting ? '保存中...' : '保存全局开关'}
                        </button>
                    </div>
                    <div className="space-y-4">
                        <label className="flex items-start gap-3 cursor-pointer group">
                            <div className="mt-0.5">
                                <input 
                                    type="checkbox" 
                                    className="rounded bg-white/5 border-white/10 text-primary form-checkbox w-4 h-4 cursor-pointer"
                                    checked={routingConfig.use_function_based_routing || false}
                                    onChange={(e) => setRoutingConfig(prev => ({...prev, use_function_based_routing: e.target.checked}))}
                                />
                            </div>
                            <div>
                                <div className="text-sm font-medium text-gray-200 group-hover:text-white transition-colors">启用功能粒度 API 路由</div>
                                <div className="text-xs text-gray-500 mt-0.5">开启后，系统在执行功能时将优先查找下方定义的功能 API 映射。不开启将走旧版的全局智能选择。</div>
                            </div>
                        </label>

                        <label className="flex items-start gap-3 cursor-pointer group">
                            <div className="mt-0.5">
                                <input 
                                    type="checkbox" 
                                    className="rounded bg-white/5 border-white/10 text-primary form-checkbox w-4 h-4 cursor-pointer"
                                    checked={routingConfig.explicit_selection || false}
                                    onChange={(e) => setRoutingConfig(prev => ({...prev, explicit_selection: e.target.checked}))}
                                />
                            </div>
                            <div>
                                <div className="text-sm font-medium text-gray-200 group-hover:text-white transition-colors">全局首选显式指定 (Explicit Selection)</div>
                                <div className="text-xs text-gray-500 mt-0.5">开启后，告诉智能路由：功能专属列表中配置的 API 就是用户的“首选明确指定”。兜底行为仅限于允许“指定失败后容灾”的模型。</div>
                            </div>
                        </label>
                        
                        <label className="flex items-start gap-3 cursor-pointer group">
                            <div className="mt-0.5">
                                <input 
                                    type="checkbox" 
                                    className="rounded bg-white/5 border-white/10 text-primary form-checkbox w-4 h-4 cursor-pointer"
                                    checked={routingConfig.strict_provider || false}
                                    onChange={(e) => setRoutingConfig(prev => ({...prev, strict_provider: e.target.checked}))}
                                />
                            </div>
                            <div>
                                <div className="text-sm font-medium text-gray-200 group-hover:text-white transition-colors">全局严格锁定供应商 (Strict Provider)</div>
                                <div className="text-xs text-gray-500 mt-0.5">开启后，系统在生成请求失败时<strong>完全不触发</strong>任何随机模型备用兜底，哪怕有模型支持容灾也会直接失败。保证生成的唯一确定性。</div>
                            </div>
                        </label>
                    </div>
                </div>

            </div>

            <div className="space-y-6">
                {functionNames.map(funcName => {
                    const items = configs[funcName] || [];
                    // Keep them sorted visually by priority desc
                    const sortedItems = [...items].sort((a, b) => b.priority - a.priority);

                    return (
                        <div key={funcName} className="bg-white/5 border border-white/10 rounded-xl p-4 md:p-6">
                            <div className="flex items-center justify-between mb-4 md:mb-5">
                                <div>
                                    <h4 className="text-lg font-medium text-blue-300">{FUNCTION_LABELS[funcName]}</h4>
                                    <p className="text-xs text-gray-400 mt-1">标识: <code className="bg-black/30 px-1.5 py-0.5 rounded text-gray-300">{funcName}</code></p>
                                </div>
                                <button
                                    onClick={() => handleSave(funcName)}
                                    disabled={saving[funcName]}
                                    className="flex items-center gap-2 bg-primary/20 hover:bg-primary/30 text-primary px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-primary/20"
                                >
                                    <Save size={16} />
                                    {saving[funcName] ? '保存中...' : '保存修改'}
                                </button>
                            </div>

                            <div className="space-y-3">
                                {sortedItems.map((item, index) => {
                                    const originalIndex = items.findIndex(orig => orig === item);

                                    return (
                                        <div key={originalIndex} className="flex flex-col md:flex-row gap-3 md:items-center bg-[#111114] p-3 rounded-lg border border-white/5">
                                            <div className="flex-1">
                                                <select
                                                    value={item.system_api_id || ''}
                                                    onChange={(e) => handleChangeParams(funcName, originalIndex, 'system_api_id', e.target.value)}
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
                                                <div className="flex gap-2 mt-2">
                                                    <input
                                                        type="text"
                                                        value={item.alias || ''}
                                                        onChange={(e) => handleChangeParams(funcName, originalIndex, 'alias', e.target.value)}
                                                        className="flex-1 bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-primary/50"
                                                        placeholder="模型别名 (例如: gpt-4o)"
                                                    />
                                                    <select
                                                        value={Array.isArray(item.applicable_languages) ? (item.applicable_languages[0] || '') : (item.applicable_languages || '')}
                                                        onChange={(e) => handleChangeParams(funcName, originalIndex, 'applicable_languages', e.target.value ? [e.target.value] : null)}
                                                        className="w-[120px] bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-primary/50"
                                                    >
                                                        <option value="">--所有语言--</option>
                                                        <option value="zh">中文</option>
                                                        <option value="en">英文</option>
                                                    </select>
                                                </div>
                                            </div>
                                            <div className="w-[100px]">
                                                <label className="text-xs text-gray-500 mb-1 block md:hidden">优先级:</label>
                                                <div className="flex items-center bg-white/5 border border-white/10 rounded px-2 overflow-hidden h-8">
                                                    <span className="text-xs text-gray-400 px-1 border-r border-white/10 mr-2">P</span>
                                                    <input
                                                        type="number"
                                                        value={item.priority}
                                                        onChange={(e) => handleChangeParams(funcName, originalIndex, 'priority', parseInt(e.target.value) || 0)}
                                                        className="w-full bg-transparent text-sm text-white border-0 focus:ring-0 focus:outline-none p-0"
                                                        title="数值越大，优先级越高"
                                                    />
                                                </div>
                                            </div>
                                            <div className="flex-1 flex gap-4 pr-4 border-r border-white/10 overflow-x-auto">
                                                <div className="flex items-center h-8 shrink-0">
                                                    <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-300">
                                                        <input
                                                            type="checkbox"
                                                            checked={item.is_fallback}
                                                            onChange={(e) => handleChangeParams(funcName, originalIndex, 'is_fallback', e.target.checked)}
                                                            className="rounded bg-white/5 border-white/10 text-primary form-checkbox"
                                                        />
                                                        作为兜底
                                                    </label>
                                                </div>
                                            </div>
                                            <button
                                                onClick={() => handleRemoveApi(funcName, originalIndex)}
                                                className="text-red-400/70 hover:text-red-400 p-1.5 bg-red-400/5 hover:bg-red-400/10 rounded h-8 w-8 flex items-center justify-center transition-colors shrink-0"
                                                title="移除此 API"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </div>
                                    );
                                })}
                                {items.length === 0 && (
                                    <div className="text-sm text-gray-500 italic py-2">
                                        暂未配置任何可用 API
                                    </div>
                                )}
                            </div>

                            <button
                                onClick={() => handleAddApi(funcName)}
                                className="mt-4 flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 transition-colors"
                            >
                                <Plus size={16} /> 添加可用 API
                            </button>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
