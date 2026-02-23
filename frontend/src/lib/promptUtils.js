
/**
 * Processes a prompt string by replacing variables.
 * 
 * Rules:
 * 1. [Global Style] -> replaced by episodeInfo['Global Style']
 * 2. Subject token injection inside brackets (supports [Name], [@Name], CHAR:[@Name])
 *    - Keeps original bracket token and appends anchor description: [@Name](anchor)
 *    - Matches entity.name / entity.name_en (case-insensitive, normalized)
 * 
 * @param {string} prompt - The raw prompt with placeholders
 * @param {object} episodeInfo - The episode_info object (e.g. { "Global Style": "..." })
 * @param {Array} entities - List of available entities to match against
 * @returns {string} The processed prompt
 */
export const processPrompt = (prompt, episodeInfo, entities) => {
    if (!prompt) return "";
    let finalPrompt = prompt;

    const normalizeEntityToken = (value) => {
        return String(value || '')
            .replace(/[（【〔［]/g, '(')
            .replace(/[）】〕］]/g, ')')
            .replace(/[“”"'‘’]/g, '')
            .replace(/^[\[\{【｛\(\s]+|[\]\}】｝\)\s]+$/g, '')
            .replace(/^(CHAR|ENV|PROP)\s*:\s*/i, '')
            .replace(/^@+/, '')
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase();
    };

    // 1. Global Style Replacement
    // Check both potential keys: "Global Style" (from JSON) or "Global_Style" (from internal state)
    // The data might be inside `e_global_info` or flattened, depending on how it's passed.
    // We assume the caller passes the object containing the style field.
    
    // Attempt to find style string
    let style = "";
    if (episodeInfo) {
        if (episodeInfo['Global Style']) style = episodeInfo['Global Style'];
        else if (episodeInfo['Global_Style']) style = episodeInfo['Global_Style'];
        // Check nested e_global_info just in case caller passed the wrapper
        else if (episodeInfo.e_global_info) {
             if (episodeInfo.e_global_info['Global Style']) style = episodeInfo.e_global_info['Global Style'];
             else if (episodeInfo.e_global_info['Global_Style']) style = episodeInfo.e_global_info['Global_Style'];
        }
    }

    if (style) {
        // use regex with case insensitive global replacement
        finalPrompt = finalPrompt.replace(/\[Global Style\]/gi, style);
    } else {
        // If no global style defined, we might want to cleanse the tag or keep it?
        // Requirement says "replace", usually implies if value exists. 
        // If it doesn't exist, we'll strip it to avoid leaking "[Global Style]" into image gen?
        // Or keep it. Let's strip it if empty to be safe, or just leave it. 
        // User said: "use ep.info's Global Style to replace". If null, maybe replace with empty string?
        finalPrompt = finalPrompt.replace(/\[Global Style\]/gi, "");
    }

    // 2. Subject Reference Replacement
    // regex to capture content inside []
    finalPrompt = finalPrompt.replace(/\[(.*?)\]/g, (match, p1, offset, source) => {
         // Skip if it was Global Style (though likely handled above, but regex order matters)
         const cleanKey = normalizeEntityToken(p1);
         if (cleanKey === "global style" || cleanKey === "global_style") return "";

         const tail = source.slice(offset + match.length);
         if (/^['’]s\b/i.test(tail)) return match;
         if (/^\s*[\(（]/.test(tail)) return match;
         
         // Match against entities
         // Requirement: "Input chinese or english name can match"
         const safeEntities = Array.isArray(entities) ? entities : [];
         const target = safeEntities.find(e => {
            const cn = normalizeEntityToken(e?.name || '');
            const en = normalizeEntityToken(e?.name_en || '');

            let fallbackEn = '';
            if (!en && e?.description) {
                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                if (enMatch && enMatch[1]) {
                    fallbackEn = normalizeEntityToken(enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0]);
                }
            }

            return cleanKey && (cn === cleanKey || en === cleanKey || fallbackEn === cleanKey);
         });
         
         if (target) {
             const anchor = target.anchor_description || target.description || "";
             return anchor ? `${match}(${anchor})` : match;
         }
         
         // If no match found, keep original text (or strip? usually keep for other tags)
         return match;
    });

    return finalPrompt;
};
