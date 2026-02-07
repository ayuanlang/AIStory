
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Home from './pages/Home';
import ProjectList from './pages/ProjectList';
import Editor from './pages/Editor';
import Settings from './pages/Settings';
import Auth from './pages/Auth';
import UserAdmin from './pages/UserAdmin';
import SystemLogs from './pages/SystemLogs';
import { LogProvider } from './context/LogContext';
import LogPanel from './components/LogPanel';

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
  return (
    <LogProvider>
      <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <div className="min-h-screen bg-background text-foreground font-sans antialiased relative">
          <Routes>
            <Route path="/" element={<PublicRoute><Home /></PublicRoute>} />
            <Route path="/auth" element={<PublicRoute><Auth /></PublicRoute>} />
            <Route path="/projects" element={<PrivateRoute><ProjectList /></PrivateRoute>} />
            <Route path="/settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
            <Route path="/editor/:id" element={<PrivateRoute><Editor /></PrivateRoute>} />
            <Route path="/admin/users" element={<PrivateRoute><UserAdmin /></PrivateRoute>} />
            <Route path="/admin/logs" element={<PrivateRoute><SystemLogs /></PrivateRoute>} />
          </Routes>
          <LogPanel />
        </div>
      </Router>
    </LogProvider>
  );
}

export default App;
