import React, { useMemo, useState } from 'react';
import { AlertCircle, Copy, FileText, Image as ImageIcon, Loader2, Upload, Wand2, X } from 'lucide-react';

const TABS = [
    { id: 'text', label: '文生实体', icon: FileText },
    { id: 'image', label: '图生实体', icon: ImageIcon },
    { id: 'derive', label: '派生实体', icon: Copy },
];

function AiEntityCreateDialog({
    isOpen,
    onClose,
    onGenerateText,
    onGenerateImage,
    onGenerateDerived,
    entities,
    isGeneratingRow,
}) {
    const [tab, setTab] = useState('text');
    const [entityName, setEntityName] = useState('');
    const [textDesc, setTextDesc] = useState('');
    const [imageFile, setImageFile] = useState(null);
    const [deriveEntityId, setDeriveEntityId] = useState('');
    const [deriveDesc, setDeriveDesc] = useState('');
    const [error, setError] = useState('');

    const imagePreviewUrl = useMemo(() => {
        if (!imageFile) return '';
        return URL.createObjectURL(imageFile);
    }, [imageFile]);
    const isEntityNameMissing = !entityName.trim();

    if (!isOpen) return null;

    const handleGenerate = async () => {
        setError('');
        try {
            const stableEntityName = entityName.trim();
            if (!stableEntityName) {
                setError('请输入实体中文名');
                return;
            }

            if (tab === 'text') {
                if (!textDesc.trim()) {
                    setError('请输入实体描述');
                    return;
                }
                await onGenerateText(stableEntityName, textDesc);
                return;
            }

            if (tab === 'image') {
                if (!imageFile) {
                    setError('请先上传图片');
                    return;
                }
                await onGenerateImage(stableEntityName, imageFile);
                return;
            }

            if (!deriveEntityId) {
                setError('请选择参考实体');
                return;
            }
            await onGenerateDerived(stableEntityName, deriveEntityId, deriveDesc || '保持主体特征，生成一个新的变体实体');
        } catch (err) {
            const msg = err?.response?.data?.detail || err?.message || '生成失败';
            setError(String(msg));
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-6" onClick={onClose}>
            <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-[#171717] shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
                <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
                    <div>
                        <div className="text-lg font-bold text-white">AI 新增实体</div>
                        <div className="text-xs text-white/60 mt-1">支持文本生成、图片反推、基于已有实体派生新实体</div>
                    </div>
                    <button onClick={onClose} className="p-2 rounded-full hover:bg-white/10 text-white/70 hover:text-white">
                        <X size={18} />
                    </button>
                </div>

                <div className="flex border-b border-white/10">
                    {TABS.map((item) => {
                        const Icon = item.icon;
                        const active = tab === item.id;
                        return (
                            <button
                                key={item.id}
                                onClick={() => setTab(item.id)}
                                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors border-b-2 flex items-center justify-center gap-2 ${active ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5' : 'border-transparent text-white/60 hover:text-white hover:bg-white/5'}`}
                            >
                                <Icon size={15} />
                                {item.label}
                            </button>
                        );
                    })}
                </div>

                <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
                    {error && (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300 flex items-center gap-2">
                            <AlertCircle size={14} />
                            {error}
                        </div>
                    )}

                    <div className="space-y-2">
                        <div className="text-xs text-white/70 flex items-center gap-1">
                            <span>实体中文名</span>
                            <span className="text-red-400">*</span>
                        </div>
                        <input
                            value={entityName}
                            onChange={(e) => setEntityName(e.target.value)}
                            className={`w-full rounded-md bg-black/30 px-3 py-2 text-sm text-white ${isEntityNameMissing ? 'border border-red-500/60 focus:border-red-400' : 'border border-white/15'}`}
                            placeholder="例如：墨宸"
                        />
                        <div className="text-[11px] text-white/45">提交前必须填写实体中文名，最终将按该名称入库。</div>
                    </div>

                    {tab === 'text' && (
                        <div className="space-y-2">
                            <div className="text-xs text-white/70">描述内容</div>
                            <textarea
                                value={textDesc}
                                onChange={(e) => setTextDesc(e.target.value)}
                                className="w-full h-52 rounded-md border border-white/15 bg-black/30 px-3 py-2 text-sm text-white resize-none"
                                placeholder="例如：20岁女性，黑色短发，穿着深蓝色校服，气质冷静，左手佩戴银色手环。"
                            />
                        </div>
                    )}

                    {tab === 'image' && (
                        <div className="space-y-3">
                            <div className="text-xs text-white/70">上传参考图</div>
                            <label className="w-full min-h-[220px] rounded-md border border-dashed border-white/20 bg-black/30 flex flex-col items-center justify-center gap-2 cursor-pointer hover:bg-white/5 transition-colors">
                                <input
                                    type="file"
                                    accept="image/*"
                                    className="hidden"
                                    onChange={(e) => {
                                        const file = e.target.files?.[0] || null;
                                        setImageFile(file);
                                    }}
                                />
                                {imagePreviewUrl ? (
                                    <img src={imagePreviewUrl} alt="preview" className="max-h-[240px] object-contain rounded" />
                                ) : (
                                    <>
                                        <Upload size={20} className="text-white/60" />
                                        <div className="text-sm text-white/70">点击上传图片</div>
                                        <div className="text-xs text-white/40">支持 jpg/png/webp</div>
                                    </>
                                )}
                            </label>
                        </div>
                    )}

                    {tab === 'derive' && (
                        <div className="space-y-3">
                            <div>
                                <div className="text-xs text-white/70 mb-1">选择参考实体</div>
                                <select
                                    value={deriveEntityId}
                                    onChange={(e) => setDeriveEntityId(e.target.value)}
                                    className="w-full rounded-md border border-white/15 bg-black/30 px-3 py-2 text-sm text-white"
                                >
                                    <option value="">请选择</option>
                                    {(entities || []).map((item) => {
                                        const nameZh = String(item.name || '').trim();
                                        const nameEn = String(item.name_en || '').trim();
                                        const isSubset = nameZh && nameEn && (nameZh.toLowerCase().includes(nameEn.toLowerCase()) || nameEn.toLowerCase().includes(nameZh.toLowerCase()));
                                        return (
                                            <option key={item.id} value={item.id}>
                                                {item.name}{nameEn && !isSubset ? ` (${item.name_en})` : ''}
                                            </option>
                                        );
                                    })}
                                </select>
                            </div>
                            <div>
                                <div className="text-xs text-white/70 mb-1">追加描述</div>
                                <textarea
                                    value={deriveDesc}
                                    onChange={(e) => setDeriveDesc(e.target.value)}
                                    className="w-full h-36 rounded-md border border-white/15 bg-black/30 px-3 py-2 text-sm text-white resize-none"
                                    placeholder="例如：保持脸部特征不变，发型改为波浪短发，服装换成黑色风衣。"
                                />
                                <div className="text-[11px] text-white/45 mt-1">
                                    LLM 会基于参考实体的中英文提示词改写为新实体提示词，并将参考实体自动设为视觉依赖。
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <div className="px-6 py-4 bg-black/20 border-t border-white/10 flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        disabled={isGeneratingRow}
                        className="px-4 py-2 text-sm font-medium text-white/70 hover:text-white transition-colors"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleGenerate}
                        disabled={isGeneratingRow || isEntityNameMissing}
                        className="px-6 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                        {isGeneratingRow ? (
                            <>
                                <Loader2 size={16} className="animate-spin" />
                                生成中...
                            </>
                        ) : (
                            <>
                                <Wand2 size={16} />
                                开始生成
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}

export default AiEntityCreateDialog;
