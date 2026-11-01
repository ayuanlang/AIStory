import React, { useEffect } from 'react';
import Markdown from 'react-markdown';
import { getUiLang, tUI } from '../lib/uiLang';
import { useLog } from '../context/LogContext';
import { ASSET_BASE_URL, BASE_URL } from '../config';
import { X, Copy } from 'lucide-react';

const MEDIA_PART_TYPES = new Set([
  'image_url', 'input_image', 'image',
  'video_url', 'input_video', 'video',
  'audio_url', 'input_audio', 'audio',
  'file', 'input_file', 'file_url',
]);

function pickUrl(value) {
  if (!value) return '';
  if (typeof value === 'string') return value.trim();
  if (typeof value === 'object') {
    for (const key of ['url', 'file_url', 'image_url', 'video_url', 'audio_url']) {
      const candidate = value[key];
      if (typeof candidate === 'string' && candidate.trim()) return candidate.trim();
    }
  }
  return '';
}

function attachmentRawUrl(part) {
  if (!part || typeof part !== 'object') return '';
  return (
    pickUrl(part.image_url)
    || pickUrl(part.video_url)
    || pickUrl(part.audio_url)
    || pickUrl(part.file_url)
    || pickUrl(part.file)
    || pickUrl(part.source)
    || pickUrl(part.url)
    || ''
  );
}

const MEDIA_FIELD_KEYS = new Set(['image_url', 'video_url', 'audio_url', 'file_url']);

