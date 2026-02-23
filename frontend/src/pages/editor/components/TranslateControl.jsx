import { useState } from 'react';
import { Languages, RefreshCw, X } from 'lucide-react';
import { useLog } from '../../../context/LogContext';
import { translateText } from '../../../services/api';
import { getUiLang, tUI } from '../../../lib/uiLang';

const TranslateControl = ({ text, onUpdate, onSave }) => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const { addLog } = useLog();
    const [isTranslated, setIsTranslated] = useState(false);
    const [loading, setLoading] = useState(false);
    const [originalText, setOriginalText] = useState('');

    const handleTranslate = async (e) => {
        e.stopPropagation();
        e.preventDefault();

        const textToTranslate = text || '';
        if (!textToTranslate && !isTranslated) {
            addLog('No text to translate', 'warning');
            return;
        }

        setLoading(true);
        try {
            if (!isTranslated) {
                setOriginalText(textToTranslate);
                const res = await translateText(textToTranslate, 'en', 'zh');
                if (res.translated_text) {
                    onUpdate(res.translated_text);
                    setIsTranslated(true);
                    addLog('Translated to Chinese', 'info');
                } else {
                    throw new Error('No translation returned');
                }
            } else {
                const res = await translateText(textToTranslate, 'zh', 'en');
                if (res.translated_text) {
                    onUpdate(res.translated_text);
                    if (onSave) onSave(res.translated_text);
                    setIsTranslated(false);
                    addLog('Translated back and saved', 'success');
                } else {
                    if (textToTranslate.trim() === '') {
                        onUpdate('');
                        if (onSave) onSave('');
                        setIsTranslated(false);
                        return;
                    }
                    throw new Error('No translation returned');
                }
            }
        } catch (e2) {
            console.error('Translation failed', e2);
            const msg = e2.response?.data?.detail || e2.message || 'Unknown error';
            addLog(`Translation error: ${msg}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleCancel = (e) => {
        e.stopPropagation();
        onUpdate(originalText);
        setIsTranslated(false);
        addLog('Reverted to original English', 'info');
    };

    if (isTranslated) {
        return (
            <div className="flex items-center gap-1">
                <button
                    onClick={handleTranslate}
                    disabled={loading}
                    className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors bg-indigo-500/80 text-white hover:bg-indigo-500"
                    title={t('翻译回英文并保存', 'Translate back to English & Save')}
                >
                    {loading ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Languages className="w-3 h-3" />}
                    Save (EN)
                </button>
                <button
                    onClick={handleCancel}
                    disabled={loading}
                    className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors bg-white/10 hover:bg-white/20 text-muted-foreground hover:text-white"
                    title={t('取消编辑并恢复原文', 'Cancel edit and revert to original')}
                >
                    <X className="w-3 h-3" />
                </button>
            </div>
        );
    }

    return (
        <button
            onClick={handleTranslate}
            disabled={loading}
            className={`text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors ${isTranslated ? 'bg-indigo-500/80 text-white hover:bg-indigo-500' : 'bg-white/10 hover:bg-white/20 text-muted-foreground hover:text-white'}`}
            title={isTranslated ? t('翻译回英文并保存', 'Translate back to English & Save') : t('翻译为中文以便编辑', 'Translate to Chinese for editing')}
        >
            {loading ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Languages className="w-3 h-3" />}
            {isTranslated ? 'Save (EN)' : 'CN'}
        </button>
    );
};

export default TranslateControl;
