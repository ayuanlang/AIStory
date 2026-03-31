
import React, { useCallback, useEffect, useState } from 'react';
import {
    api,
    fetchProjects,
    createProject,
    updateProject,
    getSettings,
    updateSetting,
    getSettingDefaults,
    deleteSetting,
    deleteProject,
    recordSystemLogAction,
    fetchProjectShares,
    createProjectShare,
    deleteProjectShare,
    fetchProjectReviewThreads,
    fetchReviewInboxThreads,
    fetchReviewOutboxThreads,
    createProjectReviewThread,
    fetchReviewThread,
    markReviewThreadRead,
    updateReviewThreadStatus,
    fetchReviewThreadRounds,
    createReviewThreadRound,
    fetchReviewRoundMessages,
    createReviewRoundMessage,
    getKieStandardValueOptions,
    submitImageGenerationJob,
    getImageGenerationJobStatus,
} from '../services/api';
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
    Bell,
    X,
    Menu,
    Loader2,
    ChevronsLeft,
    ChevronsRight,
    Info,
    ChevronDown
} from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { confirmUiMessage, promptUiMessage } from '../lib/uiMessage';
import { getUiLang, tUI } from '../lib/uiLang';
import {
    PROJECT_EP_TYPE_OPTIONS,
    PROJECT_EP_LANGUAGE_OPTIONS,
    PROJECT_EP_BASE_POSITIONING_OPTIONS,
    PROJECT_SCENE_ANALYSIS_ERA_OPTIONS,
    PROJECT_SCENE_ANALYSIS_REGION_OPTIONS,
    PROJECT_SCENE_ANALYSIS_MODEL_FAMILY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_WORKFLOW_OPTIONS,
    PROJECT_SCENE_ANALYSIS_GOAL_OPTIONS,
    PROJECT_SCENE_ANALYSIS_CHARACTER_EMPHASIS_OPTIONS,
    PROJECT_SCENE_ANALYSIS_NARRATIVE_DENSITY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_COMMERCIAL_CONSTRAINT_OPTIONS,
    PROJECT_SCENE_ANALYSIS_MODALITY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_CONTINUITY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_SAFETY_OPTIONS,
    PROJECT_SCENE_ANALYSIS_DEFAULTS,
} from './editor/projectOptionConfig';

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
const PROJECT_SETTINGS_RETURN_SNAPSHOT_KEY = 'aistory.projects.return.snapshot';
const PROJECT_CREATE_FALLBACK_ASPECT_RATIO_OPTIONS = ['16:9', '2.35:1', '4:3', '9:16', '1:1'];
const PROJECT_CREATE_FALLBACK_IMAGE_SIZE_OPTIONS = ['0.5K', '1K', '2K', '4K'];
const PROJECT_CREATE_PREFERRED_ASPECT_RATIO = '9:16';
const PROJECT_CREATE_PREFERRED_IMAGE_SIZE = '1K';
const PROJECT_CREATE_DEFAULT_OPTIONS = {
    type: [...PROJECT_EP_TYPE_OPTIONS],
    language: [...PROJECT_EP_LANGUAGE_OPTIONS],
    base_positioning: [...PROJECT_EP_BASE_POSITIONING_OPTIONS],
    aspect_ratio: [...PROJECT_CREATE_FALLBACK_ASPECT_RATIO_OPTIONS],
    image_size: [...PROJECT_CREATE_FALLBACK_IMAGE_SIZE_OPTIONS],
};

const createDefaultProjectSceneAnalysisConfig = () => ({
    ...PROJECT_SCENE_ANALYSIS_DEFAULTS,
});

const PROJECT_SCENE_ANALYSIS_CREATE_FIELDS = [
    { key: 'primary_goal', labelZh: '主要目标', labelEn: 'Primary Goal', options: PROJECT_SCENE_ANALYSIS_GOAL_OPTIONS },
    { key: 'secondary_goal', labelZh: '次级目标', labelEn: 'Secondary Goal', options: PROJECT_SCENE_ANALYSIS_GOAL_OPTIONS },
    { key: 'expected_model_family', labelZh: '预期模型族', labelEn: 'Expected Model Family', options: PROJECT_SCENE_ANALYSIS_MODEL_FAMILY_OPTIONS },
    { key: 'generation_workflow', labelZh: '生成工作流', labelEn: 'Generation Workflow', options: PROJECT_SCENE_ANALYSIS_WORKFLOW_OPTIONS },
    { key: 'era_setting', labelZh: '时代设定', labelEn: 'Era Setting', options: PROJECT_SCENE_ANALYSIS_ERA_OPTIONS },
    { key: 'region_culture', labelZh: '地域文化语境', labelEn: 'Region / Culture', options: PROJECT_SCENE_ANALYSIS_REGION_OPTIONS },
    { key: 'character_emphasis', labelZh: '人物侧重点', labelEn: 'Character Emphasis', options: PROJECT_SCENE_ANALYSIS_CHARACTER_EMPHASIS_OPTIONS },
    { key: 'narrative_density', labelZh: '叙事密度', labelEn: 'Narrative Density', options: PROJECT_SCENE_ANALYSIS_NARRATIVE_DENSITY_OPTIONS },
    { key: 'commercial_constraint', labelZh: '商业约束', labelEn: 'Commercial Constraint', options: PROJECT_SCENE_ANALYSIS_COMMERCIAL_CONSTRAINT_OPTIONS },
    { key: 'modality_focus', labelZh: '模态侧重', labelEn: 'Modality Focus', options: PROJECT_SCENE_ANALYSIS_MODALITY_OPTIONS },
    { key: 'continuity_priority', labelZh: '连续性优先级', labelEn: 'Continuity Priority', options: PROJECT_SCENE_ANALYSIS_CONTINUITY_OPTIONS },
    { key: 'safety_broadcast_level', labelZh: '播出安全等级', labelEn: 'Safety / Broadcast Level', options: PROJECT_SCENE_ANALYSIS_SAFETY_OPTIONS },
];

const uniqueNonEmptyStrings = (items) => {
    if (!Array.isArray(items)) return [];
    const out = [];
    const seen = new Set();
    items.forEach((item) => {
        const value = String(item || '').trim();
        if (!value || seen.has(value)) return;
        seen.add(value);
        out.push(value);
    });
    return out;
};

const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

const extractImageJobResultUrl = (statusResp) => {
    const result = (statusResp?.result && typeof statusResp.result === 'object') ? statusResp.result : {};
    const candidates = [
        result?.url,
        result?.image_url,
        result?.imageUrl,
        result?.generated_url,
        statusResp?.url,
        statusResp?.image_url,
        statusResp?.imageUrl,
    ];
    for (const value of candidates) {
        const stable = String(value || '').trim();
        if (stable) return stable;
    }
    return '';
};

const buildProjectCoverPrompt = (project) => {
    const info = project?.global_info && typeof project.global_info === 'object' ? project.global_info : {};
    const tech = info?.tech_params && typeof info.tech_params === 'object' ? info.tech_params : {};
    const visual = tech?.visual_standard && typeof tech.visual_standard === 'object' ? tech.visual_standard : {};
    const notes = String(project?.description || info?.notes || '').trim();
    const genre = String(info?.type || '').trim();
    const language = String(info?.language || '').trim();
    const positioning = String(info?.base_positioning || '').trim();
    const tone = String(info?.color_tone || visual?.color_tone || '').trim();

    const detailBits = [
        genre ? `genre: ${genre}` : '',
        language ? `language mood: ${language}` : '',
        positioning ? `positioning: ${positioning}` : '',
        tone ? `tone: ${tone}` : '',
        notes ? `story context: ${notes}` : '',
    ].filter(Boolean);

    return [
        `Create a premium cinematic vertical cover poster for the project titled "${String(project?.title || '').trim() || 'Untitled Project'}".`,
        'Use a strong central subject, clear foreground-background separation, bold lighting, and blockbuster poster composition.',
        'Reserve clean safe areas for title placement at the top and credits or tagline at the bottom. Avoid clutter and avoid tiny repeated subjects.',
        'The image should feel like international film key art: polished, dramatic, stylish, and commercially appealing.',
        detailBits.join('; '),
    ].filter(Boolean).join(' ');
};

const parseUserListInput = (value) => {
    if (Array.isArray(value)) return uniqueNonEmptyStrings(value);
    return uniqueNonEmptyStrings(String(value || '').split(/[;,\n\r]+/));
};

const formatParsedUserHint = (value, t) => {
    const count = parseUserListInput(value).length;
    return count > 0
        ? t(`已解析 ${count} 个用户，创建时会校验是否存在`, `Parsed ${count} users. Existence will be validated on create`)
        : t('留空即可，创建时才会校验输入的用户', 'Leave empty if unused. Entered users will be validated on create');
};

const pickPreferredOrFirst = (options, preferred = '') => {
    const normalized = uniqueNonEmptyStrings(options);
    if (preferred && normalized.includes(preferred)) return preferred;
    return normalized[0] || '';
};

const normalizeProjectCreateOptions = (payload) => {
    const safe = payload && typeof payload === 'object' ? payload : {};
    const type = uniqueNonEmptyStrings(safe.type);
    const language = uniqueNonEmptyStrings(safe.language);
    const basePositioning = uniqueNonEmptyStrings(safe.base_positioning);
    const aspectRatio = uniqueNonEmptyStrings(safe.aspect_ratio);
    const imageSize = uniqueNonEmptyStrings([
        ...(Array.isArray(safe.image_size) ? safe.image_size : []),
        ...PROJECT_CREATE_DEFAULT_OPTIONS.image_size,
    ]);

    return {
        type: type.length ? type : [...PROJECT_CREATE_DEFAULT_OPTIONS.type],
        language: language.length ? language : [...PROJECT_CREATE_DEFAULT_OPTIONS.language],
        base_positioning: basePositioning.length ? basePositioning : [...PROJECT_CREATE_DEFAULT_OPTIONS.base_positioning],
        aspect_ratio: aspectRatio.length ? aspectRatio : [...PROJECT_CREATE_DEFAULT_OPTIONS.aspect_ratio],
        image_size: imageSize.length ? imageSize : [...PROJECT_CREATE_DEFAULT_OPTIONS.image_size],
    };
};

const PROJECT_SHARE_ROLE_OPTIONS = ['editor', 'reviewer', 'viewer'];
const REVIEW_LIST_MODE_OPTIONS = ['project', 'inbox', 'outbox'];
const REVIEW_DECISION_OPTIONS = ['pending', 'approved', 'conditional', 'rejected'];
const REVIEW_THREAD_STATUS_OPTIONS = ['open', 'closed', 'archived'];

const getProjectShareRoleLabel = (role, t) => {
    const normalized = String(role || 'editor').trim().toLowerCase();
    if (normalized === 'reviewer') return t('审核人', 'Reviewer');
    if (normalized === 'viewer') return t('查看者', 'Viewer');
    return t('编辑者', 'Editor');
};

const getReviewDecisionLabel = (decision, t) => {
    const normalized = String(decision || 'pending').trim().toLowerCase();
    if (normalized === 'approved') return t('通过', 'Approved');
    if (normalized === 'conditional') return t('有条件通过', 'Conditional');
    if (normalized === 'rejected') return t('不通过', 'Rejected');
    return t('待回复', 'Pending');
};

const getReviewThreadStatusLabel = (status, t) => {
    const normalized = String(status || 'open').trim().toLowerCase();
    if (normalized === 'closed') return t('已关闭', 'Closed');
    if (normalized === 'archived') return t('已归档', 'Archived');
    return t('进行中', 'Open');
};

const getReviewListModeLabel = (mode, t) => {
    if (mode === 'inbox') return t('待我审核', 'Inbox');
    if (mode === 'outbox') return t('我的发起', 'Outbox');
    return t('项目审核', 'Project Reviews');
};

const createDefaultReviewThreadForm = () => ({
    reviewer_user: '',
    title: '',
    request_message: '',
    entity_required: true,
    shot_required: true,
});

const createDefaultReviewMessageForm = () => ({
    message_text: '',
    entity_decision: 'pending',
    shot_decision: 'pending',
    entity_feedback: '',
    shot_feedback: '',
});

