           tryPush(match[1]);
        }

        // If we didn't get anything, do a simple brace-scan for objects.
        if (objs.length === 0) {
            let braceCount = 0;
            let startIndex = -1;
            let inString = false;

            for (let i = 0; i < text.length; i++) {
                const ch = text[i];
                const prev = i > 0 ? text[i - 1] : '';

                if (ch === '"' && prev !== '\\') {
                    inString = !inString;
                }
                if (inString) continue;

                if (ch === '{') {
                    if (braceCount === 0) startIndex = i;
                    braceCount++;
                } else if (ch === '}') {
                    braceCount--;
                    if (braceCount === 0 && startIndex !== -1) {
                        const candidate = text.slice(startIndex, i + 1);
                        tryPush(candidate);
                        startIndex = -1;
                    }
                }
            }
        }

        // De-dupe by JSON string
        const seen = new Set();
        const unique = [];
        for (const o of objs) {
            try {
                const k = JSON.stringify(o);
                if (!seen.has(k)) {
                    seen.add(k);
                    unique.push(o);
                }
            } catch {
                // ignore
            }
        }
        return unique;
    };

    const getAnalysisEntitiesPayloadFromJsonText = (jsonText) => {
        const objects = extractJsonObjectsFromText(jsonText);
        const normalizeKey = (key) => String(key || '').toLowerCase().replace(/[\s_\-]/g, '');

        const pickArrayByAliases = (obj, aliases) => {
            if (!obj || typeof obj !== 'object') return [];
            const aliasSet = new Set((aliases || []).map(normalizeKey));
            for (const [k, v] of Object.entries(obj)) {
                if (!Array.isArray(v)) continue;
                if (aliasSet.has(normalizeKey(k))) return v;
            }
            return [];
        };

        const splitByTypeFromArray = (arr) => {
            const payload = { characters: [], props: [], environments: [], posters: [] };
            for (const item of arr || []) {
                if (!item || typeof item !== 'object') continue;
                if (isDummySubject(item.name) || isDummySubject(item.subject_name_exact) || isDummySubject(item.name_en)) continue;
                const type = normalizeKey(item.type || item.subject_type || item.entity_type || '');
                if (['character', 'characters', 'char', 'role', 'roles', '人物', '角色'].includes(type)) {
                    payload.characters.push(item);
                } else if (['prop', 'props', 'item', 'items', '道具', '物件'].includes(type)) {
                    payload.props.push(item);
                } else if (['environment', 'environments', 'env', 'scene', '场景', '环境'].includes(type)) {
                    payload.environments.push(item);
                } else if (['poster', 'posters', 'cover', 'covers', '海报', '封面'].includes(type)) {
                    payload.posters.push(item);
                }
            }
            return payload;
        };

        const cleanArray = (arr) => (arr || []).filter(item => !isDummySubject(item?.name) && !isDummySubject(item?.name_en) && !isDummySubject(item?.subject_name_exact));

        const normalizePayload = (obj) => {
            if (!obj || typeof obj !== 'object') return null;

            let characters = pickArrayByAliases(obj, ['characters', 'character', 'chars', 'subjects', 'people', 'roles', '人物', '角色']);
            let props = pickArrayByAliases(obj, ['props', 'prop', 'items', '道具', '物件']);
            let environments = pickArrayByAliases(obj, ['environments', 'environment', 'envs', 'env', 'scenes', '场景', '环境']);
            let posters = pickArrayByAliases(obj, ['poste