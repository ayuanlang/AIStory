export const UI_LANG_KEY = 'aistory.ui.lang';
export const UI_LANG_EVENT = 'aistory.ui.lang.change';

export const getUiLang = () => {
    if (typeof window === 'undefined') return 'zh';
    return localStorage.getItem(UI_LANG_KEY) === 'en' ? 'en' : 'zh';
};

export const setUiLang = (lang) => {
    if (typeof window === 'undefined') return;
    const next = lang === 'en' ? 'en' : 'zh';
    localStorage.setItem(UI_LANG_KEY, next);
    window.dispatchEvent(new CustomEvent(UI_LANG_EVENT, { detail: next }));
};

export const tUI = (uiLang, zh, en) => (uiLang === 'en' ? en : zh);
