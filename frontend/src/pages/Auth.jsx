
import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { apiLogin, forgotPassword, registerUser, resetPassword } from '../services/api';
import { useStore } from '../lib/store';
import { Lock, Mail, User, AlertCircle } from 'lucide-react';
import { getUiLang, tUI } from '../lib/uiLang';

const Auth = () => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const [mode, setMode] = useState('login');
    const [formData, setFormData] = useState({
        username: '',
        password: '',
        email: '',
        full_name: '',
        reset_token: ''
    });
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();
    const location = useLocation();
    const { refreshSettings } = useStore();

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const urlMode = params.get('mode');
        const token = params.get('token') || '';
        if (urlMode === 'reset') {
            setMode('reset');
            if (token) {
                setFormData((prev) => ({ ...prev, reset_token: token }));
            }
        }
    }, [location.search]);

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setNotice('');
        setLoading(true);

        try {
            if (mode === 'login') {
                // Use the JSON login endpoint
                const response = await apiLogin(formData.username, formData.password);
                localStorage.setItem('token', response.access_token);
                try {
                    await refreshSettings();
                } catch (refreshErr) {
                    console.warn('Refresh settings failed after login, continuing to projects.', refreshErr);
                }
                navigate('/projects', { replace: true });
            } else if (mode === 'register') {
                await registerUser(formData);
                setMode('login');
                setNotice(t('注册成功，请登录。', 'Registration successful! Please login.'));
            } else if (mode === 'forgot') {
                await forgotPassword(formData.email);
                setNotice(t('如果邮箱存在，重置链接已发送。', 'If the email exists, a reset link has been sent.'));
            } else if (mode === 'reset') {
                await resetPassword(formData.reset_token, formData.password);
                setMode('login');
                setFormData((prev) => ({ ...prev, password: '', reset_token: '' }));
                setNotice(t('密码已重置，请登录。', 'Password reset successful. Please sign in.'));
            }
        } catch (err) {
            const detail = err.response?.data?.detail;
            let errorMessage = t('操作失败，请检查输入后重试。', 'Operation failed. Please check your input and try again.');
            
            if (Array.isArray(detail)) {
                errorMessage = detail.map(e => e.msg).join('; ');
            } else if (typeof detail === 'string') {
                errorMessage = detail;
            } else if (typeof detail === 'object') {
                errorMessage = JSON.stringify(detail);
            }
            
            // Ensure error is a string
            if (typeof errorMessage !== 'string') {
                errorMessage = String(errorMessage);
            }
            
            setError(errorMessage);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-muted/20">
            <div className="w-full max-w-md bg-card p-8 rounded-xl shadow-lg border">
                <div className="text-center mb-6">
                    <h1 className="text-2xl font-bold">
                        {mode === 'login' && t('欢迎回来', 'Welcome Back')}
                        {mode === 'register' && t('创建账号', 'Create Account')}
                        {mode === 'forgot' && t('找回密码', 'Forgot Password')}
                        {mode === 'reset' && t('重置密码', 'Reset Password')}
                    </h1>
                    <p className="text-muted-foreground mt-2">
                        {mode === 'login' && t('输入账号信息以访问你的项目。', 'Enter your credentials to access your projects.')}
                        {mode === 'register' && t('开启你的 AI Story 创作之旅。', 'Start your journey with AI Story.')}
                        {mode === 'forgot' && t('输入注册邮箱，我们会发送重置链接。', 'Enter your email and we will send a reset link.')}
                        {mode === 'reset' && t('输入重置令牌与新密码。', 'Enter your reset token and new password.')}
                    </p>
                </div>

                {notice && (
                    <div className="mb-4 p-3 bg-primary/10 text-primary text-sm rounded-md flex items-center gap-2">
                        <span>{notice}</span>
                    </div>
                )}

                {error && (
                    <div className="mb-4 p-3 bg-destructive/10 text-destructive text-sm rounded-md flex items-center gap-2">
                         <AlertCircle className="w-4 h-4" /> 
                         <span>{error}</span>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    {mode === 'register' && (
                        <>
                        <div className="space-y-1">
                            <label className="text-sm font-medium">{t('姓名', 'Full Name')}</label>
                            <div className="relative">
                                <User className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
                                <input 
                                    name="full_name"
                                    className="w-full pl-10 pr-3 py-2 border rounded-md bg-background"
                                    placeholder={t('张三', 'John Doe')}
                                    value={formData.full_name}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>
                        <div className="space-y-1">
                            <label className="text-sm font-medium">{t('邮箱', 'Email')}</label>
                            <div className="relative">
                                <Mail className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
                                <input 
                                    name="email"
                                    type="email"
                                    className="w-full pl-10 pr-3 py-2 border rounded-md bg-background"
                                    placeholder={t('name@example.com', 'john@example.com')}
                                    value={formData.email}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>
                        </>
                    )}

                    {mode === 'forgot' && (
                        <div className="space-y-1">
                            <label className="text-sm font-medium">{t('邮箱', 'Email')}</label>
                            <div className="relative">
                                <Mail className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
                                <input
                                    name="email"
                                    type="email"
                                    className="w-full pl-10 pr-3 py-2 border rounded-md bg-background"
                                    placeholder={t('name@example.com', 'john@example.com')}
                                    value={formData.email}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>
                    )}

                    {(mode === 'login' || mode === 'register') && (
                        <div className="space-y-1">
                            <label className="text-sm font-medium">{t('用户名', 'Username')}</label>
                            <div className="relative">
                                <User className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
                                <input
                                    name="username"
                                    autoComplete="username"
                                    className="w-full pl-10 pr-3 py-2 border rounded-md bg-background"
                                    placeholder={t('用户名', 'username')}
                                    value={formData.username}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>
                    )}

                    {mode === 'reset' && (
                        <div className="space-y-1">
                            <label className="text-sm font-medium">{t('重置令牌', 'Reset Token')}</label>
                            <input
                                name="reset_token"
                                className="w-full px-3 py-2 border rounded-md bg-background"
                                placeholder={t('粘贴邮件中的令牌', 'Paste token from email')}
                                value={formData.reset_token}
                                onChange={handleChange}
                            />
                        </div>
                    )}

                    {(mode === 'login' || mode === 'register' || mode === 'reset') && (
                        <div className="space-y-1">
                            <label className="text-sm font-medium">{t('密码', 'Password')}</label>
                            <div className="relative">
                                <Lock className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
                                <input
                                    name="password"
                                    type="password"
                                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                                    className="w-full pl-10 pr-3 py-2 border rounded-md bg-background"
                                    placeholder="••••••••"
                                    value={formData.password}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>
                    )}

                    <button 
                        disabled={loading}
                        className="w-full py-2 bg-primary text-primary-foreground rounded-md font-medium hover:bg-primary/90 disabled:opacity-50"
                    >
                        {loading && t('处理中...', 'Processing...')}
                        {!loading && mode === 'login' && t('登录', 'Sign In')}
                        {!loading && mode === 'register' && t('注册', 'Sign Up')}
                        {!loading && mode === 'forgot' && t('发送重置链接', 'Send Reset Link')}
                        {!loading && mode === 'reset' && t('重置密码', 'Reset Password')}
                    </button>
                </form>

                <div className="mt-6 text-center text-sm">
                    {mode === 'login' && (
                        <>
                            <button
                                onClick={() => { setMode('forgot'); setError(''); setNotice(''); }}
                                className="text-primary hover:underline font-medium mr-3"
                            >
                                {t('忘记密码？', 'Forgot password?')}
                            </button>
                            <span className="text-muted-foreground">
                                {t('还没有账号？', "Don't have an account?")}
                            </span>
                            <button
                                onClick={() => { setMode('register'); setError(''); setNotice(''); }}
                                className="text-primary hover:underline font-medium ml-1"
                            >
                                {t('去注册', 'Sign up')}
                            </button>
                        </>
                    )}

                    {mode === 'register' && (
                        <>
                            <span className="text-muted-foreground">{t('已有账号？', 'Already have an account?')}</span>
                            <button
                                onClick={() => { setMode('login'); setError(''); setNotice(''); }}
                                className="text-primary hover:underline font-medium ml-1"
                            >
                                {t('去登录', 'Sign in')}
                            </button>
                        </>
                    )}

                    {(mode === 'forgot' || mode === 'reset') && (
                        <button
                            onClick={() => { setMode('login'); setError(''); setNotice(''); }}
                            className="text-primary hover:underline font-medium"
                        >
                            {t('返回登录', 'Back to Sign in')}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Auth;