const createDefaultReviewRoundForm = () => ({
    request_message: '',
    entity_required: true,
    shot_required: true,
});

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
    },
    emerald: {
        name: {
            zh: "祖母绿幕",
            en: "Emerald Noir",
        },
        description: {
            zh: "冷静青绿色，清晰层次。",
            en: "Calm teal accents with clear layering.",
        },
        colors: {
            "--background": "168 44% 7%",
            "--card": "168 42% 9%",
            "--primary": "160 72% 78%",
            "--secondary": "167 30% 16%",
            "--muted": "167 26% 13%",
            "--border": "167 30% 18%"
        }
    },
    ember: {
        name: {
            zh: "余烬红",
            en: "Ember Red",
        },
        description: {
            zh: "低饱和暖红，电影质感。",
            en: "Muted warm reds with cinematic mood.",
        },
        colors: {
            "--background": "6 36% 8%",
            "--card": "6 34% 10%",
            "--primary": "12 84% 82%",
            "--secondary": "8 24% 17%",
            "--muted": "8 22% 14%",
            "--border": "8 24% 20%"
        }
    }
};

const ProjectList = ({ initialTab = 'projects' }) => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const location = useLocation();
    const [projects, setProjects] = useState([]);
    const [isProjectsLoading, setIsProjectsLoading] = useState(false);
    const [hasLoadedProjectsOnce, setHasLoadedProjectsOnce] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [newTitle, setNewTitle] = useState('');
    const [newDescription, setNewDescription] = useState('');
    const [newShareUsers, setNewShareUsers] = useState('');
    const [newReviewerUsers, setNewReviewerUsers] = useState('');
    const [projectCreateOptions, setProjectCreateOptions] = useState(PROJECT_CREATE_DEFAULT_OPTIONS);
    const [newType, setNewType] = useState(pickPreferredOrFirst(PROJECT_CREATE_DEFAULT_OPTIONS.type));
    const [newLanguage, setNewLanguage] = useState(pickPreferredOrFirst(PROJECT_CREATE_DEFAULT_OPTIONS.language));
    const [newBasePositioning, setNewBasePositioning] = useState(pickPreferredOrFirst(PROJECT_CREATE_DEFAULT_OPTIONS.base_positioning));
    const [newAspectRatio, setNewAspectRatio] = useState(pickPreferredOrFirst(PROJECT_CREATE_DEFAULT_OPTIONS.aspect_ratio, PROJECT_CREATE_PREFERRED_ASPECT_RATIO));
    const [newImageSize, setNewImageSize] = useState(pickPreferredOrFirst(PROJECT_CREATE_DEFAULT_OPTIONS.image_size, PROJECT_CREATE_PREFERRED_IMAGE_SIZE));
    const [newVideoSoundEnabled, setNewVideoSoundEnabled] = useState(true);
    const [isCreateCollaboratorsCollapsed, setIsCreateCollaboratorsCollapsed] = useState(true);
    const [isCreateSceneAnalysisCollapsed, setIsCreateSceneAnalysisCollapsed] = useState(true);
    const [newSceneAnalysisConfig, setNewSceneAnalysisConfig] = useState(createDefaultProjectSceneAnalysisConfig());
    const [activeTab, setActiveTab] = useState(initialTab);
    const [selectedProjectId, setSelectedProjectId] = useState(null);
    const [restoredEditorState, setRestoredEditorState] = useState(null);
    const [currentUser, setCurrentUser] = useState(null); // Simple user state to check permissions if we had endpoint
    const navigate = useNavigate();

    // Theme Logic - Moved to Parent for persistence on reload
    const [currentTheme, setCurrentTheme] = useState('default');
    const [toast, setToast] = useState(null);
    const [coverGenerationByProject, setCoverGenerationByProject] = useState({});
    const [shareModalProject, setShareModalProject] = useState(null);
    const [shareModalTab, setShareModalTab] = useState('share');
    const [projectShares, setProjectShares] = useState([]);
    const [projectShareCounts, setProjectShareCounts] = useState({});
    const [projectUnreadReviewCounts, setProjectUnreadReviewCounts] = useState({});
    const [shareTargetUser, setShareTargetUser] = useState('');
    const [shareTargetRole, setShareTargetRole] = useState('editor');
    const [shareTargetCanReview, setShareTargetCanReview] = useState(false);
    const [shareRoleDrafts, setShareRoleDrafts] = useState({});
    const [sharePermissionDrafts, setSharePermissionDrafts] = useState({});
    const [shareLoading, setShareLoading] = useState(false);
    const [shareSubmitting, setShareSubmitting] = useState(false);
    const [reviewListMode, setReviewListMode] = useState('project');
    const [projectReviewThreads, setProjectReviewThreads] = useState([]);
    const [reviewInboxThreads, setReviewInboxThreads] = useState([]);
    const [reviewOutboxThreads, setReviewOutboxThreads] = useState([]);
    const [reviewLoading, setReviewLoading] = useState(false);
    const [reviewSubmitting, setReviewSubmitting] = useState(false);
    const [selectedReviewThreadId, setSelectedReviewThreadId] = useState(null);
    const [selectedReviewThread, setSelectedReviewThread] = useState(null);
    const [selectedReviewRounds, setSelectedReviewRounds] = useState([]);
    const [selectedReviewRoundId, setSelectedReviewRoundId] = useState(null);
    const [selectedReviewMessages, setSelectedReviewMessages] = useState([]);
    const [reviewThreadForm, setReviewThreadForm] = useState(createDefaultReviewThreadForm());
    const [reviewMessageForm, setReviewMessageForm] = useState(createDefaultReviewMessageForm());
    const [reviewRoundForm, setReviewRoundForm] = useState(createDefaultReviewRoundForm());
    const [reviewStatusSubmitting, setReviewStatusSubmitting] = useState(false);
    const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
        try {
            return localStorage.getItem('project_list.sidebar.collapsed') === '1';
        } catch {
            return false;
        }
    });

    useEffect(() => {
        try {
            localStorage.setItem('project_list.sidebar.collapsed', isSidebarCollapsed ? '1' : '0');
        } catch {
            // ignore localStorage failures
        }
    }, [isSidebarCollapsed]);

    useEffect(() => {
        setIsMobileSidebarOpen(false);
    }, [activeTab, selectedProjectId]);
    
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

    useEffect(() => {
        if (location.pathname !== '/projects') {
            return;
        }
        try {
            const raw = sessionStorage.getItem(PROJECT_SETTINGS_RETURN_SNAPSHOT_KEY);
            if (!raw) return;

            const snapshot = JSON.parse(raw);
            const projectId = snapshot?.selectedProjectId;
            if (!projectId) {
                sessionStorage.removeItem(PROJECT_SETTINGS_RETURN_SNAPSHOT_KEY);
                return;
            }

            setActiveTab('projects');
            setSelectedProjectId(projectId);
            setRestoredEditorState({
                activeTab: snapshot?.activeTab || 'overview',
                activeEpisodeId: snapshot?.activeEpisodeId ?? null,
                editingShotId: snapshot?.editingShotId ?? null,
                editingShotSceneId: snapshot?.editingShotSceneId ?? null,
            });
            sessionStorage.removeItem(PROJECT_SETTINGS_RETURN_SNAPSHOT_KEY);
        } catch (e) {
            sessionStorage.removeItem(PROJECT_SETTINGS_RETURN_SNAPSHOT_KEY);
        }
    }, [location.pathname]);

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
        const loadProjectCreateOptions = async () => {
            try {
                const data = await getKieStandardValueOptions();
                const normalized = normalizeProjectCreateOptions(data);
                setProjectCreateOptions(normalized);
                setNewType((prev) => (normalized.type.includes(prev) ? prev : pickPreferredOrFirst(normalized.type)));
                setNewLanguage((prev) => (normalized.language.includes(prev) ? prev : pickPreferredOrFirst(normalized.language)));
                setNewBasePositioning((prev) => (normalized.base_positioning.includes(prev) ? prev : pickPreferredOrFirst(normalized.base_positioning)));
                setNewAspectRatio((prev) => (
                    normalized.aspect_ratio.includes(prev)
                        ? prev
                        : pickPreferredOrFirst(normalized.aspect_ratio, PROJECT_CREATE_PREFERRED_ASPECT_RATIO)
                ));
                setNewImageSize((prev) => (
                    normalized.image_size.includes(prev)
                        ? prev
                        : pickPreferredOrFirst(normalized.image_size, PROJECT_CREATE_PREFERRED_IMAGE_SIZE)
                ));
            } catch (error) {
                console.error('Failed to load project-create dictionary options', error);
            }
        };

        loadProjectCreateOptions();
    }, []);

    const loadProjects = useCallback(async () => {
        setIsProjectsLoading(true);
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

            const nextUnreadCounts = {};
            try {
                // Fetch once and aggregate by project_id to avoid N per-project review thread requests.
                const [inboxRows, outboxRows] = await Promise.all([
                    fetchReviewInboxThreads(),
                    fetchReviewOutboxThreads(),
                ]);

                const mergedRows = [
                    ...(Array.isArray(inboxRows) ? inboxRows : []),
                    ...(Array.isArray(outboxRows) ? outboxRows : []),
                ];
                const seenThreadIds = new Set();

                mergedRows.forEach((thread) => {
                    const threadId = Number(thread?.id || 0);
                    if (threadId > 0) {
                        if (seenThreadIds.has(threadId)) return;
                        seenThreadIds.add(threadId);
                    }

                    if (!thread?.has_unread) return;
                    const projectId = Number(thread?.project_id || 0);
                    if (projectId <= 0) return;
                    nextUnreadCounts[projectId] = Number(nextUnreadCounts[projectId] || 0) + 1;
                });
            } catch {
                // Keep unread counts at zero if review endpoints are temporarily unavailable.
            }

            (Array.isArray(sorted) ? sorted : []).forEach((item) => {
                const projectId = Number(item?.id || 0);
                if (projectId > 0 && nextUnreadCounts[projectId] == null) {
                    nextUnreadCounts[projectId] = 0;
                }
            });
            setProjectUnreadReviewCounts(nextUnreadCounts);
        } catch (error) {
            console.error("Failed to load projects", error);
        } finally {
            setIsProjectsLoading(false);
            setHasLoadedProjectsOnce(true);
        }
    }, [currentUser?.id]);

    useEffect(() => {
        if (activeTab === 'projects') {
            loadProjects();
        }
    }, [activeTab, loadProjects]);

    useEffect(() => {
        if (activeTab !== 'projects' || selectedProjectId) return undefined;

        const refreshIfVisible = () => {
            if (document.visibilityState !== 'visible') return;
            loadProjects();
        };

        const intervalId = window.setInterval(refreshIfVisible, 45000);
        document.addEventListener('visibilitychange', refreshIfVisible);
        window.addEventListener('focus', refreshIfVisible);

        return () => {
            window.clearInterval(intervalId);
            document.removeEventListener('visibilitychange', refreshIfVisible);
            window.removeEventListener('focus', refreshIfVisible);
        };
    }, [activeTab, selectedProjectId, loadProjects]);

    const resetCreateProjectForm = () => {
        setNewTitle('');
        setNewDescription('');
        setNewShareUsers('');
        setNewReviewerUsers('');
        setNewType(pickPreferredOrFirst(projectCreateOptions.type));
        setNewLanguage(pickPreferredOrFirst(projectCreateOptions.language));
        setNewBasePositioning(pickPreferredOrFirst(projectCreateOptions.base_positioning));
        setNewAspectRatio(pickPreferredOrFirst(projectCreateOptions.aspect_ratio, PROJECT_CREATE_PREFERRED_ASPECT_RATIO));
        setNewImageSize(pickPreferredOrFirst(projectCreateOptions.image_size, PROJECT_CREATE_PREFERRED_IMAGE_SIZE));
        setNewVideoSoundEnabled(true);
        setIsCreateCollaboratorsCollapsed(true);
        setIsCreateSceneAnalysisCollapsed(true);
        setNewSceneAnalysisConfig(createDefaultProjectSceneAnalysisConfig());
    };

    const handleCreate = async () => {
        const title = String(newTitle || '').trim();
        if (!title) return;
        const description = String(newDescription || '');
        const shareUsers = parseUserListInput(newShareUsers);
        const reviewerUsers = parseUserListInput(newReviewerUsers);
        await createProject({
            title,
            description,
            share_users: shareUsers,
            reviewer_users: reviewerUsers,
            global_info: {
                script_title: title,
                type: String(newType || '').trim(),
                language: String(newLanguage || '').trim(),
                base_positioning: String(newBasePositioning || '').trim(),
                notes: description,
                tech_params: {
                    visual_standard: {
                        aspect_ratio: String(newAspectRatio || '').trim(),
                        image_size: String(newImageSize || '').trim(),
                        sound: Boolean(newVideoSoundEnabled),
                    },
                },
                project_generation_defaults: {
                    sound: Boolean(newVideoSoundEnabled),
                },
                aspect_ratio: String(newAspectRatio || '').trim(),
                image_size: String(newImageSize || '').trim(),
                video_sound: Boolean(newVideoSoundEnabled),
                ...Object.fromEntries(
                    Object.entries(newSceneAnalysisConfig || {}).map(([key, value]) => [key, String(value || '').trim()])
                ),
            },
        });
        resetCreateProjectForm();
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
        try {
            sessionStorage.removeItem(PROJECT_SETTINGS_RETURN_SNAPSHOT_KEY);
        } catch {
            // ignore
        }
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
        if (!await confirmUiMessage(t(
            '确定要删除这个项目吗？该项目关联的业务数据库记录（场景/镜头/实体/资产关联等）和相关资产物理文件将一并删除，且不可恢复。审计日志会保留。',
            'Are you sure you want to delete this project? Related business database records (scenes/shots/entities/asset links, etc.) and associated asset files will also be permanently deleted and cannot be recovered. Audit logs will be retained.'
        ))) return;
        
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

    const handleGenerateProjectCover = async (event, project) => {
        event.stopPropagation();
        const projectId = Number(project?.id || 0);
        if (projectId <= 0 || coverGenerationByProject[projectId]) return;

        const defaultPrompt = buildProjectCoverPrompt(project);
        const promptInput = await promptUiMessage(
            t('请输入封面图提示词', 'Enter cover image prompt'),
            { defaultValue: defaultPrompt }
        );
        if (promptInput == null) return;

        const finalPrompt = String(promptInput || '').trim();
        if (!finalPrompt) {
            setToast({ type: 'error', message: t('封面图提示词不能为空', 'Cover image prompt cannot be empty') });
            setTimeout(() => setToast(null), 3000);
            return;
        }

        setCoverGenerationByProject((prev) => ({
            ...(prev || {}),
            [projectId]: { status: 'queued' },
        }));

        try {
            const submitResult = await submitImageGenerationJob(finalPrompt, null, null, {
                project_id: projectId,
                asset_type: 'cover',
                prompt_language: uiLang === 'zh' ? 'cn' : 'en',
            });
            const jobId = String(submitResult?.job_id || '').trim();
            if (!jobId) throw new Error(t('缺少封面任务 ID', 'Missing cover job id'));

            setCoverGenerationByProject((prev) => ({
                ...(prev || {}),
                [projectId]: { status: 'running', jobId },
            }));

            const deadline = Date.now() + 8 * 60 * 1000;
            let stableImageUrl = '';
            while (Date.now() < deadline) {
                const statusResp = await getImageGenerationJobStatus(jobId);
                const status = String(statusResp?.status || '').trim().toLowerCase();

                if (status === 'queued' || status === 'running' || status === 'persisting') {
                    setCoverGenerationByProject((prev) => ({
                        ...(prev || {}),
                        [projectId]: { status: status || 'running', jobId },
                    }));
                    await sleep(2500);
                    continue;
                }

                if (status === 'completed' || status === 'succeeded') {
                    stableImageUrl = extractImageJobResultUrl(statusResp);
                    if (!stableImageUrl) {
                        throw new Error(t('封面任务已完成，但未返回图片地址', 'Cover job completed but returned no image URL'));
                    }
                    break;
                }

                if (status === 'failed' || status === 'error' || status === 'canceled' || status === 'cancelled') {
                    throw new Error(statusResp?.error || statusResp?.detail || t('封面图生成失败', 'Cover image generation failed'));
                }

                await sleep(2500);
            }

            if (!stableImageUrl) {
                throw new Error(t('等待封面图结果超时', 'Timed out waiting for cover image result'));
            }

            await updateProject(projectId, { cover_image: stableImageUrl });
            setProjects((prev) => (Array.isArray(prev)
                ? prev.map((item) => (Number(item?.id || 0) === projectId ? { ...item, cover_image: stableImageUrl } : item))
                : prev
            ));
            setToast({ type: 'success', message: t('封面图已更新', 'Cover image updated') });
            setTimeout(() => setToast(null), 3000);
        } catch (error) {
            console.error('Failed to generate project cover', error);
            setToast({
                type: 'error',
                message: error?.response?.data?.detail || error?.message || t('生成封面图失败', 'Failed to generate cover image'),
            });
            setTimeout(() => setToast(null), 3500);
        } finally {
            setCoverGenerationByProject((prev) => {
                const next = { ...(prev || {}) };
                delete next[projectId];
                return next;
            });
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

    const getProjectUnreadReviewCount = (project) => Number(projectUnreadReviewCounts?.[project?.id] || 0);

    const loadProjectSharesForModal = async (projectId) => {
        const shares = await fetchProjectShares(projectId);
        const normalizedShares = Array.isArray(shares) ? shares : [];
        setProjectShares(normalizedShares);
        setProjectShareCounts((prev) => ({ ...prev, [projectId]: normalizedShares.length }));
        setShareRoleDrafts(() => {
            const next = {};
            normalizedShares.forEach((item) => {
                next[item.user_id] = String(item.role || 'editor').trim().toLowerCase() || 'editor';
            });
            return next;
        });
        setSharePermissionDrafts(() => {
            const next = {};
            normalizedShares.forEach((item) => {
                next[item.user_id] = {
                    can_review_assets: !!item?.permissions?.can_review_assets,
                };
            });
            return next;
        });
        return normalizedShares;
    };

    const loadReviewCollections = async (projectId, preferredThreadId = null) => {
        const [projectRows, inboxRows, outboxRows] = await Promise.all([
            fetchProjectReviewThreads(projectId),
            fetchReviewInboxThreads(),
            fetchReviewOutboxThreads(),
        ]);
        const normalizedProjectRows = Array.isArray(projectRows) ? projectRows : [];
        const normalizedInboxRows = Array.isArray(inboxRows) ? inboxRows : [];
        const normalizedOutboxRows = Array.isArray(outboxRows) ? outboxRows : [];
        setProjectReviewThreads(normalizedProjectRows);
        setReviewInboxThreads(normalizedInboxRows);
        setReviewOutboxThreads(normalizedOutboxRows);
        setProjectUnreadReviewCounts((prev) => ({
            ...prev,
            [projectId]: normalizedProjectRows.filter((thread) => !!thread?.has_unread).length,
        }));
        const fallbackThread = preferredThreadId
            || normalizedProjectRows[0]?.id
            || normalizedInboxRows[0]?.id
            || normalizedOutboxRows[0]?.id
            || null;
        setSelectedReviewThreadId(fallbackThread);
        return {
            projectRows: normalizedProjectRows,
            inboxRows: normalizedInboxRows,
            outboxRows: normalizedOutboxRows,
            fallbackThread,
        };
    };

    const loadReviewThreadDetail = async (threadId, preferredRoundId = null) => {
        if (!threadId) {
            setSelectedReviewThread(null);
            setSelectedReviewRounds([]);
            setSelectedReviewRoundId(null);
            setSelectedReviewMessages([]);
            return;
        }
        const [thread, rounds] = await Promise.all([
            fetchReviewThread(threadId),
            fetchReviewThreadRounds(threadId),
        ]);
        const normalizedRounds = Array.isArray(rounds) ? rounds : [];
        const nextRoundId = preferredRoundId || normalizedRounds[normalizedRounds.length - 1]?.id || null;
        setSelectedReviewThread(thread || null);
        setSelectedReviewRounds(normalizedRounds);
        setSelectedReviewRoundId(nextRoundId);
        if (!nextRoundId) {
            setSelectedReviewMessages([]);
            return;
        }
        const messages = await fetchReviewRoundMessages(nextRoundId);
        setSelectedReviewMessages(Array.isArray(messages) ? messages : []);
    };

    const refreshShareAndReviewModal = async (projectId, preferredThreadId = null) => {
        setShareLoading(true);
        setReviewLoading(true);
        try {
            await loadProjectSharesForModal(projectId);
            const reviewData = await loadReviewCollections(projectId, preferredThreadId);
            if (reviewData.fallbackThread) {
                await loadReviewThreadDetail(reviewData.fallbackThread);
            } else {
                setSelectedReviewThread(null);
                setSelectedReviewRounds([]);
                setSelectedReviewRoundId(null);
                setSelectedReviewMessages([]);
            }
        } finally {
            setShareLoading(false);
            setReviewLoading(false);
        }
    };

    const handleOpenShareModal = async (event, project) => {
        event.stopPropagation();
        if (!isProjectOwner(project)) return;
        setShareModalProject(project);
        setShareModalTab('share');
        setReviewListMode('project');
        setShareTargetUser('');
        setShareTargetRole('editor');
        setShareTargetCanReview(false);
        setReviewThreadForm(createDefaultReviewThreadForm());
        setReviewMessageForm(createDefaultReviewMessageForm());
        setReviewRoundForm(createDefaultReviewRoundForm());
        try {
            await refreshShareAndReviewModal(project.id);
        } catch (error) {
            console.error('Failed to load project collaboration data', error);
            setProjectShares([]);
            setProjectReviewThreads([]);
            setReviewInboxThreads([]);
            setReviewOutboxThreads([]);
            setSelectedReviewThread(null);
            setSelectedReviewRounds([]);
            setSelectedReviewRoundId(null);
            setSelectedReviewMessages([]);
            setToast({ type: 'error', message: t('加载共享或审核数据失败', 'Failed to load sharing or review data') });
            setTimeout(() => setToast(null), 3000);
        }
    };

    const handleCreateShare = async () => {
        if (!shareModalProject) return;
        const target = String(shareTargetUser || '').trim();
        if (!target) return;

        setShareSubmitting(true);
        try {
            await createProjectShare(shareModalProject.id, target, {
                role: shareTargetRole,
                permissions: {
                    can_review_assets: shareTargetRole === 'reviewer' || !!shareTargetCanReview,
                },
            });
            await loadProjectSharesForModal(shareModalProject.id);
            setShareTargetUser('');
            setShareTargetRole('editor');
            setShareTargetCanReview(false);
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
            const nextShares = projectShares.filter((item) => Number(item.user_id) !== Number(sharedUserId));
            setProjectShares(nextShares);
            setProjectShareCounts((prev) => ({ ...prev, [shareModalProject.id]: nextShares.length }));
        } catch (error) {
            console.error('Failed to delete share', error);
            setToast({ type: 'error', message: t('取消共享失败', 'Failed to revoke share') });
            setTimeout(() => setToast(null), 3000);
        }
    };

    const handleUpdateShareRole = async (share) => {
        if (!shareModalProject || !share) return;
        const nextRole = String(shareRoleDrafts?.[share.user_id] || share.role || 'editor').trim().toLowerCase() || 'editor';
        const nextCanReview = !!sharePermissionDrafts?.[share.user_id]?.can_review_assets;
        setShareSubmitting(true);
        try {
            await createProjectShare(shareModalProject.id, share.username || share.email, {
                role: nextRole,
                permissions: {
                    can_review_assets: nextRole === 'reviewer' || nextCanReview,
                },
            });
            await loadProjectSharesForModal(shareModalProject.id);
            setToast({ type: 'success', message: t('角色已更新', 'Share role updated') });
            setTimeout(() => setToast(null), 2500);
        } catch (error) {
            console.error('Failed to update share role', error);
            setToast({ type: 'error', message: error?.response?.data?.detail || t('角色更新失败', 'Failed to update share role') });
            setTimeout(() => setToast(null), 3000);
        } finally {
            setShareSubmitting(false);
        }
    };

    const handleSelectReviewThread = async (threadId, preferredRoundId = null) => {
        setSelectedReviewThreadId(threadId || null);
        setReviewLoading(true);
        try {
            await markReviewThreadRead(threadId);
            await loadReviewThreadDetail(threadId, preferredRoundId);
            setReviewMessageForm(createDefaultReviewMessageForm());
            setReviewRoundForm(createDefaultReviewRoundForm());
            if (shareModalProject?.id) {
                await loadReviewCollections(shareModalProject.id, threadId);
            }
        } catch (error) {
            console.error('Failed to load review thread detail', error);
            setToast({ type: 'error', message: error?.response?.data?.detail || t('加载审核详情失败', 'Failed to load review details') });
            setTimeout(() => setToast(null), 3000);
        } finally {
            setReviewLoading(false);
        }
    };

    const handleSelectReviewRound = async (roundId) => {
        if (!roundId) return;
        setSelectedReviewRoundId(roundId);
        setReviewLoading(true);
        try {
            const messages = await fetchReviewRoundMessages(roundId);
            setSelectedReviewMessages(Array.isArray(messages) ? messages : []);
            setReviewMessageForm(createDefaultReviewMessageForm());
        } catch (error) {
            console.error('Failed to load review round messages', error);
            setToast({ type: 'error', message: error?.response?.data?.detail || t('加载轮次消息失败', 'Failed to load round messages') });
            setTimeout(() => setToast(null), 3000);
        } finally {
            setReviewLoading(false);
        }
    };

    const handleRefreshReviews = async (preferredThreadId = null) => {
        if (!shareModalProject) return;
        setReviewLoading(true);
        try {
            const reviewData = await loadReviewCollections(shareModalProject.id, preferredThreadId || selectedReviewThreadId);
            if (reviewData.fallbackThread) {
                await loadReviewThreadDetail(preferredThreadId || selectedReviewThreadId || reviewData.fallbackThread, selectedReviewRoundId);
            } else {
                setSelectedReviewThread(null);
                setSelectedReviewRounds([]);
                setSelectedReviewRoundId(null);
                setSelectedReviewMessages([]);
            }
        } catch (error) {
            console.error('Failed to refresh reviews', error);
            setToast({ type: 'error', message: error?.response?.data?.detail || t('刷新审核失败', 'Failed to refresh reviews') });
            setTimeout(() => setToast(null), 3000);
        } finally {
            setReviewLoading(false);
        }
    };

    const handleCreateReviewRequest = async () => {
        if (!shareModalProject) return;
        const reviewerUser = String(reviewThreadForm.reviewer_user || '').trim();
        if (!reviewerUser) {
            setToast({ type: 'error', message: t('请输入审核人用户名或邮箱', 'Enter reviewer username or email') });
            setTimeout(() => setToast(null), 2500);
            return;
        }
        if (!reviewThreadForm.entity_required && !reviewThreadForm.shot_required) {
            setToast({ type: 'error', message: t('至少选择资产或镜头审核', 'Choose asset or shot review at minimum') });
            setTimeout(() => setToast(null), 2500);
            return;
        }
        setReviewSubmitting(true);
        try {
            const created = await createProjectReviewThread(shareModalProject.id, {
                reviewer_user: reviewerUser,
                title: reviewThreadForm.title,
                request_message: reviewThreadForm.request_message,
                scope_type: 'all_current',
                entity_required: !!reviewThreadForm.entity_required,
                shot_required: !!reviewThreadForm.shot_required,
            });
            setReviewThreadForm(createDefaultReviewThreadForm());
            await handleRefreshReviews(created?.id || null);
            setReviewListMode('project');
            if (created?.id) {
                await handleSelectReviewThread(created.id);
            }
            setToast({ type: 'success', message: t('审核请求已发起', 'Review request created') });
            setTimeout(() => setToast(null), 2500);
        } catch (error) {
            console.error('Failed to create review request', error);
            setToast({ type: 'error', message: error?.response?.data?.detail || t('发起审核失败', 'Failed to create review request') });
            setTimeout(() => setToast(null), 3000);
        } finally {
            setReviewSubmitting(false);
        }
    };

    const handleCreateReviewRound = async () => {
        if (!selectedReviewThreadId) return;
        if (!reviewRoundForm.entity_required && !reviewRoundForm.shot_required) {
            setToast({ type: 'error', message: t('至少选择资产或镜头审核', 'Choose asset or shot review at minimum') });
            setTimeout(() => setToast(null), 2500);
            return;
        }
        setReviewSubmitting(true);
        try {
            const created = await createReviewThreadRound(selectedReviewThreadId, {
                request_message: reviewRoundForm.request_message,
                scope_type: 'all_current',
                entity_required: !!reviewRoundForm.entity_required,
                shot_required: !!reviewRoundForm.shot_required,
            });
            setReviewRoundForm(createDefaultReviewRoundForm());
            await handleRefreshReviews(selectedReviewThreadId);
            if (created?.id) {
                await handleSelectReviewThread(selectedReviewThreadId, created.id);
            }
            setToast({ type: 'success', message: t('新一轮审核已发起', 'New review round created') });
            setTimeout(() => setToast(null), 2500);
        } catch (error) {
            console.error('Failed to create review round', error);
            setToast({ type: 'error', message: error?.response?.data?.detail || t('发起新一轮失败', 'Failed to create next review round') });
            setTimeout(() => setToast(null), 3000);
        } finally {
            setReviewSubmitting(false);
        }
    };

    const handleCreateReviewMessage = async () => {
        if (!selectedReviewRoundId || !selectedReviewThread) return;
        const payload = {
            message_text: reviewMessageForm.message_text,
            message_type: 'message',
        };
        const amReviewer = Number(currentUser?.id) === Number(selectedReviewThread.reviewer_user_id);
        if (amReviewer) {
            payload.entity_decision = reviewMessageForm.entity_decision;
            payload.shot_decision = reviewMessageForm.shot_decision;
            payload.entity_feedback = reviewMessageForm.entity_feedback;
            payload.shot_feedback = reviewMessageForm.shot_feedback;
        }
        setReviewSubmitting(true);
        try {
            await createReviewRoundMessage(selectedReviewRoundId, payload);
            setReviewMessageForm(createDefaultReviewMessageForm());
            await handleSelectReviewThread(selectedReviewThreadId, selectedReviewRoundId);
            await handleRefreshReviews(selectedReviewThreadId);
            setToast({ type: 'success', message: t('审核回复已发送', 'Review reply sent') });
            setTimeout(() => setToast(null), 2500);
        } catch (error) {
            console.error('Failed to create review message', error);
            setToast({ type: 'error', message: error?.response?.data?.detail || t('发送审核回复失败', 'Failed to send review reply') });
            setTimeout(() => setToast(null), 3000);
        } finally {
            setReviewSubmitting(false);
        }
    };

    const handleUpdateReviewStatus = async (status) => {
        if (!selectedReviewThreadId) return;
        setReviewStatusSubmitting(true);
        try {
            await updateReviewThreadStatus(selectedReviewThreadId, status);
            await handleRefreshReviews(selectedReviewThreadId);
            await handleSelectReviewThread(selectedReviewThreadId, selectedReviewRoundId);
            setToast({ type: 'success', message: t('审核状态已更新', 'Review status updated') });
            setTimeout(() => setToast(null), 2500);
        } catch (error) {
            console.error('Failed to update review status', error);
            setToast({ type: 'error', message: error?.response?.data?.detail || t('更新审核状态失败', 'Failed to update review status') });
            setTimeout(() => setToast(null), 3000);
        } finally {
            setReviewStatusSubmitting(false);
        }
    };

    const visibleReviewThreads = reviewListMode === 'inbox'
        ? reviewInboxThreads
        : reviewListMode === 'outbox'
            ? reviewOutboxThreads
            : projectReviewThreads;

    const selectedReviewRound = selectedReviewRounds.find((item) => Number(item.id) === Number(selectedReviewRoundId)) || selectedReviewRounds[selectedReviewRounds.length - 1] || null;
    const eligibleReviewerShares = projectShares.filter((item) => {
        const role = String(item?.role || 'editor').trim().toLowerCase();
        return role === 'editor' || role === 'reviewer' || !!item?.permissions?.can_review_assets;
    });
    const canManageSelectedReview = !!selectedReviewThread && (
        Number(currentUser?.id) === Number(selectedReviewThread.requester_user_id)
        || Number(currentUser?.id) === Number(shareModalProject?.owner_id)
    );
    const amSelectedReviewReviewer = !!selectedReviewThread && Number(currentUser?.id) === Number(selectedReviewThread.reviewer_user_id);

    const activeTabTitle = activeTab === 'projects'
        ? t('我的项目', 'My Projects')
        : activeTab === 'assets'
            ? t('素材库', 'Assets Library')
            : activeTab === 'settings'
                ? t('设置', 'Settings')
                : activeTab === 'about'
                    ? t('关于', 'About')
                    : activeTab;

    const activeTabDescription = activeTab === 'projects'
        ? t('管理和编辑你的分镜脚本。', 'Manage and edit your storyboard scripts.')
        : activeTab === 'assets'
            ? t('管理你生成的角色和场景素材。', 'Manage your generated characters and scenes.')
            : activeTab === 'settings'
                ? t('管理你的账户偏好设置。', 'Manage your account preferences.')
                : activeTab === 'about'
                    ? t('了解产品定位与支持方式。', 'Learn about the product and support channels.')
                    : '';

    const openSettingsPage = () => {
        trackMenuAction('project_list.sidebar.settings', t('设置', 'Settings'), () => {
            setActiveTab('settings');
            setSelectedProjectId(null);
            const returnTo = encodeURIComponent(`${location.pathname}${location.search}${location.hash}`);
            navigate(`/settings?return_to=${returnTo}`);
        });
    };

    const openUserAdminPage = () => {
        trackMenuAction('project_list.admin.user_admin', t('管理面板', 'Admin Panel'), () => navigate('/admin/users'));
    };

    const totalUnreadReviewCount = Object.values(projectUnreadReviewCounts || {}).reduce((sum, value) => sum + Number(value || 0), 0);

    const SidebarActionItem = ({ id, icon: Icon, label, disabled, onClick, active = false, compact = false, mobile = false, iconClassName = '', badgeCount = 0 }) => (
        <button 
            onClick={() => {
                if (disabled) return;
                onClick?.();
                if (mobile) {
                    setIsMobileSidebarOpen(false);
                }
            }}
            className={`w-full flex items-center ${compact ? 'justify-center px-3' : 'gap-3 px-4'} py-3 rounded-lg text-sm font-medium transition-colors ${
                active
                ? 'bg-primary text-primary-foreground' 
                : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
            } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
            title={label}
        >
            <Icon className={`w-5 h-5 ${iconClassName}`.trim()} />
            {!compact && <span className="truncate">{label}</span>}
            {badgeCount > 0 && (
                compact ? (
                    <span className="absolute right-2 top-2 inline-flex min-w-4 items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-semibold text-black">
                        {badgeCount > 99 ? '99+' : badgeCount}
                    </span>
                ) : (
                    <span className="ml-auto inline-flex min-w-5 items-center justify-center rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-semibold text-black">
                        {badgeCount > 99 ? '99+' : badgeCount}
                    </span>
                )
            )}
        </button>
    );

    const SidebarItem = ({ id, icon: Icon, label, disabled, compact = isSidebarCollapsed, mobile = false, badgeCount = 0 }) => (
        <SidebarActionItem
            id={id}
            icon={Icon}
            label={label}
            disabled={disabled}
            compact={compact}
            mobile={mobile}
            badgeCount={badgeCount}
            active={activeTab === id && !selectedProjectId}
            onClick={() => {
                trackMenuAction(`project_list.sidebar.${id}`, label, () => {
                    setActiveTab(id);
                    setRestoredEditorState(null);
                    setSelectedProjectId(null);
                });
            }}
        />
    );

    // If a project is selected, show the full-screen Editor immediately
    if (selectedProjectId) {
        return (
            <Editor
                projectId={selectedProjectId}
                onClose={() => {
                    setSelectedProjectId(null);
                    setRestoredEditorState(null);
                }}
                initialActiveTab={restoredEditorState?.activeTab || 'overview'}
                initialEpisodeId={restoredEditorState?.activeEpisodeId ?? null}
                initialEditingShotId={restoredEditorState?.editingShotId ?? null}
                initialEditingShotSceneId={restoredEditorState?.editingShotSceneId ?? null}
            />
        );
    }

    return (
        <div className="flex h-screen bg-background text-foreground font-sans overflow-hidden">
             {toast && (
                <div className={`fixed bottom-8 right-8 px-6 py-3 rounded-lg shadow-xl text-white z-50 animate-in fade-in slide-in-from-bottom-4 bg-green-600`}>
                    {toast.message}
                </div>
            )}
            {isMobileSidebarOpen && (
                <button
                    type="button"
                    aria-label={t('关闭菜单', 'Close menu')}
                    onClick={() => setIsMobileSidebarOpen(false)}
                    className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
                />
            )}
            {/* Sidebar */}
            <aside className={`${isSidebarCollapsed ? 'w-20 p-3' : 'w-64 p-6'} hidden md:flex border-r bg-card/30 flex-col transition-all duration-300`}>
                <div className={`flex items-center ${isSidebarCollapsed ? 'justify-center' : 'justify-between'} mb-6 px-1`}>
                    <div className={`flex items-center gap-2 ${isSidebarCollapsed ? 'justify-center' : ''}`}>
                    <img src="/woola-transparent.png?v=4" alt="Woola Story" className="w-8 h-8 object-contain" />
                        {!isSidebarCollapsed && <span className="text-xl font-bold tracking-tight">Woola Story</span>}
                    </div>
                    {!isSidebarCollapsed && (
                        <button
                            type="button"
                            onClick={() => setIsSidebarCollapsed(true)}
                            title={t('收起侧边栏', 'Collapse sidebar')}
                            className="p-2 rounded-lg text-muted-foreground hover:bg-secondary/60 hover:text-foreground transition-colors"
                        >
                            <ChevronsLeft className="w-4 h-4" />
                        </button>
                    )}
                </div>

                {isSidebarCollapsed && (
                    <div className="mb-6 flex justify-center">
                        <button
                            type="button"
                            onClick={() => setIsSidebarCollapsed(false)}
                            title={t('展开侧边栏', 'Expand sidebar')}
                            className="p-2 rounded-lg text-muted-foreground hover:bg-secondary/60 hover:text-foreground transition-colors"
                        >
                            <ChevronsRight className="w-4 h-4" />
                        </button>
                    </div>
                )}

                <div className="space-y-2 flex-1">
                    <SidebarItem id="projects" icon={Folder} label={t('我的项目', 'My Projects')} badgeCount={totalUnreadReviewCount} />
                    <SidebarItem id="assets" icon={Image} label={t('素材库', 'Assets Library')} />
                    
                    {currentUser?.is_superuser && (
                        <>
                            <SidebarActionItem
                                icon={Shield}
                                label={t('管理面板', 'Admin Panel')}
                                compact={isSidebarCollapsed}
                                onClick={openUserAdminPage}
                                iconClassName="text-red-500"
                            />
                        </>
                    )}
                    <SidebarActionItem
                        icon={Settings}
                        label={t('设置', 'Settings')}
                        compact={isSidebarCollapsed}
                        onClick={openSettingsPage}
                    />
                    <SidebarItem id="about" icon={Info} label={t('关于', 'About')} />
                </div>

                <div className="mt-auto border-t pt-6">
                    <div className={`flex items-center ${isSidebarCollapsed ? 'justify-center' : 'gap-3'} px-2 mb-4`}>
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
                        {!isSidebarCollapsed && (
                            <div className="flex-1 overflow-hidden">
                                <p className="text-sm font-medium truncate">{currentUser?.full_name || currentUser?.username || t('访客用户', 'Guest User')}</p>
                                <p className="text-xs text-muted-foreground truncate" title={currentUser?.email}>{currentUser?.email || t('无账号', 'No Account')}</p>
                            </div>
                        )}
                    </div>
                    <button 
                        onClick={handleLogout}
                        className={`w-full flex items-center ${isSidebarCollapsed ? 'justify-center' : 'gap-2'} px-2 text-sm text-muted-foreground hover:text-destructive transition-colors`}
                        title={t('退出登录', 'Sign Out')}
                    >
                        <LogOut className="w-4 h-4" /> {!isSidebarCollapsed && t('退出登录', 'Sign Out')}
                    </button>
                </div>
            </aside>

            <aside className={`fixed inset-y-0 left-0 z-50 w-[min(88vw,22rem)] border-r border-white/10 bg-card/95 backdrop-blur-xl flex flex-col p-5 transition-transform duration-300 md:hidden ${isMobileSidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
                <div className="flex items-center justify-between mb-6 gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                        <img src="/woola-transparent.png?v=4" alt="Woola Story" className="w-8 h-8 object-contain" />
                        <div className="min-w-0">
                            <div className="font-semibold truncate">Woola Story</div>
                            <div className="text-xs text-muted-foreground truncate">{activeTabTitle}</div>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={() => setIsMobileSidebarOpen(false)}
                        title={t('关闭菜单', 'Close menu')}
                        className="p-2 rounded-lg text-muted-foreground hover:bg-secondary/60 hover:text-foreground transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                <div className="space-y-2 flex-1 overflow-y-auto pr-1">
                    <SidebarItem id="projects" icon={Folder} label={t('我的项目', 'My Projects')} compact={false} mobile badgeCount={totalUnreadReviewCount} />
                    <SidebarItem id="assets" icon={Image} label={t('素材库', 'Assets Library')} compact={false} mobile />
                    {currentUser?.is_superuser && (
                        <>
                            <SidebarActionItem
                                icon={Shield}
                                label={t('管理面板', 'Admin Panel')}
                                compact={false}
                                mobile
                                onClick={openUserAdminPage}
                                iconClassName="text-red-500"
                            />
                        </>
                    )}
                    <SidebarActionItem
                        icon={Settings}
                        label={t('设置', 'Settings')}
                        compact={false}
                        mobile
                        onClick={openSettingsPage}
                    />
                    <SidebarItem id="about" icon={Info} label={t('关于', 'About')} compact={false} mobile />
                </div>

                <div className="mt-5 border-t border-white/10 pt-5">
                    <div className="flex items-center gap-3 px-1 mb-4">
                        <div className="w-10 h-10 rounded-full bg-secondary flex items-center justify-center overflow-hidden">
                            {currentUser?.avatar_url ? (
                                <img
                                    src={getAvatarUrl(currentUser.avatar_url)}
                                    alt={currentUser?.full_name || currentUser?.username || 'avatar'}
                                    className="w-10 h-10 object-cover"
                                />
                            ) : (
                                <User className="w-5 h-5 text-muted-foreground" />
                            )}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{currentUser?.full_name || currentUser?.username || t('访客用户', 'Guest User')}</p>
                            <p className="text-xs text-muted-foreground truncate">{currentUser?.email || t('无账号', 'No Account')}</p>
                        </div>
                    </div>
                    <button 
                        onClick={() => {
                            setIsMobileSidebarOpen(false);
                            handleLogout();
                        }}
                        className="w-full flex items-center gap-2 px-2 text-sm text-muted-foreground hover:text-destructive transition-colors"
                        title={t('退出登录', 'Sign Out')}
                    >
                        <LogOut className="w-4 h-4" /> {t('退出登录', 'Sign Out')}
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto bg-background/50 relative flex flex-col">
                <div className="sticky top-0 z-30 border-b border-white/10 bg-background/90 backdrop-blur-xl px-4 py-3 sm:px-6 md:hidden">
                    <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                            <div className="text-xs uppercase tracking-[0.22em] text-muted-foreground/80">{t('工作区', 'Workspace')}</div>
                            <div className="text-base font-semibold truncate">{activeTabTitle}</div>
                        </div>
                        <button
                            type="button"
                            onClick={() => setIsMobileSidebarOpen(true)}
                            className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium"
                        >
                            <Menu className="w-4 h-4" />
                            {t('菜单', 'Menu')}
                        </button>
                    </div>
                    {activeTabDescription && (
                        <p className="mt-2 text-sm text-muted-foreground line-clamp-2">{activeTabDescription}</p>
                    )}
                </div>

                <div className="max-w-7xl mx-auto w-full px-4 pt-6 pb-4 sm:px-6 lg:px-12 md:pt-8 relative z-40">
                    {/* Header */}
                    <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                        <div>
                            <h1 className="text-3xl font-bold tracking-tight capitalize">
                                {activeTabTitle}
                            </h1>
                            <p className="text-muted-foreground mt-1">
                                {activeTabDescription}
                            </p>
                        </div>
                        {activeTab === 'projects' && (
                            <div className="flex flex-wrap items-center gap-3 sm:gap-4">
                                {selectedProjectId ? (
                                    <button 
                                        onClick={() => setSelectedProjectId(null)}
                                        className="flex items-center gap-2 px-5 py-2.5 bg-secondary text-secondary-foreground rounded-full hover:bg-secondary/80 transition-all font-medium"
                                    >
                                        <ArrowLeft className="w-4 h-4" /> {t('返回项目列表', 'Back to Projects')}
                                    </button>
                                ) : (
                                    <>
                                        <button
                                            onClick={() => {
                                                setActiveTab('projects');
                                                setSelectedProjectId(null);
                                                window.scrollTo?.({ top: 0, behavior: 'smooth' });
                                            }}
                                            title={t('未读审核', 'Unread reviews')}
                                            className="relative p-2.5 rounded-full bg-secondary/60 text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
                                        >
                                            <Bell className="w-4 h-4" />
                                            {totalUnreadReviewCount > 0 && (
                                                <span className="absolute -right-1 -top-1 inline-flex min-w-5 items-center justify-center rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-semibold text-black">
                                                    {totalUnreadReviewCount > 99 ? '99+' : totalUnreadReviewCount}
                                                </span>
                                            )}
                                        </button>
                                        <div className="relative hidden md:block">
                                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                            <input 
                                                type="text" 
                                                placeholder={t('搜索项目...', 'Search projects...')} 
                                                className="pl-9 pr-4 py-2 bg-secondary/50 border-none rounded-full text-sm focus:ring-1 focus:ring-primary w-64"
                                            />
                                        </div>
                                        <button 
                                            onClick={() => {
                                                resetCreateProjectForm();
                                                setIsCreating(true);
                                            }}
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
                 <div className="h-28 sm:h-40 relative overflow-hidden group w-full select-none border-b border-white/5 shrink-0">
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

                <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-12 pb-12 mt-4 relative z-30 flex-1 flex flex-col">
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
                                        className="mb-8 p-6 border border-white/15 bg-gradient-to-br from-card to-card/90 rounded-2xl shadow-xl shadow-black/15"
                                    >
                                        <div className="mb-4 pb-3 border-b border-white/10">
                                            <h3 className="text-lg sm:text-xl font-bold tracking-wide text-white">{t('新建项目', 'Create Project')}</h3>
                                            <p className="text-xs sm:text-sm text-muted-foreground mt-1">{t('先填写核心字段，协作设置可按需展开。', 'Fill core fields first, and expand collaboration settings when needed.')}</p>
                                        </div>

                                        <label className="block text-sm font-semibold tracking-wide text-primary mb-2">{t('项目标题', 'Project Title')}</label>
                                        <div className="flex gap-3 mb-4">
                                            <input 
                                                className="flex-1 px-4 py-2.5 bg-background border border-white/15 rounded-lg focus:ring-2 focus:ring-primary/30 focus:border-primary/50 outline-none" 
                                                value={newTitle} 
                                                onChange={e => setNewTitle(e.target.value)} 
                                                placeholder={t('例如：最后的地平线 - 场景1', 'e.g., The Last Horizon - Scene 1')}
                                                autoFocus
                                            />
                                            <button onClick={handleCreate} className="px-6 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700">{t('创建', 'Create')}</button>
                                            <button onClick={() => {
                                                setIsCreating(false);
                                                resetCreateProjectForm();
                                            }} className="px-6 py-2.5 bg-secondary text-secondary-foreground rounded-lg font-medium hover:bg-secondary/80">{t('取消', 'Cancel')}</button>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
                                            <div>
                                                <label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">{t('类型', 'Type')}</label>
                                                <select className="w-full px-3 py-2.5 bg-background border rounded-lg" value={newType} onChange={(e) => setNewType(e.target.value)}>
                                                    {projectCreateOptions.type.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                                                </select>
                                            </div>
                                            <div>
                                                <label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">{t('语言', 'Language')}</label>
                                                <select className="w-full px-3 py-2.5 bg-background border rounded-lg" value={newLanguage} onChange={(e) => setNewLanguage(e.target.value)}>
                                                    {projectCreateOptions.language.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                                                </select>
                                            </div>
                                            <div>
                                                <label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">{t('基础定位', 'Base Positioning')}</label>
                                                <select className="w-full px-3 py-2.5 bg-background border rounded-lg" value={newBasePositioning} onChange={(e) => setNewBasePositioning(e.target.value)}>
                                                    {projectCreateOptions.base_positioning.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                                                </select>
                                            </div>
                                            <div>
                                                <label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">{t('画幅比例', 'Aspect Ratio')}</label>
                                                <select className="w-full px-3 py-2.5 bg-background border rounded-lg" value={newAspectRatio} onChange={(e) => setNewAspectRatio(e.target.value)}>
                                                    {projectCreateOptions.aspect_ratio.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                                                </select>
                                            </div>
                                            <div>
                                                <label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">{t('图像尺寸', 'Image Size')}</label>
                                                <select className="w-full px-3 py-2.5 bg-background border rounded-lg" value={newImageSize} onChange={(e) => setNewImageSize(e.target.value)}>
                                                    {projectCreateOptions.image_size.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                                                </select>
                                            </div>
                                        </div>

                                        <label className="flex items-center gap-2 text-sm mt-1 mb-1 cursor-pointer select-none">
                                            <input
                                                type="checkbox"
                                                className="h-4 w-4"
                                                checked={newVideoSoundEnabled}
                                                onChange={(e) => setNewVideoSoundEnabled(Boolean(e.target.checked))}
                                            />
                                            <span>{t('视频生成默认开启声音', 'Enable sound by default for video generation')}</span>
                                        </label>

                                        <label className="block text-sm font-semibold tracking-wide text-primary mt-4 mb-2">{t('项目描述（可选）', 'Project Description (Optional)')}</label>
                                        <textarea
                                            className="w-full px-4 py-2.5 bg-background border border-white/15 rounded-lg focus:ring-2 focus:ring-primary/30 focus:border-primary/50 outline-none resize-y min-h-[84px]"
                                            value={newDescription}
                                            onChange={e => setNewDescription(e.target.value)}
                                            placeholder={t('可留空。用于记录项目背景、目标或备注', 'Can be left empty. Add context, goals, or notes for this project')}
                                        />

                                        <div className="mt-5 rounded-xl border border-white/10 bg-black/15">
                                            <button
                                                type="button"
                                                onClick={() => setIsCreateSceneAnalysisCollapsed((prev) => !prev)}
                                                className="w-full px-4 py-3 flex items-center justify-between gap-3 text-left"
                                            >
                                                <div>
                                                    <div className="text-sm font-semibold tracking-wide text-primary">
                                                        {t('场景分析维度（可选）', 'Scene Analysis Dimensions (Optional)')}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground mt-0.5">
                                                        {t('用于 Skill 决策引擎路由；默认建议主目标=剧本优化，次目标=人物创作。', 'Used by the skill decision engine for routing; recommended default is primary goal = script optimization and secondary goal = character creation.')}
                                                    </div>
                                                </div>
                                                <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${isCreateSceneAnalysisCollapsed ? '' : 'rotate-180'}`} />
                                            </button>

                                            {!isCreateSceneAnalysisCollapsed && (
                                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 px-4 pb-4">
                                                    {PROJECT_SCENE_ANALYSIS_CREATE_FIELDS.map((field) => (
                                                        <div key={`project-create-dimension-${field.key}`}>
                                                            <label className="block text-xs font-semibold tracking-wide mb-1 text-primary/95">{t(field.labelZh, field.labelEn)}</label>
                                                            <select
                                                                className="w-full px-3 py-2.5 bg-background border rounded-lg"
                                                                value={String(newSceneAnalysisConfig?.[field.key] || '')}
                                                                onChange={(e) => setNewSceneAnalysisConfig((prev) => ({
                                                                    ...(prev || {}),
                                                                    [field.key]: e.target.value,
                                                                }))}
                                                            >
                                                                <option value="">{t('未指定', 'Unspecified')}</option>
                                                                {field.options.map((opt) => <option key={`${field.key}-${opt}`} value={opt}>{opt}</option>)}
                                                            </select>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>

                                        <div className="mt-5 rounded-xl border border-white/10 bg-black/15">
                                            <button
                                                type="button"
                                                onClick={() => setIsCreateCollaboratorsCollapsed((prev) => !prev)}
                                                className="w-full px-4 py-3 flex items-center justify-between gap-3 text-left"
                                            >
                                                <div>
                                                    <div className="text-sm font-semibold tracking-wide text-primary">
                                                        {t('共享与审核（可选）', 'Share & Review (Optional)')}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground mt-0.5">
                                                        {t('默认收起，不影响项目创建。', 'Collapsed by default and does not affect project creation.')}
                                                    </div>
                                                </div>
                                                <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${isCreateCollaboratorsCollapsed ? '' : 'rotate-180'}`} />
                                            </button>

                                            {!isCreateCollaboratorsCollapsed && (
                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 px-4 pb-4">
                                                    <div>
                                                        <label className="block text-xs font-semibold tracking-wide mb-2 text-primary/95">{t('分享人（可选，可多个）', 'Share Users (Optional, Multiple)')}</label>
                                                        <textarea
                                                            className="w-full px-4 py-2.5 bg-background border border-white/15 rounded-lg focus:ring-2 focus:ring-primary/30 focus:border-primary/50 outline-none resize-y min-h-[96px]"
                                                            value={newShareUsers}
                                                            onChange={(e) => setNewShareUsers(e.target.value)}
                                                            placeholder={t('输入用户名或邮箱，支持逗号、分号或换行分隔', 'Enter usernames or emails, separated by commas, semicolons, or new lines')}
                                                        />
                                                        <div className="mt-2 text-xs text-muted-foreground">
                                                            {formatParsedUserHint(newShareUsers, t)}
                                                        </div>
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs font-semibold tracking-wide mb-2 text-primary/95">{t('审核人（可选，可多个）', 'Reviewer Users (Optional, Multiple)')}</label>
                                                        <textarea
                                                            className="w-full px-4 py-2.5 bg-background border border-white/15 rounded-lg focus:ring-2 focus:ring-primary/30 focus:border-primary/50 outline-none resize-y min-h-[96px]"
                                                            value={newReviewerUsers}
                                                            onChange={(e) => setNewReviewerUsers(e.target.value)}
                                                            placeholder={t('输入用户名或邮箱，保存时校验是否存在', 'Enter usernames or emails. Existence will be validated on save')}
                                                        />
                                                        <div className="mt-2 text-xs text-muted-foreground">
                                                            {formatParsedUserHint(newReviewerUsers, t)}
                                                        </div>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </motion.div>
                                )}

                                {!isCreating && isProjectsLoading && projects.length === 0 ? (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                                        {Array.from({ length: 8 }).map((_, idx) => (
                                            <div key={`project-skeleton-${idx}`} className="bg-card/40 border border-white/5 rounded-3xl overflow-hidden animate-pulse">
                                                <div className="aspect-video w-full bg-white/5" />
                                                <div className="p-4 space-y-3">
                                                    <div className="h-5 bg-white/10 rounded w-2/3" />
                                                    <div className="h-3 bg-white/10 rounded w-full" />
                                                    <div className="h-3 bg-white/10 rounded w-3/4" />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : projects.length === 0 && !isCreating && hasLoadedProjectsOnce ? (
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
                                            onClick={() => {
                                                resetCreateProjectForm();
                                                setIsCreating(true);
                                            }}
                                            className="px-8 py-3 rounded-full bg-primary/20 border border-primary/50 text-white font-medium hover:bg-primary/30 transition-all hover:scale-105"
                                        >
                                            {t('创建第一个项目', 'Create First Project')}
                                        </button>
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                                        {projects.map(p => (
                                            <div onClick={() => {
                                                setRestoredEditorState(null);
                                                setSelectedProjectId(p.id);
                                            }} key={p.id} className="cursor-pointer">
                                                <motion.div 
                                                    whileHover={{ y: -8, scale: 1.02 }}
                                                    transition={{ type: "spring", stiffness: 300, damping: 20 }}
                                                    className="group relative bg-card/40 backdrop-blur-md border border-white/5 rounded-3xl overflow-hidden hover:border-primary/50 transition-all shadow-lg hover:shadow-2xl hover:shadow-primary/10"
                                                >
                                                    {/* Card Image Area - 16:9 Aspect Ratio */}
                                                    <div className="aspect-video w-full bg-black/60 relative overflow-hidden group-hover:bg-black/40 transition-colors">


                                                       {/* Cover Image or Fallback */}
                                                       {p.cover_image && (
                                                           <img 
                                                               src={p.cover_image.startsWith('http') ? p.cover_image : `${(BASE_URL || 'http://localhost:8000')}${p.cover_image}`} 
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
                                                                {getProjectUnreadReviewCount(p) > 0 && (
                                                                    <span className="rounded-full bg-amber-500 px-2 py-0.5 text-[11px] font-semibold text-black">
                                                                        {t('审核', 'Review')} {getProjectUnreadReviewCount(p)}
                                                                    </span>
                                                                )}
                                                                {isProjectOwner(p) && (
                                                                    <button
                                                                        onClick={(e) => handleGenerateProjectCover(e, p)}
                                                                        disabled={Boolean(coverGenerationByProject[p.id])}
                                                                        className="opacity-0 group-hover:opacity-100 p-1.5 text-muted-foreground hover:text-fuchsia-300 hover:bg-white/10 rounded-lg transition-all disabled:opacity-100 disabled:text-fuchsia-200"
                                                                        title={t('生成封面图', 'Generate Cover Image')}
                                                                    >
                                                                        {coverGenerationByProject[p.id] ? <Loader2 className="w-4 h-4 animate-spin" /> : <Image className="w-4 h-4" />}
                                                                    </button>
                                                                )}
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
                                                                {p.description || p.global_info?.notes || t('暂无描述。', 'No description added.')}
                                                            </p>
                                                            <p className="text-[11px] text-muted-foreground/80 mt-2 mb-4">
                                                                {getProjectShareCountText(p)}
                                                            </p>
                                                            {getProjectUnreadReviewCount(p) > 0 && (
                                                                <p className="text-[11px] text-amber-300 mb-4">
                                                                    {t(`有 ${getProjectUnreadReviewCount(p)} 条未读审核线程`, `${getProjectUnreadReviewCount(p)} unread review thread${getProjectUnreadReviewCount(p) === 1 ? '' : 's'}`)}
                                                                </p>
                                                            )}
                                                            
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

                        {activeTab === 'about' && (
                            <div className="bg-card/30 rounded-3xl border border-white/5 p-8 md:p-10">
                                <h2 className="text-2xl font-bold mb-4">{t('关于 Woola Story', 'About Woola Story')}</h2>
                                <p className="text-muted-foreground leading-relaxed mb-4">
                                    {t(
                                        'Woola Story 是一款面向影视与广告创作团队的 AI 分镜协作平台，帮助你把剧本、角色、场景与镜头计划串联为可执行的制作流程。',
                                        'Woola Story is an AI storyboard collaboration platform for film and creative teams, turning scripts, characters, scenes, and shot plans into an executable production workflow.'
                                    )}
                                </p>
                                <p className="text-muted-foreground leading-relaxed mb-6">
                                    {t(
                                        '你可以在这里完成剧本分析、镜头拆解、素材生成与项目协同，减少沟通成本并加快从创意到交付的速度。',
                                        'You can run script analysis, shot breakdown, asset generation, and project collaboration here to reduce communication cost and speed up delivery from idea to final output.'
                                    )}
                                </p>
                                <div className="rounded-xl border border-white/10 bg-background/50 p-4">
                                    <div className="text-sm text-muted-foreground mb-1">{t('研发公司', 'R&D Company')}</div>
                                    <div className="mb-3">{t('厦门浪迹星科技有限公司', 'Xiamen Langjixing Technology Co., Ltd.')}</div>
                                    <div className="text-sm text-muted-foreground mb-1">{t('支持邮箱', 'Support Email')}</div>
                                    <a
                                        href="mailto:metawave@126.com"
                                        className="text-primary hover:underline break-all"
                                    >
                                        metawave@126.com
                                    </a>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </main>

            {shareModalProject && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setShareModalProject(null)}>
                    <div className="w-full max-w-6xl rounded-2xl border border-white/10 bg-card p-5" onClick={(e) => e.stopPropagation()}>
                        <div className="mb-4 flex items-center justify-between">
                            <div>
                                <h3 className="text-lg font-semibold">{t('项目协作', 'Project Collaboration')} · {shareModalProject.title}</h3>
                                <div className="mt-1 text-xs text-muted-foreground">{t('管理共享角色，并发起或处理资产/镜头审核。', 'Manage share roles and create or respond to asset/shot reviews.')}</div>
                            </div>
                            <button className="rounded p-1 text-muted-foreground hover:bg-secondary" onClick={() => setShareModalProject(null)}>
                                <X className="h-4 w-4" />
                            </button>
                        </div>

                        <div className="mb-4 flex flex-wrap items-center gap-2 border-b border-white/10 pb-4">
                            {['share', 'review'].map((tab) => (
                                <button
                                    key={tab}
                                    onClick={() => setShareModalTab(tab)}
                                    className={`rounded-full px-4 py-2 text-sm transition ${shareModalTab === tab ? 'bg-primary text-primary-foreground' : 'bg-secondary/60 text-muted-foreground hover:text-foreground'}`}
                                >
                                    <span className="inline-flex items-center gap-2">
                                        <span>{tab === 'share' ? t('共享角色', 'Share Roles') : t('资产审核', 'Asset Reviews')}</span>
                                        {tab === 'review' && reviewInboxThreads.filter((thread) => !!thread?.has_unread).length > 0 && (
                                            <span className="rounded-full bg-amber-500 px-2 py-0.5 text-[11px] font-semibold text-black">
                                                {reviewInboxThreads.filter((thread) => !!thread?.has_unread).length}
                                            </span>
                                        )}
                                    </span>
                                </button>
                            ))}
                        </div>

                        {shareModalTab === 'share' ? (
                            <div className="grid gap-4 lg:grid-cols-[1.1fr_1.6fr]">
                                <div className="rounded-2xl border border-white/10 bg-background/40 p-4">
                                    <div className="mb-3 text-sm font-semibold">{t('添加协作者', 'Add Collaborator')}</div>
                                    <div className="grid gap-3">
                                        <input
                                            value={shareTargetUser}
                                            onChange={(e) => setShareTargetUser(e.target.value)}
                                            placeholder={t('输入用户名或邮箱', 'Enter username or email')}
                                            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                        />
                                        <select
                                            value={shareTargetRole}
                                            onChange={(e) => setShareTargetRole(e.target.value)}
                                            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                        >
                                            {PROJECT_SHARE_ROLE_OPTIONS.map((role) => (
                                                <option key={role} value={role}>{getProjectShareRoleLabel(role, t)}</option>
                                            ))}
                                        </select>
                                        <label className="flex items-center gap-2 text-sm text-muted-foreground">
                                            <input
                                                type="checkbox"
                                                checked={shareTargetRole === 'reviewer' ? true : shareTargetCanReview}
                                                disabled={shareTargetRole === 'reviewer'}
                                                onChange={(e) => setShareTargetCanReview(e.target.checked)}
                                            />
                                            {t('允许资产审核', 'Allow asset reviews')}
                                        </label>
                                        <button
                                            onClick={handleCreateShare}
                                            disabled={shareSubmitting || !String(shareTargetUser || '').trim()}
                                            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                                        >
                                            {shareSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                                            {t('添加协作者', 'Add Collaborator')}
                                        </button>
                                    </div>
                                </div>

                                <div className="rounded-2xl border border-white/10 bg-background/40 p-4">
                                    <div className="mb-3 flex items-center justify-between">
                                        <div className="text-sm font-semibold">{t('当前协作者', 'Current Collaborators')}</div>
                                        <div className="text-xs text-muted-foreground">{t(`共 ${projectShares.length} 人`, `${projectShares.length} users`)}</div>
                                    </div>
                                    <div className="max-h-[28rem] overflow-auto rounded-lg border border-white/10">
                                        {shareLoading ? (
                                            <div className="p-4 text-sm text-muted-foreground">{t('加载中...', 'Loading...')}</div>
                                        ) : projectShares.length === 0 ? (
                                            <div className="p-4 text-sm text-muted-foreground">{t('暂无共享用户', 'No shared users')}</div>
                                        ) : (
                                            <div className="divide-y divide-white/10">
                                                {projectShares.map((s) => {
                                                    const draftRole = shareRoleDrafts?.[s.user_id] || s.role || 'editor';
                                                    const draftCanReview = draftRole === 'reviewer' ? true : !!sharePermissionDrafts?.[s.user_id]?.can_review_assets;
                                                    return (
                                                        <div key={s.id} className="grid gap-3 px-3 py-3 lg:grid-cols-[1.2fr_0.8fr_0.8fr_auto_auto] lg:items-center">
                                                            <div>
                                                                <div className="flex items-center gap-2">
                                                                    <div className="text-sm font-medium">{s.username}</div>
                                                                    <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-muted-foreground">{getProjectShareRoleLabel(s.role, t)}</span>
                                                                </div>
                                                                <div className="text-xs text-muted-foreground">{s.email || '-'}</div>
                                                            </div>
                                                            <select
                                                                value={draftRole}
                                                                onChange={(e) => setShareRoleDrafts((prev) => ({ ...prev, [s.user_id]: e.target.value }))}
                                                                className="rounded-lg border bg-background px-2 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                                            >
                                                                {PROJECT_SHARE_ROLE_OPTIONS.map((role) => (
                                                                    <option key={role} value={role}>{getProjectShareRoleLabel(role, t)}</option>
                                                                ))}
                                                            </select>
                                                            <label className="flex items-center gap-2 text-xs text-muted-foreground">
                                                                <input
                                                                    type="checkbox"
                                                                    checked={draftCanReview}
                                                                    disabled={draftRole === 'reviewer'}
                                                                    onChange={(e) => setSharePermissionDrafts((prev) => ({
                                                                        ...prev,
                                                                        [s.user_id]: {
                                                                            ...(prev?.[s.user_id] || {}),
                                                                            can_review_assets: e.target.checked,
                                                                        },
                                                                    }))}
                                                                />
                                                                {t('可审核', 'Can review')}
                                                            </label>
                                                            <button
                                                                onClick={() => handleUpdateShareRole(s)}
                                                                disabled={shareSubmitting}
                                                                className="rounded-lg border border-primary/30 px-3 py-2 text-xs text-primary disabled:opacity-50"
                                                            >
                                                                {t('保存', 'Save')}
                                                            </button>
                                                            <button
                                                                onClick={() => handleDeleteShare(s.user_id)}
                                                                className="rounded-lg px-3 py-2 text-xs text-red-400 hover:bg-red-500/10"
                                                            >
                                                                {t('取消共享', 'Revoke')}
                                                            </button>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="grid gap-4 lg:grid-cols-[1.05fr_1.35fr]">
                                <div className="space-y-4">
                                    <div className="rounded-2xl border border-white/10 bg-background/40 p-4">
                                        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                                            <div className="text-sm font-semibold">{t('审核工作台', 'Review Workspace')}</div>
                                            <button
                                                onClick={() => handleRefreshReviews(selectedReviewThreadId)}
                                                disabled={reviewLoading}
                                                className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-muted-foreground disabled:opacity-50"
                                            >
                                                {reviewLoading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                                                {t('刷新', 'Refresh')}
                                            </button>
                                        </div>
                                        <div className="mb-4 flex flex-wrap gap-2">
                                            {REVIEW_LIST_MODE_OPTIONS.map((mode) => (
                                                <button
                                                    key={mode}
                                                    onClick={() => setReviewListMode(mode)}
                                                    className={`rounded-full px-3 py-1.5 text-xs transition ${reviewListMode === mode ? 'bg-primary text-primary-foreground' : 'bg-secondary/60 text-muted-foreground hover:text-foreground'}`}
                                                >
                                                    <span className="inline-flex items-center gap-2">
                                                        <span>{getReviewListModeLabel(mode, t)}</span>
                                                        {mode === 'project' && projectReviewThreads.filter((thread) => !!thread?.has_unread).length > 0 && <span className="rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-semibold text-black">{projectReviewThreads.filter((thread) => !!thread?.has_unread).length}</span>}
                                                        {mode === 'inbox' && reviewInboxThreads.filter((thread) => !!thread?.has_unread).length > 0 && <span className="rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-semibold text-black">{reviewInboxThreads.filter((thread) => !!thread?.has_unread).length}</span>}
                                                        {mode === 'outbox' && reviewOutboxThreads.filter((thread) => !!thread?.has_unread).length > 0 && <span className="rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-semibold text-black">{reviewOutboxThreads.filter((thread) => !!thread?.has_unread).length}</span>}
                                                    </span>
                                                </button>
                                            ))}
                                        </div>

                                        {reviewListMode === 'project' && (
                                            <div className="mb-4 rounded-xl border border-white/10 bg-card/40 p-3">
                                                <div className="mb-3 text-sm font-medium">{t('发起审核', 'Create Review')}</div>
                                                <div className="grid gap-3">
                                                    <>
                                                        <input
                                                            value={reviewThreadForm.reviewer_user}
                                                            onChange={(e) => setReviewThreadForm((prev) => ({ ...prev, reviewer_user: e.target.value }))}
                                                            placeholder={t('输入审核人用户名或邮箱', 'Enter reviewer username or email')}
                                                            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                                        />
                                                    </>
                                                    <input
                                                        value={reviewThreadForm.title}
                                                        onChange={(e) => setReviewThreadForm((prev) => ({ ...prev, title: e.target.value }))}
                                                        placeholder={t('审核标题，可选', 'Review title, optional')}
                                                        className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                                    />
                                                    <textarea
                                                        value={reviewThreadForm.request_message}
                                                        onChange={(e) => setReviewThreadForm((prev) => ({ ...prev, request_message: e.target.value }))}
                                                        rows={3}
                                                        placeholder={t('填写审核请求说明', 'Add review request notes')}
                                                        className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                                    />
                                                    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                                                        <label className="flex items-center gap-2">
                                                            <input
                                                                type="checkbox"
                                                                checked={!!reviewThreadForm.entity_required}
                                                                onChange={(e) => setReviewThreadForm((prev) => ({ ...prev, entity_required: e.target.checked }))}
                                                            />
                                                            {t('资产审核', 'Asset review')}
                                                        </label>
                                                        <label className="flex items-center gap-2">
                                                            <input
                                                                type="checkbox"
                                                                checked={!!reviewThreadForm.shot_required}
                                                                onChange={(e) => setReviewThreadForm((prev) => ({ ...prev, shot_required: e.target.checked }))}
                                                            />
                                                            {t('镜头审核', 'Shot review')}
                                                        </label>
                                                    </div>
                                                    <button
                                                        onClick={handleCreateReviewRequest}
                                                        disabled={reviewSubmitting}
                                                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                                                    >
                                                        {reviewSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                                                        {t('发起审核', 'Create Review')}
                                                    </button>
                                                    <div className="text-xs text-muted-foreground">{t('可直接输入任意已存在用户的用户名或邮箱；若项目作者指定了新审核人，系统会自动授予 reviewer 访问。', 'You can directly enter any existing username or email; when the project owner assigns a new reviewer, reviewer access will be granted automatically.')}</div>
                                                </div>
                                            </div>
                                        )}

                                        <div className="max-h-[32rem] overflow-auto rounded-lg border border-white/10">
                                            {reviewLoading && visibleReviewThreads.length === 0 ? (
                                                <div className="p-4 text-sm text-muted-foreground">{t('加载中...', 'Loading...')}</div>
                                            ) : visibleReviewThreads.length === 0 ? (
                                                <div className="p-4 text-sm text-muted-foreground">{t('暂无审核线程', 'No review threads')}</div>
                                            ) : (
                                                <div className="divide-y divide-white/10">
                                                    {visibleReviewThreads.map((thread) => (
                                                        <button
                                                            key={thread.id}
                                                            onClick={() => handleSelectReviewThread(thread.id)}
                                                            className={`w-full px-3 py-3 text-left transition hover:bg-white/5 ${Number(selectedReviewThreadId) === Number(thread.id) ? 'bg-white/5' : ''}`}
                                                        >
                                                            <div className="mb-1 flex items-center justify-between gap-3">
                                                                <div className="flex min-w-0 items-center gap-2">
                                                                    <div className="truncate text-sm font-medium">{thread.title || `${t('审核线程', 'Review Thread')} #${thread.id}`}</div>
                                                                    {thread.has_unread && <span className="rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-semibold text-black">{t('未读', 'Unread')}</span>}
                                                                </div>
                                                                <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-muted-foreground">{getReviewThreadStatusLabel(thread.status, t)}</span>
                                                            </div>
                                                            <div className="text-xs text-muted-foreground">
                                                                {thread.requester_username || '-'} → {thread.reviewer_username || '-'}
                                                            </div>
                                                            <div className="mt-1 text-[11px] text-muted-foreground">
                                                                {t('最新轮次', 'Latest round')} #{thread.latest_round_no || 0}
                                                            </div>
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <div className="rounded-2xl border border-white/10 bg-background/40 p-4">
                                    {!selectedReviewThread ? (
                                        <div className="flex h-full min-h-[28rem] items-center justify-center text-sm text-muted-foreground">
                                            {t('选择一个审核线程查看详情', 'Select a review thread to view details')}
                                        </div>
                                    ) : (
                                        <div className="grid gap-4">
                                            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 pb-4">
                                                <div>
                                                    <div className="text-lg font-semibold">{selectedReviewThread.title || `${t('审核线程', 'Review Thread')} #${selectedReviewThread.id}`}</div>
                                                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                                                        <span>{selectedReviewThread.requester_username || '-'}</span>
                                                        <span>→</span>
                                                        <span>{selectedReviewThread.reviewer_username || '-'}</span>
                                                        <span className="rounded-full border border-white/10 px-2 py-0.5">{getReviewThreadStatusLabel(selectedReviewThread.status, t)}</span>
                                                    </div>
                                                </div>
                                                <div className="flex flex-wrap gap-2">
                                                    {REVIEW_THREAD_STATUS_OPTIONS.map((status) => (
                                                        <button
                                                            key={status}
                                                            onClick={() => handleUpdateReviewStatus(status)}
                                                            disabled={reviewStatusSubmitting || String(selectedReviewThread.status || 'open') === status}
                                                            className="rounded-lg border border-white/10 px-3 py-2 text-xs text-muted-foreground disabled:opacity-40"
                                                        >
                                                            {getReviewThreadStatusLabel(status, t)}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>

                                            <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
                                                <div className="rounded-xl border border-white/10 bg-card/40 p-3">
                                                    <div className="mb-3 text-sm font-medium">{t('审核轮次', 'Review Rounds')}</div>
                                                    <div className="space-y-2">
                                                        {selectedReviewRounds.map((round) => (
                                                            <button
                                                                key={round.id}
                                                                onClick={() => handleSelectReviewRound(round.id)}
                                                                className={`w-full rounded-lg border px-3 py-2 text-left transition ${Number(selectedReviewRoundId) === Number(round.id) ? 'border-primary/40 bg-primary/10' : 'border-white/10 bg-background hover:bg-white/5'}`}
                                                            >
                                                                <div className="flex items-center justify-between gap-3 text-sm">
                                                                    <span>#{round.round_no}</span>
                                                                    <span className="text-xs text-muted-foreground">{round.overall_status || '-'}</span>
                                                                </div>
                                                                <div className="mt-1 text-xs text-muted-foreground">{round.initiated_by_username || '-'}</div>
                                                                <div className="mt-1 grid gap-1 text-[11px] text-muted-foreground">
                                                                    {round.entity_required && <div>{t('资产', 'Asset')}: {getReviewDecisionLabel(round.entity_decision, t)}</div>}
                                                                    {round.shot_required && <div>{t('镜头', 'Shot')}: {getReviewDecisionLabel(round.shot_decision, t)}</div>}
                                                                </div>
                                                            </button>
                                                        ))}
                                                    </div>
                                                </div>

                                                <div className="grid gap-4">
                                                    {selectedReviewRound && (
                                                        <div className="rounded-xl border border-white/10 bg-card/40 p-3">
                                                            <div className="mb-2 text-sm font-medium">{t('当前轮次摘要', 'Current Round Summary')} #{selectedReviewRound.round_no}</div>
                                                            <div className="grid gap-2 text-sm text-muted-foreground">
                                                                {selectedReviewRound.request_message && <div>{selectedReviewRound.request_message}</div>}
                                                                <div className="flex flex-wrap gap-4 text-xs">
                                                                    {selectedReviewRound.entity_required && <span>{t('资产', 'Asset')}: {getReviewDecisionLabel(selectedReviewRound.entity_decision, t)}</span>}
                                                                    {selectedReviewRound.shot_required && <span>{t('镜头', 'Shot')}: {getReviewDecisionLabel(selectedReviewRound.shot_decision, t)}</span>}
                                                                </div>
                                                                {selectedReviewRound.entity_feedback && <div><span className="text-foreground">{t('资产意见', 'Asset feedback')}:</span> {selectedReviewRound.entity_feedback}</div>}
                                                                {selectedReviewRound.shot_feedback && <div><span className="text-foreground">{t('镜头意见', 'Shot feedback')}:</span> {selectedReviewRound.shot_feedback}</div>}
                                                            </div>
                                                        </div>
                                                    )}

                                                    <div className="rounded-xl border border-white/10 bg-card/40 p-3">
                                                        <div className="mb-3 text-sm font-medium">{t('往返消息', 'Messages')}</div>
                                                        <div className="max-h-[16rem] space-y-2 overflow-auto pr-1">
                                                            {selectedReviewMessages.length === 0 ? (
                                                                <div className="text-sm text-muted-foreground">{t('暂无消息', 'No messages')}</div>
                                                            ) : selectedReviewMessages.map((message) => (
                                                                <div key={message.id} className="rounded-lg border border-white/10 bg-background/70 p-3">
                                                                    <div className="mb-1 flex items-center justify-between gap-3">
                                                                        <div className="text-sm font-medium">{message.sender_username || '-'}</div>
                                                                        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                                                                            <span className="rounded-full border border-white/10 px-2 py-0.5">{message.sender_role === 'reviewer' ? t('审核方', 'Reviewer') : t('发起方', 'Requester')}</span>
                                                                            <span>{message.message_type || 'message'}</span>
                                                                        </div>
                                                                    </div>
                                                                    {message.message_text && <div className="text-sm text-foreground">{message.message_text}</div>}
                                                                    <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
                                                                        {message.entity_decision && message.entity_decision !== 'pending' && <div>{t('资产结论', 'Asset decision')}: {getReviewDecisionLabel(message.entity_decision, t)}</div>}
                                                                        {message.shot_decision && message.shot_decision !== 'pending' && <div>{t('镜头结论', 'Shot decision')}: {getReviewDecisionLabel(message.shot_decision, t)}</div>}
                                                                        {message.entity_feedback && <div>{t('资产意见', 'Asset feedback')}: {message.entity_feedback}</div>}
                                                                        {message.shot_feedback && <div>{t('镜头意见', 'Shot feedback')}: {message.shot_feedback}</div>}
                                                                    </div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>

                                                    {selectedReviewThread.status !== 'archived' && selectedReviewRound && (
                                                        <div className="rounded-xl border border-white/10 bg-card/40 p-3">
                                                            <div className="mb-3 text-sm font-medium">{amSelectedReviewReviewer ? t('审核回复', 'Reviewer Reply') : t('继续沟通', 'Continue Discussion')}</div>
                                                            <div className="grid gap-3">
                                                                <textarea
                                                                    value={reviewMessageForm.message_text}
                                                                    onChange={(e) => setReviewMessageForm((prev) => ({ ...prev, message_text: e.target.value }))}
                                                                    rows={3}
                                                                    placeholder={amSelectedReviewReviewer ? t('填写审核结论或沟通说明', 'Write review conclusion or discussion notes') : t('填写补充说明或回应', 'Add follow-up notes or response')}
                                                                    className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                                                />
                                                                {amSelectedReviewReviewer && (
                                                                    <>
                                                                        <div className="grid gap-3 md:grid-cols-2">
                                                                            {selectedReviewRound.entity_required && (
                                                                                <select
                                                                                    value={reviewMessageForm.entity_decision}
                                                                                    onChange={(e) => setReviewMessageForm((prev) => ({ ...prev, entity_decision: e.target.value }))}
                                                                                    className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                                                                >
                                                                                    {REVIEW_DECISION_OPTIONS.map((decision) => (
                                                                                        <option key={decision} value={decision}>{t('资产', 'Asset')} · {getReviewDecisionLabel(decision, t)}</option>
                                                                                    ))}
                                                                                </select>
                                                                            )}
                                                                            {selectedReviewRound.shot_required && (
                                                                                <select
                                                                                    value={reviewMessageForm.shot_decision}
                                                                                    onChange={(e) => setReviewMessageForm((prev) => ({ ...prev, shot_decision: e.target.value }))}
                                                                                    className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                                                                >
                                                                                    {REVIEW_DECISION_OPTIONS.map((decision) => (
                                                                                        <option key={decision} value={decision}>{t('镜头', 'Shot')} · {getReviewDecisionLabel(decision, t)}</option>
                                                                                    ))}
                                                                                </select>
                                                                            )}
                                                                        </div>
                                                                        {selectedReviewRound.entity_required && (
                                                                            <textarea
                                                                                value={reviewMessageForm.entity_feedback}
                                                                                onChange={(e) => setReviewMessageForm((prev) => ({ ...prev, entity_feedback: e.target.value }))}
                                                                                rows={2}
                                                                                placeholder={t('资产审核意见', 'Asset review feedback')}
                                                                                className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                                                            />
                                                                        )}
                                                                        {selectedReviewRound.shot_required && (
                                                                            <textarea
                                                                                value={reviewMessageForm.shot_feedback}
                                                                                onChange={(e) => setReviewMessageForm((prev) => ({ ...prev, shot_feedback: e.target.value }))}
                                                                                rows={2}
                                                                                placeholder={t('镜头审核意见', 'Shot review feedback')}
                                                                                className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                                                            />
                                                                        )}
                                                                    </>
                                                                )}
                                                                <button
                                                                    onClick={handleCreateReviewMessage}
                                                                    disabled={reviewSubmitting}
                                                                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                                                                >
                                                                    {reviewSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                                                                    {t('发送回复', 'Send Reply')}
                                                                </button>
                                                            </div>
                                                        </div>
                                                    )}

                                                    {canManageSelectedReview && selectedReviewThread.status !== 'archived' && (
                                                        <div className="rounded-xl border border-white/10 bg-card/40 p-3">
                                                            <div className="mb-3 text-sm font-medium">{t('发起新一轮审核', 'Start Next Review Round')}</div>
                                                            <div className="grid gap-3">
                                                                <textarea
                                                                    value={reviewRoundForm.request_message}
                                                                    onChange={(e) => setReviewRoundForm((prev) => ({ ...prev, request_message: e.target.value }))}
                                                                    rows={3}
                                                                    placeholder={t('说明本轮需要审核的重点', 'Describe what should be reviewed in this round')}
                                                                    className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
                                                                />
                                                                <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                                                                    <label className="flex items-center gap-2">
                                                                        <input
                                                                            type="checkbox"
                                                                            checked={!!reviewRoundForm.entity_required}
                                                                            onChange={(e) => setReviewRoundForm((prev) => ({ ...prev, entity_required: e.target.checked }))}
                                                                        />
                                                                        {t('资产审核', 'Asset review')}
                                                                    </label>
                                                                    <label className="flex items-center gap-2">
                                                                        <input
                                                                            type="checkbox"
                                                                            checked={!!reviewRoundForm.shot_required}
                                                                            onChange={(e) => setReviewRoundForm((prev) => ({ ...prev, shot_required: e.target.checked }))}
                                                                        />
                                                                        {t('镜头审核', 'Shot review')}
                                                                    </label>
                                                                </div>
                                                                <button
                                                                    onClick={handleCreateReviewRound}
                                                                    disabled={reviewSubmitting}
                                                                    className="inline-flex items-center justify-center gap-2 rounded-lg border border-primary/30 px-3 py-2 text-sm text-primary disabled:opacity-50"
                                                                >
                                                                    {reviewSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                                                                    {t('发起新一轮', 'Create Next Round')}
                                                                </button>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
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
