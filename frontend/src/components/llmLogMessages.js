function tryParseJson(value) {
  if (!value || typeof value !== 'string') return null;
  try {
    return JSON.parse(value);
  } catch (error) {
    return null;
  }
}

function systemToText(value) {
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value)) {
    return value.map((part) => {
      if (typeof part === 'string') return part;
      if (part && typeof part.text === 'string') return part.text;
      return '';
    }).filter(Boolean).join('\n\n').trim();
  }
  if (value && typeof value === 'object') {
    return systemToText(value.parts || value.content || '');
  }
  return '';
}

function prependSystem(messages, systemValue) {
  const text = systemToText(systemValue);
  if (!text) return messages;
  const hasSystem = messages.some((row) => {
    const role = String(row?.role || '').toLowerCase();
    return role === 'system' || role === 'developer';
  });
  if (hasSystem) return messages;
  return [{ role: 'system', content: text }, ...messages];
}

function fromMessages(messages, systemValue) {
  if (!Array.isArray(messages) || messages.length === 0) return null;
  return prependSystem(messages, systemValue);
}

function fromResponses(input, instructions) {
  const rows = [];
  if (typeof input === 'string' && input.trim()) {
    rows.push({ role: 'user', content: input });
  } else if (Array.isArray(input)) {
    for (const item of input) {
      if (!item || typeof item !== 'object') continue;
      const role = String(item.role || 'user').toLowerCase() || 'user';
      rows.push({ role, content: item.content });
    }
  }
  if (!rows.length) return null;
  return prependSystem(rows, instructions);
}

function geminiRole(role) {
  const value = String(role || 'user').toLowerCase();
  if (value === 'model') return 'assistant';
  if (value === 'system' || value === 'developer' || value === 'user' || value === 'assistant') return value;
  return 'user';
}

function mediaPart(mime, url) {
  const kind = String(mime || '').toLowerCase();
  if (kind.startsWith('video/')) return { type: 'video_url', video_url: { url } };
  if (kind.startsWith('audio/')) return { type: 'audio_url', audio_url: { url } };
  if (kind.startsWith('image/') || !kind) return { type: 'image_url', image_url: { url } };
  return { type: 'file', file_url: url };
}

function convertGeminiPart(part) {
  if (typeof part === 'string') {
    return part ? { type: 'text', text: part } : null;
  }
  if (!part || typeof part !== 'object') return null;
  if (typeof part.text === 'string') {
    return part.text ? { type: 'text', text: part.text } : null;
  }
  const fileData = part.file_data || part.fileData;
  if (fileData && typeof fileData === 'object') {
    const url = String(fileData.file_uri || fileData.fileUri || '').trim();
    return url ? mediaPart(fileData.mime_type || fileData.mimeType, url) : null;
  }
  const inline = part.inline_data || part.inlineData;
  if (inline && typeof inline === 'object') {
    const mime = String(inline.mime_type || inline.mimeType || 'application/octet-stream');
    const data = String(inline.data || '');
    if (!data || data.includes('BASE64_STRIPPED')) return { type: 'text', text: `[inline ${mime}]` };
    return mediaPart(mime, `data:${mime};base64,${data}`);
  }
  return { type: 'text', text: JSON.stringify(part) };
}

function messageContent(parts) {
  if (parts.length === 1 && parts[0].type === 'text') return parts[0].text;
  return parts;
}

function fromGemini(obj) {
  if (!obj || !Array.isArray(obj.contents) || obj.contents.length === 0) return null;
  const rows = [];
  const instruction = systemToText(obj.systemInstruction || obj.system_instruction);
  if (instruction) rows.push({ role: 'system', content: instruction });
  for (const item of obj.contents) {
    if (!item || typeof item !== 'object') continue;
    const role = geminiRole(item.role);
    const rawParts = Array.isArray(item.parts) ? item.parts : (item.parts ? [item.parts] : []);
    let bucket = [];
    const flush = () => {
      if (!bucket.length) return;
      rows.push({ role, content: messageContent(bucket) });
      bucket = [];
    };
    for (const part of rawParts) {
      const converted = convertGeminiPart(part);
      if (!converted) continue;
      if (converted.type === 'text' && bucket.some((entry) => entry.type === 'text')) flush();
      bucket.push(converted);
    }
    flush();
  }
  return rows.length ? rows : null;
}

export function extractLogMessages(obj, depth = 0) {
  if (!obj || depth > 4) return null;
  if (Array.isArray(obj)) return obj.length ? obj : null;
  if (typeof obj !== 'object') return null;

  const direct = fromMessages(obj.messages, obj.system)
    || fromResponses(obj.input, obj.instructions)
    || fromGemini(obj);
  if (direct) return direct;

  const nestedPayload = typeof obj.payload === 'string' ? tryParseJson(obj.payload) : obj.payload;
  const fromPayload = extractLogMessages(nestedPayload, depth + 1);
  if (fromPayload) return fromPayload;
  if (obj.request && obj.request !== obj.payload) {
    return extractLogMessages(obj.request, depth + 1);
  }
  return null;
}
