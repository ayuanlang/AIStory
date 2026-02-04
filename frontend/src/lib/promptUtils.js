
/**
 * Processes a prompt string by replacing variables.
 * 
 * Rules:
 * 1. [Global Style] -> replaced by episodeInfo['Global Style']
 * 2. [Subject Name] -> replaced by "${Subject Name} ${anchor_description}"
 *    - Matches entity.name (case-insensitive)
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
    finalPrompt = finalPrompt.replace(/\[(.*?)\]/g, (match, p1) => {
         // Skip if it was Global Style (though likely handled above, but regex order matters)
         if (p1.toLowerCase() === "global style") return "";
         
         // Match against entities
         // Requirement: "Input chinese or english name can match"
         // Since we only have `name` field, we match `name`. 
         // If `anchor_description` contains the english name, we can't easily parse it out to match against.
         // We assume `name` is the primary identifier.
         const target = entities.find(e => e.name.toLowerCase() === p1.toLowerCase());
         
         if (target) {
             // Requirement: "subject's name + anchor_description"
             const anchor = target.anchor_description || "";
             return `${target.name} ${anchor}`;
         }
         
         // If no match found, keep original text (or strip? usually keep for other tags)
         return match;
    });

    return finalPrompt;
};
