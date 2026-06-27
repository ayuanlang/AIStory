const START = '\u5f00\u59cb';
const END = '\u7ed3\u675f';

export function wrapInjectionSection(label, content) {
    const body = String(content || '').trim();
    if (!body) return '';
    return `[${label}${START}]\n${body}\n[${label}${END}]`;
}

export function unwrapInjectionSection(text, label) {
    const source = String(text || '');
    const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const pattern = new RegExp(`\\[${escaped}${START}\\]\\s*([\\s\\S]*?)\\s*\\[${escaped}${END}\\]`);
    const match = source.match(pattern);
    return match ? String(match[1] || '').trim() : '';
}

export function stripInjectionSection(text, label) {
    const source = String(text || '');
    const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const pattern = new RegExp(`\\[${escaped}${START}\\][\\s\\S]*?\\[${escaped}${END}\\]\\s*`, 'g');
    return source.replace(pattern, '').trim();
}
