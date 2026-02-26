
import React, { useEffect, useState } from 'react';
import { api, fetchProjects, createProject, getSettings, updateSetting, getSettingDefaults, deleteSetting, deleteProject, recordSystemLogAction, fetchProjectShares, createProjectShare, deleteProjectShare } from '../services/api';
import { BASE_URL } from '../config';
import Editor from './Editor';
import SettingsPage from './Settings';
import AssetsLibrary from '../components/AssetsLibrary';
import { 
    Plus, 
    Folder, 
    Layout, 
    Settings, 
    Image, 
    LogOut, 
    Search,
    User,
    Cpu,
    MessageSquare,
    Save,
    RotateCcw,
    ArrowLeft,
    Trash2,
    Edit2,
    CheckCircle,
    Video,
    Mic,
    Palette,
    Monitor,
    Activity,
    Shield,
    Share2,
    X,
    Loader2
} from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { confirmUiMessage } from '../lib/uiMessage';
import { getUiLang, tUI } from '../lib/uiLang';

const cinematicImages = [
    "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500&q=80", // Movie theater
    "https://images.unsplash.com/photo-1485846234645-a62644f84728?w=500&q=80", // Film camera
    "https://images.unsplash.com/photo-1542204165-65bf26472b9b?w=500&q=80", // Film strip
    "https://images.unsplash.com/photo-1626814026160-2237a95fc5a0?w=500&q=80", // Matrix code
    "https://images.unsplash.com/photo-1440404653325-ab127d49abc1?w=500&q=80", // Clapperboard
    "https://images.unsplash.com/photo-1598899134739-24c46f58b8c0?w=500&q=80", // Movie set
    "https://images.unsplash.com/photo-1517602302552-471fe67acf66?w=500&q=80", // Vibes
];

const getAvatarUrl = (url) => {
    if (!url) return '';
    if (url.startsWith('http') || url.startsWith('blob:') || url.startsWith('data:')) return url;
    if (url.startsWith('/')) {
        const base = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;
        return `${base}${url}`;
    }
    return url;
};

const USER_PROFILE_UPDATED_EVENT = 'aistory.user.profile.updated';

const sortProjectsNewestFirst = (items = []) => {
    const safeList = Array.isArray(items) ? [...items] : [];
    return safeList.sort((a, b) => {
        const aTs = Date.parse(a?.created_at || '') || 0;
        const bTs = Date.parse(b?.created_at || '') || 0;
        if (bTs !== aTs) return bTs - aTs;
        return (Number(b?.id) || 0) - (Number(a?.id) || 0);
    });
};

const THEMES = {
    default: {
        name: {
            zh: "电影暗夜",
            en: "Cinematic Dark",
        },
        description: {
            zh: "深色高对比，聚焦创作内容。",
            en: "Deep blacks and high contrast for focus.",
        },
        colors: {
            "--background": "224 71% 4%",
            "--card": "224 71% 4%",
            "--primary": "210 40% 98%",
            "--secondary": "222.2 47.4% 11.2%",
            "--muted": "223 47% 11%",
            "--border": "216 34% 17%"
        }
    },
    midnight: {
        name: {
            zh: "午夜蓝",
            en: "Midnight Blue",
        },
        description: {
            zh: "专业感深蓝色调。",
            en: "Professional deep blue tones.",
        },
        colors: {
            "--background": "222 47% 11%",
            "--card": "223 47% 13%",
            "--primary": "210 40% 98%",
            "--secondary": "217 33% 17%",
            "--muted": "217 33% 15%",
            "--border": "217 33% 20%"
        }
    },
    slate: {
        name: {
            zh: "钛灰",
            en: "Titanium Slate",
        },
        description: {
            zh: "中性工业灰风格。",
            en: "Neutral, industrial grey tones.",
        },
        colors: {
            "--background": "210 14% 12%",
            "--card": "210 14% 14%",
            "--primary": "210 40% 98%",
            "--secondary": "210 10% 20%",
            "--muted": "210 10% 18%",
            "--border": "210 10% 22%"
        }
    },
    nebula: {
        name: {
            zh: "星云紫",
            en: "Cosmic Nebula",
        },
        description: {
            zh: "紫色深空氛围感。",
            en: "Atmospheric purple and deep space vibes.",
        },
            colors: {
            "--background": "260 40% 8%",
            "--card": "260 40% 10%",
            "--primary": "280 70% 85%",
            "--secondary": "260 30% 18%",
            "--muted": "260 30% 14%",
            "--border": "260 30% 18%"
        }
    }
};

