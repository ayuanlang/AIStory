
import React, { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { LogProvider } from './context/LogContext';
import LogPanel from './components/LogPanel';
import GlobalMessageHost from './components/GlobalMessageHost';
import GlobalAIAssistant from './components/GlobalAIAssistant';
import ErrorBoundary from './components/ErrorBoundary';
import { getUiLang, tUI, UI_LANG_EVENT, UI_LANG_KEY } from './lib/uiLang';
import { getMaintenanceStatus } from './services/api';

const Home = lazy(() => import('./pages/Home'));
const ProjectList = lazy(() => import('./pages/ProjectList'));
const Editor = lazy(() => import('./pages/Editor'));
const AdvancedAnalysisResult = lazy(() => import('./pages/AdvancedAnalysisResult'));
const Auth = lazy(() => import('./pages/Auth'));
const UserAdmin = lazy(() => import('./pages/UserAdmin'));
const SystemLogs = lazy(() => import('./pages/SystemLogs'));

// Helper component to protect routes that require authentication
const PrivateRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/auth" replace />;
};

// Helper component to redirect authenticated users away from public routes (like Login or Home)
const PublicRoute = ({ children, bypassRedirect = false }) => {
  if (bypassRedirect) return children;
  const token = localStorage.getItem('token');
  return token ? <Navigate to="/projects" replace /> : children;
};

function App() {
  const [appUiLang, setAppUiLang] = useState(getUiLang());
  const [aiAssistantInstanceKey, setAiAssistantInstanceKey] = useState(0);
  const [maintenanceStatus, setMaintenanceStatus] = useState({ is_active: false, ends_at: null, message: '' });
  const loadingText = tUI(appUiLang, '加载中...', 'Loading...');

  const decodeJwtPayload = (token) => {
    try {
      const parts = String(token || '').split('.');
      if (parts.length < 2) return null;
      const base64Url = parts[1].replace(/-/g, '+').replace(/_/g, '/');
      const padded = base64Url.padEnd(Math.ceil(base64Url.length / 4) * 4, '=');
      return JSON.parse(atob(padded));
    } catch {
      return null;
    }
  };

  useEffect(() => {
    const sync = () => {
      const next = getUiLang();
      setAppUiLang(prev => (prev === next ? prev : next));
    };

    const onStorage = (e) => {
      if (e.key === UI_LANG_KEY) sync();
    };

    window.addEventListener('storage', onStorage);
    window.addEventListener(UI_LANG_EVENT, sync);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener(UI_LANG_EVENT, sync);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const checkMaintenance = async () => {
      try {
        const status = await getMaintenanceStatus();
        let bypassBySuperuser = false;

        if (status?.is_active) {
          const token = localStorage.getItem('token');
          if (token) {
            const payload = decodeJwtPayload(token);
            bypassBySuperuser = !!(payload?.is_superuser || payload?.superuser);
          }
        }

        if (!cancelled) {
          setMaintenanceStatus({
            ...status,
            is_active: Boolean(status?.is_active) && !bypassBySuperuser,
          });
        }
      } catch {
        if (!cancelled) {
          setMaintenanceStatus({ is_active: false, ends_at: null, message: '' });
        }
      }
    };

    checkMaintenance();
    const timer = window.setInterval(checkMaintenance, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const currentPath = typeof window !== 'undefined' ? window.location.pathname : '/';
  const allowAuthDuringMaintenance = currentPath === '/auth';

  if (maintenanceStatus?.is_active && !allowAuthDuringMaintenance) {
    return (
      <div className="min-h-screen bg-[#09090b] text-white flex items-center justify-center p-6">
        <div className="w-full max-w-xl rounded-xl border border-yellow-500/40 bg-yellow-500/10 p-8 text-center">
          <h1 className="text-2xl font-bold text-yellow-300">{tUI(appUiLang, '系统维护中', 'System Under Maintenance')}</h1>
          <p className="mt-3 text-sm text-yellow-100">
            {String(maintenanceStatus?.message || tUI(appUiLang, '系统正在维护', 'System is under maintenance'))}
          </p>
          <p className="mt-2 text-sm text-yellow-200">
            {maintenanceStatus?.ends_at
              ? tUI(appUiLang, `预计 ${maintenanceStatus.ends_at} 结束`, `Estimated to end at ${maintenanceStatus.ends_at}`)
              : tUI(appUiLang, '预计结束时间待定', 'Estimated end time is to be announced')}
          </p>
          <div className="mt-6">
            <button
              type="button"
              onClick={() => {
                if (typeof window !== 'undefined') {
                  localStorage.removeItem('token');
                  window.location.href = '/auth';
                }
              }}
              className="px-4 py-2 rounded-lg bg-white/90 text-black font-semibold hover:bg-white"
            >
              {tUI(appUiLang, '系统管理员登录', 'System Admin Login')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const RechargeListener = () => {
    const navigate = useNavigate();
    useEffect(() => {
      const fn = () => {
        // Bring user to the top-up context automatically (single unified entry in Settings)
        try {
          sessionStorage.setItem('OPEN_RECHARGE_MODAL', '1');
        } catch {
          // ignore
        }
        navigate('/settings?tab=billing', { replace: false });
      };
      window.addEventListener('SHOW_RECHARGE_MODAL', fn);
      return () => window.removeEventListener('SHOW_RECHARGE_MODAL', fn);
    }, [navigate]);
    return null;
  };

  return (
    <LogProvider>
      <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <div key={`app-ui-lang-${appUiLang}`} className="min-h-screen bg-background text-foreground font-sans antialiased relative">
          <RechargeListener />
          <Suspense fallback={<div className="p-4 text-sm text-muted-foreground">{loadingText}</div>}>
            <Routes>
              <Route path="/" element={<PublicRoute><Home /></PublicRoute>} />
              <Route path="/auth" element={<PublicRoute bypassRedirect={allowAuthDuringMaintenance}><Auth /></PublicRoute>} />
              <Route path="/projects" element={<PrivateRoute><ProjectList /></PrivateRoute>} />
              <Route path="/settings" element={<PrivateRoute><ProjectList initialTab="settings" /></PrivateRoute>} />
              <Route path="/editor/:id" element={<PrivateRoute><Editor /></PrivateRoute>} />
              <Route path="/editor/:id/analysis" element={<PrivateRoute><AdvancedAnalysisResult /></PrivateRoute>} />
              <Route path="/admin/users" element={<PrivateRoute><UserAdmin /></PrivateRoute>} />
              <Route path="/admin/logs" element={<PrivateRoute><SystemLogs /></PrivateRoute>} />
            </Routes>
          </Suspense>
          <ErrorBoundary
            fallbackRender={({ resetErrorBoundary }) => (
              <div className="fixed right-4 bottom-4 z-[121] rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-xs text-red-200 shadow-lg backdrop-blur-sm">
                <div>{tUI(appUiLang, 'AI 助手发生异常', 'AI assistant crashed')}</div>
                <button
                  type="button"
                  className="mt-1 inline-flex items-center rounded border border-red-300/50 px-2 py-0.5 text-[11px] hover:bg-red-500/20"
                  onClick={() => {
                    setAiAssistantInstanceKey((prev) => prev + 1);
                    resetErrorBoundary();
                  }}
                >
                  {tUI(appUiLang, '重试', 'Retry')}
                </button>
              </div>
            )}
          >
            <GlobalAIAssistant key={`global-ai-${aiAssistantInstanceKey}`} />
          </ErrorBoundary>
          <GlobalMessageHost />
          <LogPanel />
        </div>
      </Router>
    </LogProvider>
  );
}

export default App;
