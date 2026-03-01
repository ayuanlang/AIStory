export const normalizeEntityToken = (value) => {
    let text = String(value || '')
        .replace(/[（【〔［]/g, '(')
        .replace(/[）】〕］]/g, ')')
        .replace(/[“”"'‘’`]/g, '')
        .replace(/\s+/g, ' ')
        .trim();

    text = text.replace(/^(CHAR|ENV|PROP)\s*:\s*/i, '').trim();

    for (let i = 0; i < 3; i += 1) {
        const next = text
            .replace(/^[\[\{【｛\(\s]+|[\]\}】｝\)\s]+$/g, '')
            .replace(/^@+/, '')
            .trim();
        if (next === text) break;
        text = next;
    }

    return text.toLowerCase();
};
