import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, AlertTriangle, Info, XCircle } from 'lucide-react';
import { registerUiMessageHost } from '../lib/uiMessage';

const TYPE_STYLE = {
  success: {
    icon: CheckCircle2,
    className: 'bg-emerald-500/90 border-emerald-300 text-white',
  },
  error: {
    icon: XCircle,
    className: 'bg-red-500/90 border-red-300 text-white',
  },
  warning: {
    icon: AlertTriangle,
    className: 'bg-amber-500/90 border-amber-300 text-black',
  },
  info: {
    icon: Info,
    className: 'bg-zinc-800/95 border-zinc-500 text-zinc-100',
  },
};

export default function GlobalMessageHost() {
  const [toasts, setToasts] = useState([]);
  const [confirmState, setConfirmState] = useState(null);
  const [promptState, setPromptState] = useState(null);
  const timersRef = useRef(new Map());

  const addToast = ({ message, type = 'info', duration = 3000 }) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const toast = { id, message, type };
    setToasts((prev) => [...prev.slice(-3), toast]);

    const timeout = Math.max(1200, Number(duration) || 3000);
    const timer = window.setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== id));
      timersRef.current.delete(id);
    }, timeout);
    timersRef.current.set(id, timer);
  };

  useEffect(() => {
    const unregister = registerUiMessageHost({
      notify: addToast,
      confirm: ({
        message,
        title = 'Please Confirm',
        confirmText = 'Confirm',
        cancelText = 'Cancel',
      }) => new Promise((resolve) => {
        setConfirmState({ message, title, confirmText, cancelText, resolve });
      }),
      prompt: ({
        message,
        title = 'Input Required',
        confirmText = 'Confirm',
        cancelText = 'Cancel',
        defaultValue = '',
        placeholder = '',
      }) => new Promise((resolve) => {
        setPromptState({ message, title, confirmText, cancelText, defaultValue, placeholder, value: defaultValue, resolve });
      }),
    });

    const originalAlert = window.alert;
    window.alert = (message) => {
      const text = message == null ? '' : String(message);
      const lower = text.toLowerCase();
      const type = lower.includes('fail') || lower.includes('error') ? 'error' : 'info';
      addToast({ message: text, type, duration: 3200 });
    };

    return () => {
      unregister();
      window.alert = originalAlert;
      timersRef.current.forEach((timer) => window.clearTimeout(timer));
      timersRef.current.clear();
    };
  }, []);

  const toastItems = useMemo(() => toasts, [toasts]);

  const resolveConfirm = (value) => {
    setConfirmState((prev) => {
      if (prev?.resolve) prev.resolve(value);
      return null;
    });
  };

  const resolvePrompt = (value) => {
    setPromptState((prev) => {
      if (prev?.resolve) prev.resolve(value);
      return null;
    });
  };

  return (
    <>
      <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[120] flex w-[min(92vw,520px)] flex-col gap-2 pointer-events-none">
        {toastItems.map((toast) => {
          const style = TYPE_STYLE[toast.type] || TYPE_STYLE.info;
          const Icon = style.icon;
          return (
            <div
              key={toast.id}
              onClick={() => setToasts((prev) => prev.filter((item) => item.id !== toast.id))}
              className={`pointer-events-auto cursor-pointer rounded-xl border px-4 py-3 shadow-lg backdrop-blur ${style.className}`}
              role="status"
            >
              <div className="flex items-start gap-2">
                <Icon size={18} className="mt-0.5 shrink-0" />
                <p className="text-sm leading-5">{toast.message}</p>
              </div>
            </div>
          );
        })}
      </div>

      {confirmState && (
        <div
          className="fixed inset-0 z-[130] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => resolveConfirm(false)}
        >
          <div
            className="w-full max-w-md rounded-xl border border-white/15 bg-zinc-900 p-5 text-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold mb-2">{confirmState.title}</h3>
            <p className="text-sm text-zinc-300 mb-5 whitespace-pre-wrap">{confirmState.message}</p>
            <div className="flex justify-end gap-2">
              <button
                className="px-3 py-2 rounded-md border border-white/20 text-zinc-200 hover:bg-white/10"
                onClick={() => resolveConfirm(false)}
              >
                {confirmState.cancelText}
              </button>
              <button
                className="px-3 py-2 rounded-md bg-indigo-600 text-white hover:bg-indigo-500"
                onClick={() => resolveConfirm(true)}
              >
                {confirmState.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}

      {promptState && (
        <div
          className="fixed inset-0 z-[130] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => resolvePrompt(null)}
        >
          <div
            className="w-full max-w-md rounded-xl border border-white/15 bg-zinc-900 p-5 text-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold mb-2">{promptState.title}</h3>
            <p className="text-sm text-zinc-300 mb-4 whitespace-pre-wrap">{promptState.message}</p>
            <input
              autoFocus
              value={promptState.value}
              placeholder={promptState.placeholder}
              onChange={(e) => setPromptState((prev) => ({ ...prev, value: e.target.value }))}
              onKeyDown={(e) => {
                if (e.key === 'Enter') resolvePrompt(promptState.value);
                if (e.key === 'Escape') resolvePrompt(null);
              }}
              className="w-full px-3 py-2 rounded-md bg-zinc-800 border border-white/15 text-white outline-none focus:border-indigo-500"
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                className="px-3 py-2 rounded-md border border-white/20 text-zinc-200 hover:bg-white/10"
                onClick={() => resolvePrompt(null)}
              >
                {promptState.cancelText}
              </button>
              <button
                className="px-3 py-2 rounded-md bg-indigo-600 text-white hover:bg-indigo-500"
                onClick={() => resolvePrompt(promptState.value)}
              >
                {promptState.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