const ProjectList = ({ initialTab = 'projects' }) => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const location = useLocation();
    const [projects, setProjects] = useState([]);
    const [isCreating, setIsCreating] = useState(false);
    const [newTitle, setNewTitle] = useState('');
    const [activeTab, setActiveTab] = useState(initialTab);
    const [selectedProjectId, setSelectedProjectId] = useState(null);
    const [currentUser, setCurrentUser] = useState(null); // Simple user state to check permissions if we had endpoint
    const navigate = useNavigate();

    // Theme Logic - Moved to Parent for persistence on reload
    const [currentTheme, setCurrentTheme] = useState('default');
    const [toast, setToast] = useState(null);
    const [shareModalProject, setShareModalProject] = useState(null);
    const [projectShares, setProjectShares] = useState([]);
    const [projectShareCounts, setProjectShareCounts] = useState({});
    const [shareTargetUser, setShareTargetUser] = useState('');
    const [shareLoading, setShareLoading] = useState(false);
    const [shareSubmitting, setShareSubmitting] = useState(false);
    
    useEffect(() => {
        // Fetch User Info to check admin status
        const fetchMe = async () => {
             try {
                const res = await api.get('/users/me');
                if (res.data) {
                    setCurrentUser(res.data);
                }
             } catch(e) {
                 console.error("Failed to fetch user info", e);
             }
        };
        const handleProfileUpdated = (event) => {
            const updated = event?.detail;
            if (updated && typeof updated === 'object') {
                setCurrentUser(updated);
                return;
            }
            fetchMe();
        };

        fetchMe();
        window.addEventListener(USER_PROFILE_UPDATED_EVENT, handleProfileUpdated);
        return () => {
            window.removeEventListener(USER_PROFILE_UPDATED_EVENT, handleProfileUpdated);
        };
    }, []);

    useEffect(() => {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme && THEMES[savedTheme]) {
             handleThemeChange(savedTheme, false);
        }
    }, []);

    useEffect(() => {
        if (initialTab === 'projects' || initialTab === 'assets' || initialTab === 'settings') {
            setActiveTab(initialTab);
            setSelectedProjectId(null);
        }
    }, [initialTab]);

    useEffect(() => {
        if (location.pathname === '/settings') {
            setActiveTab('settings');
            setSelectedProjectId(null);
        } else if (location.pathname === '/projects' && initialTab === 'projects') {
            setActiveTab('projects');
        }
    }, [location.pathname, initialTab]);

    const handleThemeChange = (key, showToast = true) => {
        setCurrentTheme(key);
        const theme = THEMES[key];
        const root = document.documentElement;
        Object.entries(theme.colors).forEach(([property, value]) => {
            root.style.setProperty(property, value);
        });
        localStorage.setItem('theme', key);
        if (showToast) {
            setToast({ type: 'success', message: t(`${theme.name.zh} 已启用`, `${theme.name.en} Activated`) });
            setTimeout(() => setToast(null), 2000);
        }
    };
    
    useEffect(() => {
        if (activeTab === 'projects') {
            loadProjects();
        }
    }, [activeTab]);

    const loadProjects = async () => {
        try {
            const data = await fetchProjects();
            const sorted = sortProjectsNewestFirst(data);
            setProjects(sorted);

            const ownerProjects = (Array.isArray(sorted) ? sorted : []).filter((item) => {
                if (typeof item?.is_owner === 'boolean') return item.is_owner;
                return Number(item?.owner_id) === Number(currentUser?.id);
            });

            const countEntries = await Promise.all(
                ownerProjects.map(async (item) => {
                    try {
                        const shares = await fetchProjectShares(item.id);
                        return [item.id, Array.isArray(shares) ? shares.length : 0];
                    } catch {
                        return [item.id, 0];
                    }
                })
            );

            const nextCounts = {};
            countEntries.forEach(([projectId, count]) => {
                nextCounts[projectId] = count;
            });
            setProjectShareCounts(nextCounts);
        } catch (error) {
            console.error("Failed to load projects", error);
        }
    };

    const handleCreate = async () => {
        if (!newTitle) return;
        await createProject({ title: newTitle });
        setNewTitle('');
        setIsCreating(false);
        loadProjects();
    };

    const handleLogout = () => {
        void recordSystemLogAction({
            action: 'MENU_CLICK',
            menu_key: 'project_list.sign_out',
            menu_label: 'Sign Out',
            page: `${location.pathname}${location.search}${location.hash}`,
        });
        localStorage.removeItem('token');
        navigate('/');
        void recordSystemLogAction({
            action: 'MENU_CLICK_RESULT',
            menu_key: 'project_list.sign_out',
            menu_label: 'Sign Out',
            page: `${location.pathname}${location.search}${location.hash}`,
            result: 'success',
        });
    };

    const trackMenuAction = (menuKey, menuLabel, actionFn) => {
        const page = `${location.pathname}${location.search}${location.hash}`;
        void recordSystemLogAction({
            action: 'MENU_CLICK',
            menu_key: menuKey,
            menu_label: menuLabel,
            page,
        });

        try {
            const actionResult = actionFn?.();
            if (actionResult && typeof actionResult.then === 'function') {
                actionResult
                    .then(() => {
                        void recordSystemLogAction({
                            action: 'MENU_CLICK_RESULT',
                            menu_key: menuKey,
                            menu_label: menuLabel,
                            page,
                            result: 'success',
                        });
                    })
                    .catch((error) => {
                        void recordSystemLogAction({
                            action: 'MENU_CLICK_RESULT',
                            menu_key: menuKey,
                            menu_label: menuLabel,
                            page,
                            result: 'failed',
                            details: error?.message || 'unknown error',
                        });
                    });
                return;
            }

            void recordSystemLogAction({
                action: 'MENU_CLICK_RESULT',
                menu_key: menuKey,
                menu_label: menuLabel,
                page,
                result: 'success',
            });
        } catch (error) {
            void recordSystemLogAction({
                action: 'MENU_CLICK_RESULT',
                menu_key: menuKey,
                menu_label: menuLabel,
                page,
                result: 'failed',
                details: error?.message || 'unknown error',
            });
            throw error;
        }
    };

    const handleDeleteProject = async (e, projectId) => {
        e.stopPropagation(); // Prevent opening the project
        if (!await confirmUiMessage(t('确定要删除这个项目吗？', 'Are you sure you want to delete this project?'))) return;
        
        try {
            await deleteProject(projectId);
            setToast({ type: 'success', message: t('项目删除成功', 'Project deleted successfully') });
            setTimeout(() => setToast(null), 3000);
            loadProjects(); // Refresh list
        } catch (error) {
            console.error("Failed to delete project", error);
            setToast({ type: 'error', message: t('项目删除失败', 'Failed to delete project') });
            setTimeout(() => setToast(null), 3000);
        }
    };

    const isProjectOwner = (project) => {
        if (!project) return false;
        if (typeof project.is_owner === 'boolean') return project.is_owner;
        return Number(project.owner_id) === Number(currentUser?.id);
    };

    const getProjectShareCountText = (project) => {
        if (!project || !isProjectOwner(project)) return t('共享给你', 'Shared with you');
        const count = Number(projectShareCounts?.[project.id] || 0);
        return t(`已共享给 ${count} 人`, `Shared with ${count} user${count === 1 ? '' : 's'}`);
    };

    const handleOpenShareModal = async (event, project) => {
        event.stopPropagation();
        if (!isProjectOwner(project)) return;
        setShareModalProject(project);
        setShareTargetUser('');
        setShareLoading(true);
        try {
            const shares = await fetchProjectShares(project.id);
            setProjectShares(Array.isArray(shares) ? shares : []);
        } catch (error) {
            console.error('Failed to load project shares', error);
            setProjectShares([]);
            setToast({ type: 'error', message: t('加载共享列表失败', 'Failed to load share list') });
            setTimeout(() => setToast(null), 3000);
        } finally {
            setShareLoading(false);
        }
    };

    const handleCreateShare = async () => {
        if (!shareModalProject) return;
        const target = String(shareTargetUser || '').trim();
        if (!target) return;

        setShareSubmitting(true);
        try {
            await createProjectShare(shareModalProject.id, target);
            const shares = await fetchProjectShares(shareModalProject.id);
            setProjectShares(Array.isArray(shares) ? shares : []);
            setShareTargetUser('');
            setToast({ type: 'success', message: t('共享成功', 'Project shared successfully') });
            setTimeout(() => setToast(null), 2500);
        } catch (error) {
            console.error('Failed to create project share', error);
            setToast({ type: 'error', message: error?.response?.data?.detail || t('共享失败', 'Failed to share project') });
            setTimeout(() => setToast(null), 3000);
        } finally {
            setShareSubmitting(false);
        }
    };

    const handleDeleteShare = async (sharedUserId) => {
        if (!shareModalProject) return;
        try {
            await deleteProjectShare(shareModalProject.id, sharedUserId);
            setProjectShares((prev) => prev.filter((item) => Number(item.user_id) !== Number(sharedUserId)));
        } catch (error) {
            console.error('Failed to delete share', error);
            setToast({ type: 'error', message: t('取消共享失败', 'Failed to revoke share') });
            setTimeout(() => setToast(null), 3000);
        }
    };

    const SidebarItem = ({ id, icon: Icon, label, disabled }) => (
        <button 
            onClick={() => {
                if (disabled) return;
                trackMenuAction(`project_list.sidebar.${id}`, label, () => {
                    setActiveTab(id);
                    setSelectedProjectId(null); // Return to list view when switching tabs
                });
            }}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                activeTab === id && !selectedProjectId
                ? 'bg-primary text-primary-foreground' 
                : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
            } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
            <Icon className="w-5 h-5" />
            {label}
        </button>
    );

    // If a project is selected, show the full-screen Editor immediately
    if (selectedProjectId) {
        return <Editor projectId={selectedProjectId} onClose={() => setSelectedProjectId(null)} />;
    }

    return (
        <div className="flex h-screen bg-background text-foreground font-sans overflow-hidden">
             {toast && (
                <div className={`fixed bottom-8 right-8 px-6 py-3 rounded-lg shadow-xl text-white z-50 animate-in fade-in slide-in-from-bottom-4 bg-green-600`}>
                    {toast.message}
                </div>
            )}
            {/* Sidebar */}
            <aside className="w-64 border-r bg-card/30 flex flex-col p-6">
                <div className="flex items-center gap-2 mb-10 px-2">
                    <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                        <Layout className="w-5 h-5 text-primary-foreground" />
                    </div>
                    <span className="text-xl font-bold tracking-tight">AI Story</span>
                </div>

                <div className="space-y-2 flex-1">
                    <SidebarItem id="projects" icon={Folder} label={t('我的项目', 'My Projects')} />
                    <SidebarItem id="assets" icon={Image} label={t('素材库', 'Assets Library')} />
                    
                    {currentUser?.is_superuser && (
                        <>
                            <button 
                                onClick={() => trackMenuAction('project_list.admin.system_logs', t('系统日志', 'System Logs'), () => navigate('/admin/logs'))}
                                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors text-muted-foreground hover:bg-secondary/50 hover:text-foreground`}
                            >
                                <Activity className="w-5 h-5" />
                                {t('系统日志', 'System Logs')}
                            </button>
                            <button 
                                onClick={() => trackMenuAction('project_list.admin.user_admin', t('管理面板', 'Admin Panel'), () => navigate('/admin/users'))}
                                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors text-muted-foreground hover:bg-secondary/50 hover:text-foreground`}
                            >
                                <Shield className="w-5 h-5 text-red-500" />
                                {t('管理面板', 'Admin Panel')}
                            </button>
                        </>
                    )}
                    <button
                        onClick={() => {
                            trackMenuAction('project_list.sidebar.settings', t('设置', 'Settings'), () => {
                                setActiveTab('settings');
                                setSelectedProjectId(null);
                                const returnTo = encodeURIComponent(`${location.pathname}${location.search}${location.hash}`);
                                navigate(`/settings?return_to=${returnTo}`);
                            });
                        }}
                        className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                    >
                        <Settings className="w-5 h-5" />
                        {t('设置', 'Settings')}
                    </button>
                </div>

                <div className="mt-auto border-t pt-6">
                    <div className="flex items-center gap-3 px-2 mb-4">
                        <div className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center">
                            {currentUser?.avatar_url ? (
                                <img
                                    src={getAvatarUrl(currentUser.avatar_url)}
                                    alt={currentUser?.full_name || currentUser?.username || 'avatar'}
                                    className="w-10 h-10 rounded-full object-cover"
                                />
                            ) : (
                                <User className="w-5 h-5 text-muted-foreground" />
                            )}
                        </div>
                        <div className="flex-1 overflow-hidden">
                            <p className="text-sm font-medium truncate">{currentUser?.full_name || currentUser?.username || t('访客用户', 'Guest User')}</p>
                            <p className="text-xs text-muted-foreground truncate" title={currentUser?.email}>{currentUser?.email || t('无账号', 'No Account')}</p>
                        </div>
                    </div>
                    <button 
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2 px-2 text-sm text-muted-foreground hover:text-destructive transition-colors"
                    >
                        <LogOut className="w-4 h-4" /> {t('退出登录', 'Sign Out')}
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto bg-background/50 relative flex flex-col">
                <div className="max-w-7xl mx-auto w-full px-8 lg:px-12 pt-8 pb-4 relative z-40">
                    {/* Header */}
                    <header className="flex justify-between items-center">
                        <div>
                            <h1 className="text-3xl font-bold tracking-tight capitalize">
                                {activeTab === 'projects' ? t('我的项目', 'My Projects') : activeTab}
                            </h1>
                            <p className="text-muted-foreground mt-1">
                                {activeTab === 'projects' && t('管理和编辑你的分镜脚本。', 'Manage and edit your storyboard scripts.')}
                                {activeTab === 'assets' && t('管理你生成的角色和场景素材。', 'Manage your generated characters and scenes.')}
                                {activeTab === 'settings' && t('管理你的账户偏好设置。', 'Manage your account preferences.')}
                            </p>
                        </div>
                        {activeTab === 'projects' && (
                            <div className="flex items-center gap-4">
                                {selectedProjectId ? (
                                    <button 
                                        onClick={() => setSelectedProjectId(null)}
                                        className="flex items-center gap-2 px-5 py-2.5 bg-secondary text-secondary-foreground rounded-full hover:bg-secondary/80 transition-all font-medium"
                                    >
                                        <ArrowLeft className="w-4 h-4" /> {t('返回项目列表', 'Back to Projects')}
                                    </button>
                                ) : (
                                    <>
                                        <div className="relative hidden md:block">
                                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                            <input 
                                                type="text" 
                                                placeholder={t('搜索项目...', 'Search projects...')} 
                                                className="pl-9 pr-4 py-2 bg-secondary/50 border-none rounded-full text-sm focus:ring-1 focus:ring-primary w-64"
                                            />
                                        </div>
                                        <button 
                                            onClick={() => setIsCreating(true)}
                                            className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-full hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all hover:scale-105 font-medium"
                                        >
                                            <Plus className="w-4 h-4" /> {t('新建项目', 'New Project')}
                                        </button>
                                        <button
                                            onClick={() => {
                                                trackMenuAction('project_list.header.settings', t('打开设置', 'Open Settings'), () => {
                                                    setActiveTab('settings');
                                                    setSelectedProjectId(null);
                                                    const returnTo = encodeURIComponent(`${location.pathname}${location.search}${location.hash}`);
                                                    navigate(`/settings?return_to=${returnTo}`);
                                                });
                                            }}
                                            title={t('打开设置', 'Open Settings')}
                                            className="p-2.5 rounded-full bg-secondary/60 text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
                                        >
                                            <Settings className="w-4 h-4" />
                                        </button>
                                    </>
                                )}
                            </div>
                        )}
                    </header>
                </div>

                 {/* Cinematic Header Strip */}
                 <div className="h-40 relative overflow-hidden group w-full select-none border-b border-white/5 shrink-0">
                    {/* Gradients to fade edges and bottom */}
                    <div className="absolute inset-0 bg-gradient-to-r from-background via-transparent to-background z-20 pointer-events-none" />
                    <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-background via-background/80 to-transparent z-20 pointer-events-none" />
                    
                    <motion.div 
                        className="flex gap-6 absolute left-0 top-6 h-24 items-center pl-4 opacity-40 grayscale group-hover:grayscale-0 group-hover:opacity-80 transition-all duration-700"
                        animate={{ x: ["0%", "-50%"] }}
                        transition={{ repeat: Infinity, ease: "linear", duration: 40 }}
                        style={{ width: "fit-content" }}
                    >
                         {[...cinematicImages, ...cinematicImages].map((src, idx) => (
                             <div key={idx} className="w-64 h-36 rounded-xl overflow-hidden flex-shrink-0 border border-white/10 shadow-2xl transform -skew-x-12 hover:skew-x-0 transition-transform duration-500 origin-bottom">
                                 <img src={src} alt={t('电影视觉元素', 'Cinematic element')} className="w-full h-full object-cover scale-125" />
                                 <div className="absolute inset-0 bg-blue-900/20 mix-blend-overlay"></div>
                             </div>
                         ))}
                    </motion.div>
                </div>

                <div className="max-w-7xl mx-auto w-full px-8 lg:px-12 pb-12 mt-4 relative z-30 flex-1 flex flex-col">
                    {/* Content Views */}
                    <div className="flex-1 min-h-0 flex flex-col">
                        {activeTab === 'projects' && (
                            selectedProjectId ? (
                                <motion.div 
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="h-full flex-1"
                                >
                                    <Editor projectId={selectedProjectId} />
                                </motion.div>
                            ) : (
                            <>
                                {isCreating && (
                                    <motion.div 
                                        initial={{ opacity: 0, y: -20 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="mb-8 p-6 border bg-card rounded-2xl shadow-sm"
                                    >
                                        <label className="block text-sm font-medium mb-2">{t('项目标题', 'Project Title')}</label>
                                        <div className="flex gap-3">
                                            <input 
                                                className="flex-1 px-4 py-2.5 bg-background border rounded-lg focus:ring-2 focus:ring-primary/20 outline-none" 
                                                value={newTitle} 
                                                onChange={e => setNewTitle(e.target.value)} 
                                                placeholder={t('例如：最后的地平线 - 场景1', 'e.g., The Last Horizon - Scene 1')}
                                                autoFocus
                                            />
                                            <button onClick={handleCreate} className="px-6 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700">{t('创建', 'Create')}</button>
                                            <button onClick={() => setIsCreating(false)} className="px-6 py-2.5 bg-secondary text-secondary-foreground rounded-lg font-medium hover:bg-secondary/80">{t('取消', 'Cancel')}</button>
                                        </div>
                                    </motion.div>
                                )}

                                {projects.length === 0 && !isCreating ? (
                                    <div className="text-center py-24 rounded-3xl border border-dashed border-white/10 bg-white/[0.02] backdrop-blur-sm">
                                        <div className="w-20 h-20 bg-gradient-to-tr from-primary/20 to-purple-500/20 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-inner ring-1 ring-white/10">
                                            <Folder className="w-10 h-10 text-primary blur-[1px] absolute opacity-50" />
                                            <Folder className="w-10 h-10 text-white relative z-10" />
                                        </div>
                                        <h3 className="text-2xl font-bold mb-3 bg-clip-text text-transparent bg-gradient-to-b from-white to-white/60">{t('开始你的创作之旅', 'Start Your Journey')}</h3>
                                        <p className="text-muted-foreground max-w-sm mx-auto mb-8 text-lg font-light">
                                            {t('你的工作室还是空的。创建第一个剧本，开始生成分镜。', 'Your studio is empty. Create your first screenplay to begin generating shots.')}
                                        </p>
                                        <button 
                                            onClick={() => setIsCreating(true)}
                                            className="px-8 py-3 rounded-full bg-primary/20 border border-primary/50 text-white font-medium hover:bg-primary/30 transition-all hover:scale-105"
                                        >
                                            {t('创建第一个项目', 'Create First Project')}
                                        </button>
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8">
                                        {projects.map(p => (
                                            <div onClick={() => setSelectedProjectId(p.id)} key={p.id} className="cursor-pointer">
                                                <motion.div 
                                                    whileHover={{ y: -8, scale: 1.02 }}
                                                    transition={{ type: "spring", stiffness: 300, damping: 20 }}
                                                    className="group relative bg-card/40 backdrop-blur-md border border-white/5 rounded-3xl overflow-hidden hover:border-primary/50 transition-all shadow-lg hover:shadow-2xl hover:shadow-primary/10"
                                                >
                                                    {/* Card Image Area - Increased Height */}
                                                    <div className="h-64 bg-black/60 relative overflow-hidden group-hover:bg-black/40 transition-colors">


                                                       {/* Cover Image or Fallback */}
                                                       {p.cover_image && (
                                                           <img 
                                                               src={p.cover_image.startsWith('http') ? p.cover_image : `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${p.cover_image}`} 
                                                               alt={p.title} 
                                                               className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105 z-10"
                                                               onError={(e) => { e.target.style.display = 'none'; }}
                                                           />
                                                       )}
                                                       
                                                       {/* Fallback Icon (Always rendered behind image) */}
                                                       <div className="absolute inset-0 flex items-center justify-center z-0">
                                                            <Folder className="w-12 h-12 text-white/5 group-hover:text-primary/20 transition-all duration-500 transform group-hover:scale-110" />
                                                       </div>



                                                       {/* Gradient Overlay */}
                                                       <div className="absolute inset-0 bg-gradient-to-t from-card via-transparent to-transparent opacity-90 z-10" />

                                                       {/* Top Badge */}
                                                    <div className="absolute left-4 top-4 z-20">
                                                        <div className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full border backdrop-blur-md ${isProjectOwner(p) ? 'bg-blue-500/20 text-blue-100 border-blue-300/35' : 'bg-amber-500/20 text-amber-100 border-amber-300/35'}`}>
                                                            {isProjectOwner(p) && <Shield className="w-3 h-3" />}
                                                            {isProjectOwner(p) ? t('主理人', 'Owner') : t('共享', 'Shared')}
                                                        </div>
                                                    </div>
                                                    </div>

                                                    {/* Card Content */}
                                                    <div className="p-4 relative z-20">
                                                        <div className="flex justify-between items-center">
                                                            <h3 className="text-lg font-semibold text-white group-hover:text-primary transition-colors truncate flex-1 mr-2">{p.title}</h3>
                                                            <div className="flex items-center gap-1">
                                                                {isProjectOwner(p) && (
                                                                    <button
                                                                        onClick={(e) => handleOpenShareModal(e, p)}
                                                                        className="opacity-0 group-hover:opacity-100 p-1.5 text-muted-foreground hover:text-blue-400 hover:bg-white/10 rounded-lg transition-all"
                                                                        title={t('项目共享', 'Project Sharing')}
                                                                    >
                                                                        <Share2 className="w-4 h-4" />
                                                                    </button>
                                                                )}
                                                                {isProjectOwner(p) && (
                                                                    <button 
                                                                        onClick={(e) => handleDeleteProject(e, p.id)}
                                                                        className="opacity-0 group-hover:opacity-100 p-1.5 text-muted-foreground hover:text-red-500 hover:bg-white/10 rounded-lg transition-all"
                                                                        title={t('删除项目', 'Delete Project')}
                                                                    >
                                                                        <Trash2 className="w-4 h-4" />
                                                                    </button>
                                                                )}
                                                            </div>
                                                        </div>
                                                        
                                                        {/* Description & Footer - Reveal on Hover */}
                                                        <div className="max-h-0 opacity-0 group-hover:max-h-32 group-hover:opacity-100 overflow-hidden transition-all duration-500 ease-in-out">
                                                            <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed opacity-80 mt-2">
                                                                {p.global_info?.notes || t('暂无描述。', 'No description added.')}
                                                            </p>
                                                            <p className="text-[11px] text-muted-foreground/80 mt-2 mb-4">
                                                                {getProjectShareCountText(p)}
                                                            </p>
                                                            
                                                            {/* Footer Meta */}
                                                            <div className="flex items-center justify-between text-[10px] text-muted-foreground/60 pt-3 border-t border-white/5 group-hover:border-white/10 transition-colors">
                                                                <span>{t('2分钟前编辑', 'Edited 2m ago')}</span>
                                                                <div className="flex -space-x-2">
                                                                    <div className="w-4 h-4 rounded-full bg-blue-500 border border-card"></div>
                                                                    <div className="w-4 h-4 rounded-full bg-purple-500 border border-card"></div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </motion.div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </>
                            )
                        )}

                        {activeTab === 'assets' && (
                            <div className="h-full bg-card/30 rounded-3xl border border-white/5 overflow-hidden">
                                <AssetsLibrary />
                            </div>
                        )}

                        {activeTab === 'settings' && (
                           <div className="h-full bg-card/30 rounded-3xl border border-white/5 overflow-hidden">
                                <SettingsPage />
                           </div>
                        )}
                    </div>
                </div>
            </main>

            {shareModalProject && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setShareModalProject(null)}>
                    <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-card p-5" onClick={(e) => e.stopPropagation()}>
                        <div className="mb-4 flex items-center justify-between">
                            <h3 className="text-lg font-semibold">{t('项目共享', 'Project Sharing')} · {shareModalProject.title}</h3>
                            <button className="rounded p-1 text-muted-foreground hover:bg-secondary" onClick={() => setShareModalProject(null)}>
                                <X className="h-4 w-4" />
                            </button>
                        </div>

                        <div className="mb-4 flex gap-2">
                            <input
                                value={shareTargetUser}
                                onChange={(e) => setShareTargetUser(e.target.value)}
                                placeholder={t('输入用户名或邮箱', 'Enter username or email')}
                                className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                            />
                            <button
                                onClick={handleCreateShare}
                                disabled={shareSubmitting || !String(shareTargetUser || '').trim()}
                                className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                            >
                                {shareSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                                {t('添加', 'Add')}
                            </button>
                        </div>

                        <div className="max-h-72 overflow-auto rounded-lg border border-white/10">
                            {shareLoading ? (
                                <div className="p-4 text-sm text-muted-foreground">{t('加载中...', 'Loading...')}</div>
                            ) : projectShares.length === 0 ? (
                                <div className="p-4 text-sm text-muted-foreground">{t('暂无共享用户', 'No shared users')}</div>
                            ) : (
                                <div className="divide-y divide-white/10">
                                    {projectShares.map((s) => (
                                        <div key={s.id} className="flex items-center justify-between px-3 py-2">
                                            <div>
                                                <div className="text-sm font-medium">{s.username}</div>
                                                <div className="text-xs text-muted-foreground">{s.email || '-'}</div>
                                            </div>
                                            <button
                                                onClick={() => handleDeleteShare(s.user_id)}
                                                className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-500/10"
                                            >
                                                {t('取消共享', 'Revoke')}
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};


const SettingsPanel = ({ currentTheme, handleThemeChange, uiLang }) => {
    const t = (zh, en) => tUI(uiLang, zh, en);
    const [section, setSection] = useState('general');

    return (
        <div className="w-full h-full"> 
            <div className="flex items-center justify-between mb-8">
                <div className="flex space-x-1 bg-card/50 p-1 rounded-xl border border-white/5">
                    <button onClick={() => setSection('general')} className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${section === 'general' ? 'bg-primary text-black font-bold shadow-lg' : 'text-muted-foreground'}`}>{t('常规', 'General')}</button>
                    <button onClick={() => setSection('configuration')} className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${section === 'configuration' ? 'bg-primary text-black font-bold shadow-lg' : 'text-muted-foreground'}`}>{t('配置', 'Configuration')}</button>
                </div>
            </div>

            {section === 'general' && (
                 <div className="grid gap-8 animate-in fade-in duration-500">
                     <section>
                         <h3 className="text-xl font-bold mb-6 flex items-center gap-2">
                             <Palette className="w-5 h-5 text-primary" />
                             {t('界面外观', 'Interface Appearance')}
                         </h3>
                         <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                             {Object.entries(THEMES).map(([key, theme]) => (
                                 <div 
                                    key={key} 
                                    onClick={() => handleThemeChange(key)}
                                    className={`cursor-pointer group relative overflow-hidden rounded-2xl border transition-all duration-300 ${currentTheme === key ? 'border-primary ring-2 ring-primary/20 scale-[1.02] shadow-2xl shadow-black/50' : 'border-white/10 hover:border-white/30 bg-card/30'}`}
                                 >
                                     <div className="aspect-[1.6/1] relative border-b border-white/5" style={{ background: `hsl(${theme.colors['--background']})` }}>
                                         {/* Mock UI Preview */}
                                         <div className="absolute inset-4 flex gap-2">
                                            <div className="w-1/4 h-full rounded-lg opacity-80" style={{ background: `hsl(${theme.colors['--card']})` }}></div>
                                            <div className="flex-1 flex flex-col gap-2">
                                                <div className="h-4 rounded col-span-2 opacity-50" style={{ background: `hsl(${theme.colors['--muted']})` }}></div>
                                                <div className="h-20 rounded-lg flex items-center justify-center border border-white/5" style={{ background: `hsl(${theme.colors['--card']})` }}>
                                                    <div className="w-6 h-6 rounded-full" style={{ background: `hsl(${theme.colors['--primary']})` }}></div>
                                                </div>
                                            </div>
                                         </div>
                                     </div>
                                     <div className="p-4 bg-card/50 backdrop-blur-sm">
                                         <div className="flex justify-between items-center mb-1">
                                            <h4 className="font-bold text-sm tracking-wide">{t(theme.name.zh, theme.name.en)}</h4>
                                            {currentTheme === key && <CheckCircle className="w-4 h-4 text-green-500" />}
                                         </div>
                                         <p className="text-xs text-muted-foreground opacity-70 leading-relaxed font-light">{t(theme.description.zh, theme.description.en)}</p>
                                     </div>
                                 </div>
                             ))}
                         </div>
                     </section>
                 </div>
            )}

            {section === 'configuration' && (
                <div className="h-[calc(100vh-250px)] animate-in fade-in">
                    <SettingsPage />
                </div>
            )}
        </div>
    );
};

export default ProjectList;
