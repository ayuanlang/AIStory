
import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { apiLogin, forgotPassword, registerUser, resetPassword, sendEmailVerificationCode, confirmEmailVerificationCode } from '../services/api';
import { useStore } from '../lib/store';
import { Lock, Mail, User, AlertCircle, Sparkles, ArrowRight } from 'lucide-react';
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
        reset_token: '',
        verify_code: '',
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
                setMode('verify');
                setNotice(t('注册成功，请输入邮箱验证码完成校验。', 'Registration successful. Please enter the email verification code.'));
            } else if (mode === 'verify') {
                await confirmEmailVerificationCode(formData.email, formData.verify_code);
                setMode('login');
                setNotice(t('邮箱校验通过，请登录。', 'Email verified successfully. Please sign in.'));
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
        <div className="min-h-screen bg-background">
            <div className="mx-auto flex min-h-screen w-full max-w-6xl items-center justify-center p-4 md:p-8">
                <div className="grid w-full overflow-hidden rounded-2xl border bg-card/60 backdrop-blur md:grid-cols-2">
                    <div className="hidden border-r md:flex md:flex-col relative overflow-hidden">
                        {/* Background Image */}
                        <div 
                            className="absolute inset-0 z-0 bg-cover bg-center transition-transform duration-10000 hover:scale-105"
                            style={{ backgroundImage: "url('https://images.unsplash.com/photo-1534447677768-be436bb09401?q=80&w=2694&auto=format&fit=crop')" }}
                        />
                        {/* Vignette & Gradient Overlay for Movie Poster Feel */}
                        <div className="absolute inset-0 z-10 bg-[radial-gradient(circle_at_center,transparent_0%,rgba(0,0,0,0.8)_100%)]" />
                        <div className="absolute inset-0 z-10 bg-gradient-to-t from-background/95 via-background/40 to-transparent" />
                        
                        {/* Content */}
                        <div className="relative z-20 p-10 flex flex-col h-full justify-between">
                            <div>
                                <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-black/30 px-3 py-1 text-xs text-white backdrop-blur-md">
                                    <Sparkles className="h-3.5 w-3.5" />
                                    AI Storyboard Suite
                                </div>
                                <h2 className="mt-6 text-3xl font-semibold tracking-tight text-white drop-shadow-md">
                                    {t('智能分镜创作，从登录开始。', 'Build cinematic stories, starting here.')}
                                </h2>
                                <p className="mt-3 max-w-md text-sm leading-relaxed text-white/80 drop-shadow">
                                    {t(
                                        '统一管理项目、角色与镜头生成流程，提升稳定性与交付效率。',
                                        'Manage projects, entities, and shot generation in one workspace with reliable workflows.'
                                    )}
                                </p>
                            </div>
                            <div className="space-y-2 rounded-xl border border-white/10 bg-black/40 p-4 text-sm text-white/90 backdrop-blur-md">
                                <p>{t('• 安全访问与权限控制', '• Secure access and permission control')}</p>
                                <p>{t('• 稳定的生成与资产管理', '• Reliable generation and asset management')}</p>
                                <p>{t('• 人工智能全程控制的生产流程', '• AI-driven end-to-end production workflow')}</p>
                            </div>
                        </div>
                    </div>

                    <div className="p-6 sm:p-8 md:p-10">
                        <div className="mx-auto w-full max-w-md">
                            <div className="mb-6 flex items-center justify-between">
                                <div>
                                    <h1 className="text-2xl font-bold">
                        {mode === 'login' && t('欢迎回来', 'Welcome Back')}
                        {mode === 'register' && t('创建账号', 'Create Account')}
                        {mode === 'verify' && t('邮箱校验', 'Email Verification')}
                        {mode === 'forgot' && t('找回密码', 'Forgot Password')}
                        {mode === 'reset' && t('重置密码', 'Reset Password')}
                                    </h1>
                                    <p className="mt-2 text-sm text-muted-foreground">
                        {mode === 'login' && t('输入账号信息以访问你的项目。', 'Enter your credentials to access your projects.')}
                        {mode === 'register' && t('开启你的 AI Story 创作之旅。', 'Start your journey with AI Story.')}
                        {mode === 'verify' && t('输入邮箱收到的 6 位验证码。', 'Enter the 6-digit code sent to your email.')}
                        {mode === 'forgot' && t('输入注册邮箱，我们会发送重置链接。', 'Enter your email and we will send a reset link.')}
                        {mode === 'reset' && t('输入重置令牌与新密码。', 'Enter your reset token and new password.')}
                                    </p>
                                </div>
                            </div>

                            {(mode === 'login' || mode === 'register') && (
                                <div className="mb-6 grid grid-cols-2 rounded-lg border bg-muted/40 p-1">
                                    <button
                                        type="button"
                                        onClick={() => { setMode('login'); setError(''); setNotice(''); }}
                                        className={`rounded-md px-3 py-2 text-sm font-medium transition ${mode === 'login' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                                    >
                                        {t('登录', 'Sign In')}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => { setMode('register'); setError(''); setNotice(''); }}
                                        className={`rounded-md px-3 py-2 text-sm font-medium transition ${mode === 'register' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                                    >
                                        {t('注册', 'Sign Up')}
                                    </button>
                                </div>
                            )}

                {notice && (
                    <div className="mb-4 flex items-center gap-2 rounded-md border border-primary/20 bg-primary/10 p-3 text-sm text-primary">
                        <span>{notice}</span>
                    </div>
                )}

                {error && (
                    <div className="mb-4 flex items-center gap-2 rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
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
                                    className="w-full rounded-md border bg-background py-2 pl-10 pr-3 outline-none ring-offset-background transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
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
                                    className="w-full rounded-md border bg-background py-2 pl-10 pr-3 outline-none ring-offset-background transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
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
                                    className="w-full rounded-md border bg-background py-2 pl-10 pr-3 outline-none ring-offset-background transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                                    placeholder={t('name@example.com', 'john@example.com')}
                                    value={formData.email}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>
                    )}

                    {mode === 'verify' && (
                        <>
                        <div className="space-y-1">
                            <label className="text-sm font-medium">{t('邮箱', 'Email')}</label>
                            <div className="relative">
                                <Mail className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
                                <input
                                    name="email"
                                    type="email"
                                    className="w-full rounded-md border bg-background py-2 pl-10 pr-3 outline-none ring-offset-background transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                                    placeholder={t('name@example.com', 'john@example.com')}
                                    value={formData.email}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>
                        <div className="space-y-1">
                            <label className="text-sm font-medium">{t('验证码', 'Verification Code')}</label>
                            <input
                                name="verify_code"
                                className="w-full rounded-md border bg-background px-3 py-2 outline-none ring-offset-background transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                                placeholder={t('6 位验证码', '6-digit code')}
                                value={formData.verify_code}
                                onChange={handleChange}
                            />
                        </div>
                        <button
                            type="button"
                            onClick={async () => {
                                try {
                                    setError('');
                                    setNotice('');
                                    await sendEmailVerificationCode(formData.email);
                                    setNotice(t('验证码已发送，请查收邮箱。', 'Verification code sent. Please check your email.'));
                                } catch (err) {
                                    const detail = err.response?.data?.detail;
                                    setError(typeof detail === 'string' ? detail : t('发送验证码失败。', 'Failed to send verification code.'));
                                }
                            }}
                            className="inline-flex w-full items-center justify-center gap-2 rounded-md border py-2 font-medium transition hover:bg-muted"
                        >
                            {t('重新发送验证码', 'Resend Verification Code')}
                        </button>
                        </>
                    )}

                    {(mode === 'login' || mode === 'register') && (
                        <div className="space-y-1">
                            <label className="text-sm font-medium">{t('用户名', 'Username')}</label>
                            <div className="relative">
                                <User className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
                                <input
                                    name="username"
                                    autoComplete="username"
                                    className="w-full rounded-md border bg-background py-2 pl-10 pr-3 outline-none ring-offset-background transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
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
                                className="w-full rounded-md border bg-background px-3 py-2 outline-none ring-offset-background transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
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
                                    className="w-full rounded-md border bg-background py-2 pl-10 pr-3 outline-none ring-offset-background transition placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                                    placeholder="••••••••"
                                    value={formData.password}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>
                    )}

                    <button 
                        disabled={loading}
                        className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-primary py-2 font-medium text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
                    >
                        {loading && t('处理中...', 'Processing...')}
                        {!loading && mode === 'login' && t('登录', 'Sign In')}
                        {!loading && mode === 'register' && t('注册', 'Sign Up')}
                        {!loading && mode === 'verify' && t('验证邮箱', 'Verify Email')}
                        {!loading && mode === 'forgot' && t('发送重置链接', 'Send Reset Link')}
                        {!loading && mode === 'reset' && t('重置密码', 'Reset Password')}
                        {!loading && <ArrowRight className="h-4 w-4" />}
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

                    {(mode === 'forgot' || mode === 'reset' || mode === 'verify') && (
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
                </div>
            </div>
        </div>
    );
};

export default Auth;
