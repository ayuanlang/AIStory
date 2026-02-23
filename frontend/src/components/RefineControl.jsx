import React, { useState } from 'react';
import { useLog } from '../context/LogContext';
import { Loader2, Wand2, Image as ImageIcon, Plus, X, Languages, MessageSquare } from 'lucide-react';
import { generateImage, refinePrompt, translateText } from '../services/api';
import { BASE_URL } from '../config';
import { getUiLang, tUI } from '../lib/uiLang';

// Helper to handle relative URLs
const getFullUrl = (url) => {
    if (!url) return '';
    if (url.startsWith('http') || url.startsWith('blob:') || url.startsWith('data:')) return url;
    if (url.startsWith('/')) {
        const base = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;
        return `${base}${url}`;
    }
    return url;
};

const RefineControl = ({ originalText, onUpdate, type = 'image', currentImage = null, onImageUpdate = null, projectId = null, shotId = null, assetType = null, featureInjector = null, onPickMedia = null }) => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const { addLog } = useLog();
    const [instruction, setInstruction] = useState('');
    const [loading, setLoading] = useState(false);
    const [translating, setTranslating] = useState(false);
    const [optimizing, setOptimizing] = useState(false);
    const [extraRefs, setExtraRefs] = useState([]);

    const handleTranslateInput = async () => {
        if (!instruction.trim() || translating) return;
        setTranslating(true);
        try {
            // Translate to English (from auto-detected language)
            const res = await translateText(instruction, 'auto', 'en');
            if (res && res.translated_text) {
                setInstruction(res.translated_text);
                addLog('Instruction translated to English', 'success');
            }
        } catch (e) {
            console.error(e);
            addLog('Translation failed', 'error');
        } finally {
            setTranslating(false);
        }
    };

    const handleOptimizePrompt = async () => {
        if (!instruction.trim() || optimizing) return;
        setOptimizing(true);
        try {
            // Apply Entity Feature Injection if available
            let finalInstruction = instruction;
            if (featureInjector) {
                const { text, modified } = featureInjector(finalInstruction);
                if (modified) {
                    finalInstruction = text;
                }
            }

            const res = await refinePrompt(originalText, finalInstruction, type);
            if (res.refined_prompt) {
                onUpdate(res.refined_prompt);
                setInstruction('');
                addLog("Prompt Refined with AI", 'success');
            }
        } catch (e) {
            console.error("Optimize failed", e);
            addLog("Optimization failed", 'error');
        } finally {
            setOptimizing(false);
        }
    };

    const handleAddRef = () => {
        if (onPickMedia) {
            onPickMedia((url) => {
                setExtraRefs(prev => [...prev, url]);
            });
        }
    };

    const handleRemoveRef = (index) => {
        setExtraRefs(prev => prev.filter((_, i) => i !== index));
    };

    const handleRefine = async () => {
        if (!instruction.trim() || loading) return;
        setLoading(true);
        try {
            // Apply Entity Feature Injection if available
            let finalPrompt = instruction;
            if (featureInjector) {
                const { text, modified } = featureInjector(finalPrompt);
                if (modified) {
                    finalPrompt = text;
                }
            }

            // Mode A: Image Generation / Refinement (if onImageUpdate is provided)
            if (onImageUpdate) {
                addLog(currentImage ? "Modifying Image with AI (Img2Img)..." : "Generating Image with AI...", 'process');
                
                // Auto-append constraint for modification to preserve composition
                if (currentImage) {
                     finalPrompt += ", keeping everything else unchanged";
                }

                // Combine currentImage (if exists) with extraRefs
                const allRefs = currentImage ? [currentImage, ...extraRefs] : [...extraRefs];
                
                const res = await generateImage(finalPrompt, null, allRefs, {
                    project_id: projectId,
                    shot_id: shotId,
                    asset_type: assetType || type
                });
                
                if (res && res.url) {
                    onImageUpdate(res.url); // Update Image
                    setInstruction('');
                    setExtraRefs([]); // Clear extra refs
                    addLog("Image Generated/Modified Successfully", 'success');
                }
            } 
            // Mode B: Text Refinement (LLM) - Fallback
            else {
                const res = await refinePrompt(originalText, finalPrompt, type);
                if (res.refined_prompt) {
                    onUpdate(res.refined_prompt);
                    setInstruction('');
                    addLog("Prompt Refined with AI", 'success');
                }
            }
        } catch (e) {
            console.error("Refine failed", e);
            const msg = e.response?.data?.detail || e.message;
            addLog("Refine failed: " + msg, 'error');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col gap-1 w-full mt-1">
            <div className="flex gap-2 items-center w-full">
                <input 
                    className="flex-1 bg-black/20 border border-white/10 rounded px-2 text-[10px] h-6 focus:border-purple-500/50 outline-none text-white/80 placeholder:text-white/30"
                    placeholder={onImageUpdate ? "Describe image or change (e.g. 'Cyberpunk city', 'Add rain')..." : `AI Modify ${type === 'video' ? 'Action' : 'Shot'} (e.g. angle, pose, lighting)...`}
                    value={instruction}
                    onChange={e => setInstruction(e.target.value)}
                    onKeyDown={e => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleRefine();
                        }
                    }}
                />
                
                {onImageUpdate && onPickMedia && (
                    <button 
                        onClick={handleAddRef}
                        className="h-6 px-1.5 rounded text-[10px] flex items-center gap-1 border border-dashed border-white/20 hover:border-white/50 text-white/50 hover:text-white/80 transition-colors"
                        title={t('添加参考图', 'Add Reference Images')}
                    >
                        <ImageIcon className="w-3 h-3"/>
                        <Plus className="w-2 h-2"/>
                    </button>
                )}

                <button 
                    onClick={handleTranslateInput}
                    disabled={!instruction.trim() || translating || loading}
                    className={`h-6 px-2 rounded text-[10px] flex items-center gap-1 border transition-colors ${translating ? 'bg-blue-500/10 text-blue-500/50 border-blue-500/10' : 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 border-blue-500/30'}`}
                    title={t('将输入翻译成英文', 'Translate input to English')}
                >
                    {translating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Languages className="w-3 h-3"/>}
                </button>

                {onImageUpdate && (
                    <button 
                        onClick={handleOptimizePrompt}
                        disabled={!instruction.trim() || optimizing || loading}
                        className={`h-6 px-2 rounded text-[10px] flex items-center gap-1 border transition-colors ${optimizing ? 'bg-indigo-500/10 text-indigo-500/50 border-indigo-500/10' : 'bg-indigo-500/20 text-indigo-400 hover:bg-indigo-500/30 border-indigo-500/30'}`}
                        title={t('优化提示词文本（LLM）', 'Optimize Prompt Text (LLM)')}
                    >
                        {optimizing ? <Loader2 className="w-3 h-3 animate-spin"/> : <MessageSquare className="w-3 h-3"/>}
                    </button>
                )}

                <button 
                    onClick={handleRefine}
                    disabled={!instruction.trim() || loading}
                    className={`h-6 px-2 rounded text-[10px] flex items-center gap-1 border transition-colors ${loading ? 'bg-purple-500/10 text-purple-500/50 border-purple-500/10' : 'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 border-purple-500/30'}`}
                    title={onImageUpdate ? t('生成图片', 'Generate Image') : t('优化文本提示词', 'Refine Text Prompt')}
                >
                    {loading ? <Loader2 className="w-3 h-3 animate-spin"/> : (onImageUpdate ? <ImageIcon className="w-3 h-3"/> : <Wand2 className="w-3 h-3"/>)}
                </button>
            </div>
            
            {/* Extra Refs Display */}
            {extraRefs.length > 0 && (
                <div className="flex gap-2 overflow-x-auto pb-1 items-center">
                    <span className="text-[9px] text-muted-foreground whitespace-nowrap">Refs:</span>
                    {extraRefs.map((url, idx) => (
                        <div key={idx} className="relative w-8 h-8 rounded border border-white/10 shrink-0 group">
                            <img src={getFullUrl(url)} className="w-full h-full object-cover rounded opacity-80" alt="ref"/>
                            <button 
                                onClick={() => handleRemoveRef(idx)}
                                className="absolute -top-1 -right-1 bg-red-500 text-white w-3 h-3 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                <X className="w-2 h-2"/>
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
};

export default RefineControl;
