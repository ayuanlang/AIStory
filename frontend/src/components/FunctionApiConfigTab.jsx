import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Save, GripVertical } from 'lucide-react';
import { getFunctionApiConfigs, updateFunctionApiConfig, getSystemSettingsManage } from '../services/api';

const FUNCTION_LABELS = {
    generate_subjects: '生成实体 (角色/道具/环境)',
    generate_cover: '生成封面',
    generate_shot_images: '生成分镜图片',
    generate_videos: '生成视频',
    script_analysis: '剧本分析',
    subject_image_analysis: '实体图片分析'
};

export default function FunctionApiConfigTab() {
    const [configs, setConfigs] = useState({});
    const [systemApis, setSystemApis] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState({});

    

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [configsData, sysApis] = await Promise.all([
                getFunctionApiConfigs(),
                getSystemSettingsManage()
            ]);
            
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
                [funcName]: [...existing, { system_api_id: '', priority: 0, is_fallback: true }]
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
                is_fallback: Boolean(item.is_fallback)
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

    if (loading) return <div className="text-gray-400 p-4">Loading configurations...</div>;

    const functionNames = Object.keys(FUNCTION_LABELS);

    return (
        <div className="space-y-8 pb-10">
            <div>
                <h3 className="text-xl font-medium text-white mb-2">功能专属 API 映射设置</h3>
                <p className="text-gray-400 text-sm mb-6">
                    在此列表指定各功能执行的 API。支持为一个功能映射多 API （设定优先级）。<br/>当选择 API 失败时，会向同功能下勾选了 "作为备用 API（Fallback）" 的系统按优先级顺序重试。
                </p>
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
                                            <div className="w-[120px] flex items-center h-8">
                                                <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-300">
                                                    <input
                                                        type="checkbox"
                                                        checked={item.is_fallback}
                                                        onChange={(e) => handleChangeParams(funcName, originalIndex, 'is_fallback', e.target.checked)}
                                                        className="rounded bg-white/5 border-white/10 text-primary form-checkbox"
                                                    />
                                                    自动备用
                                                </label>
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
