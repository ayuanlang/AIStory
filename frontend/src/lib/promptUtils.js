
import { entityTokenMatchesName, normalizeEntityToken } from './entityToken';

const isSubjectEntity = (entity) => {
    const typeValue = String(entity?.type || '').trim().toLowerCase();
    return typeValue === 'subject' || typeValue === 'character' || typeValue === 'char';
};

const buildSubjectRefIndexMap = (sourceText = '', entities = []) => {
    const indexMap = new Map();
    const refs = [];
    const matches = String(sourceText || '').match(/[\[【](.*?)[\]】]/g) || [];

    for (const token of matches) {
        const cleanKey = normalizeEntityToken(token);
        const entity = (Array.isArray(entities) ? entities : []).find((candidate) => entityTokenMatchesName(candidate, cleanKey));
        if (!entity || !isSubjectEntity(entity)) continue;

        const imageUrl = String(entity?.image_url || '').trim();
        if (!imageUrl) continue;
        if (!refs.includes(imageUrl)) refs.push(imageUrl);
        indexMap.set(String(entity?.id || ''), refs.indexOf(imageUrl) + 1);
    }

    return indexMap;
};

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
    const safeEntities = Array.isArray(entities) ? entities : [];
    const injectedEntities = new Set();
    const subjectRefIndexMap = buildSubjectRefIndexMap(finalPrompt, safeEntities);

    finalPrompt = finalPrompt.replace(/\[(.*?)\]/g, (match, p1, offset, source) => {
         // Skip if it was Global Style (though likely handled above, but regex order matters)
         const cleanKey = normalizeEntityToken(p1);
         if (cleanKey === "global style" || cleanKey === "global_style") return "";

         const tail = source.slice(offset + match.length);
         if (/^['’]s\b/i.test(tail)) return match;
         if (/^\s*[\(（]/.test(tail)) return match;
         
         // Match against entities
         // Requirement: "Input chinese or english name can match"
         const target = safeEntities.find((entity) => cleanKey && entityTokenMatchesName(entity, cleanKey));
         
         if (target) {
             const anchor = target.anchor_description || target.description || "";
             const entityId = String(target?.id || '');
             const refNo = isSubjectEntity(target) ? subjectRefIndexMap.get(entityId) : null;

             if (injectedEntities.has(cleanKey)) {
                 return refNo ? `${match}(ref_image_url: #${refNo})` : match;
             }

             injectedEntities.add(cleanKey);
             const anchorWithRef = [anchor, refNo ? `ref_image_url: #${refNo}` : ''].filter(Boolean).join(' | ');
             return anchorWithRef ? `${match}(${anchorWithRef})` : match;
         }
         
         // If no match found, keep original text (or strip? usually keep for other tags)
         return match;
    });

    return finalPrompt;
};
