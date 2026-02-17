
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useLog } from '../context/LogContext';
import { useStore } from '../lib/store';
import LogPanel from '../components/LogPanel';
import AgentChat from '../components/AgentChat';
import { MessageSquare, X, LayoutDashboard, FileText, Clapperboard, Users, Film, Settings as SettingsIcon, Settings2, ArrowLeft, ChevronDown, Plus, Trash2, Upload, Download, Table as TableIcon, Edit3, ScrollText, LayoutList, Copy, Image as ImageIcon, Video, FolderOpen, Maximize2, Info, RefreshCw, Wand2, Link as LinkIcon, CheckCircle, Check, Languages, Loader2, Save, Layers, ArrowUp, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { API_URL, BASE_URL } from '../config';

// Helper to handle relative URLs
const getFullUrl = (url) => {
    if (!url) return '';
    if (url.startsWith('http') || url.startsWith('blob:') || url.startsWith('data:')) return url;
    // If it's a relative path starting with /, append BASE_URL
    if (url.startsWith('/')) {
        // Avoid double slash if BASE_URL ends with /
        const base = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;
        return `${base}${url}`;
    }
    return url;
};

import { 
    fetchProject, 
    updateProject,
    fetchEpisodes, 
    createEpisode, 
    updateEpisode,
    updateEpisodeSegments,
    deleteEpisode,
    fetchScenes, 
    createScene,
    updateScene, 
    fetchShots,
    fetchEpisodeShots,
    createShot,
    updateShot,
    deleteShot,
    fetchEntities, 
    createEntity,
    updateEntity,
    deleteEntity,
    deleteAllEntities,
    generateImage,
    generateVideo,
    fetchAssets, 
    generateSceneShots,
    fetchSceneShotsPrompt,
    createAsset,
    uploadAsset,
    getSettings,
    translateText,
    refinePrompt,
    analyzeScene,
    fetchPrompt,
    fetchMe,
    analyzeEntityImage
} from '../services/api';

import RefineControl from '../components/RefineControl.jsx';
import VideoStudio from '../components/VideoStudio';

// RefineControl moved to components/RefineControl.jsx

import ReactMarkdown from 'react-markdown';
import { processPrompt } from '../lib/promptUtils';
import SettingsPage from './Settings';

const PROVIDER_LABELS = {
    image: {
        "Midjourney": "Midjourney",
        "Doubao": "Doubao (豆包 - Volcengine)",
        "Grsai-Image": "Grsai (Aggregation)",
        "DALL-E 3": "DALL-E 3",
        "Stable Diffusion": "Stable Diffusion (SDXL/Pony)",
        "Flux": "Flux.1",
        "Tencent Hunyuan": "Tencent Hunyuan (腾讯混元)"
    },
    video: {
        "Runway": "Runway Gen-2/Gen-3",
        "Luma": "Luma Dream Machine",
        "Kling": "Kling AI (可灵)",
        "Sora": "Sora (OpenAI)",
        "Grsai-Video": "Grsai (Standard)",
        "Grsai-Video (Upload)": "Grsai (File Upload)",
        "Stable Video": "Stable Video Component",
        "Doubao Video": "Doubao (豆包 - Volcengine)",
        "Wanxiang": "Wanxiang (通义万相 - Aliyun)",
        "Vidu (Video)": "Vidu (Shengshu)"
    }
};

const MODEL_OPTIONS = {
    image: {
        "Midjourney": [
            { label: "Standard (v6.0)", value: "default" },
            { label: "Niji (Anime)", value: "niji" }
        ],
        "Stable Diffusion": [
            { label: "SDXL 1.0 (Stability)", value: "stable-diffusion-xl-1024-v1-0" },
            { label: "SD 1.6", value: "stable-diffusion-v1-6" },
            { label: "SD3 Large", value: "sd3-large" },
            { label: "SD3 Large Turbo", value: "sd3-large-turbo" }
        ],
        "DALL-E 3": [
            { label: "DALL-E 3 (High Quality)", value: "dall-e-3" }
        ],
        "Doubao": [
            { label: "Doubao Image (Seedream)", value: "doubao-seedream-4-5-251128" }
        ],
        "Tencent Hunyuan": [
            { label: "Hunyuan Vision", value: "hunyuan-vision" },
            { label: "Standard (201)", value: "201" }
        ],
        "Grsai-Image": [
            { label: "Sora Image", value: "sora-image" },
            { label: "GPT Image 1.5", value: "gpt-image-1.5" },
            { label: "Nano Banana Pro", value: "nano-banana-pro" },
            { label: "Nano Banana Pro VT", value: "nano-banana-pro-vt" },
            { label: "Nano Banana Fast", value: "nano-banana-fast" },
            { label: "Nano Banana Pro CL", value: "nano-banana-pro-cl" },
            { label: "Nano Banana Pro VIP", value: "nano-banana-pro-vip" },
            { label: "Nano Banana", value: "nano-banana" },
            { label: "Nano Banana Pro 4K VIP", value: "nano-banana-pro-4k-vip" }
        ],
        "Flux": [
            { label: "Flux.1 Pro", value: "flux-pro" },
            { label: "Flux.1 Dev", value: "flux-dev" },
            { label: "Flux.1 Schnell", value: "flux-schnell" }
        ]
    },
    video: {
        "Runway": [
            { label: "Gen-3 Alpha", value: "gen-3-alpha" },
            { label: "Gen-2 (Standard)", value: "gen-2" }
        ],
        "Luma": [
            { label: "Ray 2", value: "ray-2" },
            { label: "Ray 1.6", value: "ray-1-6" }
        ],
        "Kling": [
            { label: "Kling v1.0", value: "kling-v1" },
            { label: "Kling v1.5", value: "kling-v1-5" }
        ],
        "Sora": [
             { label: "Sora", value: "sora" }
        ],
        "Grsai-Video": [
            { label: "Sora Video", value: "sora-video" },
            { label: "Sora V2", value: "sora-2" },
            { label: "Luma Ray 2", value: "luma-ray-2" },
            { label: "Luma Ray 1-6", value: "luma-ray-1-6" },
            { label: "Runway Gen3", value: "runway-gen3" },
            { label: "Runway Gen3 Alpha", value: "runway-gen3-alpha" },
            { label: "Runway Gen2", value: "runway-gen2" },
            { label: "Kling v1", value: "kling-v1" },
            { label: "Kling v1.5", value: "kling-v1-5" },
            { label: "Minimax Video", value: "minimax-video" },
            { label: "CogVideoX", value: "cogvideox" },
            { label: "Hunyuan Video (Tencent)", value: "hunyuan-video" }
        ],
        "Grsai-Video (Upload)": [
             { label: "Default (Upload Mode)", value: "default-upload" }
        ],
        "Stable Video": [
             { label: "SVD 1.1", value: "svd-xt-1-1" }
        ],
        "Doubao Video": [
            { label: "Doubao Video", value: "doubao-vid-s-251128" },
            { label: "Doubao Video Pro", value: "doubao-seedance-1-5-pro-251215" }
        ],
        "Wanxiang": [
            { label: "WanX 2.1 (Image2Video)", value: "wanx2.1-i2v-plus" },
            { label: "WanX 2.1 (KeyFrame2Video)", value: "wanx2.1-kf2v-plus" },
            { label: "WanX 2.0 (Text2Video)", value: "wanx2.0-t2v-turbo" }
        ],
        "Vidu (Video)": [
             { label: "Vidu 2.0", value: "vidu2.0" }
        ]
    }
};



const InputGroup = ({ label, value, onChange, list, placeholder, idPrefix, multi = false }) => {
    const [isOpen, setIsOpen] = useState(false);
    const wrapperRef = useRef(null);

    // Close on click outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Helper for multi-select check
    const isSelected = (opt) => {
        if (!multi) return value === opt;
        const current = (value || '').split(',').map(s => s.trim());
        return current.includes(opt);
    };

    return (
        <div className="flex flex-col gap-1" ref={wrapperRef}>
            <label className="text-xs text-muted-foreground uppercase font-bold">{label}</label>
            <div className="relative">
                <input 
                    className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full"
                    value={value || ''}
                    onChange={(e) => {
                        onChange(e.target.value);
                        if (list) setIsOpen(true);
                    }}
                    onFocus={() => list && setIsOpen(true)}
                    placeholder={placeholder}
                />
                {list && (
                    <button 
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-white/50 hover:text-white"
                        onClick={() => setIsOpen(!isOpen)}
                        tabIndex={-1}
                    >
                        <ChevronDown size={14} />
                    </button>
                )}
                
                {list && isOpen && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-[#1e1e1e] border border-white/10 rounded-md shadow-xl max-h-48 overflow-y-auto z-50 custom-scrollbar">
                        {list.map(opt => {
                            const selected = isSelected(opt);
                            return (
                                <div 
                                    key={opt}
                                    className={`px-3 py-2 text-sm cursor-pointer flex justify-between items-center ${selected ? 'bg-primary/20 text-primary' : 'text-white hover:bg-white/5'}`}
                                    onClick={() => {
                                        if (multi) {
                                            let current = (value || '').split(',').map(s => s.trim()).filter(Boolean);
                                            if (current.includes(opt)) {
                                                current = current.filter(c => c !== opt);
                                            } else {
                                                current.push(opt);
                                            }
                                            onChange(current.join(', '));
                                        } else {
                                            onChange(opt);
                                            setIsOpen(false);
                                        }
                                    }}
                                >
                                    <span>{opt}</span>
                                    {selected && <CheckCircle size={14} />}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

// Mock Data / Placeholders for Tabs
const ProjectOverview = ({ id, onProjectUpdate }) => {
    const [project, setProject] = useState(null);
    const [info, setInfo] = useState({
        script_title: "",
        series_episode: "",
        base_positioning: "Modern Workplace",
        type: "Live Action (Realism/Cinematic 8K)",
        Global_Style: "Photorealistic, Cinematic Lighting, 8k, Masterpiece",
        tech_params: {
            visual_standard: {
                horizontal_resolution: "720",
                vertical_resolution: "1080",
                frame_rate: "24",
                aspect_ratio: "9:16",
                quality: "Ultra High"
            }
        },
        tone: "Skin Tone Optimized, Dreamy",
        lighting: "",
        language: "English",
        borrowed_films: ["King Kong (2005)", "Joker (2019)", "The Truman Show"],
        notes: ""
    });

    useEffect(() => {
    // ... no changes to rest

        const load = async () => {
            try {
                const data = await fetchProject(id);
                setProject(data);
                if (data.global_info) {
                     // Merger with defaults to ensure structure
                     const merged = {
                         ...info,
                         ...data.global_info,
                         tech_params: {
                             visual_standard: {
                                 ...info.tech_params.visual_standard,
                                 ...(data.global_info.tech_params?.visual_standard || {})
                             }
                         }
                     };
                     setInfo(merged);
                }
            } catch (e) {
                console.error("Failed to load project", e);
            }
        };
        load();
    }, [id]);

    const handleSave = async () => {
        try {
            await updateProject(id, { global_info: info });
            alert("Project info saved!");
            if (onProjectUpdate) onProjectUpdate();
        } catch (e) {
            console.error("Failed to save", e);
            alert("Failed to save.");
        }
    };

    const updateField = (key, value) => {
        setInfo(prev => ({ ...prev, [key]: value }));
    };

    const updateTech = (key, value) => {
        setInfo(prev => ({
            ...prev,
            tech_params: {
                ...prev.tech_params,
                visual_standard: {
                    ...prev.tech_params.visual_standard,
                    [key]: value
                }
            }
        }));
    };

    const handleBorrowedFilmsChange = (str) => {
        // Simple comma separated handling
        const arr = str.split(/[,，]/).map(s => s.trim()).filter(Boolean);
        setInfo(prev => ({ ...prev, borrowed_films: arr }));
    };

    if (!project) return <div className="p-8 text-muted-foreground">Loading...</div>;

    const prefix = "proj-";

    return (
        <div className="p-8 w-full h-full overflow-y-auto">
            <div className="flex justify-between items-center mb-8">
                <h2 className="text-2xl font-bold">Project Overview</h2>
                <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center gap-2">
                    <SettingsIcon className="w-4 h-4" /> Save Changes
                </button>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 max-w-6xl">
                {/* Basic Info */}
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-6">
                    <h3 className="text-lg font-semibold text-primary border-b border-white/10 pb-2">Basic Information</h3>
                    
                    <div className="grid grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix} label="Script Title" value={info.script_title} onChange={v => updateField('script_title', v)} placeholder="e.g. My Sci-Fi Epic" />
                        <InputGroup idPrefix={prefix} label="Series/Episode" value={info.series_episode} onChange={v => updateField('series_episode', v)} placeholder="e.g. Ep 01" />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label="Type" 
                            value={info.type} 
                            onChange={v => updateField('type', v)} 
                            list={[
                                "Live Action", 
                                "Live Action (Realism/Cinematic 8K)",
                                "2D Animation", 
                                "3D Animation", 
                                "Stop Motion", 
                                "Tokusatsu", 
                                "Stage Play", 
                                "CG Animation", 
                                "Mixed Media", 
                                "Documentary"
                            ]} 
                        />
                         <InputGroup idPrefix={prefix}
                            label="Language" 
                            value={info.language} 
                            onChange={v => updateField('language', v)} 
                            list={["Chinese", "English", "Bilingual (CN/EN)", "Japanese", "Korean", "French", "Spanish", "German", "Other"]} 
                        />
                    </div>
                    
                    <InputGroup idPrefix={prefix}
                        label="Base Positioning" 
                        value={info.base_positioning} 
                        onChange={v => updateField('base_positioning', v)} 
                        list={["Urban Romance", "Sci-Fi Adventure", "Mystery / Thriller", "Period / Wuxia", "Fantasy Epic", "Modern Workplace", "High School / Youth", "Cyberpunk", "Horror", "Comedy", "Drama", "Action", "Historical"]}
                        placeholder="e.g. Urban Romance / Sci-Fi"
                    />

                    <InputGroup idPrefix={prefix}
                        label="Global Style" 
                        value={info.Global_Style} 
                        onChange={v => updateField('Global_Style', v)} 
                        list={[
                            "Photorealistic, Cinematic Lighting, 8k, Masterpiece",
                            "Hyperrealistic Portrait, RAW Photo, Ultra Detailed",
                            "Cyberpunk", 
                            "Minimalist", 
                            "Photorealistic", 
                            "Disney Style", 
                            "Ghibli Style", 
                            "Film Noir", 
                            "Steampunk", 
                            "Watercolor", 
                            "Oil Painting", 
                            "Pixel Art", 
                            "Vaporwave", 
                            "Gothic", 
                            "Surrealism"
                        ]} 
                    />

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">Borrowed Films (Ref)</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                            value={info.borrowed_films.join(", ")}
                            onChange={(e) => handleBorrowedFilmsChange(e.target.value)}
                            placeholder="Use commas to separate, e.g. Blade Runner, Matrix"
                        />
                    </div>
                </div>

                {/* Technical & Visual Params */}
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-6">
                    <h3 className="text-lg font-semibold text-primary border-b border-white/10 pb-2">Technical & Visual Parameters</h3>
                    
                    <div className="grid grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label="H. Resolution" 
                            value={info.tech_params?.visual_standard?.horizontal_resolution} 
                            onChange={v => updateTech('horizontal_resolution', v)} 
                            placeholder="3840"
                        />
                        <InputGroup idPrefix={prefix}
                            label="V. Resolution" 
                            value={info.tech_params?.visual_standard?.vertical_resolution} 
                            onChange={v => updateTech('vertical_resolution', v)} 
                            placeholder="2160"
                            list={["2160", "1920", "1080", "720"]}
                        />
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                        <InputGroup idPrefix={prefix}
                            label="Frame Rate" 
                            value={info.tech_params?.visual_standard?.frame_rate} 
                            onChange={v => updateTech('frame_rate', v)} 
                            list={["24", "30", "60"]} 
                        />
                         <InputGroup idPrefix={prefix}
                            label="Aspect Ratio" 
                            value={info.tech_params?.visual_standard?.aspect_ratio} 
                            onChange={v => updateTech('aspect_ratio', v)} 
                            list={["16:9", "2.35:1", "4:3", "9:16"]} 
                        />
                         <InputGroup idPrefix={prefix}
                            label="Quality" 
                            value={info.tech_params?.visual_standard?.quality} 
                            onChange={v => updateTech('quality', v)} 
                            list={["Ultra High", "High", "Medium", "Low", "Draft"]} 
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label="Tone" 
                            value={info.tone} 
                            onChange={v => updateField('tone', v)} 
                            multi={true}
                            list={[
                                "Cool", 
                                "Warm", 
                                "Neutral", 
                                "High Contrast", 
                                "Dark / Moody", 
                                "Dreamy", 
                                "Vibrant", 
                                "Desaturated", 
                                "Pastel", 
                                "Gritty",
                                "Skin Tone Optimized",
                                "Film Presence", 
                                "Muted Tones",
                                "Skin Tone Optimized, Dreamy",
                                "Film Presence, Muted Tones",
                                "Neutral, High Contrast",
                                "Dark / Moody, Gritty",
                                "Vibrant, High Contrast"
                            ]} 
                        />
                        <InputGroup idPrefix={prefix}
                            label="Lighting" 
                            value={info.lighting} 
                            onChange={v => updateField('lighting', v)} 
                            multi={true}
                            list={[
                                "Natural Light", 
                                "Soft Light", 
                                "Hard Light", 
                                "Rim Light", 
                                "Rembrandt", 
                                "Neon / Cyber", 
                                "Cinematic", 
                                "Low Key", 
                                "High Key", 
                                "Volumetric",
                                "Butterfly Light",
                                "Studio Light",
                                "Golden Hour", 
                                "Window Light", 
                                "Split Light",
                                "Butterfly Light, Soft Light",
                                "Rembrandt, Volumetric",
                                "Cinematic, Rim Light, Volumetric",
                                "Studio Light, Hard Light",
                                "Natural Light, Window Light"
                            ]} 
                        />
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">Additional Notes</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none"
                            value={info.notes}
                            onChange={(e) => updateField('notes', e.target.value)}
                            placeholder="Any other important information..."
                        />
                    </div>
                </div>
            </div>
        </div>
    );
};



const EpisodeInfo = ({ episode, onUpdate }) => {
    const [info, setInfo] = useState({
        e_global_info: {
            script_title: "",
            series_episode: "",
            base_positioning: "Modern Workplace",
            type: "Live Action (Realism/Cinematic 8K)",
            Global_Style: "Photorealistic, Cinematic Lighting, 8k, Masterpiece",
            tech_params: {
                visual_standard: {
                    horizontal_resolution: "3840",
                    vertical_resolution: "2160",
                    frame_rate: "24",
                    aspect_ratio: "9:16",
                    quality: "Ultra High"
                }
            },
            tone: "Skin Tone Optimized, Dreamy",
            lighting: "",
            language: "English",
            borrowed_films: ["King Kong (2005)", "Joker (2019)", "The Truman Show"],
            notes: ""
        }
    });

    useEffect(() => {
        if (episode) {
             const loaded = episode.episode_info || {};
             
             // Ensure structure exists even if loaded data is partial
             const merged = {
                 e_global_info: {
                     ...info.e_global_info, // default structure
                     ...(loaded.e_global_info || {}), // loaded data
                 }
             };

             // Deep merge tech_params if they exist
             if (loaded.e_global_info?.tech_params?.visual_standard) {
                 merged.e_global_info.tech_params = {
                     ...merged.e_global_info.tech_params,
                     visual_standard: {
                         ...merged.e_global_info.tech_params.visual_standard,
                         ...loaded.e_global_info.tech_params.visual_standard
                     }
                 };
             }
             
             setInfo(merged);
        }
    }, [episode]);

    const handleSave = async () => {
        try {
            await onUpdate(episode.id, { episode_info: info });
            alert("Episode global info saved!");
        } catch (e) {
            console.error("Failed to save", e);
            alert("Failed to save.");
        }
    };

    const updateField = (key, value) => {
        setInfo(prev => ({
            ...prev,
            e_global_info: {
                ...prev.e_global_info,
                [key]: value
            }
        }));
    };

    const updateTech = (key, value) => {
        setInfo(prev => ({
            ...prev,
            e_global_info: {
                ...prev.e_global_info,
                tech_params: {
                    ...prev.e_global_info.tech_params,
                    visual_standard: {
                        ...prev.e_global_info.tech_params.visual_standard,
                        [key]: value
                    }
                }
            }
        }));
    };
    
    const handleBorrowedFilmsChange = (str) => {
        const arr = str.split(/[,，]/).map(s => s.trim()).filter(Boolean);
        updateField('borrowed_films', arr);
    };

    if (!episode) return <div className="p-8 text-muted-foreground">Select an episode to view info.</div>;

    const data = info.e_global_info;
    const prefix = "ep-";

    return (
        <div className="p-8 w-full h-full overflow-y-auto">
             <div className="flex justify-between items-center mb-8">
                <h2 className="text-2xl font-bold">Episode Global Info</h2>
                <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center gap-2">
                    <SettingsIcon className="w-4 h-4" /> Save Changes
                </button>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 max-w-6xl">
                 {/* Basic Info */}
                <div className="bg-card border border-white/10 p-6 rounded-xl space-y-6">
                    <h3 className="text-lg font-semibold text-primary border-b border-white/10 pb-2">Basic Information</h3>
                    
                    <div className="grid grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix} label="Script Title" value={data.script_title} onChange={v => updateField('script_title', v)} placeholder="Episode Script Title" />
                        <InputGroup idPrefix={prefix} label="Series/Episode" value={data.series_episode} onChange={v => updateField('series_episode', v)} placeholder="e.g. S01E01" />
                    </div>

                    <InputGroup idPrefix={prefix}
                        label="Base Positioning" 
                        value={data.base_positioning} 
                        onChange={v => updateField('base_positioning', v)} 
                        list={["Urban Romance", "Sci-Fi Adventure", "Mystery / Thriller", "Period / Wuxia", "Fantasy Epic", "Modern Workplace", "High School / Youth", "Cyberpunk", "Horror", "Comedy", "Drama", "Action", "Historical"]}
                        placeholder="e.g. Mystery / Thriller"
                    />
                    
                    <div className="grid grid-cols-2 gap-4">
                        <InputGroup idPrefix={prefix}
                            label="Type" 
                            value={data.type} 
                            onChange={v => updateField('type', v)} 
                            list={[
                                "Live Action", 
                                "Live Action (Realism/Cinematic 8K)",
                                "2D Animation", 
                                "3D Animation", 
                                "Stop Motion", 
                                "Tokusatsu", 
                                "Stage Play", 
                                "CG Animation", 
                                "Mixed Media", 
                                "Documentary"
                            ]} 
                        />
                        <InputGroup idPrefix={prefix}
                            label="Language" 
                            value={data.language} 
                            onChange={v => updateField('language', v)} 
                            list={["Chinese", "English", "Bilingual (CN/EN)", "Japanese", "Korean", "French", "Spanish", "German", "Other"]} 
                        />
                    </div>
                    
                    <InputGroup idPrefix={prefix}
                        label="Global Style" 
                        value={data.Global_Style} 
                        onChange={v => updateField('Global_Style', v)} 
                        list={[
                            "Photorealistic, Cinematic Lighting, 8k, Masterpiece",
                            "Hyperrealistic Portrait, RAW Photo, Ultra Detailed",
                            "Cyberpunk", 
                            "Minimalist", 
                            "Photorealistic", 
                            "Disney Style", 
                            "Ghibli Style", 
                            "Film Noir", 
                            "Steampunk", 
                            "Watercolor", 
                            "Oil Painting", 
                            "Pixel Art", 
                            "Vaporwave", 
                            "Gothic", 
                            "Surrealism"
                        ]}
                        placeholder="e.g. Cyberpunk"
                    />

                     <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">Borrowed Films</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-20 resize-none"
                            value={(data.borrowed_films || []).join(", ")}
                            onChange={(e) => handleBorrowedFilmsChange(e.target.value)}
                            placeholder="e.g. Gone Girl, Joker"
                        />
                    </div>
                </div>

                {/* Tech Params */}
                 <div className="bg-card border border-white/10 p-6 rounded-xl space-y-6">
                    <h3 className="text-lg font-semibold text-primary border-b border-white/10 pb-2">Technical & Mood</h3>
                    
                    <div className="grid grid-cols-2 gap-4">
                         <InputGroup idPrefix={prefix} label="H. Resolution" value={data.tech_params?.visual_standard?.horizontal_resolution} onChange={v => updateTech('horizontal_resolution', v)} placeholder="3840" list={["3840", "1920", "1280", "1080"]}/>
                         <InputGroup idPrefix={prefix} label="V. Resolution" value={data.tech_params?.visual_standard?.vertical_resolution} onChange={v => updateTech('vertical_resolution', v)} placeholder="2160" list={["2160", "1920", "1080", "720"]}/>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-4">
                         <InputGroup idPrefix={prefix} label="Frame Rate" value={data.tech_params?.visual_standard?.frame_rate} onChange={v => updateTech('frame_rate', v)} list={["24", "30", "60"]} />
                         <InputGroup idPrefix={prefix} label="Aspect Ratio" value={data.tech_params?.visual_standard?.aspect_ratio} onChange={v => updateTech('aspect_ratio', v)} list={["16:9", "2.35:1", "4:3", "9:16", "1:1"]} />
                         <InputGroup idPrefix={prefix} label="Quality" value={data.tech_params?.visual_standard?.quality} onChange={v => updateTech('quality', v)} list={["Ultra High", "High", "Medium", "Low", "Draft"]} />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                         <InputGroup idPrefix={prefix}
                            label="Tone" 
                            value={data.tone} 
                            onChange={v => updateField('tone', v)} 
                            multi={true}
                            list={[
                                "Cool", 
                                "Warm", 
                                "Neutral", 
                                "High Contrast", 
                                "Dark / Moody", 
                                "Dreamy", 
                                "Vibrant", 
                                "Desaturated", 
                                "Pastel", 
                                "Gritty",
                                "Skin Tone Optimized",
                                "Film Presence", 
                                "Muted Tones",
                                "Skin Tone Optimized, Dreamy",
                                "Film Presence, Muted Tones",
                                "Neutral, High Contrast",
                                "Dark / Moody, Gritty",
                                "Vibrant, High Contrast"
                            ]}
                         />
                         <InputGroup idPrefix={prefix}
                            label="Lighting" 
                            value={data.lighting} 
                            onChange={v => updateField('lighting', v)} 
                            multi={true}
                            list={[
                                "Natural Light", 
                                "Soft Light", 
                                "Hard Light", 
                                "Rim Light", 
                                "Rembrandt", 
                                "Neon / Cyber", 
                                "Cinematic", 
                                "Low Key", 
                                "High Key", 
                                "Volumetric",
                                "Butterfly Light",
                                "Studio Light",
                                "Golden Hour", 
                                "Window Light", 
                                "Split Light",
                                "Butterfly Light, Soft Light",
                                "Rembrandt, Volumetric",
                                "Cinematic, Rim Light, Volumetric",
                                "Studio Light, Hard Light",
                                "Natural Light, Window Light"
                            ]}
                         />
                    </div>

                    <div>
                        <label className="text-xs text-muted-foreground uppercase font-bold mb-1 block">Notes</label>
                        <textarea 
                            className="bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full h-24 resize-none"
                            value={data.notes}
                            onChange={(e) => updateField('notes', e.target.value)}
                            placeholder="Additional Style Notes..."
                        />
                    </div>
                 </div>
            </div>
        </div>
    );
};


const ScriptEditor = ({ activeEpisode, project, onUpdateScript, onLog }) => {
    const [segments, setSegments] = useState([]);
    const [showMerged, setShowMerged] = useState(false);
    const [mergedContent, setMergedContent] = useState('');
    const [rawContent, setRawContent] = useState('');
    const [isRawMode, setIsRawMode] = useState(false);

    const handleMerge = () => {
        const fullText = segments
            .map(seg => seg.content || '')
            .filter(t => t.trim().length > 0)
            .join('\n\n');
        setMergedContent(fullText);
        setShowMerged(true);
    };

    useEffect(() => {
        if (activeEpisode?.script_content) {
            setRawContent(activeEpisode.script_content);
        } else {
            setRawContent('');
        }

        if (!activeEpisode?.script_content) {
            setSegments([]);
            setIsRawMode(true);
            return;
        }

        const content = activeEpisode.script_content;
        
        // Mode 1: Markdown Table parser
        const hasTableStructure = /\|\s*Paragraph ID\s*\|/.test(content) || /\|\s*Content \(Revised\)\s*\|/.test(content);
        
        if (hasTableStructure) {
             const lines = content.split('\n').map(l => l.trim()).filter(l => l.includes('|'));
             const parsed = [];
             
             const headerIdx = lines.findIndex(l => l.includes("Paragraph ID") || l.includes("Content (Revised)"));
             if (headerIdx === -1) {
                 setSegments([]);
                 setIsRawMode(true);
                 return;
             }

             for (let i = headerIdx + 1; i < lines.length; i++) {
                 const line = lines[i];
                 if (line.includes('---')) continue; 
                 
                 let cols = line.split('|').map(c => c.trim());
                 if (cols.length > 0 && cols[0] === "") cols.shift();
                 if (cols.length > 0 && cols[cols.length-1] === "") cols.pop();
                 
                 if (cols.length >= 6) {
                      parsed.push({
                         id: cols[0],
                         title: cols[1],
                         content: cols[2].replace(/<br\s*\/?>/gi, '\n'),
                         original: cols[3].replace(/<br\s*\/?>/gi, '\n'),
                         narrative_role: cols[4].replace(/<br\s*\/?>/gi, '\n'),
                         analysis: cols[5].replace(/<br\s*\/?>/gi, '\n')
                      });
                 }
             }
             if (parsed.length > 0) {
                 setSegments(parsed);
                 setIsRawMode(false);
             } else {
                 setSegments([]);
                 setIsRawMode(true);
             }
             return;
        }

        // Mode 2: Legacy parser
        const chunks = content.split(/## Segment (\d+)/).filter(Boolean);
        const parsed = [];
        
        // Basic heuristic to check if it matches legacy format at all
        let isLegacy = false;
        
        for (let i = 0; i < chunks.length; i += 2) {
            const id = chunks[i];
            const body = chunks[i+1] || "";
            if (!/^\d+$/.test(id)) continue;

            isLegacy = true; 
            const roleMatch = body.match(/\*\*Narrative Role:\*\*\s*([\s\S]*?)(?=\*\*Analysis:|\n##|$)/);
            const analysisMatch = body.match(/\*\*Analysis:\*\*\s*([\s\S]*?)(?=$)/);
            
            let narratives = roleMatch ? roleMatch[1].trim() : "";
            let analysis = analysisMatch ? analysisMatch[1].trim() : "";
            
            let mainContent = body;
            if (roleMatch) mainContent = mainContent.replace(roleMatch[0], '');
            if (analysisMatch) mainContent = mainContent.replace(analysisMatch[0], '');
            
            mainContent = mainContent.trim();
            const lines = mainContent.split('\n').filter(l => l.trim().length > 0);
            
            const title = (lines.length > 0 && lines[0].length < 50) ? lines[0] : "Untitled Segment";
            const textBody = (lines.length > 0 && lines[0].length < 50) ? lines.slice(1).join('\n') : lines.join('\n');

            parsed.push({ 
                id, 
                title, 
                content: textBody, 
                original: '',
                narrative_role: narratives, 
                analysis: analysis 
            });
        }
        
        if (isLegacy && parsed.length > 0) {
            setSegments(parsed);
            setIsRawMode(false);
        } else {
            setSegments([]);
            setIsRawMode(true);
        }
    }, [activeEpisode]);

    const handleSegmentChange = (idx, field, value) => {
        const newSegments = [...segments];
        newSegments[idx] = { ...newSegments[idx], [field]: value };
        setSegments(newSegments);
    };

    const handleSave = async () => {
        if (!activeEpisode) return;
        if (onLog) onLog("Saving Script...", "process");

        let fullContent = rawContent;

        if (!isRawMode && segments.length > 0) {
            const header = `| Paragraph ID | Title | Content (Revised) | Content (Original) | Narrative Function | Analysis & Adaptation Notes |\n|---|---|---|---|---|---|`;
            const rows = segments.map(seg => {
                const clean = (txt) => (txt || '').replace(/\n/g, '<br>').replace(/\|/g, '\\|');
                return `| ${seg.id} | ${clean(seg.title)} | ${clean(seg.content)} | ${clean(seg.original)} | ${clean(seg.narrative_role)} | ${clean(seg.analysis)} |`;
            }).join('\n');
            fullContent = header + '\n' + rows;
        }
        
        // console.log("Saving Content:", fullContent.substring(0, 100) + "...");

        try {
            await onUpdateScript(activeEpisode.id, fullContent);
            if (onLog) onLog(`Script saved. Length: ${fullContent.length}`, "success");
            // If we just saved from Raw Mode, keep it in sync but don't force parse unless user wants to
            // Actually the Effect will trigger on activeEpisode update if we parent updates it? 
            // Usually onUpdateScript updates parent state? If so, useEffect runs. 
            // If raw text saved, it will probably stay in Raw Mode (parsing fails).
            alert("Script saved successfully!");
        } catch (e) {
             console.error(e);
             if (onLog) onLog(`Script Save Failed: ${e.message}`, "error");
             alert(`Failed to save script: ${e.message}`);
        }
    };
    
    // AI Analysis Handler
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [showAnalysisModal, setShowAnalysisModal] = useState(false);
    const [systemPrompt, setSystemPrompt] = useState("");
    const [userPrompt, setUserPrompt] = useState("");
    const [isSuperuser, setIsSuperuser] = useState(false);

    // Check user role on mount
    useEffect(() => {
        fetchMe().then(user => {
            if (user && user.is_superuser) {
                setIsSuperuser(true);
            }
        }).catch(() => {});
    }, []);

    const handleAnalysisClick = async () => {
        if (!rawContent || rawContent.trim().length < 10) {
            alert("Script content is too short for analysis.");
            return;
        }

        if (isSuperuser) {
            // Fetch default prompt
            try {
                const res = await fetchPrompt("scene_analysis.txt");
                setSystemPrompt(res.content);
                
                // Construct full user prompt with metadata visible
                let fullContent = rawContent;
                if (project?.global_info) {
                     const info = project.global_info;
                     const metaParts = ["Project Overview Context:"];
                     if (info.script_title) metaParts.push(`Title: ${info.script_title}`);
                     if (info.type) metaParts.push(`Type: ${info.type}`);
                     if (info.tone) metaParts.push(`Tone: ${info.tone}`);
                     if (info.Global_Style) metaParts.push(`Global Style: ${info.Global_Style}`);
                     if (info.base_positioning) metaParts.push(`Base Positioning: ${info.base_positioning}`);
                     if (info.lighting) metaParts.push(`Lighting: ${info.lighting}`);
                     if (info.series_episode) metaParts.push(`Episode: ${info.series_episode}`);
                     
                     if (metaParts.length > 1) {
                        fullContent = `${metaParts.join('\n')}\n\nScript to Analyze:\n\n${rawContent}`;
                     }
                }
                
                setUserPrompt(fullContent);
                setShowAnalysisModal(true);
            } catch (e) {
                console.error("Failed to fetch system prompt", e);
                // Fallback if fails
                setSystemPrompt("Error loading system prompt.");
                setUserPrompt(rawContent);
                setShowAnalysisModal(true);
            }
        } else {
             // Normal user flow
             if (!confirm("This will overwrite the current raw content with the AI analysis result (Markdown Table format). Continue?")) {
                return;
            }
            executeAnalysis(rawContent);
        }
    };

    const executeAnalysis = async (content, customSystemPrompt = null, skipMetadata = false) => {
        setIsAnalyzing(true);
        if (onLog) onLog("Starting AI Scene Analysis...", "start");

        try {
            // Include project metadata if available, unless skipped (baked in)
            const metadata = skipMetadata ? null : (project?.global_info || null);
            console.log("[ScriptEditor] Executing Analysis. Project Prop:", project);
            console.log("[ScriptEditor] Using Metadata:", metadata);
            
            const result = await analyzeScene(content, customSystemPrompt, metadata);
            const analyzedText = result.result || result.analysis || (typeof result === 'string' ? result : JSON.stringify(result));

            setRawContent(analyzedText);
            
            // Auto-save the analyzed content
            if (onLog) onLog("Analysis complete. Saving result...", "process");
            await onUpdateScript(activeEpisode.id, analyzedText);
            
            if (onLog) onLog("AI Analysis applied and saved.", "success");
            alert("AI Scene Analysis Completed!");
            setShowAnalysisModal(false);
        } catch (e) {
            console.error(e);
            if (onLog) onLog(`Analysis Failed: ${e.message}`, "error");
            alert(`Analysis failed: ${e.message}`);
        } finally {
            setIsAnalyzing(false);
        }
    };

    if (!activeEpisode) return <div className="p-8 text-muted-foreground">Select or create an episode to start writing.</div>;

    return (
        <div className="p-4 sm:p-8 h-full flex flex-col w-full max-w-full overflow-hidden">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4 shrink-0">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                    {activeEpisode.title}
                    <span className="text-sm font-normal text-muted-foreground bg-white/5 px-2 py-0.5 rounded-full">
                        {isRawMode ? 'Raw Editor' : `${segments.length} Segments`}
                    </span>
                </h2>
                <div className="flex items-center gap-2">
                    {segments.length > 0 && (
                        <button 
                            onClick={() => setIsRawMode(!isRawMode)} 
                            className="px-4 py-2 bg-white/10 text-white rounded-lg text-sm font-bold hover:bg-white/20"
                        >
                            {isRawMode ? "Switch to Table View" : "Edit Raw Text"}
                        </button>
                    )}
                    {isRawMode && (
                        <button 
                            onClick={handleAnalysisClick} 
                            disabled={isAnalyzing}
                            className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 ${isAnalyzing ? 'bg-purple-900/50 text-purple-200 cursor-not-allowed' : 'bg-purple-600 text-white hover:bg-purple-500'}`}
                            title="Analyze raw script to generate structure"
                        >
                            {isAnalyzing ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" /> Analyzing...
                                </>
                            ) : (
                                <>
                                    <Wand2 className="w-4 h-4" /> AI Scene Analysis
                                </>
                            )}
                        </button>
                    )}
                    {!isRawMode && (
                        <button 
                            onClick={handleMerge} 
                            className="px-4 py-2 bg-white/10 text-white rounded-lg text-sm font-bold hover:bg-white/20 flex items-center gap-2"
                            title="Merge all segments into a single script"
                        >
                            <LayoutList className="w-4 h-4" />
                            Merge Script
                        </button>
                    )}
                    <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90">Save Changes</button>
                </div>
            </div>

            <div className="flex-1 overflow-hidden border border-white/10 rounded-xl bg-black/20 flex flex-col">
                {isRawMode ? (
                    <textarea 
                        className="w-full h-full p-6 bg-transparent text-white/90 font-mono text-sm leading-relaxed focus:outline-none custom-scrollbar resize-none"
                        placeholder="Paste or type your script here..."
                        value={rawContent}
                        onChange={(e) => setRawContent(e.target.value)}
                    />
                ) : (
                    <div className="overflow-auto custom-scrollbar h-full w-full">
                        <table className="w-full text-left border-collapse text-sm">
                            <thead className="bg-white/5 sticky top-0 z-10 backdrop-blur-md">
                                <tr>
                                    <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-16">ID</th>
                                    <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-48">Title</th>
                                    <th className="p-4 border-b border-white/10 font-medium text-muted-foreground min-w-[300px]">Content (Revised)</th>
                                    <th className="p-4 border-b border-white/10 font-medium text-muted-foreground min-w-[300px]">Content (Original)</th>
                                    <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-48">Narrative Function</th>
                                    <th className="p-4 border-b border-white/10 font-medium text-muted-foreground w-64">Analysis & Adaptation Notes</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {segments.map((seg, idx) => (
                                    <tr key={idx} className="hover:bg-white/5 transition-colors group">
                                        <td className="p-4 align-top font-mono text-xs text-muted-foreground">{seg.id}</td>
                                        <td className="p-4 align-top font-bold text-primary">
                                            {seg.title}
                                        </td>
                                        <td className="p-4 align-top">
                                            <textarea 
                                                className="w-full bg-transparent border-none text-white/90 leading-relaxed font-serif focus:outline-none focus:ring-0 resize-none overflow-hidden"
                                                style={{ minHeight: '60px' }}
                                                ref={(el) => {
                                                    if (el) {
                                                        el.style.height = 'auto';
                                                        el.style.height = el.scrollHeight + 'px';
                                                    }
                                                }}
                                                onInput={(e) => {
                                                    e.target.style.height = 'auto';
                                                    e.target.style.height = e.target.scrollHeight + 'px';
                                                }}
                                                value={seg.content || ''}
                                                onChange={(e) => handleSegmentChange(idx, 'content', e.target.value)}
                                            />
                                        </td>
                                        <td className="p-4 align-top whitespace-pre-wrap text-muted-foreground leading-relaxed text-xs italic">
                                            {seg.original}
                                        </td>
                                        <td className="p-4 align-top text-xs text-muted-foreground whitespace-pre-wrap">
                                            {seg.narrative_role}
                                        </td>
                                        <td className="p-4 align-top text-xs text-indigo-300/80 bg-white/5 group-hover:bg-white/10 whitespace-pre-wrap">
                                            {seg.analysis}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {showAnalysisModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={() => setShowAnalysisModal(false)}>
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-6xl h-[90vh] flex flex-col shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <Wand2 className="w-5 h-5 text-purple-500" />
                                Advanced AI Analysis (Superuser)
                            </h3>
                            <button onClick={() => setShowAnalysisModal(false)} className="p-1 hover:bg-white/10 rounded-lg transition-colors">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        
                        <div className="flex-1 p-6 grid grid-cols-2 gap-6 overflow-hidden">
                            <div className="flex flex-col h-full">
                                <label className="text-sm font-bold text-muted-foreground mb-2 flex items-center justify-between">
                                    System Prompt
                                    <span className="text-xs font-normal opacity-70">Define the AI persona & rules</span>
                                </label>
                                <textarea
                                    className="flex-1 w-full bg-black/30 border border-white/10 text-white/90 p-3 font-mono text-xs leading-relaxed rounded-lg focus:outline-none focus:border-purple-500/50 resize-none custom-scrollbar"
                                    value={systemPrompt}
                                    onChange={(e) => setSystemPrompt(e.target.value)}
                                    spellCheck={false}
                                />
                            </div>
                            <div className="flex flex-col h-full">
                                <label className="text-sm font-bold text-muted-foreground mb-2 flex items-center justify-between">
                                    User Input (Script)
                                    <span className="text-xs font-normal opacity-70">The content to act upon</span>
                                </label>
                                <textarea
                                    className="flex-1 w-full bg-black/30 border border-white/10 text-white/90 p-3 font-mono text-sm leading-relaxed rounded-lg focus:outline-none focus:border-purple-500/50 resize-none custom-scrollbar"
                                    value={userPrompt}
                                    onChange={(e) => setUserPrompt(e.target.value)}
                                    spellCheck={false}
                                />
                            </div>
                        </div>
                        
                        <div className="p-4 border-t border-white/10 bg-white/5 flex justify-end gap-2">
                             <button
                                onClick={() => {
                                    const fullText = `[System Instruction]\n${systemPrompt}\n\n[User Input]\n${userPrompt}`;
                                    navigator.clipboard.writeText(fullText);
                                    if(onLog) onLog("Copied full prompt to clipboard.", "success");
                                    alert("Full prompt copied!");
                                }}
                                className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg font-medium transition-colors text-white border border-white/10"
                             >
                                <Copy className="w-4 h-4" /> Copy Full Prompt
                             </button>
                             <button 
                                onClick={() => executeAnalysis(userPrompt, systemPrompt, true)}
                                disabled={isAnalyzing}
                                className="flex items-center gap-2 px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                             >
                                {isAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                                Run Analysis
                             </button>
                        </div>
                    </div>
                </div>
            )}

            {showMerged && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={() => setShowMerged(false)}>
                    <div className="bg-[#1a1a1a] border border-white/10 rounded-xl w-full max-w-4xl h-[85vh] flex flex-col shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <ScrollText className="w-5 h-5 text-primary" />
                                Merged Script
                            </h3>
                            <button onClick={() => setShowMerged(false)} className="p-1 hover:bg-white/10 rounded-lg transition-colors">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <div className="flex-1 p-6 overflow-hidden">
                            <textarea
                                className="w-full h-full bg-black/30 border border-white/10 text-white p-4 font-serif text-lg leading-relaxed rounded-lg focus:outline-none focus:border-primary/50 resize-none custom-scrollbar"
                                value={mergedContent}
                                readOnly
                            />
                        </div>
                        <div className="p-4 border-t border-white/10 bg-white/5 flex justify-end gap-2">
                             <button 
                                onClick={() => {
                                    navigator.clipboard.writeText(mergedContent);
                                    alert("Script copied to clipboard!");
                                }}
                                className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg font-medium transition-colors text-white"
                             >
                                <Copy className="w-4 h-4" /> Copy to Clipboard
                             </button>
                             <button 
                                onClick={() => setShowMerged(false)}
                                className="px-4 py-2 bg-primary text-black rounded-lg font-bold hover:bg-primary/90"
                             >
                                Close
                             </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};


const MarkdownCell = ({ value, onChange, placeholder, className }) => {
    const [isEditing, setIsEditing] = useState(false);
    const [localValue, setLocalValue] = useState(value || '');

    useEffect(() => {
        setLocalValue(value || '');
    }, [value]);

    const handleBlur = () => {
        setIsEditing(false);
        onChange(localValue);
    };

    if (isEditing) {
        return (
            <textarea
                className={`w-full bg-black/40 border border-primary/50 rounded p-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-y min-h-[5rem] custom-scrollbar ${className}`}
                value={localValue}
                onChange={(e) => setLocalValue(e.target.value)}
                onBlur={handleBlur}
                autoFocus
                placeholder={placeholder}
            />
        );
    }

    return (
        <div 
            className={`w-full min-h-[3rem] p-2 hover:bg-white/10 cursor-text text-sm prose prose-invert prose-p:my-1 prose-headings:my-2 max-w-none text-gray-300 border border-transparent hover:border-white/10 rounded transition-colors ${className}`}
            onClick={() => setIsEditing(true)}
            title="Click to edit"
        >
            {value ? <ReactMarkdown>{value}</ReactMarkdown> : <span className="opacity-30 italic">{placeholder || 'Empty'}</span>}
        </div>
    );
};


const MediaDetailModal = ({ media, onClose }) => {
    if (!media) return null;

    return (
        <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-8" onClick={onClose}>
             <div className="bg-[#1a1a1a] border border-white/10 rounded-xl overflow-hidden max-w-6xl w-full max-h-[90vh] flex shadow-2xl" onClick={e => e.stopPropagation()}>
                {/* Media Area */}
                <div className="flex-1 bg-black/50 flex items-center justify-center p-4 relative group/modal min-h-[400px]">
                    {media.type === 'video' ? (
                        <video src={getFullUrl(media.url)} controls autoPlay className="max-w-full max-h-full shadow-lg rounded" />
                    ) : (
                        <img src={getFullUrl(media.url)} className="max-w-full max-h-full object-contain shadow-lg rounded" alt="Detail" />
                    )}
                    
                    <button 
                        className="absolute top-4 right-4 bg-black/50 text-white p-2 rounded-full hover:bg-white/20 transition-colors"
                        onClick={onClose}
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* Metadata Sidebar */}
                <div className="w-80 bg-[#151515] border-l border-white/10 p-6 flex flex-col gap-4 overflow-y-auto shrink-0">
                    <div>
                        <h3 className="text-xl font-bold text-white mb-1 truncate" title={media.title || 'Media Details'}>{media.title || 'Media Details'}</h3>
                        <div className="text-xs text-muted-foreground uppercase font-bold">{media.type || 'Image'} Asset</div>
                    </div>

                    <div className="space-y-4">
                        {media.prompt && (
                             <div className="bg-white/5 p-3 rounded-lg border border-white/5">
                                <span className="text-[10px] uppercase font-bold text-primary/70 block mb-1">Prompt / Description</span>
                                <p className="text-xs text-gray-300 leading-relaxed font-mono">
                                    {media.prompt}
                                </p>
                            </div>
                        )}
                        
                        <div className="grid grid-cols-2 gap-2">
                             <div className="bg-white/5 p-2 rounded border border-white/5">
                                <span className="text-[10px] uppercase text-gray-500 block">Resolution</span>
                                <span className="text-xs text-gray-300">{media.resolution || 'Unknown'}</span>
                            </div>
                             <div className="bg-white/5 p-2 rounded border border-white/5">
                                <span className="text-[10px] uppercase text-gray-500 block">Source</span>
                                <span className="text-xs text-gray-300">{media.source || 'Generated'}</span>
                            </div>
                        </div>

                         {/* JSON Metadata */}
                         {media.metadata && (
                            <div className="space-y-1">
                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Technical Metadata</h4>
                                <div className="p-2 bg-black/40 rounded border border-white/5 text-[10px] font-mono text-gray-400 overflow-x-auto whitespace-pre-wrap">
                                    {typeof media.metadata === 'string' ? media.metadata : JSON.stringify(media.metadata, null, 2)}
                                </div>
                            </div>
                         )}

                         <div className="mt-auto pt-4 border-t border-white/10">
                            <a href={media.url} download target="_blank" rel="noopener noreferrer" className="w-full py-2 bg-white/5 hover:bg-white/10 text-white border border-white/10 rounded flex items-center justify-center gap-2 text-sm font-medium transition-colors">
                                <Download size={16}/> Download Original
                            </a>
                         </div>
                    </div>
                </div>
             </div>
        </div>
    );
};

const MediaPickerModal = ({ isOpen, onClose, onSelect, projectId, context = {}, entities = [], episodeId = null }) => {
    const [tab, setTab] = useState('assets');
    const [assets, setAssets] = useState([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState(null); // Detail/Preview Mode
    
    // Filters
    const [filterScope, setFilterScope] = useState('project'); // 'project', 'subject', 'shot', 'type'
    const [filterType, setFilterType] = useState('all'); // 'all', 'image', 'video'
    const [filterValue, setFilterValue] = useState(''); // entity_id or shot_id or entity_type
    
    const [availableShots, setAvailableShots] = useState([]);

    useEffect(() => {
        if (isOpen) {
             setSelectedAsset(null); // Reset detail view on open
        }
        if (isOpen && tab === 'assets') {
             // Reset filters if context is provided?
             // If context has entityId, maybe default to subject?
             if (context.entityId && filterScope === 'project') {
                 setFilterScope('subject');
                 setFilterValue(context.entityId);
             } else if (context.shotId && filterScope === 'project') {
                 // setFilterScope('shot'); // Optional: heuristic
                 // setFilterValue(context.shotId);
             }
        }
    }, [isOpen]);

    useEffect(() => {
         // Load shots if needed
         if (filterScope === 'shot' && episodeId && availableShots.length === 0) {
             fetchEpisodeShots(episodeId).then(data => {
                 setAvailableShots(data.sort((a,b) => {
                      // simple sort by shot_id alphanumeric
                      return a.shot_id.localeCompare(b.shot_id, undefined, { numeric: true });
                 }));
             }).catch(console.error);
         }
    }, [filterScope, episodeId]);

    useEffect(() => {
        if (isOpen && tab === 'assets') {
            loadAssets();
        }
    }, [isOpen, tab, filterScope, filterType, filterValue]);

    const loadAssets = () => {
        setLoading(true);
        const params = {};
        if (filterType !== 'all') params.type = filterType;
        
        // Base scope is Project
        if (projectId) params.project_id = projectId;
        
        // Refine scope
        let clientSideFilterIds = null; // If set, filter by these entity IDs locally

        if (filterScope === 'subject' && filterValue) {
            params.entity_id = filterValue;
        } else if (filterScope === 'shot' && filterValue) {
            params.shot_id = filterValue;
        } else if (filterScope === 'type' && filterValue) {
            // "By Type" strategy: Fetch project assets, then filter by entity_id belonging to that type
            // Find all entities of this type
            const targetEntities = entities.filter(e => (e.type || 'prop').toLowerCase() === filterValue.toLowerCase());
            clientSideFilterIds = new Set(targetEntities.map(e => e.id));
        }
        
        fetchAssets(params).then(data => {
            let res = data || [];
            
            // Client-side filtering for Entity Type logic (if backend doesn't support recursive type filtering)
            if (clientSideFilterIds) {
                res = res.filter(a => {
                    const eid = a.meta_info?.entity_id;
                    return eid && clientSideFilterIds.has(Number(eid));
                });
            }

            setAssets(res);
        }).catch(console.error).finally(() => setLoading(false));
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setUploading(true);
        try {
            // Attach context to upload
            const meta = {};
            if (projectId) meta.project_id = projectId;
            if (context.entityId) meta.entity_id = context.entityId;
            if (context.shotId) meta.shot_id = context.shotId;

            const asset = await uploadAsset(file, meta); 
            if (asset && asset.url) {
                onSelect(asset.url, asset.type || (file.type.startsWith('video') ? 'video' : 'image'));
            }
            if (tab === 'assets') loadAssets();
        } catch (e) {
            console.error("Upload failed", e);
            alert("Upload failed: " + e.message);
        } finally {
            setUploading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[110] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
             <div className="bg-[#1e1e1e] border border-white/10 rounded-xl w-full max-w-2xl h-[600px] flex flex-col shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
                <div className="flex justify-between items-center p-4 border-b border-white/10 bg-black/20">
                    <h3 className="font-bold text-md">Select Media</h3>
                    <button onClick={onClose} className="text-white/50 hover:text-white"><X size={20} /></button>
                </div>

                <div className="flex border-b border-white/10">
                    {['assets', 'upload', 'url'].map(t => (
                        <button
                            key={t}
                            onClick={() => setTab(t)}
                            className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${tab === t ? 'border-primary text-primary bg-primary/5' : 'border-transparent text-muted-foreground hover:text-white hover:bg-white/5'}`}
                        >
                            {t.charAt(0).toUpperCase() + t.slice(1)}
                        </button>
                    ))}
                </div>

                {/* Filters Bar */}
                {tab === 'assets' && (
                    <div className="flex items-center gap-2 p-3 bg-black/10 border-b border-white/5 flex-wrap">
                        <select 
                            value={filterScope}
                            onChange={(e) => {
                                setFilterScope(e.target.value);
                                setFilterValue('');
                            }}
                            className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                        >
                            <option value="project">All Project Assets</option>
                            <option value="type">By Subject Type</option>
                            <option value="subject">By Exact Subject</option>
                            <option value="shot">By Storyboard (Shot)</option>
                        </select>

                        {/* Refinement Selector */}
                        {filterScope === 'type' && (
                             <select 
                                value={filterValue}
                                onChange={(e) => setFilterValue(e.target.value)}
                                className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50 max-w-[150px]"
                            >
                                <option value="">Select Type...</option>
                                <option value="character">Characters</option>
                                <option value="prop">Props</option>
                                <option value="environment">Environments</option>
                            </select>
                        )}

                        {filterScope === 'subject' && (
                             <select 
                                value={filterValue}
                                onChange={(e) => setFilterValue(e.target.value)}
                                className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50 max-w-[150px]"
                            >
                                <option value="">Select Subject...</option>
                                {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                            </select>
                        )}

                        {filterScope === 'shot' && (
                             <select 
                                value={filterValue}
                                onChange={(e) => setFilterValue(e.target.value)}
                                className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50 max-w-[150px]"
                            >
                                <option value="">Select Shot...</option>
                                {availableShots.map(s => <option key={s.id} value={s.id}>{s.shot_id} - {s.shot_name || 'Untitled'}</option>)}
                            </select>
                        )}

                        <select 
                            value={filterType}
                            onChange={(e) => setFilterType(e.target.value)}
                            className="bg-[#151515] border border-white/10 rounded text-xs px-2 py-1 text-white outline-none focus:border-primary/50"
                        >
                            <option value="all">All Types</option>
                            <option value="image">Images Only</option>
                            <option value="video">Videos Only</option>
                        </select>
                        
                        <div className="ml-auto text-[10px] text-muted-foreground">
                            {assets.length} results
                        </div>
                    </div>
                )}

                <div className="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#151515]">
                    {tab === 'assets' && (
                        loading ? <div className="flex items-center justify-center h-full"><RefreshCw className="animate-spin text-muted-foreground"/></div> :
                        <div className="grid grid-cols-4 gap-3">
                            {assets.map(asset => (
                                <div 
                                    key={asset.id} 
                                    onClick={() => setSelectedAsset(asset)}
                                    className="aspect-square bg-black/40 rounded overflow-hidden border border-white/5 hover:border-primary/50 cursor-pointer group relative"
                                >
                                    {asset.type === 'video' ? (
                                        <div className="w-full h-full flex items-center justify-center bg-black">
                                            <Video className="text-white/50 group-hover:text-primary transition-colors"/>
                                        </div>
                                    ) : (
                                        <img src={getFullUrl(asset.url)} alt="asset" className="w-full h-full object-cover" />
                                    )}
                                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
                                    <div className="absolute bottom-0 inset-x-0 p-1 bg-black/60 text-[9px] truncate text-white/70">
                                        {asset.name}
                                    </div>
                                    {/* Quick Select Button on Hover */}
                                    <button 
                                        onClick={(e) => { e.stopPropagation(); onSelect(asset.url, asset.type); }}
                                        className="absolute top-1 right-1 bg-primary text-black p-1 rounded-full opacity-0 group-hover:opacity-100 transition-all hover:scale-110 shadow-lg"
                                        title="Quick Select"
                                    >
                                        <Check size={12} strokeWidth={3} />
                                    </button>
                                </div>
                            ))}
                            {assets.length === 0 && <div className="col-span-4 text-center text-muted-foreground py-8">No assets found</div>}
                        </div>
                    )}
                    
                    {/* Asset Detail Overlay */}
                    {selectedAsset && (
                        <div className="absolute inset-0 bg-[#1e1e1e] z-20 flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-200">
                             <div className="flex justify-between items-center p-3 border-b border-white/10 bg-black/20">
                                <h4 className="font-bold text-sm flex items-center gap-2">
                                    <button onClick={() => setSelectedAsset(null)} className="hover:bg-white/10 p-1 rounded"><ArrowLeft size={16}/></button>
                                    Asset Details
                                </h4>
                                <div className="flex gap-2">
                                     <button 
                                        onClick={() => { onSelect(selectedAsset.url, selectedAsset.type); }}
                                        className="bg-primary text-black text-xs font-bold px-3 py-1.5 rounded hover:opacity-90 flex items-center gap-1"
                                     >
                                        <Check size={14}/> Select This Asset
                                     </button>
                                </div>
                            </div>
                            <div className="flex-1 overflow-hidden flex">
                                <div className="flex-1 bg-black/40 flex items-center justify-center p-4">
                                     {selectedAsset.type === 'video' ? (
                                        <video src={getFullUrl(selectedAsset.url)} controls className="max-w-full max-h-full rounded shadow-lg"/>
                                     ) : (
                                        <img src={getFullUrl(selectedAsset.url)} className="max-w-full max-h-full object-contain rounded shadow-lg"/>
                                     )}
                                </div>
                                <div className="w-80 bg-[#151515] border-l border-white/10 p-4 overflow-y-auto space-y-4">
                                    <div>
                                        <label className="text-[10px] tx-muted-foreground font-bold uppercase">Name</label>
                                        <div className="text-sm font-medium">{selectedAsset.name || 'Untitled'}</div>
                                    </div>
                                    
                                    {selectedAsset.meta_info?.entity_id && (
                                        <div>
                                            <label className="text-[10px] tx-muted-foreground font-bold uppercase">Linked Entity</label>
                                            <div className="text-xs bg-white/5 p-2 rounded border border-white/5 mt-1">
                                                {entities.find(e => e.id === Number(selectedAsset.meta_info.entity_id))?.name || `Entity #${selectedAsset.meta_info.entity_id}`}
                                            </div>
                                        </div>
                                    )}
                                    
                                    {selectedAsset.meta_info?.shot_id && (
                                        <div>
                                            <label className="text-[10px] tx-muted-foreground font-bold uppercase">Source Shot</label>
                                            <div className="text-xs bg-white/5 p-2 rounded border border-white/5 mt-1">
                                                {availableShots.find(s => s.id === Number(selectedAsset.meta_info.shot_id))?.shot_id || `Shot #${selectedAsset.meta_info.shot_id}`}
                                            </div>
                                        </div>
                                    )}

                                    {selectedAsset.meta_info?.prompt && (
                                        <div>
                                            <label className="text-[10px] tx-muted-foreground font-bold uppercase">Prompt</label>
                                            <div className="text-xs text-gray-400 bg-white/5 p-2 rounded border border-white/5 mt-1 max-h-[150px] overflow-y-auto custom-scrollbar">
                                                {selectedAsset.meta_info.prompt}
                                            </div>
                                        </div>
                                    )}
                                    
                                    {/* Detailed Technical Metadata */}
                                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/5">
                                         {selectedAsset.meta_info?.resolution && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">Resolution</label>
                                                <div className="text-xs text-gray-300">{selectedAsset.meta_info.resolution}</div>
                                            </div>
                                         )}
                                         {selectedAsset.meta_info?.size && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">Size</label>
                                                <div className="text-xs text-gray-300">{selectedAsset.meta_info.size}</div>
                                            </div>
                                         )}
                                          {selectedAsset.meta_info?.format && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">Format</label>
                                                <div className="text-xs text-gray-300">{selectedAsset.meta_info.format}</div>
                                            </div>
                                         )}
                                          {selectedAsset.meta_info?.duration && (
                                            <div>
                                                <label className="text-[10px] tx-muted-foreground font-bold uppercase">Duration</label>
                                                <div className="text-xs text-gray-300">{/* Normalize 5.0 to 5s */}
                                                {String(selectedAsset.meta_info.duration).endsWith('.0') ? parseInt(selectedAsset.meta_info.duration) : selectedAsset.meta_info.duration}s
                                                </div>
                                            </div>
                                         )}
                                    </div>

                                    <div className="text-[10px] text-muted-foreground pt-4 border-t border-white/5">
                                        File: {selectedAsset.url.split('/').pop()} <br/>
                                        Created: {new Date(selectedAsset.created_at).toLocaleString()}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {tab === 'upload' && (
                        <div className="flex flex-col items-center justify-center h-full space-y-4">
                            <div className="p-8 border-2 border-dashed border-white/10 rounded-xl bg-black/20 hover:border-primary/50 hover:bg-primary/5 transition-all w-full max-w-sm flex flex-col items-center justify-center cursor-pointer relative">
                                <input 
                                    type="file" 
                                    accept="image/*,video/*" 
                                    onChange={handleUpload}
                                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                    disabled={uploading} 
                                />
                                {uploading ? <RefreshCw className="animate-spin text-primary mb-2" size={32} /> : <Upload className="text-muted-foreground mb-2" size={32} />}
                                <span className="text-sm font-medium text-muted-foreground">
                                    {uploading ? 'Uploading...' : 'Click or drop file here'}
                                </span>
                            </div>
                        </div>
                    )}

                    {tab === 'url' && (
                         <div className="flex flex-col items-center justify-center h-full">
                            <div className="w-full max-w-sm space-y-4">
                                <div>
                                    <label className="text-xs font-bold uppercase text-muted-foreground mb-1 block">Image / Video URL</label>
                                    <input 
                                        type="text" 
                                        id="media-url-input"
                                        placeholder="https://..." 
                                        className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm focus:border-primary/50 outline-none"
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') onSelect(e.target.value, 'image'); // Default to image on enter, user can correct contexts usually know
                                        }}
                                    />
                                </div>
                                <button 
                                    onClick={() => {
                                        const val = document.getElementById('media-url-input').value;
                                        if (val) onSelect(val, 'image');
                                    }}
                                    className="w-full py-2 bg-primary text-black font-bold rounded hover:opacity-90"
                                >
                                    Confirm
                                </button>
                            </div>
                        </div>
                    )}
                </div>
             </div>
        </div>
    );
};

const ReferenceManager = ({ shot, entities, onUpdate, title = "Reference Images", promptText = "", onPickMedia = null, useSequenceLogic = false, storageKey = "ref_image_urls", additionalAutoRefs = [], strictPromptOnly = false, onFindPrevFrame = null }) => {
    const [selectedImage, setSelectedImage] = useState(null);

    // 1. Parsing Entities Logic
    const getEntityMatches = () => {
        if (!shot || !entities.length) return [];
        
        // 1. Collect Raw Strings
        const rawMatches = [];
        
        // Source 1: Associated Entities (if allowed)
        if (!strictPromptOnly && shot.associated_entities) {
            rawMatches.push(...shot.associated_entities.split(/[,，]/));
        }
        
        // Source 2: Prompt Text - Extract content inside [], {}, 【】, ｛｝
        // Use [\s\S]+? to capture anything (including newlines) until the first closing bracket.
        // This is robust against strange characters and newlines.
        const regexes = [
            /\[([\s\S]+?)\]/g,    // [...]
            /\{([\s\S]+?)\}/g,    // {...}
            /【([\s\S]+?)】/g,     // 【...】
            /｛([\s\S]+?)｝/g      // ｛...｝ (Full-width braces)
        ];

        console.log("Ref Parsing Prompt Length:", promptText?.length || 0);

        if (promptText) {
            regexes.forEach(regex => {
                let match;
                regex.lastIndex = 0;
                while ((match = regex.exec(promptText)) !== null) {
                    if (match[1]) rawMatches.push(match[1]);
                }
            });
        }
        
        // Manual override for tricky nested cases or if regex fails:
        // Try to find specific pattern {Entity (...)}
        const complexRegex = /\{([^\}]+?)\}\(/g; // Look for } followed by (
        // Actually the main regex should catch {Entity...} fine.
        
        const uniqueRaws = [...new Set(rawMatches.map(s => s.trim()).filter(Boolean))];
        
        // Helper to normalize punctuation (Full-width to Half-width)
        const normalize = (str) => {
            return (str || '')
                .replace(/[（【〔［]/g, '(')
                .replace(/[）】〕］]/g, ')')
                .replace(/[“”"']/g, '') // Remove quotes
                .replace(/\s+/g, ' ')   // Collapse spaces
                .trim()
                .toLowerCase();
        };

        // 2. Generate Search Candidates
        const candidates = new Set();
        uniqueRaws.forEach(raw => {
            // Remove outer brackets [] {} first
            const content = raw.replace(/[\[\]\{\}【】｛｝]/g, '');
            
            // Norm 1: Full content normalized
            const base = normalize(content);
            if (base) candidates.add(base);
            
            // Norm 2: Strip parentheses content (Iterative to handle simple nesting or multiple groups)
            let stripped = base;
            let prev;
            do {
                prev = stripped;
                stripped = stripped.replace(/\([^\(\)]*\)/g, '').trim();
            } while (stripped !== prev);
            
            // Clean up double spaces created by deletion
            stripped = stripped.replace(/\s+/g, ' ').trim();

            if (stripped && stripped !== base) {
                candidates.add(stripped);
            }
        });

        // Debug Log
        console.log(`[${title}] Ref Debug:`, { 
            promptText: (promptText || '').slice(0, 50) + "...", 
            uniqueRaws, 
            candidates: Array.from(candidates),
            entitiesCount: entities.length
        });

        // 3. Match against Entities
        return entities.filter(e => {
            const cn = normalize(e.name);
            const en = normalize(e.name_en);
            
            // Skip empty entities
            if (!cn && !en) return false;

            // Check if ANY candidate matches this entity
            const isMatch = Array.from(candidates).some(cand => {
                // Algorithm: 
                // 1. Exact Match (Highest Priority) - Reference content vs Entity Name
                // User Requirement: Strict Name Matching. NO partial match allowed between candidates and Entity Name.
                // e.g. "Isabella (脏污)" != "Isabella (精致妆容)"
                // BUT "Isabella" candidate should match "Isabella" entity.
                
                // IMPORTANT: The `candidates` set contains BOTH raw strings (e.g. "isabella(dirty)") 
                // AND stripped strings (e.g. "isabella") if parentheses stripping logic ran above.
                
                // So we just need to ensure that the candidate string IS EXACTLY equal to the entity name.
                // We should NOT do .includes() checks anymore per request.

                if (cn && cand === cn) return true;
                if (en && cand === en) return true;
                
                // Super Normalized Match (Ignore spaces and brackets)
                // e.g. "公司门口(低角度)" matches "公司 门口 （低角度）"
                const superNormalize = (s) => s.replace(/[\s\(\)\[\]\{\}（）]/g, '');
                if (cn && superNormalize(cand) === superNormalize(cn)) return true;
                if (en && superNormalize(cand) === superNormalize(en)) return true;

                return false;
            });

            if (isMatch) {
               console.log(`Matched Entity [${e.name}] (norm: ${cn}) with Candidates`, Array.from(candidates));
            }
            // Optional: Log Failures for target specific debugging
            // if (e.name.includes("动物园")) console.log(`Checking Entity [${e.name}] (norm: ${cn}) against`, Array.from(candidates), isMatch);
            
            return isMatch;
        });
    };

    let activeRefs = [];
    const tech = JSON.parse(shot.technical_notes || '{}');
    
    // Normal Mode vs Sequence Mode
    if (useSequenceLogic) {
        // Force Order: [Start Frame, ...Keyframes, End Frame]
        if (shot.image_url) activeRefs.push(shot.image_url);
        if (tech.keyframes && Array.isArray(tech.keyframes)) {
            activeRefs.push(...tech.keyframes);
        }
        if (tech.end_frame_url) activeRefs.push(tech.end_frame_url);
        // Deduplicate while preserving order if needed, but for sequence, duplicates might differ by position technically
        // but image url same means same image. Let's uniq by URL to avoid UI keys issues
        activeRefs = [...new Set(activeRefs)];
    } else {
        // Standard entity/manual ref logic
        const isManualMode = tech[storageKey] && Array.isArray(tech[storageKey]);
        
        // User Request: Refs (Video) should NOT do entity identification (only start/end/keyframes).
        const shouldDetectEntities = storageKey !== 'video_ref_image_urls';
        const autoMatches = shouldDetectEntities ? getEntityMatches().map(e => e.image_url).filter(Boolean) : [];

        if (isManualMode) {
             // Manual Mode: Use saved list
             // User Request: "Detected in Prompt" should be directly visible in Refs even in Manual Mode
             // Logic: Merge saved refs with auto-detected matches, unless they are explicitly deleted.
             const savedRefs = [...tech[storageKey]];
             const deletedRefs = tech.deleted_ref_urls || [];
             
             // Identify auto matches that are NOT in saved list AND NOT in deleted list
             const newAutoMatches = autoMatches.filter(url => 
                !savedRefs.includes(url) && !deletedRefs.includes(url)
             );

             activeRefs = [...savedRefs, ...newAutoMatches];
        } else {
             // Auto Mode: Visualize what will be used by default (since nothing saved yet)
             activeRefs = [...autoMatches];

            // --- GLOBAL INJECTION RULES (Apply only in Auto Mode to allow manual overrides) ---
            
            // 1. Inject Additional Auto Refs (e.g. Previous Shot End Frame for Start Refs)
            if (additionalAutoRefs && additionalAutoRefs.length > 0) {
                // Iterate in reverse to keep order when unshifting
                for (let i = additionalAutoRefs.length - 1; i >= 0; i--) {
                    const ref = additionalAutoRefs[i];
                    if (!activeRefs.includes(ref)) {
                        activeRefs.unshift(ref);
                    }
                }
            }
        }
        
        // 2. Special Logic for End Refs: Always include Start Frame (Global Injection to ensure Realtime Updates)
        if (storageKey === 'end_ref_image_urls' && shot.image_url) {
            // Check if explicitly deleted
            const deleted = tech.deleted_ref_urls || [];
            const isExplicitlyDeleted = deleted.includes(shot.image_url);

            if (!activeRefs.includes(shot.image_url) && !isExplicitlyDeleted) {
                activeRefs.unshift(shot.image_url); // Prepend Start Frame for context
            }
        }
        
        // 3. Special Logic for Video Refs: Only visual assets
        if (storageKey === 'video_ref_image_urls') {
             // For video, we largely ignore user manual list if it contradicts the generated assets flow?
             // Actually, if user customized it, we should respect it?
             // But the code previously cleared it in Auto mode.
             // Let's keep logic simple: If Video Mode, we assume strict structural refs.
             // But if user manually added strict refs, we keep them?
             // Reverting to previous strict logic for video mode seems safer to avoid "entity pollution".
             if (!tech[storageKey]) {
                activeRefs = [];
                if (shot.image_url) activeRefs.push(shot.image_url);
                if (tech.keyframes && Array.isArray(tech.keyframes)) activeRefs.push(...tech.keyframes);
                if (tech.end_frame_url) activeRefs.push(tech.end_frame_url);
             } else if (isManualMode && shot.image_url && !activeRefs.includes(shot.image_url)) {
                // Ensure Start Frame is visible even in Manual Mode if user didn't explicitly remove it? 
                // Wait - logic above says inject into Auto Only. 
                // If Manual Mode, we trust the list.
                // However user says: "Refs (End)引用首帧时不能实时更新，但Refs (Video)可以"
                // This means when shot.image_url changes, it doesn't show up in Refs(End) if it was already in Manual Mode or Auto Mode didn't catch it?
                
                // If in Auto Mode, the `shot.image_url` is added via Rule #2.
                // If in Manual Mode, `activeRefs` comes from `tech[storageKey]`.
                // If `shot.image_url` changes, `tech[storageKey]` is STALE.
                
                // We must Inject/Update Start Frame in Manual Mode too if it's missing or different?
                // But we don't know if user DELETED it.
                // Compromise: If Start Frame exists, we PREPEND it visually if likely candidates match, 
                // OR we just rely on the fact that if it's "Start Frame", it should always be there for End Gen context.
             }
        }
        
        // FIX FOR REFS (END) NOT UPDATING:
        // Refs (Video) works because we likely force it or it's using a different path.
        // Actually, looking at "Refs (Video)" logic above (lines 1190+), if no manual list, it rebuilds completely including `shot.image_url`.
        // "Refs (End)" logic (line 1175): Only injects `shot.image_url` IF `!activeRefs.includes`.
        
        // Critical Issue: `activeRefs` in Auto Mode comes from `getEntityMatches()` (entity images). 
        // Then we unshift `shot.image_url`.
        // If `shot.image_url` changes, the component re-renders. 
        // `activeRefs` is rebuilt. `shot.image_url` is new. It gets pushed.
        
        // HOWEVER, if Manual Mode (`end_ref_image_urls` exists):
        // `activeRefs` = loaded from DB.
        // If DB has OLD start frame url, and `shot.image_url` is NEW, 
        // `!activeRefs.includes(shot.image_url)` is TRUE.
        // So we unshift the NEW url. 
        // But the OLD url is still there? 
        // Yes, duplicate if old one is just a string.
        
        // User complaint: "Can't realtime update". 
        // Maybe because `ReferenceManager` is memozied or `shot` prop isn't triggering deep update?
        // No, `shot` is passed new object.
        
        // Let's force ensure Start Frame is present for End Refs, similar to Video Refs logic?
        // Actually, the issue might be that we only apply Rule #2 in the `else` (Auto Mode) block from my previous edit.
        // I moved the injection rules INSIDE the `else` block to fix the "Delete" issue.
        // But this broke the "Realtime Update" for manual mode? 
        // If I generate a new Start Frame, I enter Manual Mode? No, generating keeps it in whatever mode.
        // But if I ever saved the list (e.g. by deleting something), I am in Manual Mode.
        // And in Manual Mode, I explicitly REMOVED the injection logic to support deletion.
        
        // Logic Conflict:
        // 1. User wants to DELETE items (requires Manual Mode where we don't Force-Inject).
        // 2. User wants REALTIME UPDATE of Start Frame (requires Force-Injection whenever it changes).
        
        // Resolution:
        // We should identify the "Start Frame" in the list and REPLACE it if it changes, rather than blindly injecting.
        // OR: We only auto-inject into Manual Mode IF the list doesn't contain the *current* start frame.
        // BUT if user deleted it, we re-inject it? That creates the Zombie bug again.
        
        // Correct Approach for "Refs (End)" (Contextual Refs):
        // The Start Frame is a *Dependency*, not just a suggestion.
        // For End Frame generation, you almost ALWAYS want the Start Frame.
        // If the Start Frame updates, the Ref list *should* update to reflect the new reality.
        
        // What if we separate "Hard Dependencies" (Start Frame) from "Soft References" (Style/Entities)?
        // In the UI, we could show Start Frame as a pinned item?
        
        // Current quick fix:
        // Re-enable Injection for Manual Mode but be smarter?
        // OR: Just move the Rule #2 OUT of the `else` block (make it Global again) but check for *stale* versions?
        // For End Refs, the "Start Frame" is key.
        // If I move Rule #2 back out, deleting it becomes impossible because it re-injects.
        
        // Maybe we just allow Deleting it -> adds to an "Ignore List"? Too complex.
        
        // Let's look at "Refs (Video)".
        // It has logic: `if (!tech[storageKey]) { ...rebuild... }`
        // If Manual Mode, it uses `tech[storageKey]`.
        // Does "Refs (Video)" update start frame in Manual Mode?
        // If I have manual video refs, and I update start frame, does it update?
        // If logic is same, it shouldn't.
        // User says "Refs (Video) works". 
        // Maybe because they haven't triggered Manual Mode for Video yet?
        
        // Let's Apply the "Update Logic" specifically for Start Frame replacement.
        // If we find an item in `activeRefs` that LOOKS like a start frame (maybe check previous `shot` state? We don't have it).
        
        // Alternative:
        // We assume `shot.image_url` IS the single truth for the Start Frame dependency.
        // We simply render it as a "System Pinned" reference that cannot be removed? 
        // No, user wants to remove "Start" from "Refs (Start)" previously.
        // But for "Refs (End)", Start Frame is external context.
        
        // Let's try moving Rule #2 back to Global Scope (apply to Manual too), 
        // BUT make `ReferenceManager` smart enough to not resurrect it if *explicitly removed* in this session?
        // Hard to track session.
        
        // Let's strictly follow the request: "Refs (End) ... Refs (Video) worked".
        // Let's see if I can simply enable the injection for Manual Mode ONLY IF it's "Refs (End)" or "Refs (Video)" (for start frame).
        // And accept that Deleting it might be tricky?
        // Or better: Allow Deleting, but if a *New* Start Frame is generated, it comes back?
        // That happens naturally if `shot.image_url` changes value.
        
        // Let's try:
        // Move the Injection Rule for `end_ref_image_urls` + `shot.image_url` OUTSIDE the else block.
        // To prevent "Cannot Delete" Zombie bug:
        // The user was likely complaining about "Refs (Start)" (Start Frame generation refs).
        // "Refs (End)" (End Frame generation refs) *needs* the Start Frame.
        // The previous Zombie bug report was "Refs (Start) delete button invalid". 
        // "Refs (Start)" uses `additionalAutoRefs` (Previous Shot End Frame).
        // It does NOT use `shot.image_url` as a ref (it IS the result).
        
        // So:
        // Rule 1 (Additional Auto Refs - e.g. Prev Shot): Kept inside `else` (Auto only). Fixes "Refs (Start)" delete bug.
        // Rule 2 (Start Frame for End/Video Refs): Move OUTSIDE `else` (Global). 
        // This ensures Start Frame always appears in End/Video refs, updating in real-time.
        // Does this prevent deletion of Start Frame from End Refs? Yes.
        // Is that acceptable? Usually yes, Start Frame is the anchor for End Frame.
        // If user wants to generate End Frame *without* Start Frame context... that's rare?
        // If they really want to, they might struggle. But this fixes the "Update" issue.
        
        // Let's move Rule 2 out.
        
        // 3. Special Logic for Video Refs: Only visual assets
        if (storageKey === 'video_ref_image_urls') {
             // For video, we largely ignore user manual list if it contradicts the generated assets flow?
             // Actually, if user customized it, we should respect it?
             // But the code previously cleared it in Auto mode.
             // Let's keep logic simple: If Video Mode, we assume strict structural refs.
             // But if user manually added strict refs, we keep them?
             // Reverting to previous strict logic for video mode seems safer to avoid "entity pollution".
             if (!tech[storageKey]) {
                activeRefs = [];
                if (shot.image_url) activeRefs.push(shot.image_url);
                if (tech.keyframes && Array.isArray(tech.keyframes)) activeRefs.push(...tech.keyframes);
                if (tech.end_frame_url) activeRefs.push(tech.end_frame_url);
             }
        }
        
        // Deduplicate
        activeRefs = [...new Set(activeRefs)];
    }
    
    // Filter matches that are NOT already active to display as suggestions (Standard Mode Only)
    // USER REQUEST: Show detected entities as suggestions even if in Manual Mode, so user can add them.
    // UPDATE: Detected entities are now auto-merged into activeRefs (unless deleted), so availableMatches logic is minimized.
    // Note: Video Refs totally skip entity matching.
    const entityMatches = (useSequenceLogic || storageKey === 'video_ref_image_urls') ? [] : getEntityMatches();
    const availableMatches = entityMatches.filter(e => {
        // Technically these are items that matched but are NOT in activeRefs.
        // This only happens if they have no image OR were explicitly deleted.
        return !!e.image_url && !activeRefs.includes(e.image_url);
    });

    const handleAdd = (url) => {
        if (!url || activeRefs.includes(url)) return;
        const newRefList = [...activeRefs, url];
        // If sequential, do we save back to ref_image_urls? 
        // User request implies the LOGIC for getting pics is fixed. 
        // So for "Refs (Video)", maybe we don't save to 'ref_image_urls' necessarily, 
        // OR we overwrite 'ref_image_urls' with this sequence so backend uses it?
        // Let's assume we update the standard field so backend picks it up easily.
        const newTech = { ...tech, [storageKey]: newRefList };
        onUpdate({ technical_notes: JSON.stringify(newTech) });
    };

    const handleRemove = (url) => {
        if (useSequenceLogic) return; // Cannot remove derived items in this view
        
        // Track deletions to prevent zombie resurrection by auto-injection
        let deleted = tech.deleted_ref_urls || [];
        if (!deleted.includes(url)) {
            deleted = [...deleted, url];
        }

        const newRefs = activeRefs.filter(u => u !== url);
        const newTech = { ...tech, [storageKey]: newRefs, deleted_ref_urls: deleted };
        onUpdate({ technical_notes: JSON.stringify(newTech) });
    };

    const getEntityInfo = (url) => {
        return entities.find(e => e.image_url === url);
    };

    // Modal Content
    const renderModal = () => {
        if (!selectedImage) return null;
        
        const entity = getEntityInfo(selectedImage);
        
        return (
            <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-8" onClick={() => setSelectedImage(null)}>
                 <div className="bg-[#1a1a1a] border border-white/10 rounded-xl overflow-hidden max-w-5xl w-full max-h-[90vh] flex shadow-2xl" onClick={e => e.stopPropagation()}>
                    {/* Image Area */}
                    <div className="flex-1 bg-black/50 flex items-center justify-center p-4 relative group/modal">
                        <img src={getFullUrl(selectedImage)} className="max-w-full max-h-full object-contain shadow-lg rounded" alt="Detail" />
                        <button 
                            className="absolute top-4 right-4 bg-black/50 text-white p-2 rounded-full hover:bg-white/20 transition-colors"
                            onClick={() => setSelectedImage(null)}
                        >
                            <X size={24} />
                        </button>
                    </div>

                    {/* Metadata Sidebar */}
                    <div className="w-80 bg-[#151515] border-l border-white/10 p-6 flex flex-col gap-4 overflow-y-auto">
                        <div>
                            <h3 className="text-xl font-bold text-white mb-1">{entity?.name || 'External Image'}</h3>
                            {entity?.name_en && <div className="text-sm text-muted-foreground">{entity.name_en}</div>}
                        </div>

                        <div className="space-y-4">
                            {entity ? (
                                <>
                                    <div className="bg-white/5 p-3 rounded-lg border border-white/5">
                                        <span className="text-[10px] uppercase font-bold text-primary/70 block mb-1">Description</span>
                                        <p className="text-sm text-gray-300 leading-relaxed max-h-[200px] overflow-y-auto custom-scrollbar">
                                            {entity.description || 'No description available.'}
                                        </p>
                                    </div>
                                    
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="bg-white/5 p-2 rounded border border-white/5">
                                            <span className="text-[10px] uppercase text-gray-500 block">Type</span>
                                            <span className="text-xs text-gray-300">{entity.type || 'Unknown'}</span>
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div className="text-sm text-muted-foreground italic">
                                    This image was added via URL or is external to the entity library. Metadata is unavailable.
                                </div>
                            )}

                            {/* Actions */}
                            <div className="pt-4 mt-auto border-t border-white/10 flex flex-col gap-2">
                                {activeRefs.includes(selectedImage) ? (
                                    <button 
                                        onClick={() => { handleRemove(selectedImage); setSelectedImage(null); }}
                                        className="w-full py-2 bg-red-500/10 text-red-400 border border-red-500/30 rounded flex items-center justify-center gap-2 hover:bg-red-500/20 text-sm font-medium"
                                    >
                                        <Trash2 size={16} /> Remove Reference
                                    </button>
                                ) : (
                                     <button 
                                        onClick={() => { handleAdd(selectedImage); }} // Update status, keep modal open to show it's active now
                                        className="w-full py-2 bg-primary/10 text-primary border border-primary/30 rounded flex items-center justify-center gap-2 hover:bg-primary/20 text-sm font-medium"
                                    >
                                        <Plus size={16} /> Add to References
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                 </div>
            </div>
        )
    }

    return (
        <>
            {renderModal()}
            <div className="space-y-2 pb-4 border-b border-white/10 mb-4">
                <div className="flex items-center justify-between">
                     <h4 className="text-xs font-bold text-muted-foreground uppercase flex items-center gap-2">
                        {title}
                        {onFindPrevFrame && (
                            <button 
                                onClick={(e) => {
                                    e.stopPropagation();
                                    const url = onFindPrevFrame();
                                    if (url) handleAdd(url);
                                }}
                                className="p-1 bg-white/5 hover:bg-primary/20 text-white/70 hover:text-primary rounded transition-colors"
                                title="Fetch Previous Shot End Frame"
                            >
                                <ArrowUp className="w-3 h-3" />
                            </button>
                        )}
                    </h4>
                    <span className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded text-white/50">Used by AI: {activeRefs.length}</span>
                </div>
                
                <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar min-h-[90px]">
                    {/* 1. Active Refs (Selected) */}
                    {activeRefs.map((url, idx) => (
                        <div key={url + idx} className="relative group shrink-0 w-[140px] aspect-video bg-black/40 rounded border border-primary/50 overflow-hidden shadow-[0_0_10px_rgba(0,0,0,0.5)] cursor-zoom-in" onClick={() => setSelectedImage(url)}>
                            {(url.toLowerCase().endsWith('.mp4') || url.toLowerCase().endsWith('.webm')) ? (
                                <video src={getFullUrl(url)} className="w-full h-full object-cover" muted loop onMouseEnter={e=>e.target.play()} onMouseLeave={e=>{e.target.pause();e.target.currentTime=0;}} />
                            ) : (
                                <img src={getFullUrl(url)} className="w-full h-full object-cover" alt="ref" />
                            )}
                            {!useSequenceLogic && (
                                <button 
                                    onClick={(e) => { e.stopPropagation(); handleRemove(url); }}
                                    className="absolute top-1 right-1 bg-red-500 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:scale-110 z-10"
                                >
                                    <X className="w-3 h-3"/>
                                </button>
                            )}
                        </div>
                    ))}
                    
                    {/* Add Button */}
                    {!useSequenceLogic && onPickMedia && (
                        <button 
                            onClick={() => onPickMedia((url) => handleAdd(url), { shotId: shot?.id })}
                            className="shrink-0 w-[50px] aspect-video bg-white/5 hover:bg-white/10 border border-white/10 border-dashed rounded flex flex-col items-center justify-center gap-1 text-muted-foreground hover:text-white transition-colors"
                            title="Pick from Assets"
                        >
                            <Plus className="w-5 h-5"/>
                        </button>
                    )}
                </div>
            </div>
        </>
    )
};

const SceneCard = ({ scene, entities, onClick, onGenerateShots }) => {
    const [images, setImages] = useState([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [isGenerating, setIsGenerating] = useState(false);

    useEffect(() => {
        // Parse logic
        const sourceText = scene.environment_name || scene.location || '';
        let anchors = [];
        const bracketMatches = sourceText.match(/\[(.*?)\]/g);
        if (bracketMatches && bracketMatches.length > 0) {
            anchors = bracketMatches.map(m => m.replace(/[\[\]\*]/g, '').trim());
        } else {
            anchors = sourceText.split(/[,，]/).map(s => s.replace(/[\*]/g, '').trim()).filter(Boolean);
        }

        const validUrls = [];
        // Updated cleaner: Removes whitespace to handle "主视角" vs "主视角 " mismatch
        const cleanForMatch = (str) => (str || '').replace(/[（\(\)）\s]/g, '').toLowerCase();

        anchors.forEach(rawLoc => {
            const targetName = cleanForMatch(rawLoc);
            if (!targetName) return;

             // Logic extracted from getSceneImages
            let match = entities.find(e => {
                const cn = cleanForMatch(e.name);
                let en = (e.name_en || '').toLowerCase();
                if (!en && e.description) {
                    const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                    if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
                }
                const enClean = cleanForMatch(en);
                return cn === targetName || enClean === targetName;
            });

            if (!match) {
                 match = entities.find(e => {
                    const cn = cleanForMatch(e.name);
                    let en = (e.name_en || '').toLowerCase();
                    if (!en && e.description) {
                        const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                        if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
                    }
                    const enClean = cleanForMatch(en);
                    return (cn && (cn.includes(targetName) || targetName.includes(cn))) ||
                           (enClean && (enClean.includes(targetName) || targetName.includes(enClean)));
                 });
            }
            if (match && match.image_url) validUrls.push(match.image_url);
        });

        // Use Set to remove duplicates
        setImages([...new Set(validUrls)]);
        setCurrentIndex(0);
    }, [scene, entities]);

    useEffect(() => {
        if (images.length <= 1) return;
        const interval = setInterval(() => {
            setCurrentIndex(prev => (prev + 1) % images.length);
        }, 3000);
        return () => clearInterval(interval);
    }, [images]);

    const handleGenerate = async (e) => {
        e.stopPropagation();
        if (isGenerating) return;
        
        setIsGenerating(true);
        if (onGenerateShots) {
            await onGenerateShots(scene.id);
        }
        setIsGenerating(false);
    };

    const imgUrl = images.length > 0 ? images[currentIndex] : null;

    return (
        <div 
            className="bg-card/80 backdrop-blur-sm rounded-xl border border-white/10 overflow-hidden group hover:border-primary/50 transition-all cursor-pointer relative"
            onClick={onClick}
        >
            <div className="aspect-video bg-black/60 flex items-center justify-center text-muted-foreground relative group-hover:bg-black/40 transition-colors overflow-hidden">
                {imgUrl ? (
                    <motion.img 
                        key={imgUrl}
                        src={getFullUrl(imgUrl)} 
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.5 }}
                        className="w-full h-full object-cover absolute inset-0" 
                        alt={scene.scene_name}
                    />
                ) : (
                    <div className="flex flex-col items-center gap-2 opacity-50">
                        <ImageIcon className="w-8 h-8" />
                        <span className="text-xs">No Env Image</span>
                    </div>
                )}
                
                {/* Dots indicator for multiple images */}
                {images.length > 1 && (
                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1 z-10">
                        {images.map((_, idx) => (
                            <div key={idx} className={`w-1.5 h-1.5 rounded-full ${idx === currentIndex ? 'bg-primary' : 'bg-white/50'}`} />
                        ))}
                    </div>
                )}

                <div className="absolute top-2 left-2 bg-black/60 px-2 py-1 rounded text-xs font-mono font-bold text-white border border-white/10 z-10 max-w-[80%] truncate">
                    {scene.scene_no || scene.id}
                </div>
                <div className="absolute top-2 right-2 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
                     <button 
                        onClick={handleGenerate}
                        disabled={isGenerating}
                        className="bg-primary/90 hover:bg-primary text-black px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 shadow-lg"
                        title="AI Generate Shot List"
                     >
                        {isGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                        AI Shots
                     </button>
                </div>
                <div className="absolute bottom-2 right-2 bg-primary text-black px-2 py-0.5 rounded text-[10px] font-bold z-10">
                    {scene.equivalent_duration || '0m'}
                </div>
            </div>
            
            <div className="p-4 space-y-2.5">
                <h3 className="font-bold text-sm text-white line-clamp-1" title={scene.scene_name}>{scene.scene_name || 'Untitled Scene'}</h3>
                
                <div className="text-xs text-muted-foreground space-y-2">
                    {/* Core Info - handled to prevent layout chaos with Markdown */}
                    <div className="bg-white/5 p-2 rounded border border-white/5 relative group/info">
                        <span className="font-bold text-white/50 block text-[10px] uppercase mb-1">Core Info</span>
                        <div className="max-h-[4.5em] overflow-hidden text-white/80 leading-normal prose prose-invert prose-p:my-0 prose-p:leading-normal prose-headings:my-0 prose-ul:my-0 prose-li:my-0 text-[11px]">
                             <ReactMarkdown components={{
                                 p: ({node, ...props}) => <p className="mb-1" {...props} />
                             }}>{scene.core_scene_info || 'No core info'}</ReactMarkdown>
                        </div>
                         {/* Hover expand could be cool, but simplistic for now */}
                    </div>

                    {/* Linked Characters & Key Props */}
                    <div className="space-y-1.5">
                        {(scene.linked_characters || scene.key_props) ? (
                            <>
                            {scene.linked_characters && (
                                <div className="flex flex-col gap-0.5">
                                    <span className="font-bold text-white/40 text-[9px] uppercase">Cast</span>
                                    <div className="flex flex-wrap gap-1">
                                        {scene.linked_characters.split(/[，,]/).filter(Boolean).map((char, i) => (
                                            <span key={i} className="inline-block bg-indigo-500/20 text-indigo-200 border border-indigo-500/30 px-1.5 py-0.5 rounded text-[10px]">
                                                {char.trim()}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            {scene.key_props && (
                                <div className="flex flex-col gap-0.5">
                                    <span className="font-bold text-white/40 text-[9px] uppercase">Props</span>
                                    <div className="flex flex-wrap gap-1">
                                        {scene.key_props.split(/[，,]/).filter(Boolean).map((prop, i) => (
                                            <span key={i} className="inline-block bg-emerald-500/20 text-emerald-200 border border-emerald-500/30 px-1.5 py-0.5 rounded text-[10px]">
                                                {prop.trim()}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            </>
                        ) : (
                             <div className="line-clamp-2 opacity-50 italic">
                                {scene.original_script_text || 'No description'}
                            </div>
                        )}
                    </div>
                </div>
                
                <div className="pt-2 border-t border-white/5 text-[10px] text-gray-400 mt-auto flex justify-between items-center">
                    <div className="flex items-center gap-1 max-w-[70%] truncate">
                        <span className="opacity-50">Env:</span>
                        <span className="text-white/70" title={scene.environment_name}>{scene.environment_name || '-'}</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

const SceneManager = ({ activeEpisode, projectId, project, onLog }) => {
    const [scenes, setScenes] = useState([]);
    const [entities, setEntities] = useState([]);
    const [editingScene, setEditingScene] = useState(null);
    const [shotPromptModal, setShotPromptModal] = useState({ open: false, sceneId: null, data: null, loading: false });

    // Debug: Monitor Data State
    useEffect(() => {
        console.log("[SceneManager] Component Active. ProjectId:", projectId, "Episode:", activeEpisode?.id);
    }, [projectId, activeEpisode]);

    useEffect(() => {
        console.log(`[SceneManager] Scenes Updated: ${scenes.length} items`);
        if (scenes.length > 0) console.log("Sample Scene:", scenes[0]);
    }, [scenes]);

    useEffect(() => {
        console.log(`[SceneManager] Entities Updated: ${entities.length} items`);
        if (entities.length > 0) console.log("Sample Entity:", entities[0]);
    }, [entities]);

    // Fetch Entities (Environment) for image matching
    useEffect(() => {
        // Shared Parsing Logic
        const parseScenesFromText = (text) => {
             if (!text) return [];
             const lines = text.split('\n').filter(l => l.trim().includes('|'));
             const headerIdx = lines.findIndex(l => 
                (l.includes("Scene No") || l.includes("场次序号") || l.includes("Scene ID") || l.includes("场次") || l.includes("Title"))
             );
             
             if (headerIdx === -1) return [];
             
             // Parse Headers
             const headerLine = lines[headerIdx];
             let headers = headerLine.split('|').map(c => c.trim());
             if (headers.length > 0 && headers[0] === "") headers.shift();
             if (headers.length > 0 && headers[headers.length-1] === "") headers.pop();
             
             const normalizeHeader = (h) => h.toLowerCase().replace(/[\.\s]/g, '');
             const headerMap = {};
             headers.forEach((h, idx) => {
                 const n = normalizeHeader(h);
                 if(n.includes("sceneno") || n.includes("场次")) headerMap['scene_no'] = idx;
                 else if(n.includes("scenename") || n.includes("title")) headerMap['scene_name'] = idx;
                 else if(n.includes("equivalentduration")) headerMap['equivalent_duration'] = idx;
                 else if(n.includes("coresceneinfo") || n.includes("coregoal")) headerMap['core_scene_info'] = idx;
                 else if(n.includes("originalscripttext") || n.includes("description")) headerMap['original_script_text'] = idx;
                 else if(n.includes("environmentname") || n.includes("environment")) headerMap['environment_name'] = idx;
                 else if(n.includes("linkedcharacters")) headerMap['linked_characters'] = idx;
                 else if(n.includes("keyprops")) headerMap['key_props'] = idx;
             });

             const rows = [];
             let inShotTable = false;

             for (let i = headerIdx + 1; i < lines.length; i++) {
                const line = lines[i];
                if (line.includes("Shot ID") || line.includes("镜头ID")) {
                    inShotTable = true;
                    continue;
                }
                if (line.includes("Scene No") || line.includes("场次序号")) {
                    inShotTable = false;
                    continue;
                }
                if (inShotTable) continue;
                if (line.includes('---')) continue;
                
                let cols = line.split('|').map(c => c.trim());
                if (cols.length > 0 && cols[0] === "") cols.shift();
                if (cols.length > 0 && cols[cols.length-1] === "") cols.pop();
                
                if (cols.length >= 2) {
                    const cleanCol = (txt) => txt ? txt.replace(/<br\s*\/?>/gi, '\n').replace(/\\\|/g, '|') : '';
                    
                    // Helper to get by mapped index, defaulting to hardcoded fallback if map fails (legacy support)
                    const getVal = (key, fallbackIdx) => {
                        const idx = headerMap[key] !== undefined ? headerMap[key] : fallbackIdx;
                        return cols[idx] ? cleanCol(cols[idx]) : '';
                    };

                    rows.push({
                        scene_no: getVal('scene_no', 0),
                        scene_name: getVal('scene_name', 1),
                        equivalent_duration: getVal('equivalent_duration', 2),
                        core_scene_info: getVal('core_scene_info', 3),
                        original_script_text: getVal('original_script_text', 4),
                        environment_name: getVal('environment_name', 5),
                        linked_characters: getVal('linked_characters', 6),
                        key_props: getVal('key_props', 7)
                    });
                }
             }
             return rows;
        };

        const loadScenes = async () => {
             if (activeEpisode?.id) {
                 try {
                     const dbScenes = await fetchScenes(activeEpisode.id);
                     if (dbScenes && dbScenes.length > 0) {
                         // Check for incomplete data (Schema Update Backfill)
                         const inContent = activeEpisode.scene_content;
                         if (inContent && dbScenes.some(s => !s.linked_characters && !s.key_props)) {
                             console.log("[SceneManager] Detected stale DB records. Attempting merge from text content...");
                             const parsed = parseScenesFromText(inContent);
                             if (parsed.length > 0) {
                                 const merged = dbScenes.map(dbS => {
                                     // Match by Scene Number
                                     const match = parsed.find(p => p.scene_no === dbS.scene_no);
                                     if (match) {
                                         return {
                                             ...dbS,
                                             linked_characters: dbS.linked_characters || match.linked_characters,
                                             key_props: dbS.key_props || match.key_props,
                                             environment_name: dbS.environment_name || match.environment_name,
                                             core_scene_info: dbS.core_scene_info || match.core_scene_info
                                         };
                                     }
                                     return dbS;
                                 });
                                 setScenes(merged);
                                 return;
                             }
                         }
                         setScenes(dbScenes);
                     } else {
                         // Only parse if DB is empty
                         setScenes(parseScenesFromText(activeEpisode?.scene_content));
                     }
                 } catch(e) {
                     console.error("Failed to load scenes from DB", e);
                     const parsedFallback = parseScenesFromText(activeEpisode?.scene_content);
                     setScenes(parsedFallback);
                 }
             }
        };

        if (projectId) fetchEntities(projectId).then(setEntities).catch(console.error);
        loadScenes();
    }, [activeEpisode, projectId]);

    const handleSceneUpdate = (updatedScene) => {
        setScenes(prev => prev.map(s => s.id === updatedScene.id ? updatedScene : s));
        if (editingScene && editingScene.id === updatedScene.id) {
            setEditingScene(updatedScene);
        }
    };

    const handleSave = async () => {
        if (!activeEpisode) return;
        
        onLog?.('SceneManager: Saving content...', 'info');

        const contextInfo = `Project: ${project?.title || 'Unknown'} | Episode: ${activeEpisode?.title || 'Unknown'}\n`;
        const header = `| Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Original Script Text | Environment Name | Linked Characters | Key Props |\n|---|---|---|---|---|---|---|---|`;
        
        const content = scenes.map(s => {
             const clean = (txt) => (txt || '').replace(/\n/g, '<br>').replace(/\|/g, '\\|');
             return `| ${clean(s.scene_no)} | ${clean(s.scene_name)} | ${clean(s.equivalent_duration)} | ${clean(s.core_scene_info)} | ${clean(s.original_script_text)} | ${clean(s.environment_name)} | ${clean(s.linked_characters)} | ${clean(s.key_props)} |`;
        }).join('\n');
        
        try {
            // Update scenes in DB (Create if missing ID, Update if exists)
            const savePromises = scenes.map(async (s) => {
                const payload = {
                    scene_no: s.scene_no,
                    scene_name: s.scene_name,
                    equivalent_duration: s.equivalent_duration,
                    core_scene_info: s.core_scene_info,
                    original_script_text: s.original_script_text,
                    environment_name: s.environment_name,
                    linked_characters: s.linked_characters,
                    key_props: s.key_props
                };

                if (s.id) {
                    await updateScene(s.id, payload);
                    return s;
                } else {
                    const created = await createScene(activeEpisode.id, payload);
                    return { ...s, id: created.id };
                }
            });

            const savedScenes = await Promise.all(savePromises);
            setScenes(savedScenes);

            await updateEpisode(activeEpisode.id, { scene_content: contextInfo + header + '\n' + content });
            onLog?.('SceneManager: Saved successfully.', 'success');
        } catch(e) {
            console.error(e);
            onLog?.(`SceneManager: Save failed - ${e.message}`, 'error');
            alert("Failed to save scenes");
        }
    };

    const getSceneImage = (scene) => {
        // Use environment_name as requested, cleaning markdown ** and []
        const sourceText = scene.environment_name || scene.location || '';
        const rawLoc = sourceText.replace(/[\[\]\*]/g, '').trim().toLowerCase();
        
        if (!rawLoc) return null;

        // Debug Log - Unconditionally log for now to verify execution
        console.log(`[SceneManager] Matching Image for Scene: "${scene.scene_name}" using Anchor: "${sourceText}" (Cleaned: "${rawLoc}")`);
        
        const cleanForMatch = (str) => (str || '').replace(/[（\(\)）]/g, '').trim().toLowerCase();
        const targetName = cleanForMatch(rawLoc);

        // Try exact match first
        let match = entities.find(e => {
            const cn = cleanForMatch(e.name);
            let en = (e.name_en || '').toLowerCase();
            
            // Fallback EN extract
            if (!en && e.description) {
                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
            }
            const enClean = cleanForMatch(en);

            const isMatch = cn === targetName || enClean === targetName;
            
            // Debugging specific failing case
            if (rawLoc.includes("废弃")) {
                 console.log(`Checking Entity: "${e.name}" (CN: "${cn}") vs Target: "${targetName}" -> Match? ${isMatch}`);
            }
            
            return isMatch;
        });

        // Try fuzzy match if exact fails
        if (!match) {
             match = entities.find(e => {
                const cn = cleanForMatch(e.name);
                let en = (e.name_en || '').toLowerCase();
                // Fallback EN extract
                if (!en && e.description) {
                    const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                    if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
                }
                const enClean = cleanForMatch(en);

                if (cn && (cn.includes(targetName) || targetName.includes(cn))) {
                    if (rawLoc.includes("废弃")) console.log(`  -> Fuzzy Match Found (CN): ${cn} <-> ${targetName}`);
                    return true;
                }
                if (enClean && (enClean.includes(targetName) || targetName.includes(enClean))) {
                    if (rawLoc.includes("废弃")) console.log(`  -> Fuzzy Match Found (EN): ${enClean} <-> ${targetName}`);
                    return true;
                }
                return false;
             });
        }
        
        if (rawLoc.includes("废弃") && !match) {
            console.log("  -> No match found for", rawLoc);
            console.log("  -> Available Entities:", entities.map(e => e.name));
        }

        return match ? match.image_url : null;
    };

    const handleGenerateShots = async (sceneId) => {
        if (!sceneId) {
            alert("Please save the scene list first to create database records before generating shots.");
            return;
        }


        setShotPromptModal({ open: true, sceneId: sceneId, data: null, loading: true });

        try {
            const data = await fetchSceneShotsPrompt(sceneId);
            setShotPromptModal({ open: true, sceneId: sceneId, data: data, loading: false });
        } catch (e) {
             onLog?.(`SceneManager: Failed to fetch prompt preview - ${e.message}`, 'error');
             setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });
        }
    };

    const handleConfirmGenerateShots = async () => {
         const { sceneId, data } = shotPromptModal;
         if (!confirm("This will overwrite existing shots for this scene. Continue?")) return;
         
         setShotPromptModal(prev => ({ ...prev, loading: true }));
         onLog?.(`SceneManager: Generating shots for Scene ${sceneId}...`, 'info');
         try {
             await generateSceneShots(sceneId, { 
                 user_prompt: data.user_prompt,
                 system_prompt: data.system_prompt 
             });
             onLog?.(`SceneManager: Shot list generated for Scene ${sceneId}.`, 'success');
             setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });
             // No need to refresh scenes usually, but maybe good idea?
         } catch (e) {
             console.error(e);
             onLog?.(`SceneManager: Failed to generate shots - ${e.message}`, 'error');
             alert("Failed to generate shots: " + e.message);
             setShotPromptModal(prev => ({ ...prev, loading: false }));
         }
    };

    if (!activeEpisode) return <div className="p-6 text-muted-foreground">Select an episode to manage scenes.</div>;

    return (
        <div className="p-4 sm:p-8 h-full flex flex-col w-full max-w-full overflow-hidden">
             <div className="flex justify-between items-center mb-6 shrink-0">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                    Scenes
                    <span className="text-sm font-normal text-muted-foreground bg-white/5 px-2 py-0.5 rounded-full">{scenes.length} Scenes</span>
                </h2>
                <div className="flex gap-2">
                     <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center gap-2">
                        <CheckCircle className="w-4 h-4" />
                        Save Changes
                     </button>
                </div>
            </div>

            <div className="flex-1 overflow-auto custom-scrollbar pb-20">
                    {scenes.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                        <Clapperboard className="w-12 h-12 mb-4 opacity-20" />
                        <p>No scenes found.</p>
                        <p className="text-xs mt-2 opacity-50">Paste a Markdown table in Import or generate content.</p>
                    </div>
                    ) : (
                    <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-6">
                        {scenes.map((scene, idx) => {
                            return (
                                <SceneCard 
                                    key={idx} 
                                    scene={scene} 
                                    entities={entities} 
                                    onClick={() => setEditingScene(scene)} 
                                    onGenerateShots={handleGenerateShots}
                                />
                            );
                        })}
                    </div>
                    )}
            </div>
            
            <AnimatePresence>
                {editingScene && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={() => setEditingScene(null)}>
                        <motion.div 
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            onClick={e => e.stopPropagation()}
                            className="bg-[#09090b] border border-white/10 rounded-xl w-full max-w-5xl h-[90vh] shadow-2xl flex flex-col overflow-hidden"
                        >
                             <div className="p-4 border-b border-white/10 flex items-center justify-between bg-[#09090b]">
                                <h3 className="font-bold text-lg">Edit Scene {editingScene.scene_no || editingScene.id}</h3>
                                <button onClick={() => setEditingScene(null)} className="p-2 hover:bg-white/10 rounded-full"><X className="w-5 h-5"/></button>
                            </div>
                            
                            <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
                                <div className="space-y-6">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-4">
                                            <div className="grid grid-cols-2 gap-4">
                                                <InputGroup label="Scene No" value={editingScene.scene_no || editingScene.id} onChange={v => handleSceneUpdate({...editingScene, scene_no: v})} />
                                                <InputGroup label="Duration" value={editingScene.equivalent_duration} onChange={v => handleSceneUpdate({...editingScene, equivalent_duration: v})} />
                                            </div>
                                            <InputGroup label="Scene Name" value={editingScene.scene_name} onChange={v => handleSceneUpdate({...editingScene, scene_name: v})} />
                                            <InputGroup label="Environment Anchor" value={editingScene.environment_name} onChange={v => handleSceneUpdate({...editingScene, environment_name: v})} />
                                            <InputGroup label="Linked Characters (Comma separated)" value={editingScene.linked_characters} onChange={v => handleSceneUpdate({...editingScene, linked_characters: v})} />
                                            <InputGroup label="Key Props" value={editingScene.key_props} onChange={v => handleSceneUpdate({...editingScene, key_props: v})} />
                                        </div>

                                        <div className="flex flex-col h-full"> 
                                            <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-2 block">Original Script Text</label>
                                            <MarkdownCell value={editingScene.original_script_text} onChange={v => handleSceneUpdate({...editingScene, original_script_text: v})} className="flex-1 min-h-[200px]" />
                                        </div>
                                    </div>
                                    
                                    <div className="pt-4 border-t border-white/5 h-full flex flex-col">
                                         <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-2 block text-primary/80">Core Scene Info (Visual Direction)</label>
                                         <textarea 
                                            className="w-full flex-1 bg-black/40 border border-white/10 rounded p-3 text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-none custom-scrollbar font-mono leading-relaxed min-h-[400px]"
                                            value={editingScene.core_scene_info || ''}
                                            onChange={e => handleSceneUpdate({...editingScene, core_scene_info: e.target.value})}
                                            placeholder="Enter visual direction, lighting, mood, composition..."
                                        />
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
            
            {shotPromptModal.open && (
                <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
                    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">
                        <div className="p-4 border-b border-white/10 flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2"><Wand2 size={16} className="text-primary"/> Generate AI Shots</h3>
                            <button onClick={() => setShotPromptModal({open: false, sceneId: null, data: null, loading: false})}><X size={18}/></button>
                        </div>
                        
                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                            {shotPromptModal.loading && !shotPromptModal.data ? (
                                <div className="flex items-center justify-center h-40"><Loader2 className="animate-spin text-primary" size={32}/></div>
                            ) : (
                                <>
                                    <div className="bg-blue-500/10 border border-blue-500/20 rounded p-3 text-xs text-blue-200 flex items-start gap-2">
                                        <Info size={14} className="shrink-0 mt-0.5" />
                                        Review and edit the prompt before generation. Only the User Prompt (scenario context) is typically edited.
                                    </div>

                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-bold text-muted-foreground uppercase">User Prompt (Scenario content)</label>
                                        <textarea 
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-sm text-white/90 font-mono h-64 focus:outline-none focus:border-primary/50 resize-y"
                                            value={shotPromptModal.data?.user_prompt || ''}
                                            onChange={e => setShotPromptModal(prev => ({...prev, data: {...prev.data, user_prompt: e.target.value}}))}
                                        />
                                    </div>
                                    
                                     <div className="flex flex-col gap-2">
                                         <div className="flex items-center justify-between">
                                              <label className="text-xs font-bold text-muted-foreground uppercase">System Prompt (Instructions)</label>
                                              <span className="text-xs text-muted-foreground px-2 py-1 bg-white/5 rounded">Default/Template</span>
                                         </div>
                                        <textarea 
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-xs text-muted-foreground font-mono h-32 focus:outline-none focus:border-primary/50 resize-y"
                                            value={shotPromptModal.data?.system_prompt || ''}
                                            onChange={e => setShotPromptModal(prev => ({...prev, data: {...prev.data, system_prompt: e.target.value}}))}
                                        />
                                    </div>
                                </>
                            )}
                        </div>
                        
                        <div className="p-4 border-t border-white/10 flex justify-end gap-3 bg-black/20">
                            <button 
                                onClick={() => {
                                    const full = (shotPromptModal.data?.system_prompt || '') + "\n\n" + (shotPromptModal.data?.user_prompt || '');
                                    navigator.clipboard.writeText(full);
                                    onLog?.("Full prompt copied to clipboard", "success");
                                }}
                                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded text-sm font-medium flex items-center gap-2 mr-auto"
                            >
                                <Copy size={16}/> Copy Full Prompt
                            </button>
                            <button 
                                onClick={() => setShotPromptModal({open: false, sceneId: null, data: null, loading: false})}
                                className="px-4 py-2 rounded hover:bg-white/10 text-sm"
                            >
                                Cancel
                            </button>
                            <button 
                                onClick={handleConfirmGenerateShots}
                                disabled={shotPromptModal.loading}
                                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium flex items-center gap-2"
                            >
                                {shotPromptModal.loading ? <Loader2 className="animate-spin" size={16}/> : <Wand2 size={16}/>}
                                {shotPromptModal.loading ? "Generating..." : "Generate Shots"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

const SubjectLibrary = ({ projectId, currentEpisode }) => {
    const { addLog: onLog } = useLog();
    const [subTab, setSubTab] = useState('character');
    const [entities, setEntities] = useState([]);
    const [allEntities, setAllEntities] = useState([]); // Store ALL entities for cross-reference
    const [selectedEntity, setSelectedEntity] = useState(null);
    const [showImageModal, setShowImageModal] = useState(false);
    const [imageModalTab, setImageModalTab] = useState('library'); // library, upload, generate
    const [generating, setGenerating] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [prompt, setPrompt] = useState('');
    const [provider, setProvider] = useState('');
    const [refImage, setRefImage] = useState(null);
    const [refSelectionMode, setRefSelectionMode] = useState(null); // 'assets'
    const [assets, setAssets] = useState([]);
    const [availableProviders, setAvailableProviders] = useState([]);
    const [viewingEntity, setViewingEntity] = useState(null);
    const [isBatchGeneratingEntities, setIsBatchGeneratingEntities] = useState(false);
    const [batchEntityProgress, setBatchEntityProgress] = useState(null);
    const [pickerConfig, setPickerConfig] = useState({ isOpen: false, callback: null });

    const openMediaPicker = (callback, context = {}) => {
        setPickerConfig({ isOpen: true, callback, context });
    };

    // Load active providers
    useEffect(() => {
        const loadProviders = async () => {
            try {
                const settings = await getSettings();
                // Filter for Image provider that are active
                // Ensure unique providers if multiple keys exist for same provider? 
                // DB structure seems to be one entry per provider config.
                // But let's verify what 'settings' looks like. 
                // APISetting schema: provider, api_key, category, is_active...
                const imageProviders = settings.filter(s => s.category === 'Image' && s.is_active);
                setAvailableProviders(imageProviders);
            } catch (e) {
                console.error("Failed to load providers", e);
            }
        };
        loadProviders();
    }, []);
    
    // Load entities - NOW FETCHES ALL and filters locally
    const loadEntities = useCallback(async () => {
        if (!projectId) return;
        try {
            const data = await fetchEntities(projectId); // Fetch ALL types
            setAllEntities(data);
        } catch (e) {
            console.error(e);
        }
    }, [projectId]);

    useEffect(() => {
        loadEntities();
    }, [loadEntities]);

    // Local Filtering based on subTab
    useEffect(() => {
        setEntities(allEntities.filter(e => e.type === subTab));
    }, [allEntities, subTab]);

    // Create Entity
    const [isAnalyzingEntity, setIsAnalyzingEntity] = useState(false);

    const handleAnalyzeEntity = async (entity) => {
        if (!entity || !entity.id || !entity.image_url) {
            alert("No entity or image selected.");
            return;
        }
        
        setIsAnalyzingEntity(true);
        if (onLog) onLog(`Analyzing image for subject ${entity.name}...`, "process");
        
        try {
            const updated = await analyzeEntityImage(entity.id);
            setViewingEntity(updated);
            setEntities(prev => prev.map(e => e.id === updated.id ? updated : e));
            if (onLog) onLog("Subject updated from analysis.", "success");
        } catch (e) {
            console.error(e);
            alert("Analysis failed: " + (e.response?.data?.detail || e.message));
            if (onLog) onLog("Analysis failed.", "error");
        } finally {
            setIsAnalyzingEntity(false);
        }
    };

    const handleCreate = async () => {
        // Create a temporary "New Entity" state to open the modal in "Create Mode"
        // We use a special ID 'new' to signal that this is not yet in DB
        setViewingEntity({
            id: 'new',
            name: '',
            type: subTab,
            description: '',
            anchor_description: '',
            generation_prompt_en: '',
            appearance_cn: '',
            clothing: '',
            visual_params: '',
            atmosphere: '',
            narrative_description: '',
            name_en: '',
            role: '',
            archetype: '',
            gender: ''
        });
    };

    // Helper: Update Field (Sync to DB if not new)
    const handleFieldUpdate = (field, value) => {
        if (!viewingEntity) return;
        
        // Always update local viewing state
        setViewingEntity(prev => ({ ...prev, [field]: value }));

        // Only sync to server if it's an existing entity
        if (viewingEntity.id !== 'new') {
            const updated = { ...viewingEntity, [field]: value };
            
            // Optimistic Update
            setEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
            setAllEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
            
            updateEntity(updated.id, { [field]: value }).catch(console.error);
        }
    };

    // Helper: Commit Create (Save manually)
    const handleCommitCreate = async () => {
        if (!viewingEntity || !viewingEntity.name) {
            alert("Name is required");
            return;
        }
        try {
            // Must clone and remove the 'new' ID
            const payload = { ...viewingEntity };
            delete payload.id; 
            
            const newEnt = await createEntity(projectId, payload);
            
            // Update local state with real object (and real ID)
            setAllEntities(prev => [...prev, newEnt]);
            
            // If current tab matches, show it
            if (newEnt.type === subTab) {
                setEntities(prev => [...prev, newEnt]);
            }
            
            // Switch view to the real entity (no longer 'new')
            setViewingEntity(newEnt);
            alert("Subject Created Successfully!");
        } catch (e) {
            console.error(e);
            alert("Failed to create subject: " + e.message);
        }
    };


    // Delete Entity
    const handleDeleteEntity = async (e, entity) => {
        e.stopPropagation();
        if (!confirm(`Are you sure you want to delete ${entity.name}?`)) return;
        try {
            await deleteEntity(entity.id);
            loadEntities();
            if (viewingEntity?.id === entity.id) setViewingEntity(null);
        } catch (e) {
            console.error(e);
            alert("Failed to delete entity");
        }
    };

    const handleDeleteAllEntities = async () => {
        if (!confirm("WARNING: This will delete ALL subjects/entities in this library. This action cannot be undone. Are you sure?")) return;
        try {
            await deleteAllEntities(projectId);
            loadEntities();
            setViewingEntity(null);
        } catch (e) {
            console.error(e);
            alert("Failed to delete all entities");
        }
    };
    
    // Open Image Modal
    const handleOpenImageModal = (entity, defaultTab = 'library') => {
        console.log("Opening Modal for:", entity.name, "EpInfo:", currentEpisode?.episode_info);

        setSelectedEntity(entity);
        setImageModalTab(defaultTab); // This might cause render before prompt is set?
        
        // Prefill prompt with processed template
        let rawPrompt = entity.generation_prompt_en || '';
        
        // Fallback: Try to extract from description if available (for legacy imports)
        if (!rawPrompt && entity.description) {
            const match = entity.description.match(/Prompt:\s*(.*)/);
            if (match && match[1]) {
                rawPrompt = match[1].trim();
            }
        }

        const epInfo = currentEpisode?.episode_info || {};
        
        // If undefined, ensure we pass empty object to avoid crash in utils
        // Use allEntities for resolution to ensure cross-type references work
        let processed = processPrompt(rawPrompt, epInfo, allEntities) || ''; 

        // Append Type, Lighting, Quality from Episode Global Info
        const infoSource = epInfo.e_global_info || epInfo;
        const type = infoSource.type;
        const lighting = infoSource.lighting;
        const quality = infoSource.tech_params?.visual_standard?.quality;
        
        const suffixes = [type, lighting, quality].filter(Boolean);
        if (suffixes.length > 0) {
            processed += ", " + suffixes.join(", ");
        }
        
        console.log("Setting processed prompt:", processed);
        setPrompt(processed);
        setShowImageModal(true); // Show AFTER setting everything

        setRefImage(null);
        
        // Default to active provider if available, otherwise system default
        if (availableProviders && availableProviders.length > 0) {
            setProvider(availableProviders[0].provider);
        } else {
            setProvider('');
        }
        setRefSelectionMode(null); 
        loadAssets();
    };

    // Load Assets
    const loadAssets = async () => {
        try {
            const data = await fetchAssets();
            setAssets(data.filter(a => a.type === 'image'));
        } catch (e) {
            console.error(e);
        }
    };

    // Image Handlers
    const  handleSelectAsset = async (asset) => {
        await updateEntityImage(asset.url);
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setUploading(true);
        try {
            const asset = await uploadAsset(file);
            await updateEntityImage(asset.url);
        } catch (e) {
            console.error(e);
        } finally {
            setUploading(false);
        }
    };

    const handleGenerate = async () => {
        if (!prompt) return;
        setGenerating(true);

        // Use shared utility for prompt processing
        const epInfo = currentEpisode?.episode_info || {};
        // prompt likely already has suffixes appended from initialization, 
        // but we run processPrompt again in case user added new variables.
        // Use allEntities for resolution
        const finalPrompt = processPrompt(prompt, epInfo, allEntities);
        
        // Update UI to show processed prompt (in case var replacement happened)
        setPrompt(finalPrompt);

        try {
            // Resolve Visual Dependencies
            const depUrls = [];
            if (selectedEntity && selectedEntity.visual_dependencies) {
                 const deps = Array.isArray(selectedEntity.visual_dependencies) ? selectedEntity.visual_dependencies : [];
                 deps.forEach(dep => {
                     // dep can be name or id
                     const startDep = String(dep).trim();
                     if (!startDep) return;
                     const startDepLower = startDep.toLowerCase();
                     
                     // Use allEntities for resolution with case-insensitive match
                     const target = allEntities.find(e => {
                         if (!e) return false;
                         if (String(e.id) === startDep) return true;
                         if (e.name && e.name.trim().toLowerCase() === startDepLower) return true;
                         if (e.name_en && e.name_en.trim().toLowerCase() === startDepLower) return true;
                         return false;
                     });

                     if (target && target.image_url) {
                         depUrls.push(target.image_url);
                     }
                 });
            }

            // Combine manual ref and auto-refs
            const allRefs = [];
            if (refImage?.url) allRefs.push(refImage.url);
            if (depUrls.length > 0) allRefs.push(...depUrls);
            
            // Deduplicate
            const uniqueRefs = [...new Set(allRefs)];
            
            console.log(`[Editor] Generating Image. Providers: ${provider || 'Auto'}`);
            console.log(`[Editor] Refs (Total ${uniqueRefs.length}):`, uniqueRefs);

            const asset = await generateImage(finalPrompt, provider || null, uniqueRefs.length > 0 ? uniqueRefs : null);
            await updateEntityImage(asset.url);
        } catch (e) {
            console.error(e);
            alert("Generation Failed: " + (e.response?.data?.detail || e.message));
        } finally {
            setGenerating(false);
        }
    };

    const handleRefUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        try {
             // We reuse uploadAsset but don't assign to entity yet, just set as refImage
             const asset = await uploadAsset(file);
             setRefImage(asset);
        } catch (e) {
            console.error(e);
        }
    };

    const updateEntityImage = async (url) => {
        if (!selectedEntity) return;
        try {
            await updateEntity(selectedEntity.id, { image_url: url });
            setShowImageModal(false);
            loadEntities();
        } catch (e) {
            console.error(e);
        }
    };

    const handleBatchGenerateEntities = async () => {
        const toGenerate = allEntities.filter(e => !e.image_url);
        if (toGenerate.length === 0) {
            alert("All entities already have images!");
            return;
        }

        if (!confirm(`Batch generate images for ${toGenerate.length} entities? This will respect dependency order.`)) return;

        setBatchEntityProgress({ current: 0, total: toGenerate.length, status: 'Initializing...' });
        setIsBatchGeneratingEntities(true);

        // Determine Dependency Map
        const nameMap = new Map();
        allEntities.forEach(e => {
            if (e.name) nameMap.set(e.name.trim().toLowerCase(), e);
            if (e.name_en) nameMap.set(e.name_en.trim().toLowerCase(), e);
        });

        // Current status of images (starts with existing)
        // We use a mutable URL map to track latest URLs during the batch process
        const urlMap = new Map();
        allEntities.forEach(e => {
            if (e.image_url) urlMap.set(e.id, e.image_url);
        });

        let queue = [...toGenerate];
        let processedCount = 0;
        
        // Helper to check if entity is ready (all its deps have images)
        const isReady = (ent) => {
            const deps = Array.isArray(ent.visual_dependencies) ? ent.visual_dependencies : [];
            if (deps.length === 0) return true;
            
            return deps.every(depRaw => {
                const dep = String(depRaw).trim().toLowerCase();
                let target = null;
                 if (allEntities.find(e => String(e.id) === dep)) {
                     target = allEntities.find(e => String(e.id) === dep);
                 } else {
                     target = nameMap.get(dep);
                 }

                if (!target) return true; // External/Unknown dep doesn't block
                return urlMap.has(target.id);
            });
        };

        try {
            while (queue.length > 0) {
                // Find all entities that are ready
                const readyBatch = queue.filter(e => isReady(e));
                
                let batch = [];
                if (readyBatch.length > 0) {
                    batch = readyBatch;
                } else {
                    // Cycle or blocked -> Force proceed with one
                    batch = [queue[0]];
                }

                for (const entity of batch) {
                    const idx = processedCount + 1;
                    setBatchEntityProgress({ current: idx, total: toGenerate.length, status: `Generating ${entity.name}...` });
                    
                    try {
                        // 1. Prepare Prompt
                        const epInfo = currentEpisode?.episode_info || {};
                        let basePrompt = entity.generation_prompt_en || 
                                         entity.description || 
                                         `A ${entity.type} named ${entity.name}.`;
                        
                        if (!basePrompt || basePrompt.trim().length < 2) {
                             basePrompt = `${entity.type} ${entity.name}`;
                        }

                        // We pass 'allEntities' so [Reference] replacement works
                        // Note: processPrompt uses allEntities to find values. 
                        // It reads entity.description usually.
                        const finalPrompt = processPrompt(basePrompt, epInfo, allEntities);
                        
                        // 2. Resolve Dependencies (Build Ref URLs FROM LATEST MAP)
                        const depUrls = [];
                         const deps = Array.isArray(entity.visual_dependencies) ? entity.visual_dependencies : [];
                         deps.forEach(dep => {
                             const startDep = String(dep).trim();
                             const startDepLower = startDep.toLowerCase();
                             
                             let target = allEntities.find(e => {
                                 if (!e) return false;
                                 if (String(e.id) === startDep) return true;
                                 if (e.name && e.name.trim().toLowerCase() === startDepLower) return true;
                                 if (e.name_en && e.name_en.trim().toLowerCase() === startDepLower) return true;
                                 return false;
                             });

                             // Use urlMap to get the LATEST url (since target object might be stale in allEntities closure vs real-time updates)
                             if (target && urlMap.has(target.id)) {
                                 depUrls.push(urlMap.get(target.id));
                             }
                        });
                        const uniqueRefs = [...new Set(depUrls)];
                        
                        // 3. Generate
                        const res = await generateImage(finalPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null);
                        
                        if (res && res.url) {
                            // 4. Update
                            await updateEntity(entity.id, { image_url: res.url });
                            
                            // Update local tracking
                            urlMap.set(entity.id, res.url);
                            
                            const updatedEnt = { ...entity, image_url: res.url };
                            
                            // Update Master List
                            setAllEntities(prev => prev.map(e => e.id === entity.id ? updatedEnt : e));
                            
                            // Update Current View (Force Refresh)
                            setEntities(prev => {
                                if (prev.some(p => p.id === entity.id)) {
                                    return prev.map(e => e.id === entity.id ? updatedEnt : e);
                                }
                                return prev;
                            });

                            // Update Modal if open
                            if (viewingEntity && viewingEntity.id === entity.id) {
                                setViewingEntity(updatedEnt);
                            }
                        }

                    } catch(e) {
                         console.error(`Batch Gen Error for ${entity.name}`, e);
                    }

                    queue = queue.filter(q => q.id !== entity.id);
                    processedCount++;
                }
            }
            alert("Batch Generation Complete!");
        } catch (e) {
            console.error(e);
            alert("Batch Generation Failed: " + e.message);
        } finally {
            setIsBatchGeneratingEntities(false);
            setBatchEntityProgress(null);
        }
    };

    return (
        <div className="p-6 h-full flex flex-col w-full relative">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold">Subjects Library</h2>
                <div className="flex items-center gap-4">
                     <button 
                        onClick={handleDeleteAllEntities}
                        className="p-2 text-red-400 hover:text-red-300 hover:bg-red-900/20 rounded-md transition-colors"
                        title="Delete All Subjects"
                    >
                        <Trash2 size={16} />
                    </button>
                     <button 
                        onClick={handleBatchGenerateEntities}
                        disabled={isBatchGeneratingEntities}
                        className="px-3 py-2 text-xs font-bold uppercase rounded-md bg-white/10 hover:bg-white/20 text-white flex items-center gap-2 disabled:opacity-50 transition-all border border-white/10"
                        title="Batch Generate All Entities (Respects Dependencies)"
                    >
                         {isBatchGeneratingEntities ? (
                             <>
                                 <RefreshCw className="animate-spin" size={12} /> 
                                 Batching {batchEntityProgress ? `${batchEntityProgress.current}/${batchEntityProgress.total}` : '...'}
                             </>
                         ) : (
                             <>
                                <Wand2 size={12} /> Auto-Fill All Images
                             </>
                         )}
                    </button>

                    <div className="flex space-x-1 bg-card border border-white/10 p-1 rounded-lg">
                        {['character', 'environment', 'prop'].map(t => (
                            <button 
                                key={t}
                                onClick={() => setSubTab(t)}
                                className={`px-4 py-2 text-xs font-bold uppercase rounded-md transition-all ${subTab === t ? 'bg-primary text-black' : 'hover:bg-white/5 text-muted-foreground'}`}
                            >
                                {t}s
                            </button>
                        ))}
                    </div>
                </div>
            </div>
            
            {/* Batch Status Bar */}
            {isBatchGeneratingEntities && batchEntityProgress && (
                <div className="mb-4 bg-primary/10 border border-primary/20 rounded-lg p-3 flex items-center justify-between text-xs text-primary">
                    <span className="font-bold flex items-center gap-2">
                         <RefreshCw className="animate-spin" size={12} />
                         {batchEntityProgress.status}
                    </span>
                    <span className="font-mono">{Math.round((batchEntityProgress.current / batchEntityProgress.total) * 100)}%</span>
                </div>
            )}
            
            <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-6 w-full">
                <div 
                    onClick={handleCreate}
                    className="aspect-[3/4] border-2 border-dashed border-white/10 rounded-xl flex flex-col items-center justify-center text-muted-foreground hover:border-primary/50 hover:text-primary cursor-pointer transition-all bg-black/20 w-full">
                    <span className="text-4xl mb-2"><Plus /></span>
                    <span className="text-xs uppercase font-bold">New {subTab}</span>
                </div>
                
                {entities.map(entity => (
                    <div 
                        key={entity.id} 
                        onClick={() => setViewingEntity(entity)}
                        className="aspect-[3/4] bg-card border border-white/10 rounded-xl overflow-hidden relative group w-full cursor-pointer hover:border-primary/50 transition-all"
                    >
                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent z-10 pointer-events-none"></div>
                        {entity.image_url ? (
                            <img src={getFullUrl(entity.image_url)} alt={entity.name} className="absolute inset-0 object-cover w-full h-full" />
                        ) : (
                            <div className="absolute inset-0 flex items-center justify-center bg-white/5">
                                <Users className="text-white/20" size={48} />
                            </div>
                        )}
                        
                        <div className="absolute top-2 right-2 z-20 opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
                            <button 
                                onClick={(e) => { e.stopPropagation(); handleOpenImageModal(entity, 'library'); }}
                                className="p-2 bg-black/50 hover:bg-black/80 rounded-full text-white backdrop-blur-md"
                                title="Change Image (Library/Upload)"
                            >
                                <ImageIcon size={16} />
                            </button>
                            <button 
                                onClick={(e) => { e.stopPropagation(); handleOpenImageModal(entity, 'generate'); }}
                                className="p-2 bg-black/50 hover:bg-black/80 rounded-full text-white backdrop-blur-md"
                                title="Generate AI Image"
                            >
                                <Wand2 size={16} />
                            </button>
                            <button 
                                onClick={(e) => handleDeleteEntity(e, entity)}
                                className="p-2 bg-red-500/80 hover:bg-red-600 rounded-full text-white backdrop-blur-md"
                                title="Delete Entity"
                            >
                                <Trash2 size={16} />
                            </button>
                        </div>

                        <div className="absolute bottom-3 left-3 z-20 pointer-events-none">
                            <div className="font-bold text-white capitalize">{entity.name}</div>
                            <div className="text-[10px] text-white/60">{entity.description?.substring(0, 30)}...</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Entity Detail Modal */}
            <AnimatePresence>
                {viewingEntity && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-8" onClick={() => setViewingEntity(null)}>
                        <motion.div 
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-[#1e1e1e] border border-white/10 rounded-2xl w-full max-w-5xl h-[80vh] flex shadow-2xl overflow-hidden"
                        >
                            {/* Left: Image */}
                            <div className="w-1/2 bg-black relative flex items-center justify-center">
                                {viewingEntity.image_url ? (
                                    <img src={getFullUrl(viewingEntity.image_url)} alt={viewingEntity.name} className="max-w-full max-h-full object-contain" />
                                ) : (
                                    <div className="flex flex-col items-center justify-center text-white/20">
                                        <Users size={64} />
                                        <span className="mt-4 text-sm font-bold uppercase">No Image</span>
                                    </div>
                                )}
                                
                                {viewingEntity.id !== 'new' && (
                                    <div className="absolute top-4 left-4 flex gap-2">
                                         <button 
                                            onClick={() => { setViewingEntity(null); handleOpenImageModal(viewingEntity, 'library'); }}
                                            className="p-3 bg-black/50 hover:bg-black/80 rounded-full text-white backdrop-blur-md transition-colors"
                                            title="Change Image"
                                         >
                                             <ImageIcon size={20} />
                                         </button>
                                         <button 
                                            onClick={(e) => { e.stopPropagation(); handleAnalyzeEntity(viewingEntity); }}
                                            disabled={isAnalyzingEntity}
                                            className="p-3 bg-indigo-500/80 hover:bg-indigo-500 text-white rounded-full backdrop-blur-md transition-colors disabled:opacity-50 shadow-lg border border-white/10"
                                            title="Analyze Image & Refine Subject Info (Generates new prompt file)"
                                         >
                                             {isAnalyzingEntity ? <Loader2 size={20} className="animate-spin" /> : <Sparkles size={20} />}
                                         </button>
                                    </div>
                                )}
                            </div>
                            
                            {/* Right: Info */}
                            <div className="w-1/2 flex flex-col h-full bg-[#1e1e1e]">
                                <div className="p-6 border-b border-white/10 flex justify-between items-start">
                                    <div className="flex-1 mr-4">
                                        <input 
                                            value={viewingEntity.name || ''}
                                            onChange={(e) => {
                                                const val = e.target.value;
                                                setViewingEntity(prev => ({ ...prev, name: val }));
                                            }}
                                            onBlur={(e) => handleFieldUpdate('name', e.target.value)}
                                            className="text-3xl font-bold font-serif mb-1 bg-transparent border-b border-transparent hover:border-white/10 focus:border-primary outline-none w-full transition-colors truncate"
                                            placeholder="Entity Name"
                                        />
                                        <input 
                                            value={viewingEntity.name_en || ''} 
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, name_en: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('name_en', e.target.value)}
                                            className="text-lg text-muted-foreground font-mono bg-transparent border-b border-transparent hover:border-white/10 focus:border-primary outline-none w-full transition-colors"
                                            placeholder="English Name"
                                        />
                                    </div>
                                    <button 
                                        onClick={() => setViewingEntity(null)}
                                        className="p-2 hover:bg-white/10 rounded-full text-muted-foreground hover:text-white transition-colors"
                                    >
                                        <X size={24} />
                                    </button>
                                </div>
                                
                                <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
                                    {/* Role & Archetype Tags */}
                                    <div className="flex flex-wrap gap-2">
                                        {['role', 'archetype', 'gender'].map(field => (
                                            <input
                                                key={field}
                                                value={viewingEntity[field] || ''}
                                                onChange={(e) => setViewingEntity(prev => ({ ...prev, [field]: e.target.value }))}
                                                onBlur={(e) => handleFieldUpdate(field, e.target.value)}
                                                placeholder={field}
                                                className="px-3 py-1 bg-white/5 text-xs font-bold uppercase tracking-wider rounded-full border border-transparent focus:border-primary outline-none text-center min-w-[60px]"
                                            />
                                        ))}
                                    </div>

                                    {/* Description */}
                                    <div className="space-y-2">
                                        <h4 className="text-xs font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <FileText size={12} /> Description
                                        </h4>
                                        <textarea 
                                            value={viewingEntity.description || ''}
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, description: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('description', e.target.value)}
                                            className="w-full text-sm leading-relaxed text-white/80 bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-24 resize-none transition-colors"
                                            placeholder="Enter description..."
                                        />
                                    </div>

                                    {/* Environment Details */}
                                    {viewingEntity.type === 'environment' && (
                                        <div className="space-y-4 p-4 bg-white/5 rounded-lg border border-white/5">
                                             <div className="space-y-1">
                                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Atmosphere</h4>
                                                 <input 
                                                    value={viewingEntity.atmosphere || ''}
                                                    onChange={(e) => setViewingEntity(prev => ({ ...prev, atmosphere: e.target.value }))}
                                                    onBlur={(e) => handleFieldUpdate('atmosphere', e.target.value)}
                                                    className="w-full text-sm bg-transparent border-b border-white/10 hover:border-white/30 focus:border-primary p-2 outline-none transition-colors"
                                                    placeholder="Atmosphere (e.g. Dark, Cozy)"
                                                />
                                            </div>
                                             <div className="space-y-1">
                                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Visual Params</h4>
                                                <textarea 
                                                    value={viewingEntity.visual_params || ''}
                                                    onChange={(e) => setViewingEntity(prev => ({ ...prev, visual_params: e.target.value }))}
                                                    onBlur={(e) => handleFieldUpdate('visual_params', e.target.value)}
                                                    className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-24 resize-none"
                                                    placeholder="Visual parameters..."
                                                />
                                            </div>
                                             <div className="space-y-1">
                                                <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Narrative Description</h4>
                                                <textarea 
                                                    value={viewingEntity.narrative_description || ''}
                                                    onChange={(e) => setViewingEntity(prev => ({ ...prev, narrative_description: e.target.value }))}
                                                    onBlur={(e) => handleFieldUpdate('narrative_description', e.target.value)}
                                                    className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-24 resize-none"
                                                    placeholder="Detailed narrative (Description field)..."
                                                />
                                            </div>
                                        </div>
                                    )}

                                    {/* Appearance Details */}
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-1">
                                            <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Appearance</h4>
                                            <textarea 
                                                value={viewingEntity.appearance_cn || ''}
                                                onChange={(e) => setViewingEntity(prev => ({ ...prev, appearance_cn: e.target.value }))}
                                                onBlur={(e) => handleFieldUpdate('appearance_cn', e.target.value)}
                                                className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-20 resize-none"
                                                placeholder="Appearance details..."
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Clothing</h4>
                                            <textarea 
                                                value={viewingEntity.clothing || ''}
                                                onChange={(e) => setViewingEntity(prev => ({ ...prev, clothing: e.target.value }))}
                                                onBlur={(e) => handleFieldUpdate('clothing', e.target.value)}
                                                className="w-full text-sm bg-transparent border border-transparent hover:border-white/10 focus:border-primary focus:bg-white/5 rounded p-2 outline-none h-20 resize-none"
                                                placeholder="Clothing details..."
                                            />
                                        </div>
                                    </div>
                                    
                                    {/* Technical / Prompt */}
                                    <div className="space-y-2">
                                        <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <Wand2 size={10} /> Generation Prompt
                                        </h4>
                                        <textarea
                                            value={viewingEntity.generation_prompt_en || ''}
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, generation_prompt_en: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('generation_prompt_en', e.target.value)}
                                            className="w-full p-4 bg-black/20 rounded-lg border border-white/5 text-xs font-mono text-white/60 focus:text-white/90 focus:border-primary outline-none min-h-[100px] resize-y"
                                            placeholder="Enter generation prompt..."
                                        />
                                    </div>

                                    {/* Action Characteristics */}
                                    <div className="space-y-1">
                                        <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <Clapperboard size={10} /> Action Characteristics
                                        </h4>
                                        <textarea 
                                            value={viewingEntity.action_characteristics || ''}
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, action_characteristics: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('action_characteristics', e.target.value)}
                                            className="w-full text-sm p-3 bg-white/5 rounded-lg border border-white/5 hover:border-white/10 focus:border-primary outline-none resize-y min-h-[60px]"
                                            placeholder="Action characteristics..."
                                        />
                                    </div>

                                    {/* Anchor Description */}
                                    <div className="space-y-1">
                                        <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                            <LinkIcon size={10} /> Anchor Description
                                        </h4>
                                        <textarea 
                                            value={viewingEntity.anchor_description || ''}
                                            onChange={(e) => setViewingEntity(prev => ({ ...prev, anchor_description: e.target.value }))}
                                            onBlur={(e) => handleFieldUpdate('anchor_description', e.target.value)}
                                            className="w-full text-sm p-3 bg-white/5 rounded-lg border border-white/5 font-mono text-xs hover:border-white/10 focus:border-primary outline-none resize-y min-h-[60px]"
                                            placeholder="Anchor description..."
                                        />
                                    </div>

                                    {/* Dependency Strategy */}
                                    {viewingEntity.dependency_strategy && (viewingEntity.dependency_strategy.type || viewingEntity.dependency_strategy.logic) && (
                                        <div className="space-y-1 pt-2 border-t border-white/5">
                                            <h4 className="text-[10px] font-bold uppercase text-muted-foreground flex items-center gap-2">
                                                <Settings2 size={10} /> Dependency Strategy
                                            </h4>
                                            <div className="bg-white/5 rounded-lg border border-white/5 p-3 text-xs space-y-1">
                                                {viewingEntity.dependency_strategy.type && (
                                                    <div className="flex gap-2">
                                                        <span className="text-muted-foreground">Type:</span>
                                                        <span className="font-bold text-primary">{viewingEntity.dependency_strategy.type}</span>
                                                    </div>
                                                )}
                                                {viewingEntity.dependency_strategy.logic && (
                                                    <div className="flex gap-2 flex-col sm:flex-row sm:items-baseline">
                                                        <span className="text-muted-foreground whitespace-nowrap">Logic:</span>
                                                        <span className="text-white/80 italic">{viewingEntity.dependency_strategy.logic}</span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}

                                    {/* Visual Dependencies (Editable) */}
                                    <div className="space-y-2 pt-2 border-t border-white/5">
                                         <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Visual Dependencies</h4>
                                         <p className="text-[10px] text-white/40 mb-1">Add entity names to use their images as reference when generating this entity.</p>
                                         <div className="bg-black/20 p-3 rounded-lg border border-white/5">
                                             <div className="flex flex-wrap gap-2 mb-2">
                                                 {(Array.isArray(viewingEntity.visual_dependencies) ? viewingEntity.visual_dependencies : []).map((dep, i) => (
                                                     <div key={i} className="px-2 py-1 bg-primary/20 text-primary border border-primary/20 rounded text-xs flex items-center gap-2 group">
                                                         <span className="font-bold">{typeof dep === 'string' ? dep : JSON.stringify(dep)}</span>
                                                         <button 
                                                            onClick={() => {
                                                                 const current = Array.isArray(viewingEntity.visual_dependencies) ? viewingEntity.visual_dependencies : [];
                                                                 const newDeps = current.filter(d => d !== dep);
                                                                 handleFieldUpdate('visual_dependencies', newDeps);
                                                            }} 
                                                            className="hover:text-white opacity-50 group-hover:opacity-100"
                                                        >
                                                            <X size={10}/>
                                                        </button>
                                                     </div>
                                                 ))}
                                             </div>
                                             
                                             <div className="relative flex items-center gap-2">
                                                 <input 
                                                     type="text" 
                                                     placeholder="Type Entity Name & Enter..." 
                                                     className="w-full bg-transparent text-xs outline-none text-white/90 placeholder:text-white/20"
                                                     id="dep-input"
                                                     onKeyDown={(e) => {
                                                         if (e.key === 'Enter') {
                                                             const val = e.currentTarget.value.trim();
                                                             if(val) {
                                                                const current = Array.isArray(viewingEntity.visual_dependencies) ? viewingEntity.visual_dependencies : [];
                                                                if(!current.includes(val)) {
                                                                     handleFieldUpdate('visual_dependencies', [...current, val]);
                                                                }
                                                                e.currentTarget.value = '';
                                                             }
                                                         }
                                                     }}
                                                 />
                                                 <Plus className="w-3 h-3 text-muted-foreground cursor-pointer hover:text-white" onClick={() => {
                                                     const input = document.getElementById('dep-input');
                                                     if (!input) return;
                                                     const val = input.value.trim();
                                                     if (val) {
                                                         const current = Array.isArray(viewingEntity.visual_dependencies) ? viewingEntity.visual_dependencies : [];
                                                         if(!current.includes(val)) {
                                                             handleFieldUpdate('visual_dependencies', [...current, val]);
                                                         }
                                                         input.value = '';
                                                     }
                                                 }}/>
                                             </div>
                                         </div>
                                    </div>
                                    {/* Create Mode Actions */}
                                    {viewingEntity.id === 'new' && (
                                        <div className="mt-8 pt-4 border-t border-white/10 flex justify-end gap-3 sticky bottom-0 bg-[#1e1e1e] pb-2 z-10">
                                            <button 
                                                onClick={() => setViewingEntity(null)}
                                                className="px-4 py-2 rounded-lg font-bold text-xs text-muted-foreground hover:bg-white/10 transition-colors uppercase"
                                            >
                                                Cancel
                                            </button>
                                            <button 
                                                onClick={handleCommitCreate}
                                                className="px-6 py-2 rounded-lg font-bold text-xs bg-primary text-black hover:brightness-110 flex items-center gap-2 uppercase tracking-wide shadow-lg shadow-primary/20 transition-all active:scale-95"
                                            >
                                                <Plus size={14} strokeWidth={3} /> Create Subject
                                            </button>
                                        </div>
                                    )}

                                    {/* Attributes Display - Show ALL fields except the ones already shown above */
                                    (() => {
                                        const hiddenFields = ['id', 'project_id', 'image_url', 'created_at', 'updated_at', 'name', 'name_en', 'description', 
                                            'author_id', 'role', 'archetype', 'gender', 'appearance_cn', 'clothing', 'generation_prompt_en', 'visual_dependencies', 'type', 'project', 'dependency_strategy', 'action_characteristics', 'anchor_description', 'custom_attributes'];
                                        
                                        // Flatten custom_attributes into the view if they exist
                                        let mergedSource = { ...viewingEntity };
                                        if (viewingEntity.custom_attributes && typeof viewingEntity.custom_attributes === 'object') {
                                            mergedSource = { ...viewingEntity.custom_attributes, ...mergedSource };
                                        }

                                        // Merge known extra fields with potentially new ones, excluding standard
                                        const extraFields = Object.entries(mergedSource).filter(([key, val]) => 
                                            !hiddenFields.includes(key) && 
                                            val !== null && 
                                            val !== undefined
                                        );

                                        return (
                                            <div className="space-y-2 pt-4 border-t border-white/5">
                                                <div className="flex justify-between items-center">
                                                    <h4 className="text-[10px] font-bold uppercase text-muted-foreground">Other Attributes</h4>
                                                    <button 
                                                        onClick={() => {
                                                            const key = prompt("Enter new attribute name:");
                                                            if (key && !viewingEntity[key] && !hiddenFields.includes(key)) {
                                                                setViewingEntity(prev => ({...prev, [key]: "New Value"}));
                                                                // Auto save? Maybe wait for value edit.
                                                            }
                                                        }}
                                                        className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded text-white"
                                                    >
                                                        + Add
                                                    </button>
                                                </div>
                                                <div className="grid grid-cols-1 gap-2">
                                                    {extraFields.map(([key, value]) => (
                                                        <div key={key} className="p-3 bg-white/5 rounded-lg text-xs space-y-1 group relative">
                                                            <div className="flex justify-between">
                                                                <span className="opacity-50 font-mono uppercase text-[10px] break-all">{key.replace(/_/g, ' ')}</span>
                                                                <button 
                                                                    onClick={async () => {
                                                                        if(!confirm(`Delete attribute ${key}?`)) return;
                                                                        const updated = { ...viewingEntity };
                                                                        delete updated[key];
                                                                        setViewingEntity(updated);
                                                                        setEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
                                                                        setAllEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
                                                                        // For API, we might need to send null or special flag if backend handles it, 
                                                                        // but typically PUT replaces. If PATCH, we might need to set to null.
                                                                        // Assuming partial update, set to null to delete? Or backend ignores missing?
                                                                        // If backend is SQLModel/Pydantic with extra=ignore, it might persist.
                                                                        // Let's assume we send null to clear.
                                                                        updateEntity(updated.id, { [key]: null }); 
                                                                    }}
                                                                    className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-400 p-1"
                                                                >
                                                                    <Trash2 size={12} />
                                                                </button>
                                                            </div>
                                                            <textarea
                                                                value={typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                                                                onChange={(e) => {
                                                                    setViewingEntity(prev => ({ ...prev, [key]: e.target.value }));
                                                                }}
                                                                onBlur={(e) => {
                                                                    let val = e.target.value;
                                                                    // Try to parse JSON if it looks like object
                                                                    if (val.trim().startsWith('{') || val.trim().startsWith('[')) {
                                                                        try { val = JSON.parse(val); } catch(err) {} 
                                                                    }
                                                                    const updated = { ...viewingEntity, [key]: val };
                                                                    setEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
                                                                    setAllEntities(prev => prev.map(ent => ent.id === updated.id ? updated : ent));
                                                                    updateEntity(updated.id, { [key]: val });
                                                                }}
                                                                className="w-full bg-transparent border-none focus:bg-black/20 focus:ring-1 focus:ring-primary rounded p-1 outline-none font-mono resize-y min-h-[40px]" 
                                                            />
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })()}

                                </div>
                                
                                <div className="p-4 border-t border-white/10 bg-black/20 flex justify-end gap-3">
                                    <button 
                                        onClick={(e) => handleDeleteEntity(e, viewingEntity)}
                                        className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-md text-sm font-bold transition-colors flex items-center gap-2"
                                    >
                                        <Trash2 size={16} /> Delete
                                    </button>
                                    <button 
                                        onClick={() => { setViewingEntity(null); handleOpenImageModal(viewingEntity, 'generate'); }}
                                        className="px-4 py-2 bg-primary hover:bg-primary/90 text-black rounded-md text-sm font-bold transition-colors flex items-center gap-2"
                                    >
                                        <Wand2 size={16} /> Generate Image
                                    </button>
                                </div>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>

            {/* Image Selection Modal */}
            <AnimatePresence>
                {showImageModal && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                        <motion.div 
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            className="bg-[#1e1e1e] border border-white/10 rounded-xl w-full max-w-2xl h-[650px] flex flex-col shadow-2xl overflow-hidden"
                        >
                            <div className="flex justify-between items-center p-4 border-b border-white/10 bg-black/20">
                                <h3 className="font-bold text-lg">Select Image for {selectedEntity?.name}</h3>
                                <button onClick={() => setShowImageModal(false)} className="text-white/50 hover:text-white">
                                    <X size={20} />
                                </button>
                            </div>

                            <div className="flex border-b border-white/10">
                                {['library', 'upload', 'generate', 'advanced'].map(tab => (
                                    <button
                                        key={tab}
                                        onClick={() => setImageModalTab(tab)}
                                        className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${imageModalTab === tab ? 'border-primary text-primary bg-primary/5' : 'border-transparent text-muted-foreground hover:text-white hover:bg-white/5'}`}
                                    >
                                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                                    </button>
                                ))}
                            </div>

                            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                                {imageModalTab === 'library' && (
                                    <div className="grid grid-cols-4 gap-4">
                                        {assets.map(asset => (
                                            <div 
                                                key={asset.id} 
                                                onClick={() => handleSelectAsset(asset)}
                                                className="aspect-square bg-black/40 rounded-lg overflow-hidden border border-white/5 hover:border-primary/50 cursor-pointer group relative"
                                            >
                                                <img src={asset.url} alt="asset" className="w-full h-full object-cover" />
                                                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
                                            </div>
                                        ))}
                                        {assets.length === 0 && (
                                            <div className="col-span-4 py-12 text-center text-muted-foreground">
                                                No images found in library
                                            </div>
                                        )}
                                    </div>
                                )}

                                {imageModalTab === 'upload' && (
                                    <div className="flex flex-col items-center justify-center h-full space-y-4">
                                        <div className="p-8 border-2 border-dashed border-white/10 rounded-xl bg-black/20 hover:border-primary/50 hover:bg-primary/5 transition-all w-full max-w-sm flex flex-col items-center justify-center cursor-pointer relative">
                                            <input 
                                                type="file" 
                                                accept="image/*" 
                                                onChange={handleUpload}
                                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                                disabled={uploading} 
                                            />
                                            {uploading ? (
                                                <RefreshCw className="animate-spin text-primary mb-2" size={32} />
                                            ) : (
                                                <Upload className="text-muted-foreground mb-2" size={32} />
                                            )}
                                            <span className="text-sm font-medium text-muted-foreground">
                                                {uploading ? 'Uploading...' : 'Click or drop image here'}
                                            </span>
                                        </div>
                                        
                                        <div className="w-full max-w-sm mt-8">
                                             <div className="text-xs text-muted-foreground mb-2 uppercase font-bold tracking-wider">Or import from URL</div>
                                             <div className="flex gap-2">
                                                <input 
                                                    type="text" 
                                                    placeholder="https://..." 
                                                    className="flex-1 bg-black/40 border border-white/10 rounded-md px-3 py-2 text-sm focus:border-primary/50 outline-none"
                                                    onKeyDown={(e) => {
                                                        if (e.key === 'Enter') updateEntityImage(e.target.value);
                                                    }}
                                                />
                                                <button className="p-2 bg-white/10 hover:bg-white/20 rounded-md">
                                                    <LinkIcon size={18} />
                                                </button>
                                             </div>
                                        </div>
                                    </div>
                                )}

                                {imageModalTab === 'advanced' && (
                                    <div className="flex flex-col h-full">
                                        <div className="mb-4">
                                            <h4 className="text-xs font-bold uppercase text-muted-foreground mb-2">Advanced Refinement</h4>
                                            <p className="text-[10px] text-white/50 mb-4">
                                                Use AI to refine or modify the image with step-by-step instructions.
                                            </p>
                                        </div>
                                        <div className="flex-1">
                                            <RefineControl 
                                                originalText={selectedEntity?.generation_prompt_en || ""}
                                                onUpdate={(txt) => setPrompt(txt)}
                                                currentImage={selectedEntity?.image_url}
                                                onImageUpdate={updateEntityImage}
                                                projectId={projectId}
                                                featureInjector={(text) => {
                                                    const epInfo = currentEpisode?.episode_info || {};
                                                    const processed = processPrompt(text, epInfo, allEntities);
                                                    return { text: processed, modified: processed !== text };
                                                }}
                                                onPickMedia={(cb) => openMediaPicker(cb, { entityId: selectedEntity?.id })}
                                                type="image"
                                            />
                                        </div>
                                    </div>
                                )}

                                {imageModalTab === 'generate' && (
                                    <div className="flex flex-col h-full">
                                        <textarea
                                            value={prompt}
                                            onChange={(e) => setPrompt(e.target.value)}
                                            placeholder="Describe the image you want to generate. Use [Global Style] for episode style. Use [Subject Name] to reference other entities."
                                            className="w-full h-32 bg-black/40 border border-white/10 rounded-lg p-4 text-sm focus:border-primary/50 outline-none resize-none mb-4"
                                        />
                                        
                                        {/* Auto-detected Visual Dependencies */}
                                        {selectedEntity?.visual_dependencies && selectedEntity.visual_dependencies.length > 0 && (
                                            <div className="mb-4">
                                                <label className="text-[10px] uppercase font-bold text-muted-foreground mb-1 block">Visual Dependencies (Auto-Used)</label>
                                                <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
                                                    {(Array.isArray(selectedEntity.visual_dependencies) ? selectedEntity.visual_dependencies : []).map((dep, idx) => {
                                                        const startDep = String(dep).trim();
                                                        const startDepLower = startDep.toLowerCase();
                                                        
                                                        const depEntity = allEntities.find(e => {
                                                            if (!e) return false;
                                                            if (String(e.id) === startDep) return true;
                                                            if (e.name && e.name.trim().toLowerCase() === startDepLower) return true;
                                                            if (e.name_en && e.name_en.trim().toLowerCase() === startDepLower) return true;
                                                            return false;
                                                        });
                                                        
                                                        return (
                                                            <div key={idx} className="flex-shrink-0 w-24 bg-black/40 border border-white/10 rounded-lg p-1.5 flex flex-col gap-1 relative group">
                                                                <div className="aspect-square bg-black rounded overflow-hidden">
                                                                     {depEntity?.image_url ? (
                                                                         <img src={getFullUrl(depEntity.image_url)} alt={dep} className="w-full h-full object-cover" />
                                                                     ) : (
                                                                         <div className="w-full h-full flex items-center justify-center bg-white/5">
                                                                             <Users size={16} className="text-white/20"/>
                                                                         </div>
                                                                     )}
                                                                </div>
                                                                <div className="text-[10px] truncate font-bold text-white px-0.5" title={dep}>
                                                                    {depEntity ? depEntity.name : dep}
                                                                </div>
                                                                {!depEntity && <div className="text-[8px] text-red-400 px-0.5">Not Found</div>}
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        )}
                                        
                                        {/* Configuration Row */}
                                        <div className="flex items-center gap-4 mb-4">
                                            {/* Provider Select */}
                                            <div className="flex-1">
                                                <label className="text-[10px] uppercase font-bold text-muted-foreground mb-1 block">Provider</label>
                                                <select 
                                                    value={provider} 
                                                    onChange={e => setProvider(e.target.value)}
                                                    className="w-full bg-black/40 border border-white/10 rounded-md px-2 py-1.5 text-xs text-white focus:border-primary/50 outline-none"
                                                >
                                                    <option value="">Default (System)</option>
                                                    {availableProviders.map(p => (
                                                        <option key={p.provider} value={p.provider}>
                                                           {p.provider ? (p.provider.charAt(0).toUpperCase() + p.provider.slice(1)) : 'Unknown'}
                                                        </option>
                                                    ))}
                                                </select>
                                            </div>
                                            
                                            {/* Reference Image Select */}
                                            <div className="flex-[2] relative">
                                                 <label className="text-[10px] uppercase font-bold text-muted-foreground mb-1 block">Ref Image (Optional)</label>
                                                 
                                                 {!refImage ? (
                                                     <div className="flex gap-2 items-center">
                                                          <div className="flex-1 flex gap-2">
                                                              {/* Selection Buttons */}
                                                              <button 
                                                                onClick={() => setRefSelectionMode(refSelectionMode === 'assets' ? null : 'assets')}
                                                                className={`p-2 rounded border border-white/10 text-xs font-bold hover:bg-white/10 flex items-center gap-1 ${refSelectionMode === 'assets' ? 'bg-primary/20 text-primary border-primary/50' : 'bg-black/40 text-muted-foreground'}`}
                                                              >
                                                                  <FolderOpen size={14} /> Assets
                                                              </button>
                                                              <div className="relative overflow-hidden w-24">
                                                                  <button className="w-full p-2 bg-black/40 border border-white/10 rounded text-xs font-bold hover:bg-white/10 text-muted-foreground flex items-center gap-1 justify-center">
                                                                    <Upload size={14} /> Upload
                                                                  </button>
                                                                  <input 
                                                                    type="file" 
                                                                    className="absolute inset-0 opacity-0 cursor-pointer" 
                                                                    accept="image/*"
                                                                    onChange={handleRefUpload}
                                                                  />
                                                              </div>
                                                          </div>
                                                          
                                                          {/* URL Input (Fallback) */}
                                                          <div className="w-1/3 relative">
                                                              <input 
                                                                  type="text" 
                                                                  placeholder="URL..." 
                                                                  onBlur={(e) => {
                                                                      if (e.target.value) setRefImage({ url: e.target.value, name: 'External URL', type: 'image' });
                                                                  }}
                                                                  onKeyDown={(e) => {
                                                                        if (e.key === 'Enter' && e.target.value) setRefImage({ url: e.target.value, name: 'External URL', type: 'image' });
                                                                  }}
                                                                  className="w-full bg-black/40 border border-white/10 rounded px-2 py-2 text-xs text-white focus:border-primary/50 outline-none"
                                                              />
                                                          </div>
                                                     </div>
                                                 ) : (
                                                     // Selected Preview State
                                                     <div className="flex gap-3 bg-black/40 border border-white/10 rounded-lg p-2 items-center relative group">
                                                         <div className="w-10 h-10 bg-black rounded overflow-hidden flex-shrink-0 border border-white/5">
                                                             <img src={getFullUrl(refImage.url)} alt="ref" className="w-full h-full object-cover" />
                                                         </div>
                                                         <div className="flex-1 overflow-hidden">
                                                             <div className="text-xs font-bold text-white truncate">{refImage.name || 'Reference Image'}</div>
                                                             <div className="text-[10px] text-muted-foreground flex gap-2">
                                                                 <span>{refImage.dimensions || 'Unknown Size'}</span>
                                                                 {refImage.type && <span className="uppercase">{refImage.type}</span>}
                                                             </div>
                                                         </div>
                                                         <button 
                                                             onClick={() => setRefImage(null)}
                                                             className="p-1 hover:bg-white/10 rounded-md text-white/50 hover:text-white"
                                                         >
                                                             <X size={14} />
                                                         </button>
                                                     </div>
                                                 )}

                                                 {/* Asset Picker Popover */}
                                                 {refSelectionMode === 'assets' && !refImage && (
                                                     <div className="absolute top-full left-0 right-0 mt-2 z-10 bg-[#09090b] border border-white/10 rounded-xl shadow-2xl h-64 overflow-hidden flex flex-col">
                                                         <div className="p-2 border-b border-white/10 flex justify-between items-center bg-black/20">
                                                             <span className="text-xs font-bold text-muted-foreground ml-2">Select from Assets</span>
                                                             <button onClick={() => setRefSelectionMode(null)}><X size={14} className="text-white/50 hover:text-white"/></button>
                                                         </div>
                                                         <div className="flex-1 overflow-y-auto p-2 custom-scrollbar">
                                                             <div className="grid grid-cols-4 gap-2">
                                                                 {assets.map(asset => (
                                                                     <div 
                                                                         key={asset.id} 
                                                                         onClick={() => {
                                                                             setRefImage(asset);
                                                                             setRefSelectionMode(null);
                                                                         }}
                                                                         className="aspect-square bg-black/40 rounded border border-white/5 hover:border-primary/50 cursor-pointer overflow-hidden relative group"
                                                                     >
                                                                         <img src={getFullUrl(asset.url)} alt={asset.name} className="w-full h-full object-cover" />
                                                                         <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
                                                                     </div>
                                                                 ))}
                                                                 {assets.length === 0 && (
                                                                     <div className="col-span-4 py-8 text-center text-xs text-muted-foreground">No assets found</div>
                                                                 )}
                                                             </div>
                                                         </div>
                                                     </div>
                                                 )}
                                            </div>
                                        </div>

                                        <div className="flex justify-end">
                                            <button 
                                                onClick={handleGenerate}
                                                disabled={generating || !prompt}
                                                className="flex items-center space-x-2 bg-primary text-black px-6 py-2 rounded-lg font-bold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                            >
                                                {generating ? (
                                                    <RefreshCw className="animate-spin" size={18} />
                                                ) : (
                                                    <Wand2 size={18} />
                                                )}
                                                <span>{generating ? 'Generating...' : 'Generate Image'}</span>
                                            </button>
                                        </div>
                                        
                                        <div className="mt-6">
                                            <h4 className="text-xs font-bold uppercase text-muted-foreground mb-3">Prompt Variables</h4>
                                            <ul className="text-xs text-white/60 space-y-2 list-disc pl-4">
                                                <li><code className="bg-white/10 px-1 rounded text-primary">[Global Style]</code>: Injects current episode style.</li>
                                                <li><code className="bg-white/10 px-1 rounded text-primary">[Subject Name]</code>: Injects matched Entity name + description.</li>
                                            </ul>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
            
            <MediaPickerModal 
                isOpen={pickerConfig.isOpen}
                onClose={() => setPickerConfig(prev => ({ ...prev, isOpen: false }))}
                onSelect={(url, type) => {
                    if (pickerConfig.callback) pickerConfig.callback(url, type);
                    setPickerConfig(prev => ({ ...prev, isOpen: false }));
                }}
                projectId={projectId}
                context={pickerConfig.context}
                entities={allEntities}
                episodeId={currentEpisode?.id}
            />
        </div>
    );
};

const ShotsView = ({ activeEpisode, projectId, project, onLog, editingShot, setEditingShot }) => {
    const { generationConfig, saveToolConfig, savedToolConfigs, llmConfig } = useStore();
    const [scenes, setScenes] = useState([]);
    const [selectedSceneId, setSelectedSceneId] = useState('all');
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [shots, setShots] = useState([]);
    const [isImportOpen, setIsImportOpen] = useState(false);
    // const [editingShot, setEditingShot] = useState(null); // Lifted state
    const [entities, setEntities] = useState([]);
    
    // NEW: Abort Controller Ref for retries
    const abortGenerationRef = useRef(false);

    // Local Notification for ShotsView (Edit Dialog)
    const [notification, setNotification] = useState(null);
    const showNotification = (message, type = 'success') => {
        setNotification({ message, type });
        setTimeout(() => setNotification(null), 3000);
    };

    useEffect(() => {
        if (projectId) {
            fetchEntities(projectId).then(setEntities).catch(console.error);
        }
    }, [projectId]);


    // Note: Provider selection functionality removed (defaults to Backend Active Settings)
    // Code for local state imageProvider/videoProvider removed.


    // AI Prompt Preview Modal State
    const [shotPromptModal, setShotPromptModal] = useState({ open: false, sceneId: null, data: null, loading: false });

    // Media Handling
    const [viewMedia, setViewMedia] = useState(null);
    const [pickerConfig, setPickerConfig] = useState({ isOpen: false, callback: null });
    const [generatingState, setGeneratingState] = useState({ start: false, end: false, video: false });
    const [isBatchGenerating, setIsBatchGenerating] = useState(false);
    const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0, status: '' }); // Progress tracking

    // Helper: Construct Global Context String from Episode Info
    const getGlobalContextStr = () => {
        const info = activeEpisode?.episode_info?.e_global_info;
        if (!info) return "";
        const parts = [];
        // Append explicit labels so the model understands the context
        if (info.Global_Style) parts.push(`Style: ${info.Global_Style}`);
        if (info.tone) parts.push(`Tone: ${info.tone}`);
        if (info.lighting) parts.push(`Lighting: ${info.lighting}`);
        
        return parts.length > 0 ? " | " + parts.join(", ") : "";
    };

    const openMediaPicker = (callback, context = {}) => {
        setPickerConfig({ isOpen: true, callback, context });
    };

    const onUpdateShot = async (shotId, changes) => {
        try {
            // Fix 422 Error: Backend requires 'shot_number' and 'description'
            // We must merge with existing shot data to ensure these fields exist
            const currentShot = shots.find(s => s.id === shotId);
            if (!currentShot) return;

            const payload = {
                ...currentShot,
                ...changes
            };
            
            // Explicitly ensure required keys are present if they were somehow missing in object
            // (though spread of currentShot should handle it)
            if (!payload.shot_number) payload.shot_number = "1"; 
            if (!payload.description) payload.description = "";

            await updateShot(shotId, payload);
            setShots(prev => prev.map(s => s.id === shotId ? { ...s, ...changes } : s));

            // Sync editingShot safely
            setEditingShot(prev => {
                if (prev && prev.id === shotId) {
                    return { ...prev, ...changes };
                }
                return prev;
            });
        } catch(e) { 
            console.error("Update Shot Failed", e); 
            onLog?.("Failed to save changes", "error");
        }
    }

    const handleGenerateShots = async (sceneId) => {
        if (sceneId === 'all') {
            onLog?.("Please select a specific scene to generate shots.", "warning");
            return;
        }
        setShotPromptModal({ open: true, sceneId: sceneId, data: null, loading: true });
        try {
            const data = await fetchSceneShotsPrompt(sceneId);
            setShotPromptModal({ open: true, sceneId: sceneId, data: data, loading: false });
        } catch (e) {
             onLog?.(`Failed to fetch prompt preview - ${e.message}`, 'error');
             setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });
        }
    };

    const handleConfirmGenerateShots = async () => {
         const { sceneId, data } = shotPromptModal;
         if (!confirm("This will overwrite existing shots for this scene. Continue?")) return;
         
         setShotPromptModal(prev => ({ ...prev, loading: true }));
         onLog?.(`Generating shots for Scene ${sceneId}...`, 'info');
         try {
             await generateSceneShots(sceneId, { 
                 user_prompt: data.user_prompt,
                 system_prompt: data.system_prompt 
             });
             onLog?.(`Shot list generated for Scene ${sceneId}.`, 'success');
             setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });
             
             // Refresh Logic
             refreshShots();
         } catch (e) {
             console.error(e);
             onLog?.(`Failed to generate shots - ${e.message}`, 'error');
             alert("Failed to generate shots: " + e.message);
             setShotPromptModal(prev => ({ ...prev, loading: false }));
         }
    };

    const handleMediaSelect = (url, type) => {
        if (pickerConfig.callback) {
            pickerConfig.callback(url, type);
        }
        setPickerConfig({ isOpen: false, callback: null });
    };

    useEffect(() => {
        if (activeEpisode?.project_id) {
            // console.log("Fetching Entities for Project:", activeEpisode.project_id);
            fetchEntities(activeEpisode.project_id)
                .then(data => {
                    // console.log("Entities Loaded:", data.length);
                    setEntities(data);
                })
                .catch(console.error);
        } else {
            console.warn("ShotsView: No activeEpisode or project_id to fetch entities.");
        }
    }, [activeEpisode]);

    const refreshShots = useCallback(async () => {
        if (!selectedSceneId || !activeEpisode?.id) return;
        
        try {
            // Optimized: Fetch all shots for the EPISODE.
            // This satisfies the requirement to select based on Project/Episode, and associate via Scene ID locally.
            // Also fixes issues where unlinked shots or imports were hidden.
            const allShots = await fetchEpisodeShots(activeEpisode.id);
            console.log(`[ShotsView] Loaded ${allShots.length} total shots for Episode ${activeEpisode.id}`);

            if (selectedSceneId === 'all') {
                setShots(allShots);
            } else {
                // Local Filter by scene_id
                const filtered = allShots.filter(s => String(s.scene_id) === String(selectedSceneId));
                setShots(filtered);

                // Legacy Auto-Sync Check (Optional, but kept for script-to-shot workflow convenience)
                if (filtered.length === 0 && (activeEpisode?.scene_content || activeEpisode?.shot_content)) {
                     // Only if we truly have 0 matching shots, maybe try to parses content
                     // Check if we haven't already synced (prevent loops)
                     // Here we just log or optionally call sync. 
                     // We'll keep it simple for now as user asked to remove "sync logic".
                     // But if user relies on auto-generation... 
                     // Let's assume 'remove sync logic' refers to the strict scene_code matching.
                }
            }
        } catch (e) {
            console.error("Failed to refresh shots", e);
        }
    }, [activeEpisode?.id, selectedSceneId]);

    useEffect(() => {
        if(activeEpisode?.id) {
            fetchScenes(activeEpisode.id).then((data) => {
                setScenes(data);
                // If previously 'all' but couldn't load due to empty scenes, this will re-trigger refreshShots via useEffect[selectedSceneId, refreshShots]
                // because refreshShots depends on 'scenes' if selectedSceneId is 'all'
            }).catch(e => console.error(e));
        }
    }, [activeEpisode]);

    useEffect(() => {
        refreshShots();
    }, [refreshShots]);


    const handleDeleteAllShots = async () => {
        if (shots.length === 0) return;
        if (!window.confirm(`Are you sure you want to delete all ${shots.length} shots displayed here? This cannot be undone.`)) return;

        onLog?.("Deleting all shots...", "process");
        try {
            await Promise.all(shots.map(s => deleteShot(s.id)));
            onLog?.(`Successfully deleted ${shots.length} shots.`, "success");
            setShots([]);
        } catch (e) {
            console.error(e);
            onLog?.("Error deleting shots", "error");
            refreshShots();
        }
    };

    const handleSyncScenes = async (onlyForSceneId = null) => {
        // Support pulling from scene_content OR shot_content
        const contentSources = [];
        if (activeEpisode?.scene_content) contentSources.push(activeEpisode.scene_content);
        if (activeEpisode?.shot_content) contentSources.push(activeEpisode.shot_content);

        if (contentSources.length === 0) {
            onLog?.("No scene/shot content to sync from source text.", "warning");
            return;
        }
        
        onLog?.(onlyForSceneId ? "Syncing Logic (Smart Refresh)..." : "Syncing Scenes & Shots...", "process");
        
        // Merge lines from both sources
        let allLines = [];
        contentSources.forEach(txt => {
            allLines = allLines.concat(txt.split('\n'));
        });
        
        const lines = allLines;
        
        // Cache to avoid duplicates and redundant calls
        const sceneShotsCache = {};
        let countShots = 0;

        // 1. Fetch ALL existing scenes from DB first
        let dbScenes = [];
        try { 
            dbScenes = await fetchScenes(activeEpisode.id); 
            // Update UI with fresh scenes immediately to avoid "Missing Scenes" visual
            if (!onlyForSceneId) setScenes(dbScenes);
        } catch(e) { console.error(e); }
        
        // Map: "1" -> SceneObj, "01" -> SceneObj
        const getSceneKey = (num) => String(num).replace(/^0+/, '').replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
        const sceneMap = {};
        dbScenes.forEach(s => { 
            if(s.scene_no) sceneMap[getSceneKey(s.scene_no)] = s; 
        });

        let defaultSceneId = null; // Track created default scene

        // 2. Iterate text lines looking ONLY for Shots
        for (let line of lines) {
             const trimmed = line.trim();
             if (!trimmed.includes('|')) continue;
             if (trimmed.includes('Shot No') || trimmed.includes('Shot ID') || trimmed.includes('镜头ID') || trimmed.includes('---')) continue;
             
             const cols = trimmed.split('|').map(c => c.trim());
             if (cols.length > 0 && cols[0] === '') cols.shift();
             if (cols.length > 0 && cols[cols.length-1] === '') cols.pop();
             if (cols.length < 2) continue; // Not a valid row
             
             const clean = (t) => t ? t.replace(/<br\s*\/?>/gi, '\n').replace(/\\\|/g, '|') : '';
             const shotNumRaw = clean(cols[0]); // e.g. "1-1", "1A-1"
             
             // 3. Determine Target Scene from Shot Number Prefix
             // "1-12" -> Scene "1"
             // "1A-5" -> Scene "1A"
             // "2"    -> Scene "2" (if loose)
             let targetSceneId = null;
             
             // Strategy: Look for "-" separator
             const parts = shotNumRaw.split(/[-_]/);
             const scenePrefix = parts.length > 1 ? parts[0] : null; 
             
             if (scenePrefix) {
                 const key = getSceneKey(scenePrefix);
                 if (sceneMap[key]) {
                     targetSceneId = sceneMap[key].id;
                 }
             }

             // Fallback: If no prefix match, try selectedSceneId (if not 'all')
             if (!targetSceneId && selectedSceneId && selectedSceneId !== 'all') {
                 targetSceneId = parseInt(selectedSceneId);
             }

             // Auto-Create Default Scene if Orphaned
             if (!targetSceneId) {
                 if (defaultSceneId) {
                     targetSceneId = defaultSceneId;
                 } else {
                     // Check existing "Default Scene"
                     const existingDefault = dbScenes.find(s => s.scene_name === "Default Scene" || s.scene_no === "DEFAULT");
                     if (existingDefault) {
                         targetSceneId = existingDefault.id;
                         defaultSceneId = existingDefault.id;
                     } else if (dbScenes.length === 0) {
                         // Only create if NO scenes exist (assuming shot-only import)
                         try {
                              console.log("Creating Default Scene for orphaned shots...");
                              // We need to await inside loop, but it's only once
                              // eslint-disable-next-line no-await-in-loop
                              const newScene = await createScene(activeEpisode.id, {
                                  scene_number: "DEFAULT",
                                  title: "Default Scene",
                                  description: "Auto-generated for imported shots",
                                  location: "Unknown",
                                  time_of_day: "Unknown"
                              });
                              dbScenes.push(newScene);
                              setScenes(prev => [...prev, newScene]);
                              targetSceneId = newScene.id;
                              defaultSceneId = newScene.id;
                         } catch(e) {
                             console.error("Failed to create default scene", e);
                         }
                     }
                 }
             }

             // If still no scene, we verify if the USER wants us to create shots purely based on sequence? 
             // Current strict mode: If we can't link, we skip.
             if (!targetSceneId) continue;
             
             // Smart Filter for partial updates
             if (onlyForSceneId && targetSceneId !== onlyForSceneId) continue;

             // 4. Create/Sync Shot
             const currentSceneId = targetSceneId;
             
             // IDEMPOTENCY CHECK
             if (!sceneShotsCache[currentSceneId]) {
                 try {
                     sceneShotsCache[currentSceneId] = await fetchShots(currentSceneId);
                 } catch(e) { sceneShotsCache[currentSceneId] = []; }
             }
             
             const shotData = {
                 shot_id: shotNumRaw.replace(/\*\*/g, ''),
                 shot_name: clean(cols[1]),
                 start_frame: clean(cols[2]),
                 end_frame: clean(cols[3]),
                 video_content: clean(cols[4]),
                 duration: clean(cols[5]),
                 associated_entities: clean(cols[6])
             };
             
             // Duplication Check
             const existingShots = sceneShotsCache[currentSceneId];
             const alreadyExists = existingShots.find(s => {
                 const sNum = String(s.shot_id || '').replace(/\*\*/g, '').replace(/Shot\s*/i, '').trim();
                 const tNum = String(shotData.shot_id || '').replace('Shot', '').trim();
                 return sNum === tNum;
             });
             
             if (!alreadyExists) {
                try {
                    const newShot = await createShot(currentSceneId, shotData);
                    existingShots.push(newShot); 
                    countShots++;
                } catch(e) { console.error("Sync Shot Error", e); }
             }
        }
        
        if (countShots > 0) {
            onLog?.(`Synced ${countShots} shots to ${Object.keys(sceneShotsCache).length} scenes.`, "success");
        } else if (!onlyForSceneId) {
             onLog?.("No new shots found to sync.", "info");
        }

        // Force Refresh UI
        if (!onlyForSceneId) {
            // Re-fetch all scenes to update lists
            try {
                 const currentScenes = await fetchScenes(activeEpisode.id);
                 setScenes(currentScenes);
            } catch(e) { console.error(e); }

            // Using unified refresh logic
            refreshShots();
        }
    };

    const handleImport = async (text) => {
        if (!selectedSceneId) {
             onLog?.("Please select a scene first.", "error");
             return;
        }
        
        onLog?.("Processing Shot Import...", "process");
        const lines = text.split('\n');
        
        const currentScene = scenes.find(s => s.id == selectedSceneId);
        
        const parsedShots = [];
        let headerFound = false;
        let headerMap = {}; // Map normalized header string to column index

        for (let line of lines) {
             // Skip context header (Project | Episode)
             if (line.includes('Project:') && line.includes('Episode:')) continue;
             
             // Check for possible header row by keywords
             const normLine = line.toLowerCase();
             const isHeader = line.includes('|') && (
                 normLine.includes('shot no') || normLine.includes('shot id') || normLine.includes('镜头id') || normLine.includes('scene id')
             );
             
             // Process Row splitting logic consistently for Header and Data
             if (line.includes('|') && !line.includes('---')) {
                 const cols = line.split('|').map(c => c.trim());
                 if (cols.length > 0 && cols[0] === '') cols.shift();
                 if (cols.length > 0 && cols[cols.length-1] === '') cols.pop();

                 if (isHeader) {
                     headerFound = true;
                     cols.forEach((col, idx) => {
                         // Normalize header key: remove special chars, lowercase
                         const key = col.toLowerCase().replace(/[\(\)（）\s\.]/g, '');
                         headerMap[key] = idx;
                     });
                     console.log("Import Header Map FULL:", JSON.stringify(headerMap));
                     console.log("Looking for keys: shotlogiccn, shotlogic, etc.");
                     onLog?.("Parsed Headers: " + Object.keys(headerMap).join(", "), "info");
                     continue;
                 }
                 
                 if (headerFound) {
                     const clean = (t) => t ? t.replace(/<br\/?>/gi, '\n') : '';
                     
                     // Helper to get value by possible keys
                     const getVal = (keys, defaultIdx) => {
                         for (const k of keys) {
                             if (headerMap[k] !== undefined && headerMap[k] < cols.length) {
                                 return clean(cols[headerMap[k]]); 
                             }
                         }
                         // Fallback to default index if map logic fails or specific column not found
                         // Only fallback if we don't have a reliable map (e.g. maybe map is empty?)
                         if (Object.keys(headerMap).length === 0 && defaultIdx < cols.length) {
                             return clean(cols[defaultIdx]);
                         }
                         return ''; 
                     };

                     // Determine fallback offset based on column count if map failed (legacy logic)
                     // But if we have map, we rely on it.
                     const useMap = Object.keys(headerMap).length > 0;
                     
                     // Legacy offset logic for fallback
                     let colStart = 2; 
                     let legacySceneCode = '';
                     if (!useMap) {
                        if (cols.length >= 8) {
                            legacySceneCode = clean(cols[2]);
                            colStart = 3;
                        }
                     }
                     
                     let extractedSceneCode = useMap ? getVal(['sceneid', 'sceneno', 'scenecode', '场号'], -1) : legacySceneCode;
                     // Ensure scene_code is populated if import misses it
                     if (!extractedSceneCode && currentScene) {
                         extractedSceneCode = currentScene.scene_no;
                     }

                     const shotData = {
                         shot_id: useMap ? getVal(['shotid', 'shotno', '镜头id', 'id'], 0) : clean(cols[0]),
                         shot_name: useMap ? getVal(['shotname', 'name', '镜头名称'], 1) : clean(cols[1]),
                         
                         scene_code: extractedSceneCode,
                         
                         start_frame: useMap ? getVal(['startframe', 'start', '首帧'], 2) : clean(cols[colStart]),
                         end_frame: useMap ? getVal(['endframe', 'end', '尾帧'], 3) : clean(cols[colStart+1]),
                         video_content: useMap ? getVal(['videocontent', 'video', 'description', '视频内容'], 4) : clean(cols[colStart+2]),
                         duration: useMap ? getVal(['duration', 'duration(s)', 'dur', '时长'], 5) : clean(cols[colStart+3]),
                         associated_entities: useMap ? getVal(['associatedentities', 'entities', 'associated', '实体'], 6) : clean(cols[colStart+4]),
                         shot_logic_cn: (() => {
                             const val = useMap ? getVal(['shotlogiccn', 'shotlogic', 'logic', 'logiccn', 'shotlogic(cn)'], 7) : '';
                             if (val) console.log("DEBUG: Found shot_logic_cn:", val);
                             return val;
                         })(),
                         keyframes: useMap ? getVal(['keyframes', 'key frames', '关键帧', 'kf'], 8) : '',

                         // Clear unused
                         shot_type: '',
                         lens: '',
                         framing: '',
                         dialogue: '',
                         technical_notes: ''
                     };
                     
                     // Only push valid rows
                     if (shotData.shot_id && String(shotData.shot_id).trim() !== '') {
                        parsedShots.push(shotData);
                     }
                 }
             }
        }

        if (parsedShots.length > 0) {
            let shouldOverwrite = false;
            // Removed redundant currentScene fetch here
            
            // Check if import sceneCode matches selected scene
            if (currentScene && currentScene.scene_no) {
                const importCode = parsedShots[0].scene_code;
                if (importCode && String(importCode).trim() === String(currentScene.scene_no).trim()) {
                    shouldOverwrite = true;
                }
            }
            
            if (shouldOverwrite && shots.length > 0) {
                 onLog?.(`Scene Code matched (${parsedShots[0].scene_code}). Overwriting existing shots...`, 'warning');
                 try {
                     await Promise.all(shots.map(s => deleteShot(s.id)));
                     setShots([]); 
                 } catch(e) {
                     console.error("Failed to delete existing shots", e);
                     onLog?.("Failed to clear shots. Appending...", "error");
                 }
            }

            let count = 0;
            // Create shots sequentially
            // Use 'selectedSceneId' for physical relationship, but 's.scene_code' ensures logical grouping
            // Note: If s.scene_code is missing, endpoints.py might hide the shot!
            for (const s of parsedShots) {
                 try {
                    // Ensure the shot object has scene_code
                    if (!s.scene_code && currentScene) s.scene_code = currentScene.scene_no;
                    
                    if (count === 0) {
                        console.log("First Shot Payload:", s);
                        if (!s.shot_logic_cn) {
                             onLog?.("Warning: 'Shot Logic (CN)' is empty in the parsed data.", "warning");
                        }
                    }

                    await createShot(selectedSceneId, s);
                    count++;
                 } catch(e) {
                     console.error("Failed to create shot", e);
                     onLog?.(`Failed to create shot ${s.shot_id || 'unknown'}: ${e.message}`, "error");
                 }
            }

            if (count > 0) {
                onLog?.(`Imported ${count} shots successfully. Refreshing view...`, 'success');
                setIsImportOpen(false);
                
                // FORCE REFRESH: Fetch specifically for current scene to ensure we have data immediately
                // Try refreshing both full episode list and specific scene
                await refreshShots(); 
                
                try {
                    const sceneSpecific = await fetchShots(selectedSceneId);
                    if (sceneSpecific && sceneSpecific.length > 0) {
                        setShots(sceneSpecific);
                        console.log("[Import] Force set shots via direct Scene Fetch:", sceneSpecific.length);
                    }
                } catch(e) { console.error("Post-import fetch failed", e); }

            } else {
                 onLog?.('Import completed but no shots created.', 'warning');
            }
        } else {
             onLog?.('No valid shots data found.', 'warning');
        }
    };

    // --- Helper: Parsing Entities matches ---
    // Updated Logic: Matches both [Name] and {Name}, allowing specific text source
    const getSuggestedRefImages = useCallback((shot, sourceText = null, strictMode = false) => {
        if (!shot) return [];
        // In ShotsView, 'entities' contains ALL entities (fetched by project)
        const entList = entities;
        
        if (!entList.length) {
            return [];
        }


        // Updated Logic: Matches both [Name] and {Name}, allowing specific text source
        // Now synchronized with ReferenceManager logic for consistent robust matching
        const cleanName = (s) => s.replace(/[\[\]\{\}【】"''“”‘’\(\)（）]/g, '').trim().toLowerCase();
        const superNormalize = (s) => s.replace(/[\s\(\)\[\]\{\}【】（）\-_\.]/g, '').toLowerCase();
        
        // Associated Entities (Included unless strictMode is true)
        const rawNames1 = strictMode ? [] : (shot.associated_entities || '').split(/[,，]/);
        
        // Prompt Search logic - Unified Regexes from ReferenceManager
        const regexes = [
            /\[([\s\S]+?)\]/g,    // [...]
            /\{([\s\S]+?)\}/g,    // {...}
            /【([\s\S]+?)】/g,     // 【...】
            /｛([\s\S]+?)｝/g,      // ｛...｝
            // Also keep legacy simple regex for cases without full brackets if needed? 
            // The legacy regex was: /[\[【\{]([^\]】\}\(]+)[\]】\}\(]/g; which was too restrictive.
        ];
        
        // If sourceText is provided, use it. Otherwise use shot fields EXCLUDING description (as per user request)
        let textToScan = sourceText;
        if (!textToScan) {
            const parts = [];
            if (shot.start_frame) parts.push(shot.start_frame);
            if (shot.end_frame) parts.push(shot.end_frame);
            if (shot.video_content) parts.push(shot.video_content);
            if (shot.prompt) parts.push(shot.prompt);
            textToScan = parts.join(' ');
        }

        const rawNames2 = [];
        if (textToScan) {
            regexes.forEach(regex => {
                let match;
                regex.lastIndex = 0;
                while ((match = regex.exec(textToScan)) !== null) {
                    if (match[1] && match[1].trim()) rawNames2.push(match[1]);
                }
            });
            // Legacy Fallback for simple "CharacterName" without brackets? No, usually enforced by [] 
        }
        
        // 3. Match Logic
        const candidates = [...rawNames1, ...rawNames2];
        const normalizedCandidates = candidates.map(cleanName).filter(Boolean);
        const superCandidates = candidates.map(superNormalize).filter(Boolean);

        let refs = entList.filter(e => {
            const cn = cleanName(e.name || '');
            const en = cleanName(e.name_en || '');
            
            // 3b. English Name extraction from Description (Legacy)
             if (!en && e.description) {
                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                if (enMatch && enMatch[1]) {
                    const complexEn = enMatch[1];
                    const rawEn = complexEn.split(/(?:\s+role:|\s+archetype:|\s+appearance:|\n|,)/)[0]; 
                    // We don't redefine 'en' here as it's const, use local var if needed or just skip
                }
            }

            // Robust Check
            const isMatch = normalizedCandidates.some(n => n === cn || (en && n === en));
            if (isMatch) return true;
            
            // Supercheck
            const scn = superNormalize(e.name || '');
            const sen = superNormalize(e.name_en || '');
            const isSuperMatch = superCandidates.some(sn => sn === scn || (sen && sn === sen));
            
            return isSuperMatch;
        }).map(e => e.image_url).filter(Boolean);
        
        return [...new Set(refs)];
    }, [entities]);

    // Initialize Reference Images in technical_notes if empty
    // Also perform Entity Feature Injection (Auto-Expand) on load
    useEffect(() => {
        if (editingShot && entities.length > 0) {
            let updates = {};
            let hasUpdates = false;

            // 1. Ref Images Init
            try {
                const tech = JSON.parse(editingShot.technical_notes || '{}');
                if (tech.ref_image_urls === undefined) {
                    // Initialize strictly with Start Frame Prompt (camera_position)
                    const suggested = getSuggestedRefImages(editingShot, editingShot.start_frame);
                    if (suggested.length > 0) {
                        tech.ref_image_urls = suggested;
                        updates.technical_notes = JSON.stringify(tech);
                        hasUpdates = true;
                    }
                }
            } catch (e) { console.error("Error init ref images", e); }

            // 2. Feature Injection (Start Frame)
            const startPrompt = editingShot.start_frame || '';
            const { text: newStart, modified: modStart } = injectEntityFeatures(startPrompt);
            if (modStart) {
                updates.start_frame = newStart;
                hasUpdates = true;
            }

            // 3. Feature Injection (End Frame)
            const endPrompt = editingShot.end_frame || '';
            const { text: newEnd, modified: modEnd } = injectEntityFeatures(endPrompt);
            if (modEnd) {
                updates.end_frame = newEnd;
                hasUpdates = true;
            }

            // 4. Feature Injection (Video Prompt)
            const videoPrompt = editingShot.prompt || editingShot.video_content || '';
            const { text: newVideo, modified: modVideo } = injectEntityFeatures(videoPrompt);
            if (modVideo) {
                updates.prompt = newVideo;
                hasUpdates = true;
            }

            if (hasUpdates) {
                setEditingShot(prev => ({ ...prev, ...updates }));
            }
        }
    }, [editingShot?.id, entities]); // Only run when shot ID changes or entities load

    // Keyframe State Management
    const [localKeyframes, setLocalKeyframes] = useState([]);
    
    // Parse keyframes from shot text + technical_notes images
    useEffect(() => {
        if (!editingShot) return;

        const rawText = editingShot.keyframes || "";
        const tech = JSON.parse(editingShot.technical_notes || '{}');
        const legacyUrls = tech.keyframes || [];
        const mappedImages = tech.keyframe_images || {}; // Map: "1.5s": url

        let parsed = [];
        
        // 1. Parse Text Prompts
        if (rawText && rawText !== "NO" && rawText.length > 5) {
            // Regex to find [Time: XX] blocks
            // Assumption: keyframes are separated by [Time: ...]
            // Example: [Time: 1.5s] Desc... [Time: 2.0s] Desc...
            // Or newlines.
            const parts = rawText.split(/\[Time:\s*/i).filter(p => p.trim().length > 0);
            
            parts.forEach((p, idx) => {
                // p will be "1.5s] Description..."
                const closeBracket = p.indexOf(']');
                let time = `KF${idx+1}`;
                let prompt = p;
                
                if (closeBracket > -1) {
                    time = p.substring(0, closeBracket).trim();
                    prompt = p.substring(closeBracket+1).trim();
                } else {
                    // Fallback
                    prompt = "[Time: " + p; 
                }
                
                // Find image
                // Try map first
                let url = mappedImages[time];
                
                // Fallback to legacy array if index matches and no map entry
                if (!url && idx < legacyUrls.length) {
                    url = legacyUrls[idx];
                }

                parsed.push({ id: idx, time, prompt, url });
            });
        }
        
        // 2. Append extra legacy images that didn't match validation text
        if (legacyUrls.length > parsed.length) {
            for (let i = parsed.length; i < legacyUrls.length; i++) {
                parsed.push({ 
                    id: i, 
                    time: `Legacy ${i+1}`, 
                    prompt: "Legacy Keyframe (Image Only)", 
                    url: legacyUrls[i],
                    isLegacy: true
                });
            }
        }
        
        // If empty and not "NO", maybe init one? No, let user add.
        setLocalKeyframes(parsed);
        
    }, [editingShot?.id, editingShot?.keyframes, editingShot?.technical_notes]);

    const handleUpdateKeyframePrompt = (idx, newText) => {
        const updated = [...localKeyframes];
        updated[idx].prompt = newText;
        setLocalKeyframes(updated);
        // Debounced save or save on blur is better, but here we can just wait for a "Save" action or similar
        // Or reconstruct immediately. Reconstructing immediately is safer for consistency.
        reconstructKeyframes(updated);
    };
    
    const reconstructKeyframes = async (currentList, newTechOverride = null) => {
         // Rebuild shot.keyframes String
         // Format: [Time: time] prompt ...
         
         const textParts = currentList
            .filter(k => !k.isLegacy) // Legacy items don't go into text unless converted
            .map(k => `[Time: ${k.time}] ${k.prompt}`);
         
         const newKeyframesText = textParts.length > 0 ? textParts.join('\n') : "NO";
         
         // Rebuild Technical Notes
         const tech = JSON.parse(editingShot.technical_notes || '{}');
         
         // 1. Legacy Array (keep for safety, but sync with list)
         const urls = currentList.map(k => k.url).filter(Boolean);
         tech.keyframes = urls;
         
         // 2. Map (Preferred)
         const imgMap = {};
         currentList.forEach(k => {
             if (k.url) imgMap[k.time] = k.url;
         });
         tech.keyframe_images = imgMap;
         
         if (newTechOverride) {
             Object.assign(tech, newTechOverride);
         }
         
         // Update Local Logic (Optimistic)
         // We don't setLocalKeyframes here because that would trigger re-render loop if we are not careful
         // But we need to update 'editingShot' to trigger persistence
         
         const newData = {
             keyframes: newKeyframesText,
             technical_notes: JSON.stringify(tech)
         };
         
         // Update parent
         await onUpdateShot(editingShot.id, newData);
         // setEditingShot handled by onUpdateShot's internal state update wrapper if we used one, 
         // but local setEditingShot is raw.
         // onUpdateShot does: setShots ... and setEditingShot ...
         // So this will trigger useEffect parse again.
         // This might cause cursor jump in textarea. 
         // Strategy: Only update 'editingShot' if we are sure? 
         // Or rely on the fact that we are editing 'localKeyframes' state for text, and only syncing on Blur?
    };

    // Helper for Generating Keyframe
    const handleGenerateKeyframe = async (kfIndex) => {
        const kf = localKeyframes[kfIndex];
        if (!kf) return;
        
        // UI Loading State (Local)
        const updated = [...localKeyframes];
        updated[kfIndex].loading = true;
        setLocalKeyframes(updated); // Show spinner
        
        onLog?.(`Generating Keyframe for T=${kf.time}...`, 'info');
        
        try {
            // Prompt Construction
            const globalCtx = getGlobalContextStr();
            const fullPrompt = kf.prompt + globalCtx;
            
            // Generate
            const res = await generateImage(fullPrompt, null, null, {
                project_id: projectId,
                shot_id: editingShot.id,
                shot_number: `${editingShot.shot_id}_KF_${kf.time}`,
                asset_type: 'keyframe'
            });
            
            if (res && res.url) {
                updated[kfIndex].url = res.url;
                updated[kfIndex].loading = false;
                
                // Save
                setLocalKeyframes([...updated]); // Force re-render with image
                await reconstructKeyframes(updated);
                onLog?.(`Keyframe T=${kf.time} Generated.`, 'success');
            }
        } catch(e) {
            console.error(e);
            onLog?.(`Keyframe Gen Failed: ${e.message}`, 'error');
            updated[kfIndex].loading = false;
            setLocalKeyframes(updated);
        }
    };
    
    // --- Entity Injection Helper ---
    // Converts [Name] -> {Name}(Description) ...
    const injectEntityFeatures = (text) => {
        if (!text) return { text, modified: false };
        
        // In ShotsView, 'entities' contains ALL entities.
        const entList = entities;

        const regex = /[\[【](.*?)[\]】]/g;
        let newText = text;
        let modified = false;

        newText = newText.replace(regex, (match, name, offset, string) => {
            const cleanKey = name.trim().toLowerCase();

            // Check if followed by 's (possessive) -> Skip injection
            if (string.slice(offset + match.length).startsWith("'s")) {
                return match;
            }

            // 1. Global Style Injection
            if (cleanKey === 'global style' || cleanKey === 'global_style') {
                const style = activeEpisode?.episode_info?.e_global_info?.Global_Style;
                if (style) {
                    modified = true;
                    return `{Global Style}(${style})`;
                }
                return match; 
            }

            // 2. Entity Injection
            if (entList.length > 0) {
                const entity = entList.find(e => {
                    const cn = (e.name || '').toLowerCase();
                    const en = (e.name_en || '').toLowerCase();
                    
                    let fallbackEn = '';
                    if (!en && e.description) {
                        const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                        if (enMatch && enMatch[1]) fallbackEn = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
                    }
                    return (cn === cleanKey) || (en === cleanKey) || (fallbackEn === cleanKey);
                });

                if (entity) {
                    modified = true;
                    const anchor = entity.anchor_description || entity.description || '';
                    return `{${name}}(${anchor})`;
                }
            }

            return match; 
        });

        return { text: newText, modified };
    };

    // --- Generation Handlers ---
    const handleGenerateStartFrame = async () => {
        if (!editingShot) return;

        // Check for "SAME" logic - Inherit from previous End Frame
        const currentPrompt = (editingShot.start_frame || "").trim();
        if (currentPrompt === "SAME") {
            const currentIdx = shots.findIndex(s => s.id === editingShot.id);
            if (currentIdx > 0) {
                const prevShot = shots[currentIdx - 1];
                const prevTech = JSON.parse(prevShot.technical_notes || '{}');
                const prevEndUrl = prevTech.end_frame_url;

                if (prevEndUrl) {
                    try {
                        onLog?.('Inheriting Start Frame from previous shot...', 'info');
                        const newData = { image_url: prevEndUrl }; // Keep prompt as "SAME"
                        await onUpdateShot(editingShot.id, newData);
                        setEditingShot(prev => ({...prev, ...newData}));
                        onLog?.('Start Frame inherited successfully', 'success');
                        showNotification('Start Frame inherited from previous shot', 'success');
                        return; // Exit, do not generate
                    } catch (err) {
                        console.error("Error inheriting frame", err);
                        showNotification("Failed to inherit frame", "error");
                    }
                } else {
                    showNotification("Previous shot has no End Frame to inherit", "warning");
                    // Fallthrough to attempt generation? No, "SAME" is bad prompt.
                    return; 
                }
            } else {
                 showNotification("No previous shot to inherit from", "warning");
                 return;
            }
        }

        setGeneratingState(prev => ({ ...prev, start: true }));
        abortGenerationRef.current = false; 

        // 1. Feature Injection
        let prompt = editingShot.start_frame || editingShot.video_content || "A cinematic shot";
        
        // Apply injection logic
        const { text: injectedPrompt, modified } = injectEntityFeatures(prompt);
        if (modified) {
            // Update local State & use new prompt
            setEditingShot(prev => ({ ...prev, start_frame: injectedPrompt }));
            prompt = injectedPrompt; // Use for generation
        }

        onLog?.('Generating Start Frame...', 'info');
        
        let success = false;
        let attempts = 0;
        const maxAttempts = 3; // Reduced from 10

        while (!success && attempts < maxAttempts) {
             if (abortGenerationRef.current) {
                 onLog?.('Start Frame generation stopped by user.', 'warning');
                 break;
             }

             attempts++;
             if (attempts > 1) {
                 onLog?.(`Retrying Start Frame (Attempt ${attempts}/${maxAttempts})...`, 'warning');
                 showNotification(`Retrying Start Frame (Attempt ${attempts}/${maxAttempts})...`, 'info');
             }

             try {
                // Refs Logic for Start Frame (updated):
                // 1. If user has manually edited the Refs list (it exists in tech notes), respect it 100% (handling deletions/inactive).
                // 2. If list is undefined (never touched), auto-populate strictly from Subjects (latest entity images).
                // 3. Filter out any null/empty strings just in case.
                
                let refs = [];
                try {
                    const noteStr = editingShot.technical_notes || '{}';
                    const tech = JSON.parse(noteStr);
                    
                    // Always calculate auto-suggested refs first (with new robust logic)
                    const autoMatches = getSuggestedRefImages(editingShot, prompt, true);
                    console.log("Auto-Detected Matches:", autoMatches);

                    if (Array.isArray(tech.ref_image_urls)) {
                        // Manual Mode: Merge saved list with NEW auto-matches (respecting deletions)
                        const savedRefs = tech.ref_image_urls;
                        const deletedRefs = tech.deleted_ref_urls || [];
                        
                        const newAutoMatches = autoMatches.filter(url => 
                            !savedRefs.includes(url) && !deletedRefs.includes(url)
                        );
                        
                        refs = [...savedRefs, ...newAutoMatches];
                        console.log("Merged Manual Refs:", refs);
                    } else {
                        // Auto-populate mode
                        console.log("Auto-populating Refs for Start Generation...");
                        refs = autoMatches;
                        
                        try {
                            const currentIdx = shots.findIndex(s => s.id === editingShot.id);
                            if (currentIdx > 0) {
                                const prevShot = shots[currentIdx - 1];
                                const prevTech = JSON.parse(prevShot.technical_notes || '{}');
                                if (prevTech.end_frame_url && !refs.includes(prevTech.end_frame_url)) {
                                    refs.unshift(prevTech.end_frame_url);
                                    console.log("Inherited Prev End Frame:", prevTech.end_frame_url);
                                }
                            }
                        } catch(err) { console.error("Prev shot lookup failed", err); }
                        
                        // Deduplicate only in Auto Mode
                        refs = [...new Set(refs)];
                    }
                } catch(e) { console.error("Error determining refs:", e); }
                
                // Final clean
                refs = refs.filter(Boolean);
                console.log("Final Refs being sent to Generate:", refs);

                // NEW: Inject Global Context
                const globalCtx = getGlobalContextStr();
                const finalPrompt = prompt + globalCtx;

                const res = await generateImage(finalPrompt, null, refs.length > 0 ? refs : null, {
                    project_id: projectId,
                    shot_id: editingShot.id,
                    shot_number: editingShot.shot_id,
                    asset_type: 'start_frame',
                });
                if (res && res.url) {
                    // Save original prompt to DB (user view), but image was generated with context
                    const newData = { image_url: res.url, start_frame: prompt };
                    await onUpdateShot(editingShot.id, newData);
                    setEditingShot(prev => ({...prev, ...newData})); 
                    onLog?.('Start Frame Generated', 'success');
                    showNotification('Start Frame Generated', 'success');
                    success = true;
                } else {
                    throw new Error("No image URL returned");
                }
            } catch (e) {
                console.error(`Attempt ${attempts} failed:`, e);
                if (attempts >= maxAttempts) {
                    onLog?.(`Generation failed after ${maxAttempts} attempts: ${e.message}`, 'error');
                    showNotification(`Generation failed: ${e.message}`, 'error');
                }
            }
        }
        setGeneratingState(prev => ({ ...prev, start: false }));
    };

    const handleGenerateEndFrame = async () => {
        if (!editingShot) return;
        setGeneratingState(prev => ({ ...prev, end: true }));
        abortGenerationRef.current = false;

        // 1. Feature Injection for End Frame
        let prompt = editingShot.end_frame || "End frame";
        const { text: injectedPrompt, modified } = injectEntityFeatures(prompt);
        if (modified) {
            setEditingShot(prev => ({ ...prev, end_frame: injectedPrompt }));
            prompt = injectedPrompt;
        }

        onLog?.('Generating End Frame...', 'info');

        let success = false;
        let attempts = 0;
        const maxAttempts = 3; // Reduced from 10

        while (!success && attempts < maxAttempts) {
             if (abortGenerationRef.current) {
                 onLog?.('End Frame generation stopped by user.', 'warning');
                 break;
             }

             attempts++;
             if (attempts > 1) {
                 onLog?.(`Retrying End Frame (Attempt ${attempts}/${maxAttempts})...`, 'warning');
                 showNotification(`Retrying End Frame (Attempt ${attempts}/${maxAttempts})...`, 'info');
             }

             try {
                // Include Entity Refs + Manual Refs
                const tech = JSON.parse(editingShot.technical_notes || '{}');
                // Use End Refs specifically
                const refs = [];
                
                if (Array.isArray(tech.end_ref_image_urls)) {
                    refs.push(...tech.end_ref_image_urls);
                } else {
                    if (prompt.length > 5) {
                        const suggested = getSuggestedRefImages(editingShot, prompt, true);
                        refs.push(...suggested);
                    }
                }
                
                const deletedRefs = Array.isArray(tech.deleted_ref_urls) ? tech.deleted_ref_urls : [];
                const isDeleted = deletedRefs.includes(editingShot.image_url);
                
                if (editingShot.image_url && !refs.includes(editingShot.image_url) && !isDeleted) {
                    refs.unshift(editingShot.image_url);
                }
                
                const uniqueRefs = [...new Set(refs)].filter(Boolean);
                
                // NEW: Inject Global Context
                const globalCtx = getGlobalContextStr();
                const finalPrompt = prompt + globalCtx;

                const res = await generateImage(finalPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, {
                    project_id: projectId,
                    shot_id: editingShot.id,
                    shot_number: editingShot.shot_id,
                    asset_type: 'end_frame',
                });
                if (res && res.url) {
                    tech.end_frame_url = res.url;
                    tech.video_gen_mode = 'start_end'; // Auto-switch to Start+End
                    const newData = { technical_notes: JSON.stringify(tech), end_frame: prompt };
                    await onUpdateShot(editingShot.id, newData);
                    setEditingShot(prev => ({...prev, ...newData}));
                    onLog?.('End Frame Generated', 'success');
                    showNotification('End Frame Generated', 'success');
                    success = true;
                } else {
                     throw new Error("No image URL returned");
                }
            } catch (e) {
                console.error(`Attempt ${attempts} failed:`, e);
                if (attempts >= maxAttempts) {
                    onLog?.(`Generation failed after ${maxAttempts} attempts: ${e.message}`, 'error');
                    showNotification(`Generation failed: ${e.message}`, 'error');
                }
            }
        }
        setGeneratingState(prev => ({ ...prev, end: false }));
    };

    const handleGenerateVideo = async () => {
        if (!editingShot) return;
        if (generatingState.video) {
             console.log("Video generation already in progress used. Ignoring double click.");
             return; 
        }

        setGeneratingState(prev => ({ ...prev, video: true }));

        // 1. Feature Injection for Video Prompt
        let prompt = editingShot.prompt || editingShot.video_content || "Video motion";
        const { text: injectedPrompt, modified } = injectEntityFeatures(prompt);
        if (modified) {
            setEditingShot(prev => ({ ...prev, prompt: injectedPrompt }));
            prompt = injectedPrompt;
        }

        onLog?.('Generating Video...', 'info');
        try {
            const tech = JSON.parse(editingShot.technical_notes || '{}');
            const keyframes = tech.keyframes || [];
            
            const refs = [];
            // 1. Video Ref Selection Strategy
            // Shot-Specific Mode from technical_notes (default: start)
            // USER REQUEST: Default to 'start' only (Start Only) unless specified
            let shotMode = tech.video_gen_mode;
            
            // Logic: Default is Start+End IF End Frame URL exists.
            // NEW REQ: If end_frame prompt length < 3 -> Start Only
            if (!shotMode) {
                 const endPrompt = editingShot.end_frame || ""; // End Frame text
                 const endPromptLen = endPrompt.trim().length;
                 
                 if (tech.end_frame_url && endPromptLen >= 3) {
                     shotMode = 'start_end';
                 } else {
                     shotMode = 'start';
                 }
            }
            
            // Check if user has explicitly managed video refs
            if (tech.video_ref_image_urls && Array.isArray(tech.video_ref_image_urls)) {
                // Manual Mode: Use strictly what's in the list
                refs.push(...tech.video_ref_image_urls);
            } else {
                // Auto Mode respecting shotMode ('start_end' | 'start' | 'end')
                
                // A. Start Frame (Skip if 'end' mode)
                if (shotMode !== 'end' && editingShot.image_url) {
                    refs.push(editingShot.image_url);
                }
                
                // B. Keyframes
                if (keyframes && keyframes.length) refs.push(...keyframes);
                
                // C. End Frame as Ref (Only in Start+End mode)
                if (shotMode === 'start_end' && tech.end_frame_url) {
                    refs.push(tech.end_frame_url);
                }

                // D. Entity Refs from Video Prompt -> REMOVED per user request strictness
                // "Only take from Refs (Video)". The UI for Refs (Video) excludes entity prompts by default now.
                // const entityRefs = getSuggestedRefImages(editingShot, prompt, true);
                // refs.push(...entityRefs);
            }
            
            const uniqueRefs = [...new Set(refs)];
            
            // Last Frame Argument logic
            
            // Refined Strategy: "Final Video取首尾帧要从Refs (Video)按序获取，第一个和最后一个"
            
            let finalStartRef = null;
            let finalEndRef = null;
            
            if (uniqueRefs.length > 0) {
                 finalStartRef = uniqueRefs[0];
                 // Take the last item as End Frame if there is more than 1 item
                 if (uniqueRefs.length > 1) {
                     finalEndRef = uniqueRefs[uniqueRefs.length - 1];
                 }
            }
            
            console.log("[Editor] Video Generation Refs (Ordered):", uniqueRefs);
            console.log("[Editor] Selected Start:", finalStartRef);
            console.log("[Editor] Selected End:", finalEndRef);
            
            // Duration Logic: Use Shot Duration (s) if valid, else default to 5
            const durParam = parseFloat(editingShot.duration) || 5;

            // NEW: Inject Global Context
            const globalCtx = getGlobalContextStr();
            const finalPrompt = prompt + globalCtx;
            
            console.log("--------------------------------------------------");
            console.log("[DEBUG] Final Video Prompt (Single):", finalPrompt);
            console.log("--------------------------------------------------");

            const res = await generateVideo(finalPrompt, null, finalStartRef, finalEndRef, durParam, {
                project_id: projectId,
                shot_id: editingShot.id,
                shot_number: editingShot.shot_id,
                asset_type: 'video',
            }, keyframes);
            if (res && res.url) {
                const newData = { video_url: res.url, prompt: prompt };
                
                // 1. Force Local State Update IMMEDIATELY (Optimistic/Local)
                setEditingShot(prev => {
                   if (!prev) return null;
                   return { ...prev, ...newData };
                });
                
                onLog?.('Video Generated', 'success');
                showNotification('Video Generated', 'success');

                // 2. Update Server & Master List (Async persistence)
                try {
                    await onUpdateShot(editingShot.id, newData);
                } catch (updateErr) {
                    console.error("Failed to save shot update to backend:", updateErr);
                    // We don't block the UI - the video is here.
                }
            }
        } catch (e) {
             onLog?.(`Generation failed: ${e.message}`, 'error');
             showNotification(`Generation failed: ${e.message}`, 'error');
        } finally {
            setGeneratingState(prev => ({ ...prev, video: false }));
        }
    };

    const handleBatchGenerate = async () => {
        if (shots.length === 0) return;
        if (!confirm(`Generate missing Start/End frames for all ${shots.length} shots? This may take a while.`)) return;

        setIsBatchGenerating(true);
        setBatchProgress({ current: 0, total: shots.length, status: 'Starting...' });
        onLog?.("Starting Batch Generation...", "process");

        let generatedCount = 0;
        let processedCount = 0;

        // Iterate sequentially
        for (const shot of shots) {
             // Update progress UI
             processedCount++;
             const statusBase = `Processing Shot ${shot.shot_id}`;
             setBatchProgress({ current: processedCount, total: shots.length, status: statusBase });

             // 1. Check Start Frame
            if (!shot.image_url) {
                try {
                    setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: Start Frame...` });
                    let prompt = shot.start_frame || shot.video_content || "A cinematic shot";
                    const { text: injectedPrompt } = injectEntityFeatures(prompt);
                    
                    let refs = [];
                    try {
                        const noteStr = shot.technical_notes || '{}';
                        const tech = JSON.parse(noteStr);
                        if (Array.isArray(tech.ref_image_urls)) {
                            refs = [...tech.ref_image_urls];
                        } else {
                            refs = getSuggestedRefImages(shot, injectedPrompt, true);
                        }

                        // UNIVERSAL INJECTION: Previous Shot End Frame (Batch)
                        try {
                            const idx = shots.findIndex(s => s.id === shot.id);
                            if (idx > 0) {
                                const prevShot = shots[idx - 1];
                                const prevTech = JSON.parse(prevShot.technical_notes || '{}');
                                if (prevTech.end_frame_url && !refs.includes(prevTech.end_frame_url)) {
                                     refs.unshift(prevTech.end_frame_url);
                                }
                            }
                        } catch(e) {}
                    } catch(e) {}
                    refs = [...new Set(refs)].filter(Boolean);

                    onLog?.(`[Batch ${processedCount}/${shots.length}] Generating Start for Shot ${shot.shot_id}...`, "info");
                    
                    // NEW: Inject Global Context
                    const globalCtx = getGlobalContextStr();
                    const finalPrompt = injectedPrompt + globalCtx; 

                    const res = await generateImage(finalPrompt, null, refs.length > 0 ? refs : null, {
                        project_id: projectId,
                        shot_id: shot.id,
                        shot_number: shot.shot_id,
                        asset_type: 'start_frame'
                    });

                    if (res && res.url) {
                        const newData = { image_url: res.url, start_frame: injectedPrompt };
                        await onUpdateShot(shot.id, newData); // This triggers UI update
                        generatedCount++;
                    }
                } catch(e) {
                    console.error(`Batch Start Gen Error (Shot ${shot.id}):`, e);
                }
            }
            
            // 2. Check End Frame
            let tech = {};
            try { tech = JSON.parse(shot.technical_notes || '{}'); } catch(e){}
            
            if (!tech.end_frame_url) {
                 try {
                     let prompt = shot.end_frame || "End frame";
                     const { text: injectedPrompt } = injectEntityFeatures(prompt);
                     
                     let refs = [];
                     
                     // 1. Manual List
                     if (Array.isArray(tech.end_ref_image_urls)) {
                         refs.push(...tech.end_ref_image_urls);
                     } else {
                         // 2. Auto Entities
                         if (injectedPrompt.length > 5) {
                             const suggested = getSuggestedRefImages(shot, injectedPrompt, true);
                             refs.push(...suggested);
                         }
                     }
                     
                     // UNIVERSAL INJECTION: Start Frame (Batch)
                     if (shot.image_url && !refs.includes(shot.image_url)) {
                         refs.unshift(shot.image_url);
                     }
                     
                     const uniqueRefs = [...new Set(refs)].filter(Boolean);

                     onLog?.(`[Batch ${processedCount}/${shots.length}] Generating End for Shot ${shot.shot_id}...`, "info");
                     setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: End Frame...` });
                     const res = await generateImage(injectedPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, {
                        project_id: projectId,
                        shot_id: shot.id,
                        shot_number: shot.shot_id,
                        asset_type: 'end_frame'
                    });

                    if (res && res.url) {
                        tech.end_frame_url = res.url;
                        const newData = { technical_notes: JSON.stringify(tech), end_frame: injectedPrompt };
                        await onUpdateShot(shot.id, newData); // This triggers UI update
                        generatedCount++;
                    }
                 } catch(e) {
                      console.error(`Batch End Gen Error (Shot ${shot.id}):`, e);
                 }
            }
        }

        setIsBatchGenerating(false);
        setBatchProgress({ current: 0, total: 0, status: '' });
        onLog?.(`Batch Generation Complete. Generated ${generatedCount} new keyframes.`, "success");
        refreshShots();
    };

    const handleBatchGenerateVideo = async () => {
        if (shots.length === 0) return;
        if (!confirm(`Generate Videos for all ${shots.length} shots? This will AUTO-GENERATE any missing Start/End frames first.`)) return;

        setIsBatchGenerating(true);
        setBatchProgress({ current: 0, total: shots.length, status: 'Starting Video Batch...' });
        onLog?.("Starting Batch Video Generation...", "process");

        let generatedCount = 0;
        let processedCount = 0;

        for (const shot of shots) {
            processedCount++;
            const statusBase = `Shot ${shot.shot_id}`;
            
            // Optimization: If video exists, skip everything for this shot
            if (shot.video_url) {
                // Optional: Update progress or log if needed, but 'continue' is faster
                continue; 
            }

            setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: Checking...` });
            
            // We use a local updated copy to carry forward image urls generated in step 1/2 to step 3
            let currentShot = { ...shot }; 
            let shotTech = {};
            try { shotTech = JSON.parse(currentShot.technical_notes || '{}'); } catch(e){}
            const currentShotMode = shotTech.video_gen_mode || 'start'; // Default: Start Only

            try {
                // 1. Ensure Start Frame
                if (currentShotMode !== 'end' && !currentShot.image_url) {
                    try {
                        setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: Start Frame...` });
                        let prompt = currentShot.start_frame || currentShot.video_content || "A cinematic shot";
                        const { text: injectedPrompt } = injectEntityFeatures(prompt);
                        
                        let refs = [];
                        try {
                            const noteStr = currentShot.technical_notes || '{}';
                            const tech = JSON.parse(noteStr);
                            if (Array.isArray(tech.ref_image_urls)) {
                                refs = tech.ref_image_urls;
                            } else {
                                // Auto Logic used during Manual as well
                                refs = getSuggestedRefImages(currentShot, injectedPrompt, true);
                            }
                        } catch(e) {}
                        refs = [...new Set(refs)].filter(Boolean);

                        const res = await generateImage(injectedPrompt, null, refs.length > 0 ? refs : null, {
                            project_id: projectId,
                            shot_id: currentShot.id,
                            shot_number: currentShot.shot_id,
                            asset_type: 'start_frame'
                        });

                        if (res && res.url) {
                            const newData = { image_url: res.url, start_frame: injectedPrompt };
                            await onUpdateShot(currentShot.id, newData);
                            currentShot.image_url = res.url; // Update local for video step
                            onLog?.(`Generated Start Frame for Shot ${currentShot.shot_id}`, "success");
                        }
                    } catch(e) { console.error("Batch Start Gen Error", e); }
                }

                // 2. Ensure End Frame
                let tech = {};
                try { tech = JSON.parse(currentShot.technical_notes || '{}'); } catch(e){}
                
                // Determine Shot Mode (default start)
                const shotMode = tech.video_gen_mode || 'start';

                if (shotMode !== 'start' && !tech.end_frame_url) {
                    try {
                        setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: End Frame...` });
                        let prompt = currentShot.end_frame || "End frame";
                        const { text: injectedPrompt } = injectEntityFeatures(prompt);
                        
                        let refs = [];
                        if (Array.isArray(tech.end_ref_image_urls)) {
                            refs.push(...tech.end_ref_image_urls);
                        } else {
                            // Check Length Rule for Auto (Same as Manual)
                            if (prompt.length > 5) {
                                if (currentShot.image_url) refs.push(currentShot.image_url);
                                const suggested = getSuggestedRefImages(currentShot, injectedPrompt, true);
                                refs.push(...suggested);
                            }
                        }
                        const uniqueRefs = [...new Set(refs)].filter(Boolean);

                        const res = await generateImage(injectedPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, {
                            project_id: projectId,
                            shot_id: currentShot.id,
                            shot_number: currentShot.shot_id,
                            asset_type: 'end_frame'
                        });

                        if (res && res.url) {
                            tech.end_frame_url = res.url;
                            const newData = { technical_notes: JSON.stringify(tech), end_frame: injectedPrompt };
                            await onUpdateShot(currentShot.id, newData);
                            currentShot.technical_notes = JSON.stringify(tech); // Update local
                            onLog?.(`Generated End Frame for Shot ${currentShot.shot_id}`, "success");
                        }
                    } catch(e) { console.error("Batch End Gen Error", e); }
                }

                // 3. Generate Video
                if (!currentShot.video_url) {
                    try {
                        setBatchProgress({ current: processedCount, total: shots.length, status: `${statusBase}: Generating Video...` });
                        const prompt = currentShot.video_content || currentShot.video_content || currentShot.prompt || "Video motion";
                        const { text: injectedPrompt } = injectEntityFeatures(prompt);
                        
                        // Refs: Strategy based on shot specific mode
                        let refs = [];
                        let tech2 = {};
                        try { tech2 = JSON.parse(currentShot.technical_notes || '{}'); } catch(e){}
                        const shotMode2 = tech2.video_gen_mode || 'start'; // Default: Start Only

                        if (tech2.video_ref_image_urls && Array.isArray(tech2.video_ref_image_urls)) {
                             refs.push(...tech2.video_ref_image_urls);
                        } else {
                            // Auto Mode respecting shotMode
                            if (shotMode2 !== 'end' && currentShot.image_url) refs.push(currentShot.image_url);
                            if (tech2.keyframes && Array.isArray(tech2.keyframes)) refs.push(...tech2.keyframes);
                            if (shotMode2 === 'start_end' && tech2.end_frame_url) refs.push(tech2.end_frame_url);

                            // Retrieve entity keywords -> REMOVED strict logic
                            // refs.push(...getSuggestedRefImages(currentShot, injectedPrompt));
                        }

                        const uniqueRefs = [...new Set(refs)].filter(Boolean);
                        
                        let lastFrame = null;
                        if (shotMode2 === 'start_end' || shotMode2 === 'end') {
                            lastFrame = tech2.end_frame_url || null;
                        }

                        onLog?.(`[Batch ${processedCount}/${shots.length}] Generating Video for Shot ${currentShot.shot_id}...`, "info");
                        
                        const durParam = parseFloat(currentShot.duration) || 5;

                        console.log("--------------------------------------------------");
                        console.log(`[DEBUG] Final Video Prompt (Batch - Shot ${currentShot.shot_id}):`, injectedPrompt);
                        console.log("--------------------------------------------------");

                        const res = await generateVideo(injectedPrompt, null, uniqueRefs.length > 0 ? uniqueRefs : null, lastFrame, durParam, {
                            project_id: projectId,
                            shot_id: currentShot.id,
                            shot_number: currentShot.shot_id,
                            asset_type: 'video'
                        });

                        if (res && res.url) {
                            const newData = { video_url: res.url, prompt: injectedPrompt };
                            await onUpdateShot(currentShot.id, newData);
                            generatedCount++;
                            // No need to update currentShot.video_url unless we do something else later
                        }
                    } catch(e) {
                        onLog?.(`Batch Video Error (Shot ${currentShot.shot_id}): ${e.message}`, "error");
                    }
                }
            } catch(e) { console.error("Batch Loop Fatal Error", e); }
        }

        setIsBatchGenerating(false);
        setBatchProgress({ current: 0, total: 0, status: '' });
        onLog?.(`Batch Video Generation Complete. Generated ${generatedCount} videos.`, "success");
        refreshShots();
    };


    // Save to shot_content (similar to SceneManager)
    const handleSaveList = async () => {
        if (!activeEpisode) return;
        
        onLog?.('ShotsView: Saving content...', 'info');

        const contextInfo = `Project: ${project?.title || 'Unknown'} | Episode: ${activeEpisode?.title || 'Unknown'}\n`;
        const header = `| Shot No | Title | Start Frame | End Frame | Video Content | Duration | Associated Entities |\n|---|---|---|---|---|---|---|`;
        
        // Map current state to markdown table
        const content = shots.map(s => {
             const clean = (txt) => (txt || '').replace(/\n/g, '<br>').replace(/\|/g, '\\|');
             return `| ${clean(s.shot_id)} | ${clean(s.shot_name)} | ${clean(s.start_frame)} | ${clean(s.end_frame)} | ${clean(s.video_content || s.video_content)} | ${clean(s.duration)} | ${clean(s.associated_entities)} |`;
        }).join('\n');
        
        try {
            await updateEpisode(activeEpisode.id, { shot_content: contextInfo + header + '\n' + content });
            onLog?.(`Saved Shot List (${shots.length} items) to text content.`, 'success');
        } catch(e) {
            console.error(e);
            onLog?.('Failed to save shot list.', 'error');
        }
    };

    return (
        <div className="flex flex-col h-full w-full p-6 overflow-hidden">
             {/* Header / Toolbar */}
             <div className="flex justify-between items-center mb-6 shrink-0">
                <div className="flex items-center gap-4">
                    <h2 className="text-2xl font-bold flex items-center gap-2">
                        Shot Manager
                        <span className="text-sm font-normal text-muted-foreground ml-2">({shots.length})</span>
                    </h2>
                    {/* Add Save Button */}
                    <button 
                         onClick={handleSaveList}
                         className="px-3 py-1.5 bg-white/5 text-white hover:bg-white/10 rounded-lg text-sm font-medium flex items-center gap-2 border border-white/10"
                         title="Save current list to Shot Content (Text)"
                    >
                         <Save className="w-4 h-4" /> Save List
                    </button>
                    <div className="relative">
                         <select 
                            className="bg-black/40 border border-white/20 rounded px-3 py-1.5 text-sm min-w-[200px] text-white"
                            value={selectedSceneId || ''}
                            onChange={(e) => setSelectedSceneId(e.target.value)}
                         >
                            <option value="">Select a Scene...</option>
                            <option value="all">All Scenes</option>
                        {scenes.map(s => (
                                <option key={s.id} value={s.id}>{s.scene_no} - {s.scene_name || 'Untitled'}</option>
                            ))}
                         </select>
                         {selectedSceneId && selectedSceneId !== 'all' && (
                             <button
                                 onClick={() => handleGenerateShots(selectedSceneId)}
                                 className="ml-2 px-3 py-1.5 bg-primary/20 hover:bg-primary/30 text-primary border border-primary/20 rounded text-xs flex items-center gap-1"
                                 title="Generate Shots from AI Prompt"
                             >
                                 <Wand2 className="w-3 h-3"/> AI Shots
                             </button>
                         )}
                         <button 
                            onClick={() => handleSyncScenes()}
                            className="ml-2 px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded text-xs text-white border border-white/10"
                            title="Sync Scenes & Shots from Text Script"
                        >
                            <RefreshCw className="w-3 h-3"/>
                        </button>
                        <button 
                            onClick={handleDeleteAllShots}
                            className="ml-2 px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded text-xs border border-red-500/20"
                            title="Delete All Displayed Shots"
                        >
                            <Trash2 className="w-3 h-3"/>
                        </button>
                        <div className="relative inline-flex items-center ml-2 border border-white/20 rounded overflow-hidden">
                             <button 
                                onClick={handleBatchGenerate}
                                disabled={isBatchGenerating}
                                className={`px-3 py-1.5 text-xs flex items-center gap-1 transition-all border-r border-white/10 ${isBatchGenerating ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}`}
                                title="Batch Generate Missing Start/End Frames"
                            >
                                {isBatchGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                            </button>
                            <button 
                                onClick={handleBatchGenerateVideo}
                                disabled={isBatchGenerating}
                                className={`px-3 py-1.5 text-xs flex items-center gap-1 transition-all ${isBatchGenerating ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}`}
                                title="Batch Generate Videos (Auto-creates images first)"
                            >
                                {isBatchGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Film className="w-3 h-3"/>}
                            </button>
                        </div>

                        {/* Progress Indicator - Moved outside overflow-hidden container */}
                        {isBatchGenerating && batchProgress.total > 0 && (
                            <div className="absolute left-full top-0 ml-2 z-50 bg-black/80 px-3 py-2 rounded-md border border-primary/20 backdrop-blur-md shadow-xl min-w-[180px]">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-[10px] font-bold text-primary">Batch Processing</span>
                                    <span className="text-[10px] text-white font-mono">{Math.round((batchProgress.current / batchProgress.total) * 100)}%</span>
                                </div>
                                <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden mb-1.5">
                                    <div 
                                        className="h-full bg-primary transition-all duration-300 ease-out"
                                        style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}
                                    ></div>
                                </div>
                                {batchProgress.status && (
                                    <div className="text-[9px] text-muted-foreground truncate max-w-[160px]" title={batchProgress.status}>
                                        {batchProgress.status}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
                
                <div className="flex items-center gap-2">
                     {/* Settings Button Moved to Edit Shot View */}
                </div>
            </div>

             {/* Progress Bar for Batch */}
             <div className="px-4">
                 <div className={`transition-all duration-300 overflow-hidden ${isBatchGenerating ? 'h-6 mt-2' : 'h-0'}`}>
                    <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden mb-1.5">
                        <div 
                            className="h-full bg-primary transition-all duration-300 ease-out"
                            style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}
                        ></div>
                    </div>
                </div>
            </div>

            {/* Sub-header Actions */}
            <div className="px-4 pb-2 flex justify-end">
                {selectedSceneId && selectedSceneId !== 'all' && (
                    <button 
                        onClick={() => setIsImportOpen(true)}
                        className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center gap-2"
                    >
                        <Upload className="w-4 h-4"/> Import Shots
                    </button>
                )}
             </div>
             
             {/* Main Content */}
             <div className="flex-1 overflow-auto custom-scrollbar">
                 {selectedSceneId ? (
                     <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-6 pb-20">
                        {shots.map((shot, idx) => (
                            <div 
                                key={shot.id} 
                                className="bg-card/80 backdrop-blur-sm rounded-xl border border-white/10 overflow-hidden group hover:border-primary/50 transition-all cursor-pointer relative"
                                onClick={() => setEditingShot(shot)}
                            >
                                {/* Image / Thumbnail */}
                                <div className="aspect-video bg-black/60 flex items-center justify-center text-muted-foreground relative group-hover:bg-black/40 transition-colors overflow-hidden">
                                    {shot.video_url ? (
                                        <video 
                                            key={shot.video_url}
                                            src={getFullUrl(shot.video_url)} 
                                            className="w-full h-full object-cover" 
                                            muted 
                                            loop
                                            playsInline
                                            poster={getFullUrl(shot.image_url)}
                                            onMouseEnter={e => e.target.play().catch(() => {})}
                                            onMouseLeave={e => { e.target.pause(); e.target.currentTime = 0; }}
                                        />
                                    ) : shot.image_url ? (
                                        <img src={getFullUrl(shot.image_url)} alt={shot.shot_name} className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="flex flex-col items-center gap-2 opacity-50">
                                            <ImageIcon className="w-8 h-8" />
                                            <span className="text-xs">No Image</span>
                                        </div>
                                    )}
                                    <div className="absolute top-2 left-2 bg-black/60 px-2 py-1 rounded text-xs font-mono font-bold text-white border border-white/10 pointer-events-none">
                                        {shot.shot_id}
                                    </div>
                                    {shot.video_url && (
                                        <div className="absolute top-2 right-2 bg-black/60 p-1.5 rounded-full text-white border border-white/10 pointer-events-none">
                                            <Video className="w-3 h-3" />
                                        </div>
                                    )}
                                    <div className="absolute bottom-2 right-2 bg-primary text-black px-2 py-0.5 rounded text-[10px] font-bold pointer-events-none">
                                        {shot.duration || '0s'}
                                    </div>
                                </div>
                                
                                {/* Info - Simplified */}
                                <div className="p-3">
                                    <div className="flex justify-between items-center">
                                        <h3 className="font-bold text-sm text-white line-clamp-2" title={shot.shot_name}>
                                            <span className="text-primary mr-2 font-mono">{shot.shot_id}</span>
                                            {shot.shot_name || 'Untitled'}
                                        </h3>
                                        {/* Optional: Show duration if available, keep it minimal */}
                                        {shot.duration && (
                                            <span className="text-[10px] text-muted-foreground bg-white/5 px-1.5 py-0.5 rounded ml-2 whitespace-nowrap">
                                                {shot.duration}
                                            </span>
                                        )}
                                    </div>
                                    
                                    {/* Display Shot Logic (CN) Preview */}
                                    {shot.shot_logic_cn && (
                                        <div className="mt-2 text-xs text-muted-foreground bg-white/5 p-2 rounded line-clamp-3 overflow-hidden text-ellipsis">
                                            {shot.shot_logic_cn}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                        {shots.length === 0 && (
                            <div className="col-span-full h-64 flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-white/10 rounded-xl">
                                <Film className="w-12 h-12 mb-4 opacity-20" />
                                <p>No shots in this scene.</p>
                                <button className="text-primary text-sm hover:underline mt-2" onClick={() => setIsImportOpen(true)}>Import Shots Table</button>
                            </div>
                        )}
                     </div>
                 ) : (
                     <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                         <Clapperboard className="w-16 h-16 mb-4 opacity-20" />
                         <p className="text-lg font-medium">Select a Scene to manage shots</p>
                         <p className="text-sm opacity-50 max-w-md text-center mt-2">
                            Available scenes are loaded from the database. <br/>
                            If your list is empty, make sure you have created scenes in the "Scenes" tab.
                         </p>
                     </div>
                 )}
             </div>

             {/* Import Modal */}
             <ImportModal 
                isOpen={isImportOpen} 
                onClose={() => setIsImportOpen(false)} 
                onImport={handleImport}
                defaultType="shot" 
             />

             {/* Media Modals */}
             {viewMedia && <MediaDetailModal media={viewMedia} onClose={() => setViewMedia(null)} />}
             <MediaPickerModal 
                isOpen={pickerConfig.isOpen} 
                onClose={() => setPickerConfig({ ...pickerConfig, isOpen: false })} 
                onSelect={handleMediaSelect} 
                projectId={projectId}
                context={pickerConfig.context}
                entities={entities}
                episodeId={activeEpisode?.id}
            />

             {/* Edit Shot Drawer/Modal */}
             <AnimatePresence>
                {editingShot && (
                    <motion.div 
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        className="absolute top-0 right-0 w-full h-full bg-[#09090b] border-l border-white/10 z-50 overflow-y-auto shadow-2xl flex flex-col"
                    >
                        {/* Notification Toast for Edit Shot */}
                        {notification && (
                            <div className={`fixed top-4 left-1/2 transform -translate-x-1/2 z-[200] px-6 py-3 rounded-lg shadow-2xl border font-bold flex items-center gap-2 animate-in slide-in-from-top-4 fade-in duration-300 ${
                                notification.type === 'success' ? 'bg-green-500/90 text-white border-green-400' : 'bg-red-500/90 text-white border-red-400'
                            }`}>
                                {notification.type === 'success' ? <CheckCircle size={18} /> : <Info size={18} />}
                                {notification.message}
                            </div>
                        )}

                        <div className="p-4 border-b border-white/10 flex items-center justify-between sticky top-0 bg-[#09090b] z-10">
                            <h3 className="font-bold text-lg flex items-center gap-2">
                                Edit Shot {editingShot.shot_id}
                                {editingShot.shot_name && <span className="text-base font-normal text-muted-foreground">- {editingShot.shot_name}</span>}
                            </h3>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setIsSettingsOpen(true)}
                                    className="p-2 hover:bg-white/10 text-white rounded-lg border border-white/10 transition-colors"
                                    title="Open Generation Settings"
                                >
                                    <SettingsIcon className="w-5 h-5" />
                                </button>
                                <button onClick={() => setEditingShot(null)} className="p-2 hover:bg-white/10 rounded-full"><X className="w-5 h-5"/></button>
                            </div>
                        </div>
                        <div className="p-6 space-y-6">

                            <div>
                                <label className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">Shot Logic (CN)</label>
                                <textarea 
                                    className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs text-white/80 h-20 focus:outline-none focus:border-primary/50"
                                    value={editingShot.shot_logic_cn || ''}
                                    onChange={(e) => setEditingShot({...editingShot, shot_logic_cn: e.target.value})}
                                    placeholder="Shot logic description (Chinese)..."
                                />
                            </div>
                            
                            {/* 1. Workflow / Media Assets */}
                            <div className="space-y-6">
                                
                                {/* 3 Column Layout: Start | End | Video */}
                                <div className="grid grid-cols-3 gap-4">
                                    {/* Start Frame */}
                                    <div className="space-y-2">
                                        <div className="flex justify-between items-center">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                Start Frame
                                                <TranslateControl 
                                                    text={editingShot.start_frame || ''} 
                                                    onUpdate={(v) => setEditingShot({...editingShot, start_frame: v})} 
                                                />
                                            </div>
                                            <div className="flex gap-1">
                                                <button 
                                                    onClick={async () => {
                                                        openMediaPicker(async (url) => {
                                                            const newData = { image_url: url };
                                                            setEditingShot(prev => ({...prev, ...newData}));
                                                            // Auto-save user selection to ensure it counts as "latest selected"
                                                            await onUpdateShot(editingShot.id, newData);
                                                            onLog?.('Start Frame Image set', 'success');
                                                        }, { shotId: editingShot.id });
                                                    }}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded flex items-center gap-1"
                                                >
                                                    <ImageIcon className="w-3 h-3"/> Set
                                                </button>
                                                {generatingState.start ? (
                                                    <button 
                                                        onClick={() => abortGenerationRef.current = true}
                                                        className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30"
                                                        title="Stop Retry Loop"
                                                    >
                                                        <div className="w-2 h-2 bg-current rounded-[1px]" />
                                                        Stop
                                                    </button>
                                                ) : (
                                                    <button 
                                                        onClick={handleGenerateStartFrame} 
                                                        className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-primary/20 text-primary hover:bg-primary/30"
                                                    >
                                                        <Wand2 className="w-3 h-3"/>
                                                        Gen
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                        <div className="aspect-video bg-black/40 rounded border border-white/10 relative group overflow-hidden">
                                            {generatingState.start && (
                                                <div className="absolute inset-0 bg-black/60 z-10 flex items-center justify-center flex-col gap-2">
                                                    <Loader2 className="w-6 h-6 animate-spin text-primary"/>
                                                    <span className="text-[10px] text-white/70 animate-pulse">Generating Image...</span>
                                                </div>
                                            )}
                                            {editingShot.image_url ? (
                                                <>
                                                    <img 
                                                        src={getFullUrl(editingShot.image_url)} 
                                                        className="w-full h-full object-cover cursor-pointer hover:opacity-90 transition-opacity" 
                                                        onClick={() => setViewMedia({ url: editingShot.image_url, type: 'image', title: 'Start Frame', prompt: editingShot.start_frame })}
                                                        alt="Start Frame"
                                                    />
                                                    <button 
                                                        onClick={async (e) => {
                                                            e.stopPropagation();
                                                            if(!confirm("Delete Start Frame image?")) return;
                                                            const newData = { image_url: "" };
                                                            await onUpdateShot(editingShot.id, newData);
                                                            setEditingShot(prev => ({...prev, ...newData}));
                                                            onLog?.('Start Frame Image removed', 'info');
                                                        }}
                                                        className="absolute top-2 right-2 p-1.5 bg-black/60 hover:bg-red-500/80 text-white rounded-md opacity-0 group-hover:opacity-100 transition-all z-20"
                                                        title="Delete Start Frame"
                                                    >
                                                        <Trash2 className="w-3 h-3"/>
                                                    </button>
                                                </>
                                            ) : (
                                                <div className="absolute inset-0 flex items-center justify-center opacity-20"><ImageIcon className="w-8 h-8"/></div>
                                            )}
                                        </div>
                                        <textarea
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[60px]"
                                            placeholder="Start Frame Prompt..."
                                            value={editingShot.start_frame || ''} 
                                            onChange={(e) => setEditingShot({...editingShot, start_frame: e.target.value})}
                                        />
                                        <RefineControl 
                                            originalText={editingShot.start_frame || ''}
                                            onUpdate={(v) => setEditingShot({...editingShot, start_frame: v})}
                                            type="image"
                                            currentImage={editingShot.image_url}
                                            onImageUpdate={async (url) => {
                                                const newData = { image_url: url };
                                                await onUpdateShot(editingShot.id, newData);
                                                setEditingShot(prev => ({...prev, ...newData}));
                                            }}
                                            projectId={projectId}
                                            shotId={editingShot.id}
                                            assetType="start_frame"
                                            featureInjector={injectEntityFeatures}
                                            onPickMedia={openMediaPicker}
                                        />
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => setEditingShot({...editingShot, ...updates})} 
                                            title="Refs (Start)"
                                            promptText={editingShot.start_frame || ''}
                                            onPickMedia={openMediaPicker}
                                            storageKey="ref_image_urls"
                                            strictPromptOnly={true}
                                            additionalAutoRefs={(() => {
                                                // Find previous shot's End Frame (Automatic)
                                                // Kept for backward compatibility or auto-suggestion
                                                const idx = shots.findIndex(s => s.id === editingShot.id);
                                                if (idx > 0) {
                                                     try {
                                                         const prev = shots[idx-1];
                                                         const t = JSON.parse(prev.technical_notes || '{}');
                                                         return t.end_frame_url ? [t.end_frame_url] : [];
                                                     } catch(e) { return []; }
                                                }
                                                return [];
                                            })()}
                                            onFindPrevFrame={() => {
                                                // Logic to find PREVIOUS shot end frame
                                                const idx = shots.findIndex(s => s.id === editingShot.id);
                                                if (idx > 0) {
                                                    try {
                                                        const prev = shots[idx-1];
                                                        const t = JSON.parse(prev.technical_notes || '{}');
                                                        const url = t.end_frame_url || prev.video_url || prev.image_url;
                                                        if (url) {
                                                            onLog?.("Found previous shot frame: " + prev.shot_id, "success");
                                                            return url;
                                                        } else {
                                                            onLog?.("Previous shot has no media.", "warning");
                                                            return null;
                                                        }
                                                    } catch(e) { return null; }
                                                } else {
                                                    onLog?.("This is the first shot.", "info");
                                                    return null;
                                                }
                                            }}
                                        />
                                    </div>


                                    {/* End Frame */}
                                    <div className="space-y-2">
                                        <div className="flex justify-between items-center">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                End Frame
                                                <TranslateControl 
                                                    text={editingShot.end_frame || ''} 
                                                    onUpdate={(v) => setEditingShot({...editingShot, end_frame: v})} 
                                                />
                                            </div>
                                            <div className="flex gap-1">
                                                <button 
                                                    onClick={() => openMediaPicker((url) => {
                                                        const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                        tech.end_frame_url = url;
                                                        setEditingShot({...editingShot, technical_notes: JSON.stringify(tech)});
                                                    }, { shotId: editingShot.id })}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded flex items-center gap-1"
                                                >
                                                    <ImageIcon className="w-3 h-3"/> Set
                                                </button>
                                                {generatingState.end ? (
                                                    <button 
                                                        onClick={() => abortGenerationRef.current = true}
                                                        className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30"
                                                        title="Stop Retry Loop"
                                                    >
                                                        <div className="w-2 h-2 bg-current rounded-[1px]" />
                                                        Stop
                                                    </button>
                                                ) : (
                                                    <button 
                                                        onClick={handleGenerateEndFrame} 
                                                        className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-primary/20 text-primary hover:bg-primary/30"
                                                    >
                                                        <Wand2 className="w-3 h-3"/>
                                                        Gen
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                        <div className="aspect-video bg-black/40 rounded border border-white/10 relative group overflow-hidden">
                                            {generatingState.end && (
                                                <div className="absolute inset-0 bg-black/60 z-10 flex items-center justify-center flex-col gap-2">
                                                    <Loader2 className="w-6 h-6 animate-spin text-primary"/>
                                                    <span className="text-[10px] text-white/70 animate-pulse">Generating End Frame...</span>
                                                </div>
                                            )}
                                            {(() => {
                                                // Logic: If prompt words < 5, treat as empty -> show Start Frame
                                                const prompt = editingShot.end_frame || '';
                                                const wordCount = prompt.trim().split(/\s+/).filter(w => w.length > 0).length;
                                                const isSameAsStart = wordCount < 5;

                                                let endUrl = null;
                                                try { endUrl = JSON.parse(editingShot.technical_notes || '{}').end_frame_url; } catch(e){}

                                                if (isSameAsStart && editingShot.image_url) {
                                                     return (
                                                        <div className="relative w-full h-full group/mirror">
                                                            <img 
                                                                src={getFullUrl(editingShot.image_url)} 
                                                                className="w-full h-full object-cover opacity-60 group-hover/mirror:opacity-100 transition-opacity cursor-pointer"
                                                                title="Same as Start Frame (Prompt < 5 words)"
                                                                onClick={() => setViewMedia({ url: editingShot.image_url, type: 'image', title: 'Start Frame (Mirrored)', prompt: editingShot.start_frame })}
                                                            />
                                                            <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-30 group-hover/mirror:opacity-0 transition-opacity">
                                                                <span className="bg-black/50 text-white text-[9px] px-2 py-1 rounded">SAME AS START</span>
                                                            </div>
                                                        </div>
                                                     )
                                                }

                                                if (endUrl) {
                                                    return (
                                                        <>
                                                            <img 
                                                                src={getFullUrl(endUrl)} 
                                                                className="w-full h-full object-cover cursor-pointer hover:opacity-90 transition-opacity"
                                                                onClick={() => setViewMedia({ url: endUrl, type: 'image', title: 'End Frame', prompt: editingShot.end_frame })}
                                                            />
                                                            <button 
                                                                onClick={async (e) => {
                                                                    e.stopPropagation();
                                                                    if(!confirm("Delete End Frame image?")) return;
                                                                    const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                                    tech.end_frame_url = "";
                                                                    // We also track explicit deletion to avoid auto-regenerating from Start Frame immediately if user doesn't want it
                                                                    if (!tech.deleted_ref_urls) tech.deleted_ref_urls = [];
                                                                    tech.deleted_ref_urls.push(endUrl);
                                                                    
                                                                    const newData = { technical_notes: JSON.stringify(tech) };
                                                                    await onUpdateShot(editingShot.id, newData);
                                                                    setEditingShot(prev => ({...prev, ...newData}));
                                                                    onLog?.('End Frame Image removed', 'info');
                                                                }}
                                                                className="absolute top-2 right-2 p-1.5 bg-black/60 hover:bg-red-500/80 text-white rounded-md opacity-0 group-hover:opacity-100 transition-all z-20"
                                                                title="Delete End Frame"
                                                            >
                                                                <Trash2 className="w-3 h-3"/>
                                                            </button>
                                                        </>
                                                    );
                                                }

                                                return <div className="absolute inset-0 flex items-center justify-center opacity-20"><ImageIcon className="w-8 h-8"/></div>;
                                            })()}
                                        </div>
                                        
                                        <textarea
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[60px]"
                                            placeholder="End Frame Prompt..."
                                            value={editingShot.end_frame || ''} 
                                            onChange={(e) => setEditingShot({...editingShot, end_frame: e.target.value})}
                                        />
                                        <RefineControl 
                                            originalText={editingShot.end_frame || ''}
                                            onUpdate={(v) => setEditingShot({...editingShot, end_frame: v})}
                                            type="image"
                                            currentImage={(() => {
                                                try { return JSON.parse(editingShot.technical_notes || '{}').end_frame_url; } catch(e){ return null; }
                                            })()}
                                            onImageUpdate={async (url) => {
                                                const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                tech.end_frame_url = url;
                                                tech.video_gen_mode = 'start_end';
                                                const newData = { technical_notes: JSON.stringify(tech) };
                                                await onUpdateShot(editingShot.id, newData);
                                                setEditingShot(prev => ({...prev, ...newData}));
                                            }}
                                            projectId={projectId}
                                            shotId={editingShot.id}
                                            assetType="end_frame"
                                            featureInjector={injectEntityFeatures}
                                            onPickMedia={openMediaPicker}
                                        />
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => setEditingShot({...editingShot, ...updates})} 
                                            title="Refs (End)"
                                            promptText={editingShot.end_frame || ''}
                                            onPickMedia={openMediaPicker}
                                            storageKey="end_ref_image_urls"
                                            strictPromptOnly={true}
                                        />
                                    </div>

                                    {/* Final Video Output (Moved Here) */}
                                    <div className="space-y-2">
                                        <div className="flex justify-between items-center">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                Final Video
                                                <TranslateControl 
                                                    text={editingShot.prompt || editingShot.video_content || ''}
                                                    onUpdate={(v) => setEditingShot({...editingShot, prompt: v})}
                                                />
                                            </div>
                                            
                                            <div className="flex items-center gap-2">
                                                <button 
                                                    onClick={() => openMediaPicker((url) => {
                                                        const changes = { video_url: url };
                                                        onUpdateShot(editingShot.id, changes);
                                                    }, { type: 'video' })}
                                                    className="bg-white/10 hover:bg-white/20 text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors"
                                                    title="Select or Upload Video"
                                                >
                                                    <Upload size={10} /> Set
                                                </button>

                                                {/* Shot-specific Video Generation Mode */}
                                                <select
                                                    value={(() => {
                                                        try {
                                                            const t = JSON.parse(editingShot.technical_notes || '{}');
                                                            return t.video_gen_mode || 'start';
                                                        } catch(e) { return 'start'; }
                                                    })()}
                                                    onChange={(e) => {
                                                        const mode = e.target.value;
                                                        try {
                                                            const t = JSON.parse(editingShot.technical_notes || '{}');
                                                            t.video_gen_mode = mode;
                                                            setEditingShot(prev => ({ ...prev, technical_notes: JSON.stringify(t) }));
                                                            // Auto-save happens on blur or next action usually, but we might want to trigger update if needed
                                                            // onUpdateShot(editingShot.id, { technical_notes: JSON.stringify(t) }); // Optional: immediate save
                                                        } catch(e) {}
                                                    }}
                                                    className="bg-black/40 border border-white/20 text-[10px] rounded px-1 py-0.5 text-white/70 outline-none hover:bg-white/5"
                                                    title="Video Generation Reference Strategy"
                                                >
                                                    <option value="start_end">Start+End</option>
                                                    <option value="start">Start Only</option>
                                                    <option value="end">End Only</option>
                                                </select>

                                                <button 
                                                    onClick={handleGenerateVideo} 
                                                    disabled={generatingState.video}
                                                    className={`text-[10px] font-bold px-3 py-0.5 rounded flex items-center gap-1 ${generatingState.video ? 'bg-primary/50 text-black/50 cursor-wait' : 'bg-primary text-black hover:opacity-90' }`}
                                                >
                                                    {generatingState.video ? <Loader2 className="w-3 h-3 animate-spin"/> : <Film className="w-3 h-3"/>} 
                                                    {generatingState.video ? 'Generating...' : 'Generate'}
                                                </button>
                                            </div>
                                        </div>
                                        
                                        <div 
                                            className="aspect-video bg-black/40 rounded border border-white/10 relative group overflow-hidden cursor-pointer"
                                            onClick={() => editingShot.video_url && setViewMedia({ url: getFullUrl(editingShot.video_url), type: 'video', title: 'Final Video', prompt: editingShot.prompt })}
                                        >
                                            {generatingState.video && (
                                                <div className="absolute inset-0 bg-black/60 z-10 flex items-center justify-center flex-col gap-2">
                                                    <Loader2 className="w-6 h-6 animate-spin text-primary"/>
                                                    <span className="text-[10px] text-white/70 animate-pulse">Generating Video...</span>
                                                </div>
                                            )}
                                            {(editingShot.video_url) ? (
                                                <video 
                                                    key={editingShot.video_url}
                                                    src={getFullUrl(editingShot.video_url)} 
                                                    className="w-full h-full object-cover" 
                                                    onClick={(e) => e.preventDefault()} 
                                                    controls
                                                />
                                            ) : (
                                                <div className="absolute inset-0 flex items-center justify-center opacity-20 flex-col gap-2">
                                                    <Video className="w-10 h-10"/>
                                                    <span className="text-xs">No Video</span>
                                                </div>
                                            )}
                                             {(editingShot.video_url) && <div className="absolute inset-0 flex items-center justify-center pointer-events-none group-hover:bg-black/10"><Maximize2 className="text-white opacity-0 group-hover:opacity-100 drop-shadow-md"/></div>}
                                        </div>

                                        <textarea
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[60px]"
                                            placeholder="Action / Motion Prompt..."
                                            value={editingShot.prompt || editingShot.video_content || ''}
                                            onChange={(e) => setEditingShot({...editingShot, prompt: e.target.value})}
                                        />
                                        <RefineControl 
                                            originalText={editingShot.prompt || editingShot.video_content || ''}
                                            onUpdate={(v) => setEditingShot({...editingShot, prompt: v})}
                                            type="video"
                                        />
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => setEditingShot({...editingShot, ...updates})} 
                                            title="Refs (Video)"
                                            promptText={editingShot.prompt || editingShot.video_content || ''}
                                            onPickMedia={openMediaPicker}
                                            storageKey="video_ref_image_urls"
                                            strictPromptOnly={true}
                                        />
                                    </div>
                                </div>


                                {/* Keyframes Section (Enhanced) */}
                                <div className="space-y-4 border-t border-white/10 pt-4">
                                     <div className="flex justify-between items-center">
                                        <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                            Keyframes (Timeline)
                                            <span className="bg-white/10 text-white px-1.5 rounded-full text-[9px]">
                                                {localKeyframes.length}
                                            </span>
                                        </div>
                                        <button 
                                            onClick={() => {
                                                const newTime = `${(localKeyframes.length + 1) * 1.0}s`;
                                                const newKf = { 
                                                    id: Date.now(), 
                                                    time: newTime, 
                                                    prompt: "[Global Style] ...", 
                                                    url: "" 
                                                };
                                                const newList = [...localKeyframes, newKf];
                                                setLocalKeyframes(newList);
                                                // Trigger save logic? Maybe wait for edit?
                                                // auto-save structure
                                                // reconstructKeyframes(newList); // Optional, maybe let user edit first
                                            }}
                                            className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded flex items-center gap-1"
                                        >
                                            <Plus className="w-3 h-3"/> Add Keyframe
                                        </button>
                                    </div>
                                    
                                    <div className="flex gap-4 overflow-x-auto pb-4 min-h-[160px] snap-x">
                                        {localKeyframes.length === 0 && (
                                            <div className="text-xs text-muted-foreground italic p-2 w-full text-center border-dashed border border-white/10 rounded">
                                                No keyframes defined. Add one to start complex motion planning.
                                            </div>
                                        )}
                                        {localKeyframes.map((kf, idx) => (
                                            <div key={idx} className="relative w-[280px] flex-shrink-0 bg-black/20 rounded border border-white/10 p-2 space-y-2 snap-center group">
                                                {/* Header */}
                                                <div className="flex justify-between items-center text-[10px]">
                                                    <div className="flex items-center gap-1">
                                                        <span className="text-muted-foreground font-bold">T=</span>
                                                        <input 
                                                            className="bg-transparent border-b border-white/10 w-12 text-center focus:border-primary outline-none text-white"
                                                            value={kf.time}
                                                            onChange={(e) => {
                                                                const updated = [...localKeyframes];
                                                                updated[idx].time = e.target.value;
                                                                setLocalKeyframes(updated);
                                                            }}
                                                            onBlur={() => reconstructKeyframes(localKeyframes)}
                                                        />
                                                        <TranslateControl 
                                                            text={kf.prompt} 
                                                            onUpdate={(v) => {
                                                                const updated = [...localKeyframes];
                                                                updated[idx].prompt = v;
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            }} 
                                                        />
                                                    </div>
                                                    <div className="flex gap-1">
                                                        <button 
                                                            onClick={() => handleGenerateKeyframe(idx)} 
                                                            className="px-1.5 py-0.5 bg-primary/20 hover:bg-primary/30 text-primary rounded flex items-center gap-1"
                                                            disabled={kf.loading}
                                                        >
                                                            {kf.loading ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                                            Gen
                                                        </button>
                                                        <button 
                                                            onClick={() => {
                                                                const updated = [...localKeyframes];
                                                                updated.splice(idx, 1);
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            }}
                                                            className="p-1 hover:bg-red-500/20 text-muted-foreground hover:text-red-500 rounded transition-colors"
                                                        >
                                                            <Trash2 className="w-3 h-3"/>
                                                        </button>
                                                    </div>
                                                </div>

                                                {/* Image Area */}
                                                <div className="aspect-video bg-black/40 rounded border border-white/10 relative overflow-hidden group/image">
                                                    {kf.url ? (
                                                        <>
                                                            <img 
                                                                src={getFullUrl(kf.url)} 
                                                                className="w-full h-full object-cover cursor-pointer hover:opacity-90"
                                                                onClick={() => setViewMedia({ url: kf.url, type: 'image', title: `Keyframe T=${kf.time}`, prompt: kf.prompt })}
                                                            />
                                                            <button 
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    if(!confirm("Remove image?")) return;
                                                                    const updated = [...localKeyframes];
                                                                    updated[idx].url = "";
                                                                    setLocalKeyframes(updated);
                                                                    reconstructKeyframes(updated);
                                                                }}
                                                                className="absolute top-1 right-1 bg-black/60 text-white p-1 rounded opacity-0 group-hover/image:opacity-100 transition-opacity"
                                                            >
                                                                <Trash2 className="w-3 h-3"/>
                                                            </button>
                                                        </>
                                                    ) : (
                                                        <div className="absolute inset-0 flex items-center justify-center opacity-20">
                                                            <ImageIcon className="w-6 h-6"/>
                                                        </div>
                                                    )}
                                                    
                                                    {/* Quick Set Button Overlay */}
                                                    <div className="absolute bottom-1 right-1 opacity-0 group-hover/image:opacity-100 transition-opacity">
                                                        <button 
                                                            onClick={() => openMediaPicker((url) => {
                                                                const updated = [...localKeyframes];
                                                                updated[idx].url = url;
                                                                setLocalKeyframes(updated);
                                                                reconstructKeyframes(updated);
                                                            })}
                                                            className="bg-black/60 hover:bg-white/20 text-white text-[9px] px-1.5 py-0.5 rounded flex items-center gap-1 backdrop-blur-sm"
                                                        >
                                                            <Upload className="w-2.5 h-2.5"/> Set
                                                        </button>
                                                    </div>

                                                    {kf.loading && (
                                                        <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-10">
                                                            <Loader2 className="w-5 h-5 animate-spin text-primary"/>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Prompt Area */}
                                                <textarea 
                                                    className="w-full bg-black/20 border border-white/10 rounded p-1.5 text-[10px] h-[60px] focus:border-primary/50 outline-none resize-none"
                                                    placeholder="Keyframe Description..."
                                                    value={kf.prompt}
                                                    onChange={(e) => {
                                                        const updated = [...localKeyframes];
                                                        updated[idx].prompt = e.target.value;
                                                        setLocalKeyframes(updated);
                                                    }}
                                                    onBlur={() => reconstructKeyframes(localKeyframes)}
                                                />
                                                <RefineControl 
                                                    originalText={kf.prompt}
                                                    onUpdate={(v) => {
                                                        const updated = [...localKeyframes];
                                                        updated[idx].prompt = v;
                                                        setLocalKeyframes(updated);
                                                        reconstructKeyframes(updated);
                                                    }}
                                                    type="image"
                                                    currentImage={kf.url}
                                                    onImageUpdate={(url) => {
                                                        const updated = [...localKeyframes];
                                                        updated[idx].url = url;
                                                        setLocalKeyframes(updated);
                                                        reconstructKeyframes(updated);
                                                    }}
                                                    projectId={projectId}
                                                    shotId={editingShot.id}
                                                    assetType={`keyframe_${idx}`} // fallback to index
                                                    featureInjector={injectEntityFeatures}
                                                    onPickMedia={openMediaPicker}
                                                />
                                            </div>
                                        ))}
                                    </div>
                                </div>


                                {/* Video Result - REMOVED from here, moved up */}
                            </div>


                            {/* 3. Associated Entities */}
                            <div className="space-y-3 pt-4 border-t border-white/10">
                                <h4 className="text-sm font-bold text-primary flex items-center gap-2"><Users className="w-4 h-4"/> Associated Entities</h4>
                                <div className="bg-black/20 border border-white/10 rounded-xl p-4 flex gap-4 overflow-x-auto min-h-[100px] items-center">
                                    {(() => {
                                        const cleanName = (s) => s.replace(/[\[\]【】"''“”‘’]/g, '').trim().toLowerCase();
                                        const rawNames = (editingShot.associated_entities || '').split(/[,，]/);
                                        const names = rawNames.map(cleanName).filter(Boolean);
                                        
                                        // Match entity names (English or Chinese)
                                        const matches = entities.filter(e => names.some(n => {
                                            const cn = (e.name || '').toLowerCase();
                                            let en = (e.name_en || '').toLowerCase();

                                            // Fallback: Try to extract English name from description if name_en is empty
                                            if (!en && e.description) {
                                                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                                                if (enMatch && enMatch[1]) {
                                                    const complexEn = enMatch[1].trim().toLowerCase();
                                                    en = complexEn.split(/(?:\s+role:|\s+archetype:|\s+appearance:|\n|,)/)[0].trim(); 
                                                }
                                            }

                                            // Exact match check first for better precision
                                            if (cn === n || en === n) return true;
                                            
                                            // Check CN name match (both directions)
                                            if (cn && (cn.includes(n) || n.includes(cn))) return true;
                                            // Check EN name match (both directions)
                                            if (en && (en.includes(n) || n.includes(en))) return true;
                                            return false;
                                        }));

                                        // New Feature: Scene Environment Matching
                                        // Attempt to find current scene environment/location and add to matches if not already there
                                        let envMatches = [];
                                        if (selectedSceneId && selectedSceneId !== 'all') {
                                            // Find current scene from user selection
                                            const currentScene = scenes.find(s => s.id == selectedSceneId);
                                            if (currentScene) {
                                                // Extract location from scene (e.g., "[废弃展区内部 (主视角)]")
                                                // Clean brackets like [ ]
                                                const rawLoc = (currentScene.location || currentScene.environment_name || '').replace(/[\[\]]/g, '').trim().toLowerCase();
                                                
                                                if (rawLoc) {
                                                    // console.log("Matching Env:", rawLoc);
                                                    const envs = entities.filter(e => {
                                                        // Filter for Environment type entities primarily, but allow others
                                                        // if (e.type !== 'environment') return false; 
                                                        
                                                        const cn = (e.name || '').toLowerCase();
                                                        let en = (e.name_en || '').toLowerCase();
                                                        // Fallback EN extract
                                                        if (!en && e.description) {
                                                            const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                                                            if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
                                                        }

                                                        // Use looser matching for descriptions/anchors
                                                        // Is the Location string contained in Entity Name? or vice versa?
                                                        if (cn && (cn.includes(rawLoc) || rawLoc.includes(cn))) return true;
                                                        if (en && (en.includes(rawLoc) || rawLoc.includes(en))) return true;
                                                        
                                                        return false;
                                                    });
                                                    // console.log("Found Envs:", envs);
                                                    envMatches = envs.filter(env => !matches.find(m => m.id === env.id)); // Dedup
                                                }
                                            }
                                        }

                                        const allMatches = [...matches, ...envMatches];
                                        
                                        if (allMatches.length === 0) return (
                                            <div className="text-xs text-muted-foreground w-full text-center break-words p-2">
                                                No entities matched tags: "{names.join(', ')}". 
                                                <br/>
                                                <span className="opacity-50 text-[10px] block mt-1">
                                                    Available({entities.length}): {entities.map(e => `${e.name}${e.name_en ? `/${e.name_en}` : ''}`).slice(0, 15).join(', ')}
                                                </span>
                                            </div>
                                        );
                                        
                                        return allMatches.map((e, idx) => (
                                            <div key={e.id} className="flex flex-col items-center gap-2 min-w-[70px]">
                                                <div className="w-14 h-14 rounded-full overflow-hidden border border-white/20 bg-black/50 relative">
                                                    {e.image_url ? <img src={getFullUrl(e.image_url)} className="w-full h-full object-cover" /> : <Users className="w-6 h-6 m-auto absolute inset-0 text-muted-foreground opacity-50"/>}
                                                </div>
                                                <span className="text-[10px] text-center line-clamp-1 w-full opacity-80">{e.name}</span>
                                            </div>
                                        ));
                                    })()}
                                </div>
                                {/* Association Tags Input Removed as requested */}
                            </div>

                            {/* Metadata */}
                            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/10 text-xs text-muted-foreground">
                                <InputGroup label="Shot Number" value={editingShot.shot_id} onChange={(v) => { setEditingShot({...editingShot, shot_id: v}) }} />
                                <InputGroup label="Duration (s)" value={editingShot.duration} onChange={v => setEditingShot({...editingShot, duration: v})} />
                            </div>

                            <button 
                                onClick={async () => {
                                    try {
                                        await updateShot(editingShot.id, editingShot);
                                        setShots(shots.map(s => s.id === editingShot.id ? editingShot : s));
                                        setEditingShot(null);
                                        onLog?.("Shot updated.", "success");
                                    } catch(e) {
                                        onLog?.("Update failed.", "error");
                                    }
                                }}
                                className="w-full py-4 bg-primary text-black font-bold rounded-lg hover:bg-primary/90 mt-4"
                            >
                                Save Changes
                            </button>
                        </div>
                    </motion.div>
                )}
             </AnimatePresence>

             {shotPromptModal.open && (
                <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
                    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">
                        <div className="p-4 border-b border-white/10 flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2"><Wand2 size={16} className="text-primary"/> Generate AI Shots</h3>
                            <button onClick={() => setShotPromptModal({open: false, sceneId: null, data: null, loading: false})}><X size={18}/></button>
                        </div>
                        
                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                            {shotPromptModal.loading && !shotPromptModal.data ? (
                                <div className="flex items-center justify-center h-40"><Loader2 className="animate-spin text-primary" size={32}/></div>
                            ) : (
                                <>
                                    <div className="bg-blue-500/10 border border-blue-500/20 rounded p-3 text-xs text-blue-200 flex items-start gap-2">
                                        <Info size={14} className="shrink-0 mt-0.5" />
                                        Review and edit the prompt before generation. Only the User Prompt (scenario context) is typically edited.
                                    </div>

                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-bold text-muted-foreground uppercase">User Prompt (Scenario content)</label>
                                        <textarea 
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-sm text-white/90 font-mono h-64 focus:outline-none focus:border-primary/50 resize-y"
                                            value={shotPromptModal.data?.user_prompt || ''}
                                            onChange={e => setShotPromptModal(prev => ({...prev, data: {...prev.data, user_prompt: e.target.value}}))}
                                        />
                                    </div>
                                    
                                     <div className="flex flex-col gap-2">
                                         <div className="flex items-center justify-between">
                                              <label className="text-xs font-bold text-muted-foreground uppercase">System Prompt (Instructions)</label>
                                              <span className="text-xs text-muted-foreground px-2 py-1 bg-white/5 rounded">Default/Template</span>
                                         </div>
                                        <textarea 
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-xs text-muted-foreground font-mono h-32 focus:outline-none focus:border-primary/50 resize-y"
                                            value={shotPromptModal.data?.system_prompt || ''}
                                            onChange={e => setShotPromptModal(prev => ({...prev, data: {...prev.data, system_prompt: e.target.value}}))}
                                        />
                                    </div>
                                </>
                            )}
                        </div>
                        
                        <div className="p-4 border-t border-white/10 flex justify-end gap-3 bg-black/20">
                            <button 
                                onClick={() => {
                                    const full = (shotPromptModal.data?.system_prompt || '') + "\n\n" + (shotPromptModal.data?.user_prompt || '');
                                    navigator.clipboard.writeText(full);
                                    onLog?.("Full prompt copied to clipboard", "success");
                                }}
                                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded text-sm font-medium flex items-center gap-2 mr-auto"
                            >
                                <Copy size={16}/> Copy Full Prompt
                            </button>
                            <button 
                                onClick={() => setShotPromptModal({open: false, sceneId: null, data: null, loading: false})}
                                className="px-4 py-2 rounded hover:bg-white/10 text-sm"
                            >
                                Cancel
                            </button>
                            <button 
                                onClick={handleConfirmGenerateShots}
                                disabled={shotPromptModal.loading}
                                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium flex items-center gap-2"
                            >
                                {shotPromptModal.loading ? <Loader2 className="animate-spin" size={16}/> : <Wand2 size={16}/>}
                                {shotPromptModal.loading ? "Generating..." : "Generate Shots"}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {isSettingsOpen && (
                 <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-8">
                     <div className="bg-[#09090b] w-full max-w-6xl h-[90vh] rounded-2xl border border-white/10 shadow-2xl flex flex-col relative overflow-hidden">
                          <button 
                             onClick={() => setIsSettingsOpen(false)}
                             className="absolute top-4 right-4 z-50 p-2 bg-black/60 rounded-full hover:bg-white/10 text-white border border-white/10"
                             title="Close Settings"
                         >
                             <X size={20}/>
                         </button>
                         <div className="flex-1 overflow-auto custom-scrollbar">
                             <SettingsPage />
                         </div>
                     </div>
                 </div>
             )}
        </div>
    );
};

const AssetsLibrary = () => {
    const [assets, setAssets] = useState([]);
    const [selectedAsset, setSelectedAsset] = useState(null);

    const handleFileUpload = (e) => {
        const files = Array.from(e.target.files);
        files.forEach(file => {
            const reader = new FileReader();
            reader.onload = (ev) => {
                const type = file.type.startsWith('image') ? 'image' : 'video';
                const newAsset = {
                    id: Date.now() + Math.random(),
                    name: file.name,
                    type,
                    url: ev.target.result,
                    size: (file.size / 1024 / 1024).toFixed(2) + ' MB',
                    dimensions: 'Computing...',
                    createdAt: new Date().toLocaleString(),
                    notes: ''
                };

                if (type === 'image') {
                    const img = new Image();
                    img.onload = () => {
                        newAsset.dimensions = `${img.width} x ${img.height}`;
                        setAssets(prev => [newAsset, ...prev]);
                    };
                    img.src = ev.target.result;
                } else {
                    setAssets(prev => [newAsset, ...prev]);
                }
            };
            reader.readAsDataURL(file);
        });
    };

    const handleUpdateNote = (id, note) => {
        setAssets(prev => prev.map(a => a.id === id ? { ...a, notes: note } : a));
        if (selectedAsset && selectedAsset.id === id) {
            setSelectedAsset(prev => ({ ...prev, notes: note }));
        }
    };

    return (
        <div className="p-8 h-full flex flex-col w-full relative">
            <div className="flex justify-between items-center mb-6 shrink-0">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                    Assets Library
                    <span className="text-sm font-normal text-muted-foreground bg-white/5 px-2 py-0.5 rounded-full">{assets.length} Items</span>
                </h2>
                <div className="relative">
                    <input 
                        type="file" 
                        multiple 
                        accept="image/*,video/*" 
                        onChange={handleFileUpload} 
                        className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                    />
                    <button className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center gap-2">
                        <Upload className="w-4 h-4" /> Upload Assets
                    </button>
                </div>
            </div>

            {assets.length === 0 ? (
                <div className="flex-1 border border-dashed border-white/10 rounded-xl flex flex-col items-center justify-center text-muted-foreground bg-black/20">
                    <FolderOpen className="w-16 h-16 mb-4 opacity-20" />
                    <p>No assets in library.</p>
                    <p className="text-xs mt-2 opacity-50">Upload images or videos to manage your project assets.</p>
                </div>
            ) : (
                <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-6 w-full overflow-y-auto pb-20">
                    {assets.map(asset => (
                        <div 
                            key={asset.id} 
                            className="group relative aspect-square bg-card border border-white/10 rounded-xl overflow-hidden cursor-pointer hover:border-primary/50 transition-all"
                            onClick={() => setSelectedAsset(asset)}
                        >
                            {asset.type === 'image' ? (
                                <img src={getFullUrl(asset.url)} alt={asset.name} className="w-full h-full object-cover" />
                            ) : (
                                <div className="w-full h-full flex items-center justify-center bg-black/50">
                                    <Video className="w-12 h-12 text-white/50" />
                                </div>
                            )}
                            <div className="absolute inset-0 bg-gradient-to-t from-black/90 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-3">
                                <div className="text-xs font-bold text-white truncate">{asset.name}</div>
                                <div className="text-[10px] text-gray-400 flex justify-between mt-1">
                                    <span>{asset.type.toUpperCase()}</span>
                                    <span>{asset.size}</span>
                                </div>
                            </div>
                            <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <Maximize2 className="w-4 h-4 text-white drop-shadow-md" />
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Asset Detail Modal */}
            <AnimatePresence>
                {selectedAsset && (
                    <motion.div 
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-center justify-center p-8 bg-black/90 backdrop-blur-md"
                        onClick={() => setSelectedAsset(null)}
                    >
                        <motion.div 
                            initial={{ scale: 0.95, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.95, opacity: 0 }}
                            className="bg-[#09090b] border border-white/10 rounded-xl w-full max-w-6xl h-[80vh] flex overflow-hidden shadow-2xl"
                            onClick={e => e.stopPropagation()}
                        >
                            {/* Left: Preview */}
                            <div className="flex-[2] bg-black flex items-center justify-center relative border-r border-white/10 p-4">
                                {selectedAsset.type === 'image' ? (
                                    <img src={getFullUrl(selectedAsset.url)} alt={selectedAsset.name} className="max-w-full max-h-full object-contain" />
                                ) : (
                                    <video src={getFullUrl(selectedAsset.url)} controls className="max-w-full max-h-full" />
                                )}
                            </div>

                            {/* Right: Info */}
                            <div className="flex-1 flex flex-col bg-card/50">
                                <div className="p-6 border-b border-white/10 flex justify-between items-start">
                                    <div>
                                        <h3 className="text-lg font-bold text-white break-all">{selectedAsset.name}</h3>
                                        <div className="flex items-center gap-2 mt-2">
                                            <span className="px-2 py-0.5 rounded bg-white/10 text-[10px] font-bold text-muted-foreground uppercase">{selectedAsset.type}</span>
                                            <span className="text-xs text-muted-foreground">{selectedAsset.createdAt}</span>
                                        </div>
                                    </div>
                                    <button onClick={() => setSelectedAsset(null)} className="p-1 hover:bg-white/10 rounded text-muted-foreground hover:text-white">
                                        <X className="w-5 h-5" />
                                    </button>
                                </div>
                                
                                <div className="p-6 space-y-6 flex-1 overflow-y-auto">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="bg-white/5 p-3 rounded-lg border border-white/5">
                                            <div className="text-[10px] uppercase text-muted-foreground font-bold mb-1">Dimensions</div>
                                            <div className="text-sm font-mono text-white">{selectedAsset.dimensions}</div>
                                        </div>
                                        <div className="bg-white/5 p-3 rounded-lg border border-white/5">
                                            <div className="text-[10px] uppercase text-muted-foreground font-bold mb-1">File Size</div>
                                            <div className="text-sm font-mono text-white">{selectedAsset.size}</div>
                                        </div>
                                    </div>

                                    <div className="flex-1 flex flex-col">
                                        <label className="text-xs uppercase text-muted-foreground font-bold mb-2 flex items-center gap-2">
                                            <Edit3 className="w-3 h-3" /> Notes & Tags
                                        </label>
                                        <textarea 
                                            className="flex-1 min-h-[200px] w-full bg-black/20 border border-white/10 rounded-lg p-4 text-sm text-white focus:border-primary/50 focus:outline-none resize-none leading-relaxed"
                                            placeholder="Add descriptions, tags, or usage notes for this asset..."
                                            value={selectedAsset.notes}
                                            onChange={(e) => handleUpdateNote(selectedAsset.id, e.target.value)}
                                        />
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

const ImportModal = ({ isOpen, onClose, onImport, defaultType = 'auto', project }) => {
    const [text, setText] = useState('');
    const [importType, setImportType] = useState(defaultType); // auto, json, script, scene, shot
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    
    // Reset type when modal opens
    useEffect(() => {
        if (isOpen) setImportType(defaultType);
    }, [isOpen, defaultType]);

    if (!isOpen) return null;
    
    const handleImportClick = () => {
        onImport(text, importType);
    };

    const handleAIAnalysis = async () => {
        if (!text.trim()) return;
        setIsAnalyzing(true);
        try {
            const token = localStorage.getItem('token');
            const body = { 
                text: text,
                prompt_file: "scene_analysis.txt"
            };
            if (project?.global_info) {
                body.project_metadata = project.global_info;
            }

            const res = await fetch(`${API_BASE_URL}/analyze_scene`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(body)
            });
            
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Analysis Failed");
            }
            
            const data = await res.json();
            setText(data.result); // Replace content with analysis result
            alert("AI Analysis Complete! Review the generated markdown below.");
        } catch (e) {
            alert(`Analysis Error: ${e.message}`);
            console.error(e);
        } finally {
            setIsAnalyzing(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm">
            <div className="bg-[#09090b] border border-white/20 rounded-xl p-6 w-[800px] shadow-2xl flex flex-col max-h-[90vh]">
                <div className="flex justify-between items-center mb-4 shrink-0">
                     <h3 className="font-bold text-white flex items-center gap-2"><Upload className="w-5 h-5 text-primary"/> Import & AI Analysis</h3>
                     <button onClick={onClose}><X className="w-5 h-5 text-muted-foreground hover:text-white"/></button>
                </div>
                
                {/* Type Selection */}
                <div className="flex gap-4 mb-4 text-xs font-semibold text-gray-400 shrink-0">
                    <label className="flex items-center gap-1 cursor-pointer">
                        <input type="radio" name="itype" value="auto" checked={importType === 'auto'} onChange={e => setImportType(e.target.value)} />
                        Auto-Detect (Legacy)
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer">
                        <input type="radio" name="itype" value="json" checked={importType === 'json'} onChange={e => setImportType(e.target.value)} />
                        JSON (Project/Settings)
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer">
                        <input type="radio" name="itype" value="script" checked={importType === 'script'} onChange={e => setImportType(e.target.value)} />
                        Script Table
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer text-white">
                        <input type="radio" name="itype" value="scene" checked={importType === 'scene'} onChange={e => setImportType(e.target.value)} />
                        Scenes Only
                    </label>
                    <label className="flex items-center gap-1 cursor-pointer text-white">
                        <input type="radio" name="itype" value="shot" checked={importType === 'shot'} onChange={e => setImportType(e.target.value)} />
                        Shots Only
                    </label>
                </div>

                <div className="text-xs text-gray-400 mb-2 shrink-0">
                   Paste raw script text for AI Analysis, or paste formatted JSON/Table for Import.
                </div>
                <textarea 
                    className="flex-1 bg-black/40 border border-white/10 rounded-lg p-4 text-xs text-white font-mono focus:border-primary/60 outline-none resize-none mb-4 custom-scrollbar"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder={`Paste script or data here...`}
                />
                <div className="flex justify-between gap-2 shrink-0">
                    <button 
                        onClick={handleAIAnalysis}
                        disabled={!text.trim() || isAnalyzing}
                        className={`px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 border border-purple-500/30 text-purple-200 hover:bg-purple-500/20 transition-all ${isAnalyzing ? 'opacity-50' : ''}`}
                    >
                        <Sparkles className={`w-3 h-3 ${isAnalyzing ? 'animate-spin' : ''}`} />
                        {isAnalyzing ? "Analyzing Scene..." : "AI Scene Analysis"}
                    </button>
                    
                    <div className="flex gap-2">
                        <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-muted-foreground hover:bg-white/5">Cancel</button>
                        <button 
                            onClick={handleImportClick} 
                            disabled={!text.trim()}
                            className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 disabled:opacity-50"
                        >
                            Import Data
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )

};

const TranslateControl = ({ text, onUpdate, onSave }) => {
    const { addLog } = useLog();
    const [isTranslated, setIsTranslated] = useState(false);
    const [loading, setLoading] = useState(false);
    const [originalText, setOriginalText] = useState('');

    const handleTranslate = async (e) => {
        e.stopPropagation();
        e.preventDefault();
        
        const textToTranslate = text || '';
        if (!textToTranslate && !isTranslated) {
             addLog("No text to translate", 'warning');
             return;
        }

        setLoading(true);
        try {
            if (!isTranslated) {
                // EN -> ZH
                setOriginalText(textToTranslate);
                const res = await translateText(textToTranslate, 'en', 'zh');
                if (res.translated_text) {
                    onUpdate(res.translated_text);
                    setIsTranslated(true);
                    addLog("Translated to Chinese", 'info');
                } else {
                    throw new Error("No translation returned");
                }
            } else {
                // ZH -> EN (Save)
                const res = await translateText(textToTranslate, 'zh', 'en');
                if (res.translated_text) {
                    onUpdate(res.translated_text);
                    if (onSave) onSave(res.translated_text);
                    setIsTranslated(false);
                    addLog("Translated back and saved", 'success');
                } else {
                    // Try to handle case where empty string was desired?
                    // But here textToTranslate is passed.
                    if (textToTranslate.trim() === '') {
                        onUpdate('');
                        if (onSave) onSave('');
                        setIsTranslated(false);
                        return;
                    }
                     throw new Error("No translation returned");
                }
            }
        } catch (e) {
            console.error("Translation failed", e);
            const msg = e.response?.data?.detail || e.message || "Unknown error";
            addLog(`Translation error: ${msg}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleCancel = (e) => {
        e.stopPropagation();
        onUpdate(originalText);
        setIsTranslated(false);
        addLog("Reverted to original English", 'info');
    };

    if (isTranslated) {
        return (
           <div className="flex items-center gap-1">
               <button 
                   onClick={handleTranslate} 
                   disabled={loading}
                   className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors bg-indigo-500/80 text-white hover:bg-indigo-500"
                   title="Translate back to English & Save"
               >
                   {loading ? <RefreshCw className="w-3 h-3 animate-spin"/> : <Languages className="w-3 h-3"/>}
                   Save (EN)
               </button>
               <button 
                   onClick={handleCancel}
                   disabled={loading}
                   className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors bg-white/10 hover:bg-white/20 text-muted-foreground hover:text-white"
                   title="Cancel edit and revert to original"
               >
                   <X className="w-3 h-3"/>
               </button>
           </div>
        )
   }

    return (
        <button 
            onClick={handleTranslate} 
            disabled={loading}
            className={`text-[10px] px-2 py-0.5 rounded flex items-center gap-1 transition-colors ${isTranslated ? 'bg-indigo-500/80 text-white hover:bg-indigo-500' : 'bg-white/10 hover:bg-white/20 text-muted-foreground hover:text-white'}`}
            title={isTranslated ? "Translate back to English & Save" : "Translate to Chinese for editing"}
        >
            {loading ? <RefreshCw className="w-3 h-3 animate-spin"/> : <Languages className="w-3 h-3"/>}
            {isTranslated ? "Save (EN)" : "CN"}
        </button>
    );
};

const Editor = ({ projectId, onClose }) => {
    const params = useParams();
    const id = projectId || params.id;

    const [project, setProject] = useState(null);
    const [episodes, setEpisodes] = useState([]);
    const [activeEpisodeId, setActiveEpisodeId] = useState(null);
    const [isEpisodeMenuOpen, setIsEpisodeMenuOpen] = useState(false);
    const [isAgentOpen, setIsAgentOpen] = useState(false);
    const [activeTab, setActiveTab] = useState('overview');
    const [isImportOpen, setIsImportOpen] = useState(false);
    const [refreshKey, setRefreshKey] = useState(0);
    const [editingShot, setEditingShot] = useState(null);

    // Global Logging Context
    const { addLog } = useLog();

    useEffect(() => {
        loadProjectData();
    }, [id]);

    const loadProjectData = async () => {
         if (!id) return;
         try {
            const p = await fetchProject(id);
            console.log("[Editor] Loaded Project Data (Full):", p);
            console.log("[Editor] Global Info:", p?.global_info);
            setProject(p);
         } catch (e) {
            console.error("Failed to fetch project title", e);
         }
         loadEpisodes();
    };

    const loadEpisodes = async () => {
        if (!id) return;
        try {
            const data = await fetchEpisodes(id);
            setEpisodes(data);
            if (data.length > 0 && !activeEpisodeId) {
                setActiveEpisodeId(data[0].id);
            } else if (data.length === 0) {
                 // Auto create Ep 1 if none
                 const newEp = await createEpisode(id, { title: "Episode 1" });
                 setEpisodes([newEp]);
                 setActiveEpisodeId(newEp.id);
            }
        } catch (e) {
            console.error("Failed to load episodes", e);
        }
    };

    const handleUpdateScript = async (epId, content) => {
        try {
            const updatedEp = await updateEpisode(epId, { script_content: content });
            // Verify content length
            if (updatedEp.script_content && updatedEp.script_content.length !== content.length) {
                console.warn("Warning: Saved content length differs from local content.");
            }
            // Update local state to reflect content change
            setEpisodes(prev => prev.map(e => e.id === epId ? { ...e, script_content: content } : e));
            return updatedEp;
        } catch (e) {
            console.error("Update Script Failed in Parent:", e);
            throw e;
        }
    };

    const handleUpdateEpisodeInfo = async (epId, data) => {
        try {
            const updatedEp = await updateEpisode(epId, data);
            setEpisodes(prev => prev.map(e => e.id === epId ? updatedEp : e));
            return updatedEp;
        } catch (e) {
            console.error("Episode Info Update Failed:", e);
            throw e;
        }
    };

    const handleCreateEpisode = async () => {
        const title = prompt("Enter Episode Title (e.g., Episode 2):");
        if (!title) return;
        try {
            const newEp = await createEpisode(id, { title });
            setEpisodes(prev => [...prev, newEp]);
            setActiveEpisodeId(newEp.id);
            setIsEpisodeMenuOpen(false);
        } catch (e) {
            console.error(e);
        }
    };

    const handleDeleteEpisode = async (e, epId) => {
        e.stopPropagation();
        if (!confirm("Delete this episode? This will delete all script content and scenes within it.")) return;
         try {
            await deleteEpisode(epId);
            const remaining = episodes.filter(ep => ep.id !== epId);
            setEpisodes(remaining);
            if (activeEpisodeId === epId) {
                setActiveEpisodeId(remaining.length > 0 ? remaining[0].id : null);
            }
        } catch (err) {
            console.error(err);
        }
    };

    // Helper to repair common JSON syntax errors like unquoted strings
    const repairJSON = (jsonStr) => {
        try {
            return JSON.parse(jsonStr);
        } catch (e) {
            // Regex to match "key": value where value is unquoted
            // 1. "([^"]+)" matches key
            // 2. \s*:\s* matches colon
            // 3. ([^\s"{\[][\s\S]*?) matches value starting with non-quote/brace/bracket
            // 4. (?=\s*[,}\]]) lookahead for end of value (comma or brace/bracket)
            let repaired = jsonStr.replace(
                /"([^"]+)"\s*:\s*([^\s"{\[][\s\S]*?)(?=\s*[,}\]])/g, 
                (match, key, value) => {
                    const trimmedValue = value.trim();
                    if (!trimmedValue) return match;
                    
                    // Allow valid JSON primitives (numbers, bools, null)
                    if (/^(true|false|null)$/.test(trimmedValue)) return match;
                    if (!isNaN(parseFloat(trimmedValue)) && isFinite(trimmedValue)) return match;
                    
                    // Quote the string, escaping quotes and newlines
                    const safeValue = trimmedValue
                        .replace(/\\/g, '\\\\') // Escape backslashes first
                        .replace(/"/g, '\\"')
                        .replace(/\n/g, '\\n')
                        .replace(/\r/g, '');
                    return `"${key}": "${safeValue}"`;
                }
            );
            
            // Fix trailing commas
            repaired = repaired.replace(/,\s*([}\]])/g, '$1');
            
            return JSON.parse(repaired);
        }
    };

    // Helper to extract multiple JSON blocks from mixed text
    const extractJSONBlocks = (text) => {
        const results = [];
        let braceCount = 0;
        let startIndex = -1;
        
        let i = 0;
        while (i < text.length) {
            const char = text[i];
            
            // Skip strings to avoid counting braces inside them
            if (char === '"') {
                i++;
                while (i < text.length) {
                    if (text[i] === '"' && text[i-1] !== '\\') break;
                    if (text[i] === '\n') break;
                    i++;
                }
            } else if (char === '{') {
                if (braceCount === 0) startIndex = i;
                braceCount++;
            } else if (char === '}') {
                braceCount--;
                if (braceCount === 0 && startIndex !== -1) {
                    const jsonStr = text.substring(startIndex, i + 1);
                    try {
                        const obj = repairJSON(jsonStr);
                        results.push(obj);
                    } catch (e) {
                        console.warn("Failed to parse/repair block starting at " + startIndex, e);
                        // Optional: Could try to fuzzy find the end if brace counting was off
                    }
                    startIndex = -1;
                }
            }
            i++;
        }
        return results;
    }

    const handleImport = async (text, importType = 'auto') => {
        addLog(`Starting Import Analysis (${importType})...`, "process");
        
        // --- 1. JSON Processing (Only if 'auto' or 'json') ---
        const jsonBlocks = (importType === 'auto' || importType === 'json') ? extractJSONBlocks(text) : [];
        if (jsonBlocks.length > 0) {
             addLog(`Found ${jsonBlocks.length} JSON blocks to process.`, "info");
             // Process JSON Loop (same as before)
             // ... existing JSON processing code will run below ...
        }

        // Feature Flags based on Type
        // If specific type selected, FORCE recognition of that type and IGNORE others logic
        const canScript = importType === 'auto' || importType === 'script';
        const canScene = importType === 'auto' || importType === 'scene';
        const canShot = importType === 'auto' || importType === 'shot';

        // Strict: If explicit type, don't require specific headers if possible, OR just bypass strict header check?
        // Actually, existing logic relies on headers to parse columns. We still need headers.
        // But we won't misidentify Scene table as Shot table if we force one.
        
        const hasScriptTable = canScript && text.includes('|') && (text.includes('Paragraph ID') || text.includes('Paragraph Title'));
        
        // Scene header detection (Relaxed if forced scene type?)
        const sceneHeaderMarkers = ['Scene No', '场次序号', 'Scene ID', '场次'];
        let hasSceneTable = canScene && text.includes('|') && sceneHeaderMarkers.some(m => text.includes(m));
        
        // Shot header detection
        const shotHeaderMarkers = ['Shot ID', '镜头ID', 'Shot No'];
        let hasShotTable = canShot && text.includes('|') && shotHeaderMarkers.some(m => text.includes(m));

        // If explicit type is set but markers are missing, try to help user?
        if (importType === 'scene' && !hasSceneTable && text.includes('|')) {
            // Fallback: If strict mode, maybe assume the first row with | is header? 
            // Warning user is safer.
            addLog("Warning: 'Scenes' type selected, but specific Scene headers not found. Attempting to parse anyway if table exists.", "warning");
            hasSceneTable = true;
        }
        if (importType === 'shot' && !hasShotTable && text.includes('|')) {
             addLog("Warning: 'Shots' type selected, but specific Shot headers not found. Attempting to parse anyway if table exists.", "warning");
             hasShotTable = true;
        }

        addLog(`Import Flags: Script=${hasScriptTable}, Scene=${hasSceneTable}, Shot=${hasShotTable}`, "info");

        if (jsonBlocks.length === 0 && !hasScriptTable && !hasSceneTable && !hasShotTable) {

            addLog("No recognizable markers found.", "error");
            alert("No supported format detected. Please check your markers.");
            return;
        }

        let changesMade = false;
        let reloadRequired = false;

        // Process all found JSON blocks
        for (const data of jsonBlocks) {
            // 2. Process Global Info (JSON)
            if (data.global_info) {
                try {
                    await updateProject(id, { global_info: data.global_info });
                    addLog("Project Global Info updated.", "success");
                    changesMade = true;
                    reloadRequired = true;
                } catch (e) {
                    addLog(`Global Info Update Failed: ${e.message}`, "error");
                }
            }

            // 2b. Process Episode Global Info (JSON)
            if (data.e_global_info) {
                if (!activeEpisodeId) {
                    addLog("Skipping Episode Info: No Active Episode selected.", "warning");
                } else {
                    try {
                        await updateEpisode(activeEpisodeId, { 
                            episode_info: { e_global_info: data.e_global_info } 
                        });
                        addLog("Episode Global Info updated.", "success");
                        changesMade = true;
                    } catch (e) {
                        addLog(`Episode Info Update Failed: ${e.message}`, "error");
                    }
                }
            }

            // 2c. Process Entities (JSON)
            // Can be { characters: [] } or { props: [] } etc
            if (data.characters || data.props || data.environments) {
                try {
                    addLog("Processing Entities block...", "process");
                    let count = 0;

                    // Characters
                    if (data.characters && Array.isArray(data.characters)) {
                        for (const char of data.characters) {
                            const desc = [
                                `Name (EN): ${char.name_en}`,
                                `Role: ${char.role}`,
                                `Archetype: ${char.archetype}`,
                                `Appearance: ${char.appearance_cn}`,
                                `Clothing: ${char.clothing}`,
                                `Action: ${char.action_characteristics}`,
                                `Prompt: ${char.generation_prompt_en}`
                            ].join('\n\n');
                            
                            await createEntity(id, {
                                name: char.name,
                                type: 'character',
                                description: desc,
                                generation_prompt_en: char.generation_prompt_en || '',
                                anchor_description: char.anchor_description || '',
                                
                                name_en: char.name_en,
                                gender: char.gender,
                                role: char.role,
                                archetype: char.archetype,
                                appearance_cn: char.appearance_cn,
                                clothing: char.clothing,
                                action_characteristics: char.action_characteristics,
                                visual_dependencies: char.visual_dependencies || [],
                                dependency_strategy: char.dependency_strategy || {}
                            });
                            count++;
                        }
                    }

                    // Props
                    if (data.props && Array.isArray(data.props)) {
                        for (const prop of data.props) {
                             const desc = [
                                `Name (EN): ${prop.name_en}`,
                                `Type: ${prop.type}`, // inner type from JSON
                                `Description: ${prop.description_cn}`,
                                `Prompt: ${prop.generation_prompt_en}`,
                                prop.dependency_strategy?.logic ? `Dependency: ${prop.dependency_strategy.logic}` : ''
                            ].filter(Boolean).join('\n\n');

                            await createEntity(id, {
                                name: prop.name,
                                type: 'prop',
                                description: desc,
                                generation_prompt_en: prop.generation_prompt_en || '',
                                anchor_description: prop.anchor_description || '',
                                
                                name_en: prop.name_en,
                                visual_dependencies: prop.visual_dependencies || [],
                                dependency_strategy: prop.dependency_strategy || {}
                            });
                            count++;
                        }
                    }

                    // Environments
                    if (data.environments && Array.isArray(data.environments)) {
                        for (const env of data.environments) {
                             const desc = [
                                `Name (EN): ${env.name_en}`,
                                `Atmosphere: ${env.atmosphere}`,
                                `Visual Params: ${env.visual_params}`,
                                `Description: ${env.description_cn}`,
                                `Prompt: ${env.generation_prompt_en}`
                            ].join('\n\n');

                            await createEntity(id, {
                                name: env.name,
                                type: 'environment',
                                description: desc,
                                generation_prompt_en: env.generation_prompt_en || '',
                                anchor_description: env.anchor_description || '',
                                
                                name_en: env.name_en,
                                atmosphere: env.atmosphere,
                                visual_params: env.visual_params,
                                narrative_description: env.description_cn,

                                visual_dependencies: env.visual_dependencies || [],
                                dependency_strategy: env.dependency_strategy || {}
                            });
                            count++;
                        }
                    }
                    
                    if (count > 0) {
                        addLog(`Imported ${count} entities from block.`, "success");
                        changesMade = true;
                    }
                } catch (e) {
                    addLog(`Entity Import Failed: ${e.message}`, "error");
                    console.error(e);
                }
            }
        }

        // Check episode selection for Script/Scene import
        if ((hasScriptTable || hasSceneTable) && !activeEpisodeId) {
             addLog("Detection: Script/Scene content found but NO Active Episode selected.", "error");
             alert("Please create or select an episode before importing Script or Scene content.");
             return; 
        }

        // 3. Process Script Content
        if (hasScriptTable && activeEpisodeId) {
            try {
                addLog(`Processing Script Table for Episode ${activeEpisodeId}...`, "process");
                const lines = text.split('\n');
                let scriptLines = [];
                let capturing = false;

                for (let line of lines) {
                    // Start marker
                    if (line.includes('|') && (line.includes('Paragraph ID') || line.includes('Paragraph Title'))) {
                        capturing = true;
                        addLog("Found Script Header.", "info");
                    }
                    
                    if (capturing) {
                        if (line.trim().startsWith('|')) {
                            // Validate column count roughly to avoid bad lines? optional.
                            scriptLines.push(line);
                        } else if (scriptLines.length > 2 && !line.trim().startsWith('|')) {
                            capturing = false;
                            addLog("End of Script Table.", "info");
                        }
                    }
                }

                if (scriptLines.length > 0) {
                    const content = scriptLines.join('\n');
                    await updateEpisode(activeEpisodeId, { script_content: content });
                    addLog(`Imported ${scriptLines.length} lines of Script content.`, "success");
                    changesMade = true;
                } else {
                    addLog("Script markers found but no lines extracted.", "error");
                }
            } catch (e) {
                addLog(`Script Import Failed: ${e.message}`, "error");
            }
        }

        // 4. Process Scene Content (and interleaved Shots)
        if ((hasSceneTable || hasShotTable) && activeEpisodeId) {
             try {
                addLog(`Processing Scene/Shot Tables for Episode ${activeEpisodeId}...`, "process");
                const lines = text.split('\n');
                let sceneLines = [];
                let shotLines = [];
                
                // DB Sync State
                let existingScenes = [];
                try { existingScenes = await fetchScenes(activeEpisodeId); } catch(e) {}
                let currentSceneDbId = null;
                
    const processImportText = async (text) => {
        // ... (Existing implementation of handleProjectImport logic extracted here or just use inline)
        // Note: The user code seen via read_file seems to be inside a large function "handleProjectImport" or similar.
    
        // ... previous extraction logic ...
    }; // (Dummy closer for context)

    // ... (Inside the actual big loop)
    
                // State flags
                let inShotTable = false;
                let inSceneTable = false;
                let shotHeaderMap = {};

                for (let line of lines) {
                    const trimmed = line.trim();
                    let isTableRow = trimmed.startsWith('|');
                    
                    // Robustness: Allow internal rows without leading pipe
                    if (!isTableRow && (inSceneTable || inShotTable) && trimmed.includes('|')) isTableRow = true;
                    
                    let cols = [];
                    if (isTableRow || trimmed.includes('|')) { 
                        cols = line.split('|').map(c => c.trim());
                        if (trimmed.startsWith('|') && cols.length > 0 && cols[0] === "") cols.shift();
                        if (trimmed.endsWith('|') && cols.length > 0 && cols[cols.length-1] === "") cols.pop();
                    }

                    // DEBUG LOG
                    if (trimmed.length > 0 && (inSceneTable || inShotTable || isTableRow)) {
                        console.log(`[Import] Line: "${trimmed.substring(0, 30)}..." | TableRow=${isTableRow} | Cols=${cols.length} | InScene=${inSceneTable} | IsSep=${line.includes('---')} | Skip=${(cols.length < 2 || line.includes('---'))}`);
                    }

                    // 1. Header Detection (Relaxed)
                    const isShotKey = (isTableRow || line.includes('|')) && (line.includes("Shot ID") || line.includes("镜头ID") || line.includes("Shot Name") || line.includes("Shot No"));
                    const isSceneKey = (isTableRow || line.includes('|')) && (line.includes('Scene No') || line.includes('场次序号') || (line.includes('Scene ID') && !line.includes('Shot ID')));

                    // Enter Shot Table Mode
                    if (canShot && !inSceneTable && (isShotKey || (importType === 'shot' && !inShotTable && isTableRow && cols.length > 2))) {
                        inShotTable = true;
                        inSceneTable = false;
                        addLog("Found Shot Header (or Forced Type).", "info");
                        shotLines.push(line); 
                        
                        // Parse Header Map
                        const curCols = line.split('|').map(c => c.trim());
                        // ... (same as original code)
                        if (curCols.length > 0 && curCols[0] === "") curCols.shift();
                        if (curCols.length > 0 && curCols[curCols.length-1] === "") curCols.pop();
                        
                        shotHeaderMap = {};
                        curCols.forEach((col, idx) => {
                             const key = col.toLowerCase().replace(/[\(\)（）\s\.]/g, '');
                             shotHeaderMap[key] = idx;
                        });
                        continue;
                    }
                    else if (canScene && !inShotTable && (isSceneKey || (importType === 'scene' && !inSceneTable && line.includes('|') && cols.length > 2))) {
                        inSceneTable = true;
                        inShotTable = false;
                        addLog("Found Scene Header (or Forced Type).", "info");
                        sceneLines.push(line);
                        continue;
                    }

                    // 2. Data Line Processing
                    if (isTableRow) {
                         // cols already parsed and cleaned at top of loop
                         // Only skip if strict separator line. 
                         // Check only for regex match of '---|---' style or '---' in cells (handling :--- for alignment)
                         const isSeparator = /\|\s*:?-{3,}:?/.test(line) || /^[\s\|:\-]*$/.test(line);
                         const isEmptyRow = cols.every(c => c === "");

                         if (cols.length < 2 || isSeparator || isEmptyRow) {
                             if (inSceneTable) sceneLines.push(line);
                             if (inShotTable) shotLines.push(line);
                             continue; 
                         }
                         
                         const clean = (t) => t ? t.replace(/<br\s*\/?>/gi, '\n').replace(/\\\|/g, '|') : '';

                         // A. Handle Scene Row
                         if (inSceneTable) {
                             console.log("DEBUG: HIT SCENE ROW BLOCK");
                             sceneLines.push(line);
                             
                             try {
                                const scData = {
                                    scene_no: clean(cols[0]),
                                    scene_name: clean(cols[1]),
                                    equivalent_duration: clean(cols[2]),
                                    core_scene_info: clean(cols[3]),
                                    original_script_text: clean(cols[4]), 
                                    environment_name: clean(cols[5]),
                                    linked_characters: clean(cols[6]),
                                    key_props: clean(cols[7])
                                };
                                
                                if (!scData.scene_no || String(scData.scene_no).trim().length === 0) {
                                    // addLog("Skipping empty Scene row", "info"); // Optional log
                                    continue;
                                }

                                addLog(`Processing Scene Row: No=${scData.scene_no} Name=${(scData.scene_name || '').substring(0, 20)}...`, "info");

                                const match = existingScenes.find(s => String(s.scene_no) === String(scData.scene_no));
                                if (match) {
                                    await updateScene(match.id, scData); 
                                    currentSceneDbId = match.id;
                                    addLog(`Updated Scene ${scData.scene_no}`, "success");
                                } else {
                                    const newScene = await createScene(activeEpisodeId, scData);
                                    currentSceneDbId = newScene.id;
                                    existingScenes.push(newScene); 
                                    addLog(`Created Scene ${scData.scene_no}`, "success");
                                }
                             } catch (rowErr) {
                                 console.error("Row Error", rowErr);
                                 addLog(`Row Processing Failed: ${rowErr.message}`, "error");
                             }
                         }
                         
                         // B. Handle Shot Row
                         else if (inShotTable) {
                             shotLines.push(line);
                             
                             const useMap = Object.keys(shotHeaderMap).length > 0;
                             
                             const getVal = (keys, defaultIdx) => {
                                 for (const k of keys) {
                                     if (shotHeaderMap[k] !== undefined && shotHeaderMap[k] < cols.length) return clean(cols[shotHeaderMap[k]]);
                                 }
                                 if (!useMap && defaultIdx < cols.length) return clean(cols[defaultIdx]);
                                 return '';
                             };
                             
                             // Legacy offset logic
                             let colStart = 2; 
                             let legacySceneCode = '';
                             if (!useMap) {
                                if (cols.length >= 8) {
                                    legacySceneCode = clean(cols[2]);
                                    colStart = 3;
                                }
                             }

                             const rawShotId = useMap ? getVal(['shotid', 'shotno', '镜头id', 'id'], 0) : clean(cols[0]);
                             
                             if (!rawShotId || String(rawShotId).trim().length === 0) {
                                 continue; 
                             }

                             // Infer Scene from Shot ID if needed (e.g. 1-1)
                             if (!currentSceneDbId) {
                                 // Try to find scene code column first
                                let tempCode = useMap ? getVal(['sceneid', 'sceneno', 'scenecode', '场号'], -1) : legacySceneCode;
                                if (!tempCode) {
                                     // Check if shot ID has implicit scene number (e.g. 1-1A)
                                     const parts = rawShotId.split(/[-_]/);
                                     if (parts.length > 1) tempCode = parts[0];
                                }
                                
                                if (tempCode) {
                                     // Look up Scene ID by Scene No
                                     const match = existingScenes.find(s => {
                                         const dbNo = String(s.scene_no).replace(/[\*\s]/g, '');
                                         const targetNo = String(tempCode).replace(/[\*\s]/g, '');
                                         return dbNo === targetNo;
                                     });
                                     if (match) currentSceneDbId = match.id;
                                     else {
                                         // Auto-create scene if strict mode not enforced?
                                         // User asked for "strict separation", implying we shouldn't guess wild things. 
                                         // But if we can't find scene, we can't link.
                                         // Maybe we should create proper scene if missing?
                                         // For now, let's just log.
                                     }
                                }
                             }

                             
                             // !!! KEY FIX: Ensure scene_code is sent to creation !!!
                             let sceneCode = useMap ? getVal(['sceneid', 'sceneno', 'scenecode', '场号'], -1) : legacySceneCode;
                             if (!sceneCode && currentSceneDbId) {
                                 const sObj = existingScenes.find(s => s.id === currentSceneDbId);
                                 if (sObj) sceneCode = sObj.scene_no;
                             }

                             if (currentSceneDbId) {
                                 const shotData = {
                                     shot_id: rawShotId,
                                     shot_name: useMap ? getVal(['shotname', 'name', '镜头名称'], 1) : clean(cols[1]),
                                     scene_code: sceneCode, 
                                     start_frame: useMap ? getVal(['startframe', 'start', '首帧'], 2) : clean(cols[colStart]),
                                     end_frame: useMap ? getVal(['endframe', 'end', '尾帧'], 3) : clean(cols[colStart+1]),
                                     video_content: useMap ? getVal(['videocontent', 'video', 'description', '视频内容'], 4) : clean(cols[colStart+2]),
                                     duration: useMap ? getVal(['duration', 'durations', 'duration(s)', 'dur', '时长'], 5) : clean(cols[colStart+3]),
                                     associated_entities: useMap ? getVal(['associatedentities', 'entities', 'associated', '实体'], 6) : clean(cols[colStart+4]),
                                     shot_logic_cn: useMap ? getVal(['shotlogiccn', 'shotlogic', 'logic', 'logiccn', 'shotlogic(cn)', 'shot logic (cn)', 'logic(cn)'], 7) : ''
                                 };
                                 
                                 addLog(`Creating Shot ${shotData.shot_id} for Scene ID ${currentSceneDbId}...`, "info");
                                 try {
                                     await createShot(currentSceneDbId, shotData);
                                 } catch (shotErr) {
                                      console.error("Shot DB Sync Error", shotErr);
                                      addLog(`Failed to create shot ${shotData.shot_id}: ${shotErr.message}`, "error");
                                 }
                             } else {
                                 addLog(`Skipped Shot ${rawShotId}: No matching Scene found for code '${sceneCode}'`, "warning");
                             }
                         }

                    } else if (sceneLines.length > 2 && inSceneTable && !trimmed.startsWith('|') && trimmed !== '') {
                         inSceneTable = false;
                    } else if (shotLines.length > 2 && inShotTable && !trimmed.startsWith('|') && trimmed !== '') {
                         inShotTable = false;
                    }
                }

                // Update contents separately
                // Removed legacy scene_content/shot_content updates as they are deprecated in backend
                /* 
                const updatePayload = {};
                if (sceneLines.length > 0) { ... }
                */
                
                // Just force refresh
                if (sceneLines.length > 0 || shotLines.length > 0) {
                    changesMade = true;
                    reloadRequired = true;
                }
             } catch (e) {
                 addLog(`Scene Import Failed: ${e.message}`, "error");
             }
        }

        if (changesMade) {
            setIsImportOpen(false);
            
            // Always refresh episodes to show new scripts/scenes
            const fresh = await fetchEpisodes(id);
            setEpisodes(fresh);

            if (reloadRequired) {
                // Force Overview refresh if needed
                setRefreshKey(prev => prev + 1);
                addLog("Project Settings updated. Refreshing views...", "info");
                alert("Import Successful! Project settings and content have been updated.");
                
                // Force reload of scenes if the active episode was affected
                if (activeEpisodeId) {
                    try {
                        const newScenes = await fetchScenes(activeEpisodeId);
                        // Accessing SceneManager via ref or forcing a global refresh is intricate.
                        // Ideally, we just update the 'activeEpisode' reference which triggers SceneManager useEffect.
                        // But activeEpisode is derived from 'episodes'. 'setEpisodes(fresh)' does that.
                        // HOWEVER, SceneManager uses [activeEpisode, projectId] dependency.
                        // If 'fresh' episode object is identical (by reference or value), it might not trigger.
                        // Let's force a window reload as a last resort fallback, or better:
                        // window.location.reload(); // Removed to prevent full page reload navigating away
                    } catch(e) { console.error(e); }
                }
            } else {
                alert("Import Successful!");
            }
        }
    };

    const handleExport = async () => {
        addLog("Preparing project export...", "process");
        try {
            // 1. Fetch latest project data
            const projectData = await fetchProject(id);
            // 2. Fetch all episodes
            const episodesData = await fetchEpisodes(id);

            const exportData = {
                project: projectData,
                episodes: episodesData,
                export_date: new Date().toISOString(),
                version: "1.0"
            };

            const jsonString = JSON.stringify(exportData, null, 2);
            const blob = new Blob([jsonString], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `Project_${(projectData.title || id).replace(/[^a-z0-9]/gi, '_')}_Export.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            
            addLog("Project exported to local disk.", "success");
        } catch (e) {
            console.error(e);
            addLog(`Export failed: ${e.message}`, "error");
            alert("Failed to export project.");
        }
    };

    const activeEpisode = episodes.find(e => e.id === activeEpisodeId);

    const MENU_ITEMS = [
        { id: 'overview', label: 'Overview', icon: LayoutDashboard },
        { id: 'ep_info', label: 'Ep. Info', icon: Info },
        { id: 'script', label: 'Script', icon: FileText },
        { id: 'scenes', label: 'Scenes', icon: Clapperboard },
        { id: 'subjects', label: 'Subjects', icon: Users },
        { id: 'assets', label: 'Assets', icon: FolderOpen },
        { id: 'shots', label: 'Shots', icon: Film },
        { id: 'montage', label: 'Montage', icon: Video },
    ];

    return (
        <div className="flex flex-col h-screen w-full bg-background overflow-hidden relative text-foreground">
            {/* Top Navigation Bar - Compact */}
            <div className="h-12 px-4 border-b border-white/10 bg-[#09090b] flex items-center justify-between shrink-0 z-40 relative">
                {/* Left: Project Info & Episode Selector */}
                <div className="flex items-center gap-4">
                     {/* Back Button if in embedded mode */}
                     {onClose && (
                        <button onClick={onClose} className="p-1.5 hover:bg-white/10 rounded-md text-muted-foreground hover:text-white transition-colors mr-2">
                            <ArrowLeft className="w-5 h-5" />
                        </button>
                     )}
                     <div className="flex items-center gap-4">
                        <h1 className="font-bold text-sm tracking-wide text-white flex items-center gap-2">
                            <span className="text-primary hover:underline cursor-pointer">{project ? project.title : `Project #${id}`}</span>
                        </h1>
                        
                        {/* Episode Dropdown */}
                        <div className="relative">
                            <button 
                                onClick={() => setIsEpisodeMenuOpen(!isEpisodeMenuOpen)}
                                className="flex items-center gap-2 px-3 py-1 bg-white/5 hover:bg-white/10 border border-white/10 rounded-md text-xs font-medium text-white transition-colors"
                            >
                                <span className="max-w-[100px] truncate">{activeEpisode ? activeEpisode.title : 'Select Episode'}</span>
                                <ChevronDown className="w-3 h-3 text-muted-foreground" />
                            </button>

                            {/* Dropdown Menu */}
                            {isEpisodeMenuOpen && (
                                <div className="absolute top-full left-0 mt-2 w-48 bg-[#09090b] border border-white/10 rounded-lg shadow-xl py-1 z-50">
                                    {episodes.map(ep => (
                                        <div 
                                            key={ep.id}
                                            className={`px-3 py-2 text-xs flex justify-between items-center group cursor-pointer ${activeEpisodeId === ep.id ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:bg-white/5 hover:text-white'}`}
                                            onClick={() => {
                                                setActiveEpisodeId(ep.id);
                                                setIsEpisodeMenuOpen(false);
                                            }}
                                        >
                                            <span className="truncate flex-1">{ep.title}</span>
                                            <button 
                                                onClick={(e) => handleDeleteEpisode(e, ep.id)}
                                                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 hover:text-red-500 rounded"
                                            >
                                                <Trash2 className="w-3 h-3" />
                                            </button>
                                        </div>
                                    ))}
                                    <div className="border-t border-white/10 mt-1 pt-1 px-1">
                                         <button 
                                            onClick={handleCreateEpisode}
                                            className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground hover:text-white hover:bg-white/5 rounded transition-colors"
                                        >
                                            <Plus className="w-3 h-3" /> New Episode
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                     </div>
                </div>

                {/* Center: Navigation Menu */}
                <div className="flex items-center bg-transparent">
                    {MENU_ITEMS.map(item => {
                        const Icon = item.icon;
                        const isActive = activeTab === item.id;
                        return (
                            <button
                                key={item.id}
                                onClick={() => {
                                    setActiveTab(item.id);
                                    if (item.id === 'shots') setEditingShot(null);
                                }}
                                className={`flex items-center gap-2 px-4 py-1.5 text-xs font-bold transition-all relative ${isActive ? 'text-primary' : 'text-muted-foreground hover:text-white'}`}
                            >
                                <Icon className="w-3.5 h-3.5" />
                                {item.label}
                                {isActive && <div className="absolute bottom-[-13px] left-0 right-0 h-[2px] bg-primary shadow-[0_0_10px_rgba(255,255,255,0.5)]"></div>}
                            </button>
                        )
                    })}
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-3">
                    <button 
                        onClick={() => setIsImportOpen(true)}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5" 
                        title="Import Content"
                    >
                        <Upload className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">Import</span>
                    </button>
                    <button 
                        onClick={handleExport}
                        className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors flex items-center gap-1.5" 
                        title="Export Project"
                    >
                        <Download className="w-4 h-4" />
                        <span className="text-xs font-medium hidden sm:block">Export</span>
                    </button>
                    <button className="p-1.5 text-muted-foreground hover:text-white hover:bg-white/10 rounded-md transition-colors" title="Settings">
                        <SettingsIcon className="w-4 h-4" />
                    </button>
                    <button 
                        onClick={() => setIsAgentOpen(!isAgentOpen)}
                        className={`flex items-center gap-2 px-3 py-1 rounded-md text-xs font-bold transition-colors ${isAgentOpen ? 'bg-secondary text-white' : 'bg-primary text-black'}`}
                    >
                        <MessageSquare className="w-3.5 h-3.5" />
                        AI Agent
                        {/* Status Dot */}
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse ml-1 opacity-50"></div>
                    </button>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 overflow-hidden relative bg-background">
                <div className="h-full overflow-y-auto custom-scrollbar p-0">
                    <div className="animate-in fade-in duration-300 min-h-full">
                        {activeTab === 'overview' && <ProjectOverview id={id} key={refreshKey} onProjectUpdate={loadProjectData} />}
                        {activeTab === 'ep_info' && <EpisodeInfo episode={activeEpisode} onUpdate={handleUpdateEpisodeInfo} />}
                        {activeTab === 'script' && <ScriptEditor activeEpisode={activeEpisode} project={project} onUpdateScript={handleUpdateScript} onLog={addLog} />}
                        {activeTab === 'scenes' && <SceneManager activeEpisode={activeEpisode} projectId={id} project={project} onLog={addLog} />}
                        {activeTab === 'subjects' && <SubjectLibrary projectId={id} currentEpisode={activeEpisode} />}
                        {activeTab === 'assets' && <AssetsLibrary projectId={id} onLog={addLog} />}
                        {activeTab === 'shots' && <ShotsView activeEpisode={activeEpisode} projectId={id} project={project} onLog={addLog} editingShot={editingShot} setEditingShot={setEditingShot} />}
                        {activeTab === 'montage' && <VideoStudio activeEpisode={activeEpisode} projectId={id} onLog={addLog} />}
                    </div>
                </div>
            </div>

            {/* Agent Sidebar (Slide-over) */}
            <AnimatePresence>
                {isAgentOpen && (
                    <motion.div 
                        initial={{ x: "100%", opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: "100%", opacity: 0 }}
                        transition={{ type: "spring", stiffness: 300, damping: 30 }}
                        className="absolute right-0 top-12 bottom-0 w-[450px] border-l border-white/10 bg-[#09090b]/95 backdrop-blur-xl z-50 flex flex-col shadow-[-20px_0_50px_rgba(0,0,0,0.5)]"
                    >
                        <AgentChat context={{ projectId: id }} onClose={() => setIsAgentOpen(false)} />
                    </motion.div>
                )}
            </AnimatePresence>

            <ImportModal isOpen={isImportOpen} onClose={() => setIsImportOpen(false)} onImport={handleImport} project={project} />

            {/* Log Panel */}
            <LogPanel />

        </div>
    );
};

export default Editor;
