
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiLogin, registerUser } from '../services/api';
import { useStore } from '../lib/store';
import { Lock, Mail, User, AlertCircle } from 'lucide-react';
import { getUiLang, tUI } from '../lib/uiLang';

const Auth = () => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const [isLogin, setIsLogin] = useState(true);
    const [formData, setFormData] = useState({
        username: '',
        password: '',
        email: '',
        full_name: ''
    });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();
    const { refreshSettings } = useStore();

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (isLogin) {
                // Use the JSON login endpoint
                const response = await apiLogin(formData.username, formData.password);
                localStorage.setItem('token', response.access_token);
                try {
                    await refreshSettings();
                } catch (refreshErr) {
                    console.warn('Refresh settings failed after login, continuing to projects.', refreshErr);
                }
                navigate('/projects', { replace: true });
            } else {
                const response = await registerUser(formData);
                setIsLogin(true); // Switch to login after registration
                setError(t('注册成功，请登录。', 'Registration successful! Please login.'));
            }
        } catch (err) {
            const detail = err.response?.data?.detail;
            let errorMessage = t('认证失败，请检查账号信息。', 'Authentication failed. Please check your credentials.');
            
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
                    <h1 className="text-2xl font-bold">{isLogin ? t('欢迎回来', 'Welcome Back') : t('创建账号', 'Create Account')}</h1>
                    <p className="text-muted-foreground mt-2">
                        {isLogin ? t('输入账号信息以访问你的项目。', 'Enter your credentials to access your projects.') : t('开启你的 AI Story 创作之旅。', 'Start your journey with AI Story.')}
                    </p>
                </div>

                {error && (
                    <div className="mb-4 p-3 bg-destructive/10 text-destructive text-sm rounded-md flex items-center gap-2">
                         <AlertCircle className="w-4 h-4" /> 
                         <span>{error}</span>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    {!isLogin && (
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

                    <div className="space-y-1">
                        <label className="text-sm font-medium">{t('密码', 'Password')}</label>
                        <div className="relative">
                            <Lock className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
                            <input 
                                name="password"
                                type="password"
                                autoComplete={isLogin ? "current-password" : "new-password"}
                                className="w-full pl-10 pr-3 py-2 border rounded-md bg-background"
                                placeholder="••••••••"
                                value={formData.password}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    <button 
                        disabled={loading}
                        className="w-full py-2 bg-primary text-primary-foreground rounded-md font-medium hover:bg-primary/90 disabled:opacity-50"
                    >
                        {loading ? t('处理中...', 'Processing...') : (isLogin ? t('登录', 'Sign In') : t('注册', 'Sign Up'))}
                    </button>
                </form>

                <div className="mt-6 text-center text-sm">
                    <span className="text-muted-foreground">
                        {isLogin ? t('还没有账号？', "Don't have an account?") : t('已有账号？', 'Already have an account?')}
                    </span>
                    <button 
                        onClick={() => setIsLogin(!isLogin)}
                        className="text-primary hover:underline font-medium"
                    >
                        {isLogin ? t('去注册', 'Sign up') : t('去登录', 'Sign in')}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default Auth;
