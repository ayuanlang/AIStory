
import React, { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { LogProvider } from './context/LogContext';
import LogPanel from './components/LogPanel';
import GlobalMessageHost from './components/GlobalMessageHost';
import GlobalAIAssistant from './components/GlobalAIAssistant';
import ErrorBoundary from './components/ErrorBoundary';
import { getUiLang, tUI, UI_LANG_EVENT, UI_LANG_KEY } from './lib/uiLang';

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
const PublicRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? <Navigate to="/projects" replace /> : children;
};

function App() {
  const [appUiLang, setAppUiLang] = useState(getUiLang());
  const [aiAssistantInstanceKey, setAiAssistantInstanceKey] = useState(0);
  const loadingText = tUI(appUiLang, '加载中...', 'Loading...');

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
              <Route path="/auth" element={<PublicRoute><Auth /></PublicRoute>} />
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
