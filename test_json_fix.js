
const repairJSON = (jsonStr) => {
    try {
        return JSON.parse(jsonStr);
    } catch (e) {
        console.log("JSON.parse failed, attempting repair...");
        // Regex to match "key": value where value is unquoted
        // 1. "([^"]+)" matches key
        // 2. \s*:\s* matches colon
        // 3. ([^\s"{\[][\s\S]*?) matches value starting with non-quote/brace/bracket
        // 4. (?=\s*[,}\]]) lookahead for end of value (comma or brace/bracket)
        let repaired = jsonStr.replace(
            /"([^"]+)"\s*:\s*([^\s"{\[][\s\S]*?)(?=\s*[,}\]])/g, 
            (match, key, value) => {
                const trimmedValue = value.trim();
                console.log(`Found unquoted value for key "${key}":`, trimmedValue);
                if (!trimmedValue) return match;
                
                // Allow valid JSON primitives (numbers, bools, null)
                if (/^(true|false|null)$/.test(trimmedValue)) return match;
                if (!isNaN(parseFloat(trimmedValue)) && isFinite(trimmedValue)) return match;
                
                // Quote the string, escaping quotes and newlines
                const safeValue = trimmedValue
                    .replace(/\\/g, '\\\\') // Escape backslashes first
                    .replace(/"/g, '\\"')
                    .replace(/\n/g, '\\n')
                    .replace(/\r/g, '');
                return `"${key}": "${safeValue}"`;
            }
        );
        
        // Fix trailing commas
        repaired = repaired.replace(/,\s*([}\]])/g, '$1');
        
        console.log("Repaired JSON length:", repaired.length);
        // console.log("Repaired snippet:", repaired.substring(0, 500)); 

        return JSON.parse(repaired);
    }
};


const problematicInput = `{
  "environments": [
    {
      "name": "废弃展区内部（近景角度）",
      "description_cn": 用于拍摄Isabella与Kong近距离互动的镜头，如亲吻、对峙特写。",
      "visual_dependencies": []
    }
  ]
}`;

try {
    const result = repairJSON(problematicInput);
    console.log("Success!", JSON.stringify(result, null, 2));
} catch (e) {
    console.error("Failed completely:", e.message);
}
