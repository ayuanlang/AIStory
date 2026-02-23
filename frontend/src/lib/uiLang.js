export const getUiLang = () => {
    if (typeof window === 'undefined') return 'zh';
    return localStorage.getItem('aistory.ui.lang') === 'en' ? 'en' : 'zh';
};

export const tUI = (uiLang, zh, en) => (uiLang === 'en' ? en : zh);
