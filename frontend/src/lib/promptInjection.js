const START = '\u5f00\u59cb';
const END = '\u7ed3\u675f';

export const PROMPT_INJECTION_DETECTED = 'PROMPT_INJECTION_DETECTED';
export const PROMPT_LEAK_DETECTED = 'PROMPT_LEAK_DETECTED';

const INJECTION_PATTERNS = [
    { kind: 'injection_fence_start', pattern: new RegExp(`\\[[^\\n\\[\\]]{1,48}${START}\\]`) },
    { kind: 'injection_fence_end', pattern: new RegExp(`\\[[^\\n\\[\\]]{1,48}${END}\\]`) },
    { kind: 'chatml_token', pattern: /<\|(?:im_start|im_end|system|assistant|user|endoftext)\|>/i },
    { kind: 'llama_sys', pattern: /<<\s*\/?SYS\s*>>/i },
    { kind: 'llama_inst', pattern: /\[\/?INST\]/i },
    { kind: 'xml_system', pattern: /<\/?system(?:\s[^>]*)?>/i },
    { kind: 'ignore_prev', pattern: /\bignore\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?)\b/i },
    { kind: 'disregard_prev', pattern: /\bdisregard\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?|rules?)\b/i },
    { kind: 'jailbreak', pattern: /\b(?:jailbreak|dan\s+mode)\b/i },
    { kind: 'override_system_prompt', pattern: /\b(?:override|replace|reset)\s+(?:the\s+)?system\s+prompt\b/i },
    { kind: 'cn_ignore_instr', pattern: /忽略(?:以上|之前|前面|先前)(?:的)?(?:所有)?(?:系统)?(?:指令|提示词|系统提示|规则)/ },
    { kind: 'cn_override_prompt', pattern: /(?:覆盖|改写|替换)(?:你的|原有)?(?:系统)?提示词/ },
    { kind: 'cn_new_role', pattern: /你的新(?:系统)?(?:角色|提示词|指令)是/ },
    { kind: 'cn_from_now', pattern: /从现在起忽略/ },
    { kind: 'prompt_leak_watermark', pattern: /\[AIS-WM:[A-Z0-9]+:[A-Z0-9]+\]|\[(?:NULL_INK_SEAL|VOID_PROMPT_LINT|INK_SINK_MARKER)\]/ },
];

export function findPromptInjectionRisks(text) {
    const source = String(text || '');
    if (!source.trim()) return [];
    const hits = [];
    const seen = new Set();
    for (const item of INJECTION_PATTERNS) {
        const match = source.match(item.pattern);
        if (!match) continue;
        const snippet = String(match[0] || '').replace(/\s+/g, ' ').trim().slice(0, 80);
        const key = `${item.kind}:${snippet}`;
        if (seen.has(key)) continue;
        seen.add(key);
        hits.push({ kind: item.kind, snippet });
    }
    return hits;
}

export function summarizePromptInjectionHits(matches) {
    return (Array.isArray(matches) ? matches : [])
        .map((item) => String(item?.snippet || '').trim())
        .filter(Boolean)
        .slice(0, 3)
        .map((snippet) => `「${snippet.slice(0, 40)}」`)
        .join('、');
}

export function isPromptInjectionRiskError(error) {
    const code = String(error?.code || error?.response?.data?.detail?.code || '').trim();
    if (code === PROMPT_INJECTION_DETECTED || code === PROMPT_LEAK_DETECTED) return true;
    const blob = [
        error?.message,
        error?.response?.data?.detail,
        error?.response?.data?.detail?.message,
        error?.response?.data?.detail?.code,
        typeof error?.response?.data?.detail === 'object'
            ? JSON.stringify(error.response.data.detail)
            : '',
    ].map((item) => String(item || '')).join(' ');
    return /PROMPT_INJECTION_DETECTED|PROMPT_LEAK_DETECTED/i.test(blob)
        || /提示词注入|提示词泄露/.test(blob);
}

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