function isMediaHref(href) {
  return /(\.(png|jpe?g|gif|webp|bmp|avif|svg|mp4|webm|mov|m4v|mp3|wav|m4a)(\?|#|$))|(?:qn\.woola\.fun|clouddn\.com|qiniucs\.com|aliyuncs\.com|myqcloud\.com|volces\.com)/i.test(href);
}

function collectAttachmentUrls(value, acc, keyName = '') {
  if (typeof value === 'string') {
    const href = toOpenableUrl(value);
    if (href && /^https?:\/\//i.test(href) && (MEDIA_FIELD_KEYS.has(keyName) || isMediaHref(href))) acc.add(href);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectAttachmentUrls(item, acc, keyName));
    return;
  }
  if (!value || typeof value !== 'object') return;
  const type = String(value.type || '').toLowerCase();
  if (MEDIA_PART_TYPES.has(type)) {
    const href = toOpenableUrl(attachmentRawUrl(value));
    if (href && /^https?:\/\//i.test(href)) acc.add(href);
  }
  Object.entries(value).forEach(([key, item]) => collectAttachmentUrls(item, acc, key));
}

function classifyAttachmentHref(href) {
  const pageOrigin = typeof window !== 'undefined' ? window.location.origin : '';
  try {
    const parsed = new URL(String(href || ''), pageOrigin || undefined);
    return {
      kind: parsed.origin === pageOrigin ? 'local' : 'remote',
      origin: parsed.origin,
      host: parsed.host,
      path: parsed.pathname,
      queryLen: parsed.search.length,
      hrefLen: parsed.href.length,
      hasToken: /(?:^|[?&])token=/.test(parsed.search),
    };
  } catch (error) {
    return {
      kind: 'invalid',
      error: String(error?.message || error),
      hrefLen: String(href || '').length,
    };
  }
}

function writeAttachmentDebug(addLog, stage, detail) {
  const message = `[llm-log-attachment] ${stage} ${JSON.stringify(detail)}`;
  console.info(message);
  if (typeof addLog === 'function') addLog(message, 'info');
}

function LinkifiedPre({ text, className, onLinkClick }) {
  const source = String(text || '');
  const re = /https?:\/\/[^\s"'<>\\]+/g;
  const nodes = [];
  let last = 0;
  let match;
  while ((match = re.exec(source))) {
    if (match.index > last) nodes.push(source.slice(last, match.index));
    const href = match[0].replace(/[),.;]+$/g, '');
    const rest = match[0].slice(href.length);
    nodes.push(
      <a
        key={`${match.index}-${nodes.length}`}
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sky-300 underline"
        onClick={onLinkClick}
      >
        {href}
      </a>
    );
    if (rest) nodes.push(rest);
    last = match.index + match[0].length;
  }
  if (last < source.length) nodes.push(source.slice(last));
  return <pre className={className}>{nodes}</pre>;
}

function toOpenableUrl(raw) {
  let url = String(raw || '').trim();
  if (!url || url.includes('BASE64_STRIPPED')) return '';
  if (/^(?:[a-z0-9.-]+\.)?(?:woola\.fun|clouddn\.com|qiniucs\.com|aliyuncs\.com|myqcloud\.com|volces\.com)\//i.test(url)) {
    url = `https://${url}`;
  }
  if (/^https?:\/\//i.test(url) || url.startsWith('blob:') || url.startsWith('data:')) return url;
  if (url.startsWith('/')) {
    const base = String(
      ASSET_BASE_URL
      || BASE_URL
      || (typeof window !== 'undefined' ? window.location.origin : '')
    ).replace(/\/+$/, '');
    return base ? `${base}${url}` : url;
  }
  return '';
}

class LogBodyBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

export default function LlmLogViewer({ log, onClose }) {
  const uiLang = getUiLang();
  const t = (zh, en) => tUI(uiLang, zh, en);
  const logApi = useLog();
  const addLog = logApi?.addLog;

  useEffect(() => {
    if (!log) return;
    let payloadObj = log.payload_json;
    let responseObj = log.response_json;
    try {
      if (typeof payloadObj === 'string') payloadObj = JSON.parse(payloadObj);
    } catch (error) {
      payloadObj = null;
    }
    try {
      if (typeof responseObj === 'string') responseObj = JSON.parse(responseObj);
    } catch (error) {
      responseObj = null;
    }
    const found = new Set();
    collectAttachmentUrls(payloadObj, found);
    collectAttachmentUrls(responseObj, found);
    writeAttachmentDebug(addLog, 'open', {
      logId: log.id,
      pageOrigin: window.location.origin,
      baseUrl: String(BASE_URL || ''),
      assetBase: String(ASSET_BASE_URL || ''),
      count: found.size,
    });
    found.forEach((href) => {
      writeAttachmentDebug(addLog, 'url', { logId: log.id, href, ...classifyAttachmentHref(href) });
    });
  }, [log, addLog]);

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

  const debugAttachmentClick = (event) => {
    event.stopPropagation();
    const anchor = event.currentTarget;
    const intended = anchor?.getAttribute?.('href') || '';
    const browserHref = anchor?.href || '';
    writeAttachmentDebug(addLog, 'click', {
      logId: log?.id,
      intended,
      browserHref,
      hrefMatches: intended === browserHref,
      defaultPrevented: Boolean(event.defaultPrevented),
      button: event.button,
      target: anchor?.target || '',
      ...classifyAttachmentHref(browserHref || intended),
    });
  };

  const markdownComponents = {
    a: ({ href, children }) => (
      <a href={href || ''} target="_blank" rel="noopener noreferrer" className="break-all [overflow-wrap:anywhere]" onClick={debugAttachmentClick}>{children}</a>
    ),
    img: ({ src, alt }) => {
      const href = toOpenableUrl(src);
      if (!href) return null;
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" className="block max-w-full break-all [overflow-wrap:anywhere] text-sky-300 hover:text-sky-200 hover:underline" onClick={debugAttachmentClick}>
          {alt || href}
        </a>
      );
    },
  };

  const renderAttachment = (part, key) => {
    const raw = attachmentRawUrl(part);
    const href = toOpenableUrl(raw);
    if (!href) {
      return (
        <div key={key} className="mt-2 text-xs text-gray-400 break-all">
          {raw
            ? t(`附件无法打开：${String(raw).slice(0, 180)}`, `Attachment cannot be opened: ${String(raw).slice(0, 180)}`)
            : t('附件没有链接', 'Attachment has no URL')}
        </div>
      );
    }
    return (
      <div key={key} className="mt-2 min-w-0 max-w-full space-y-2">
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          onClick={debugAttachmentClick}
          className="block max-w-full text-xs text-sky-300 hover:text-sky-200 hover:underline break-all [overflow-wrap:anywhere]"
        >
          {href}
        </a>
      </div>
    );
  };

  const renderMessageContent = (content) => {
    if (typeof content === 'string') return <div className="prose prose-invert max-w-full min-w-0 prose-sm break-words"><Markdown components={markdownComponents}>{content}</Markdown></div>;
    if (Array.isArray(content)) {
      return content.map((c, i) => {
        if (!c || typeof c !== 'object') return <div key={i}>{String(c ?? '')}</div>;
        const type = String(c.type || '').toLowerCase();
        if (type === 'text' || type === 'input_text' || type === 'output_text') {
          return <div key={i} className="prose prose-invert max-w-full min-w-0 prose-sm overflow-x-hidden break-words"><Markdown components={markdownComponents}>{typeof c.text === 'string' ? c.text : ''}</Markdown></div>;
        }
        if (MEDIA_PART_TYPES.has(type) || (!type && attachmentRawUrl(c))) {
          return renderAttachment(c, i);
        }
        return <div key={i} className="text-xs break-all">{JSON.stringify(c)}</div>;
      });
    }
    if (content && typeof content === 'object' && (MEDIA_PART_TYPES.has(String(content.type || '').toLowerCase()) || attachmentRawUrl(content))) {
      return renderAttachment(content, 'attachment');
    }
    return <div className="text-xs break-all">{JSON.stringify(content)}</div>;
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
  const attachmentUrls = [];
  {
    const found = new Set();
    collectAttachmentUrls(payload, found);
    collectAttachmentUrls(response, found);
    attachmentUrls.push(...found);
  }
  const contentHasAttachment = (content) => {
    const found = new Set();
    collectAttachmentUrls(content, found);
    return found.size > 0;
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 p-6 rounded-xl w-full max-w-6xl min-w-0 overflow-hidden flex flex-col max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xl font-bold">{t('日志详情', 'Log Details')}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={24} />
          </button>
        </div>

        <div className="text-gray-400 text-[13px] border-b border-gray-700 pb-3 mb-4 flex items-center flex-wrap gap-x-6 gap-y-2 flex-shrink-0">
          <span><strong className="text-gray-200">Model:</strong> {log.model}</span>
          <span><strong className="text-gray-200">{t('运行时间', 'Runtime')}:</strong> {log.latency_ms != null && log.latency_ms !== '' && Number.isFinite(Number(log.latency_ms)) ? t(`${(Number(log.latency_ms) / 1000).toFixed(Number(log.latency_ms) >= 10000 ? 1 : 2)}秒`, `${(Number(log.latency_ms) / 1000).toFixed(Number(log.latency_ms) >= 10000 ? 1 : 2)}s`) : '-'}</span>
          <span><strong className="text-gray-200">{t('扣费金额', 'Charged')}:</strong> {log.charged_amount == null || log.charged_amount === '' ? '-' : t(`${log.charged_amount} 积分`, `${log.charged_amount} credits`)}</span>
          <span><strong className="text-gray-200">Date:</strong> {new Date(log.timestamp || log.created_at).toLocaleString()}</span>
        </div>

        <LogBodyBoundary
          fallback={(
            <LinkifiedPre text={displayPayloadJson || displayResponseJson || t('（空）', '(Empty)')} className="max-w-full overflow-auto whitespace-pre-wrap break-all text-xs text-gray-300" onLinkClick={debugAttachmentClick} />
          )}
        >
        <div className="space-y-4 overflow-y-auto overflow-x-hidden pr-2 custom-scrollbar flex-1 min-w-0 min-h-0">
          {attachmentUrls.length > 0 ? (
            <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-4 space-y-2 min-w-0">
              <div className="text-xs font-bold uppercase tracking-wider text-sky-200">{t('附件', 'Attachments')}</div>
              {attachmentUrls.map((href) => (
                <a
                  key={href}
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={debugAttachmentClick}
                  className="block max-w-full text-xs text-sky-300 hover:text-sky-200 hover:underline break-all [overflow-wrap:anywhere]"
                >
                  {href}
                </a>
              ))}
            </div>
          ) : null}
          {String(log.error_msg || '').trim() ? (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200 whitespace-pre-wrap break-words">
              <div className="text-xs font-bold uppercase tracking-wider text-red-300 mb-2">{t('错误', 'Error')}</div>
              {String(log.error_msg)}
            </div>
          ) : null}
          {messages.length > 0 ? messages.map((m, i) => (
            <details key={i} open={contentHasAttachment(m.content) ? true : undefined} className={`rounded-xl border ${m.role === 'system' ? 'bg-purple-500/10 border-purple-500/20' : m.role === 'user' ? 'bg-blue-500/10 border-blue-500/20' : 'bg-emerald-500/10 border-emerald-500/20'} relative group`}>
              <summary className="flex justify-between items-center p-4 cursor-pointer outline-none select-none list-none [&::-webkit-details-marker]:hidden">
                  <div className="text-xs font-bold uppercase tracking-wider opacity-60 flex items-center space-x-2">
                     <span className="text-gray-500 transition-transform group-open:rotate-90">▶</span>
                     <span>{m.role === 'system' ? t('System 提示词', 'System Prompt') : m.role === 'user' ? t('User 提示词', 'User Prompt') : m.role === 'assistant' ? t('Assistant 助手', 'Assistant') : m.role}</span>
                  </div>
                  <button onClick={(e) => handleCopy(e, m.content)} className="text-gray-500 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity" title="Copy">
                     <Copy size={14} />
                  </button>
              </summary>
              <div className="px-4 pb-4 min-w-0 max-w-full overflow-x-hidden break-words border-t border-white/10 pt-4">
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
               <div className="px-4 pb-4 min-w-0 max-w-full overflow-x-hidden break-words border-t border-white/10 pt-4">
                 <LinkifiedPre text={displayPayloadJson || t('（空）', '(Empty)')} className="bg-black/50 p-3 rounded-xl whitespace-pre-wrap break-all [overflow-wrap:anywhere] border border-white/5 text-xs text-gray-300" onLinkClick={debugAttachmentClick} />
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
              <div className="px-4 pb-4 min-w-0 max-w-full overflow-x-hidden break-words border-t border-white/10 pt-4">
                {typeof completionContent === 'string' && completionContent ? <div className="prose prose-invert max-w-full min-w-0 prose-sm break-words"><Markdown components={markdownComponents}>{completionContent}</Markdown></div> : (
                   <LinkifiedPre text={displayResponseJson} className="bg-black/50 p-3 rounded-xl whitespace-pre-wrap break-all [overflow-wrap:anywhere] border border-white/5 text-xs text-gray-300" onLinkClick={debugAttachmentClick} />
                )}
              </div>
            </details>
          )}
        </div>
        </LogBodyBoundary>
      </div>
    </div>
  );
}