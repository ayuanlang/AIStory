const sample = `我先按角色专用规范收敛输出范围，只处理 \`characters[]\`。接下来会把 Subject Index 的 6 个角色逐条展开。\`\`\`json
{
  "characters": [
    { "subject_no": "S001", "name": "林锐", "name_en": "Lin Rui" }
  ]
}
\`\`\``;

function extractJsonObjectsFromText(text) {
  const objs = [];
  const tryPush = (candidate) => {
    if (!candidate || typeof candidate !== 'string') return;
    const s = candidate.trim();
    if (!s) return;
    try { objs.push(JSON.parse(s)); } catch {}
  };
  const fenceRe = /```(?:json)?\s*([\s\S]*?)```/gi;
  let match;
  while ((match = fenceRe.exec(text)) !== null) tryPush(match[1]);
  if (objs.length === 0) {
    let braceCount = 0, startIndex = -1, inString = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i]; const prev = i > 0 ? text[i - 1] : '';
      if (ch === '"' && prev !== '\\') inString = !inString;
      if (inString) continue;
      if (ch === '{') { if (braceCount === 0) startIndex = i; braceCount++; }
      else if (ch === '}') { braceCount--; if (braceCount === 0 && startIndex !== -1) { tryPush(text.slice(startIndex, i + 1)); startIndex = -1; } }
    }
  }
  return objs;
}

const objs = extractJsonObjectsFromText(sample);
console.log('objs', objs.length, objs[0]?.characters?.length);
