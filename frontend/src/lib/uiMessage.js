let host = null;

export function registerUiMessageHost(nextHost) {
  host = nextHost;
  return () => {
    if (host === nextHost) {
      host = null;
    }
  };
}

export function notifyUiMessage(message, type = 'info', duration = 3000) {
  const text = message == null ? '' : String(message);
  if (host?.notify) {
    host.notify({ message: text, type, duration });
    return;
  }
  console[type === 'error' ? 'error' : 'log'](text);
}

export function confirmUiMessage(message, options = {}) {
  const text = message == null ? '' : String(message);
  if (host?.confirm) {
    return host.confirm({ message: text, ...options });
  }
  const fallback = typeof window !== 'undefined' && typeof window.confirm === 'function'
    ? window.confirm(text)
    : true;
  return Promise.resolve(fallback);
}

export function promptUiMessage(message, options = {}) {
  const text = message == null ? '' : String(message);
  if (host?.prompt) {
    return host.prompt({ message: text, ...options });
  }
  const fallback = typeof window !== 'undefined' && typeof window.prompt === 'function'
    ? window.prompt(text, options?.defaultValue ?? '')
    : null;
  return Promise.resolve(fallback);
}
