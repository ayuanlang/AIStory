import React from 'react';
import Markdown from 'react-markdown';
import { getUiLang, tUI } from '../lib/uiLang';
import { X, Copy } from 'lucide-react';

export default function LlmLogViewer({ log, onClose }) {
  const uiLang = getUiLang();
  const t = (zh, en) => tUI(uiLang, zh, en);

  if (!log) return null;

  const tryParseJson = (str) => {
    if (!str) return null;
    if (typeof str === 'object') return str;
    try { return JSON.parse(str); } catch (e) { return null; }
  };

  const payload = tryParseJson(log.payload_json);
  let response = tryParseJson(log.response_json);

  let messages = [];
  let completionContent = '';

  const normalizeResponsesInput = (input, instructions) => {
    const rows = [];
    if (Array.isArray(input)) {
      for (const item of input) {
        if (!item || typeof item !== 'object') continue;
        const role = String(item.role || 'user').toLowerCase() || 'user';
        rows.push({ role, content: item.content });
      }
    }
    const instr = typeof instructions === 'string' ? instructions.trim() : '';
    const hasSystem = rows.some((r) => r.role === 'system' || r.role === 'developer');
    // Legacy KIE payloads put system text only in top-level instructions.
    if (instr && !hasSystem) {
      rows.unshift({ role: 'system', content: instr });
    }
    return rows.length ? rows : null;
  };

  const getMsgs = (obj) => {
    if (!obj) return null;
    if (Array.isArray(obj)) return obj;
    if (obj.messages && Array.isArray(obj.messages)) return obj.messages;
    if (obj.payload && obj.payload.messages && Array.isArray(obj.payload.messages)) return obj.payload.messages;
    if (obj.request && obj.request.messages && Array.isArray(obj.request.messages)) return obj.request.messages;
    // KIE / OpenAI Responses API: prompts live in payload.input (+ optional instructions).
    const responsesMsgs =
      normalizeResponsesInput(obj.input, obj.instructions)
      || normalizeResponsesInput(obj.payload?.input, obj.payload?.instructions)
      || normalizeResponsesInput(obj.request?.input, obj.request?.instructions);
    if (responsesMsgs) return responsesMsgs;
    return null;
  };

  messages = getMsgs(payload) || getMsgs(response) || [];

  // extract response text
  let responseObj = response;
  if (responseObj && responseObj.response) {
      // sometimes nested
      responseObj = responseObj.response;
  }

  if (responseObj && Array.isArray(responseObj) && responseObj.length > 0 && responseObj[0].choices) {
    completionContent = responseObj.map(r => {
        if (r.choices && r.choices[0] && r.choices[0].delta && r.choices[0].delta.content) {
            return r.choices[0].delta.content;
        }
        return '';
    }).join('');
  } else if (responseObj && responseObj.choices && responseObj.choices[0] && responseObj.choices[0].message) {
    completionContent = responseObj.choices[0].message.content;
  } else if (responseObj && responseObj.content) {
    completionContent = responseObj.content;
  } else if (responseObj && responseObj.choices && responseObj.choices[0] && responseObj.choices[0].text) {
    completionContent = responseObj.choices[0].text;
  } else if (responseObj && responseObj.partial_content !== undefined) {
    completionContent = responseObj.partial_content;
  }

  const renderMessageContent = (content) => {
    if (typeof content === 'string') return <div className="prose prose-invert max-w-none prose-sm"><Markdown>{content}</Markdown></div>;
    if (Array.isArray(content)) {
      return content.map((c, i) => {
        if (c.type === 'text' || c.type === 'input_text' || c.type === 'output_text') {
          return <div key={i} className="prose prose-invert max-w-none prose-sm overflow-x-auto break-words"><Markdown>{c.text || ''}</Markdown></div>;
        }
        if (c.type === 'image_url' || c.type === 'input_image') {
          const url = typeof c.image_url === 'string' ? c.image_url : (c.image_url?.url || '');
          return <div key={i} className="mt-2 opacity-50 text-xs truncate">[Image URL: {url ? url.substring(0, 80) : ''}...]</div>;
        }
        return <div key={i}>{JSON.stringify(c)}</div>;
      });
    }
    return <div>{JSON.stringify(content)}</div>;
  };

  const handleCopy = async (e, text) => {
    e.preventDefault();
    e.stopPropagation();
    if (!text) {
        alert(t('无内容可复制', 'No content to copy'));
        return;
    }
    const safeText = typeof text === 'string' ? text : JSON.stringify(text, null, 2);
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(safeText);
        alert(t('复制成功', 'Copied successfully'));
      } else {
        const textArea = document.createElement("textarea");
        textArea.value = safeText;
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        alert(t('复制成功', 'Copied successfully'));
      }
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  const displayPayloadJson = typeof log.payload_json === 'object' ? JSON.stringify(log.payload_json, null, 2) : (log.payload_json || '');
  const displayResponseJson = typeof log.response_json === 'object' ? JSON.stringify(log.response_json, null, 2) : (log.response_json || '');

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 p-6 rounded-xl w-full max-w-6xl flex flex-col max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xl font-bold">{t('日志详情', 'Log Details')}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={24} />
          </button>
        </div>

        <div className="text-gray-400 text-[13px] border-b border-gray-700 pb-3 mb-4 flex items-center space-x-6 flex-shrink-0">
          <span><strong className="text-gray-200">Model:</strong> {log.model}</span>
          <span><strong className="text-gray-200">Latency:</strong> {log.latency_ms} ms</span>
          <span><strong className="text-gray-200">Date:</strong> {new Date(log.timestamp || log.created_at).toLocaleString()}</span>
        </div>

        <div className="space-y-4 overflow-y-auto pr-2 custom-scrollbar flex-1">
          {messages.length > 0 ? messages.map((m, i) => (
            <details key={i} className={`rounded-xl border ${m.role === 'system' ? 'bg-purple-500/10 border-purple-500/20' : m.role === 'user' ? 'bg-blue-500/10 border-blue-500/20' : 'bg-emerald-500/10 border-emerald-500/20'} relative group`}>
              <summary className="flex justify-between items-center p-4 cursor-pointer outline-none select-none list-none [&::-webkit-details-marker]:hidden">
                  <div className="text-xs font-bold uppercase tracking-wider opacity-60 flex items-center space-x-2">
                     <span className="text-gray-500 transition-transform group-open:rotate-90">▶</span>
                     <span>{m.role === 'system' ? t('System 提示词', 'System Prompt') : m.role === 'user' ? t('User 提示词', 'User Prompt') : m.role === 'assistant' ? t('Assistant 助手', 'Assistant') : m.role}</span>
                  </div>
                  <button onClick={(e) => handleCopy(e, m.content)} className="text-gray-500 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity" title="Copy">
                     <Copy size={14} />
                  </button>
              </summary>
              <div className="px-4 pb-4 overflow-x-auto break-words border-t border-white/10 pt-4">
                {renderMessageContent(m.content)}
              </div>
            </details>
          )) : (
             <details className="rounded-xl border bg-gray-500/10 border-gray-500/20 relative group">
               <summary className="flex justify-between items-center p-4 cursor-pointer outline-none select-none list-none [&::-webkit-details-marker]:hidden">
                 <div className="text-xs font-bold uppercase tracking-wider opacity-60 flex items-center space-x-2">
                   <span className="text-gray-500 transition-transform group-open:rotate-90">▶</span>
                   <span>Payload JSON</span>
                 </div>
                 <button onClick={(e) => handleCopy(e, displayPayloadJson)} className="text-gray-500 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity">
                    <Copy size={14}/>
                 </button>
               </summary>
               <div className="px-4 pb-4 overflow-x-auto break-words border-t border-white/10 pt-4">
                 <pre className="bg-black/50 p-3 rounded-xl whitespace-pre-wrap break-words overflow-x-auto border border-white/5 text-xs text-gray-300">{displayPayloadJson || t('（空）', '(Empty)')}</pre>
               </div>
             </details>
          )}

          {(completionContent || (log.tag !== 'LLM_REQUEST' && displayResponseJson)) && (
            <details className="rounded-xl border bg-gray-500/10 border-gray-500/20 relative group">
              <summary className="flex justify-between items-center p-4 cursor-pointer outline-none select-none list-none [&::-webkit-details-marker]:hidden">
                  <div className="text-xs font-bold uppercase tracking-wider opacity-60 flex items-center space-x-2">
                    <span className="text-gray-500 transition-transform group-open:rotate-90">▶</span>
                    <span>{t('模型回复结果', 'Model Response')}</span>
                  </div>
                  <button onClick={(e) => handleCopy(e, completionContent || displayResponseJson)} className="text-gray-500 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity" title="Copy">
                       <Copy size={14} />
                  </button>
              </summary>
              <div className="px-4 pb-4 overflow-x-auto break-words border-t border-white/10 pt-4">
                {completionContent ? <div className="prose prose-invert max-w-none prose-sm"><Markdown>{completionContent}</Markdown></div> : (
                   <pre className="bg-black/50 p-3 rounded-xl whitespace-pre-wrap break-words overflow-x-auto border border-white/5 text-xs text-gray-300">{displayResponseJson}</pre>
                )}
              </div>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}