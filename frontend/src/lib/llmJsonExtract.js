const ENTITY_JSON_KEY_RE = /"(?:characters|props|environments|covers|posters)"\s*:\s*[\[{]/i;

const REASONING_PREFIX_LINE_RE = /^\s*(?:i will|let me|let's|analysis|reasoning|thought process|\u5206\u6790|\u601d\u8def|\u63a8\u7406|\u4e0b\u9762|\u6211\u5c06|\u6211\u8ba4\u4e3a|\u63a5\u4e0b\u6765|\u6211\u5148|\u6211\u4f1a|\u73b0\u5728|\u9996\u5148)\b/i;

export const stripRedactedThinkingBlocks = (text) => (
    String(text || '').replace(/<think>[\s\S]*?<\/redacted_thinking>/gi, '').trim()
);

export const extractBalancedJsonSlice = (source, startIndex) => {
    const text = String(source || '');
    const start = Number(startIndex);
    if (!text || start < 0 || start >= text.length || text[start] !== '{') return '';

    let depth = 0;
    let inString = false;
    let escape = false;

    for (let i = start; i < text.length; i += 1) {
        const ch = text[i];
        if (inString) {
            if (escape) {
                escape = false;
                continue;
            }
            if (ch === '\\') {
                escape = true;
                continue;
            }
            if (ch === '"') inString = false;
            continue;
        }

        if (ch === '"') {
            inString = true;
            continue;
        }
        if (ch === '{') depth += 1;
        if (ch === '}') {
            depth -= 1;
            if (depth === 0) return text.slice(start, i + 1);
        }
    }

    return '';
};

export const findSubjectsJsonObjectStart = (text) => {
    const raw = String(text || '');
    const match = ENTITY_JSON_KEY_RE.exec(raw);
    if (!match) return -1;
    return raw.lastIndexOf('{', match.index);
};

export const stripLeadingReasoningLines = (text) => {
    const lines = String(text || '').split('\n');
    while (lines.length > 0) {
        const line = String(lines[0] || '').trim();
        if (!line) {
            lines.shift();
            continue;
        }
        if (line.startsWith('{') || line.startsWith('[') || line.startsWith('```') || ENTITY_JSON_KEY_RE.test(line)) {
            break;
        }
        if (REASONING_PREFIX_LINE_RE.test(line)) {
            lines.shift();
            continue;
        }
        break;
    }
    return lines.join('\n').trim();
};

export const collectLlmJsonTextCandidates = (inputText) => {
    const candidates = [];
    const seen = new Set();
    const pushCandidate = (value) => {
        const candidate = String(value || '').trim();
        if (!candidate || seen.has(candidate)) return;
        seen.add(candidate);
        candidates.push(candidate);
    };

    let text = stripRedactedThinkingBlocks(inputText);
    if (!text) return candidates;

    const closedFenceRe = /```(?:json)?\s*([\s\S]*?)```/gi;
    let match;
    while ((match = closedFenceRe.exec(text)) !== null) {
        pushCandidate(match[1]);
    }

    const openFenceRe = /```(?:json)?\s*([\s\S]*)$/i;
    const openFenceMatch = openFenceRe.exec(text);
    if (openFenceMatch) {
        pushCandidate(openFenceMatch[1]);
    }

    const trimmed = text.trim();
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        pushCandidate(trimmed);
    }

    const objectStart = findSubjectsJsonObjectStart(text);
    if (objectStart >= 0) {
        pushCandidate(extractBalancedJsonSlice(text, objectStart));
    }

    const withoutReasoning = stripLeadingReasoningLines(text);
    if (withoutReasoning && withoutReasoning !== text) {
        if (withoutReasoning.startsWith('{') || withoutReasoning.startsWith('[')) {
            pushCandidate(withoutReasoning);
        }
        const cleanedStart = findSubjectsJsonObjectStart(withoutReasoning);
        if (cleanedStart >= 0) {
            pushCandidate(extractBalancedJsonSlice(withoutReasoning, cleanedStart));
        }
    }

    return candidates.filter(Boolean);
};

export const sanitizeLlmTextForJsonImport = (inputText) => {
    const candidates = collectLlmJsonTextCandidates(inputText);
    if (candidates.length > 0) return candidates[0];

    const stripped = stripLeadingReasoningLines(stripRedactedThinkingBlocks(inputText));
    const objectStart = findSubjectsJsonObjectStart(stripped);
    if (objectStart >= 0) {
        const slice = extractBalancedJsonSlice(stripped, objectStart);
        if (slice) return slice;
    }

    return stripped;
};
