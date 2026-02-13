import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
    Image, Video, Upload, Link as LinkIcon, Plus, X, 
    MoreVertical, Trash2, Edit2, Info, Maximize2,
    Folder, User, Film, Globe, Layers, ArrowDown, ArrowUp,
    Sparkles, Copy, Loader2
} from 'lucide-react';
import { fetchAssets, createAsset, uploadAsset, deleteAsset, updateAsset, analyzeAssetImage } from '../services/api';
import { useLog } from '../context/LogContext';
import { API_URL, BASE_URL } from '../config';
import RefineControl from './RefineControl.jsx';

// Helper to construct full URL if relative
const getFullUrl = (url) => {
    if (!url) return '';
    if (url.startsWith('http') || url.startsWith('blob:') || url.startsWith('data:')) return url;
    if (url.startsWith('/')) {
        const base = BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL;
        return `${base}${url}`;
    }
    return url; 
};

const AssetItem = ({ asset, onClick, onDelete }) => {
    const videoRef = React.useRef(null);
    const [isPlaying, setIsPlaying] = useState(false);

    const handleMouseEnter = async () => {
        if (asset.type === 'video' && videoRef.current) {
            try {
                videoRef.current.currentTime = 0;
                await videoRef.current.play();
                setIsPlaying(true);
            } catch (err) {
                // Auto-play might be prevented
            }
        }
    };

    const handleMouseLeave = () => {
        if (asset.type === 'video' && videoRef.current) {
            videoRef.current.pause();
            videoRef.current.currentTime = 0;
            setIsPlaying(false);
        }
    };

    return (
        <div 
            onClick={() => onClick(asset)}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            className="group relative aspect-square bg-card rounded-xl border border-white/5 overflow-hidden cursor-pointer hover:border-primary/50 transition-all hover:scale-[1.02] shadow-sm transform-gpu"
        >
            {asset.type === 'image' ? (
                <img src={getFullUrl(asset.url)} className="w-full h-full object-cover" alt="asset" />
            ) : (
                <div className="relative w-full h-full bg-black">
                    <video 
                        ref={videoRef}
                        src={getFullUrl(asset.url)} 
                        className={`w-full h-full object-cover transition-opacity duration-300 ${isPlaying ? 'opacity-100' : 'opacity-70'}`}
                        preload="metadata"
                        muted
                        loop
                        playsInline
                    />
                    <div className={`absolute inset-0 flex items-center justify-center pointer-events-none transition-opacity duration-300 ${isPlaying ? 'opacity-0' : 'opacity-100'}`}>
                        <div className="bg-black/50 p-3 rounded-full backdrop-blur-sm">
                            <Video className="w-6 h-6 text-white" />
                        </div>
                    </div>
                </div>
            )}
            
            <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-4 pointer-events-none">
                <div className="flex justify-between items-end pointer-events-auto">
                    <div>
                        <div className="text-xs text-white/70 truncate w-24">{asset.filename || 'Untitled'}</div>
                        <div className="text-[10px] text-white/40 uppercase flex items-center gap-2">
                             {asset.type}
                             {asset.meta_info?.resolution && <span className="bg-white/10 px-1 rounded text-white/60">{asset.meta_info.resolution}</span>}
                        </div>
                    </div>
                    <button 
                        onClick={(e) => onDelete(asset.id, e)}
                        className="p-1.5 bg-red-500/20 text-red-400 rounded-md hover:bg-red-500 hover:text-white transition-colors"
                    >
                        <Trash2 size={14} />
                    </button>
                </div>
            </div>
        </div>
    );
};

const AssetsLibrary = () => {
    const { addLog } = useLog();
    const [assets, setAssets] = useState([]);
    const [filter, setFilter] = useState('all'); // all, image, video
    const [groupBy, setGroupBy] = useState('none'); // none, project, subject, shot
    const [sortOrder, setSortOrder] = useState('desc'); // desc (newest first), asc (oldest first)
    const [loading, setLoading] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState(null); 
    const [isUploadOpen, setIsUploadOpen] = useState(false);

    useEffect(() => {
        loadAssets();
    }, []);

    const loadAssets = async () => {
        setLoading(true);
        try {
            const data = await fetchAssets();
            setAssets(data);
            addLog(`Loaded ${data.length} assets from library.`);
        } catch (e) {
            console.error("Failed to load assets", e);
            addLog(`Error loading assets: ${e.message}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id, e) => {
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this asset?")) return;
        try {
            await deleteAsset(id);
            setAssets(prev => prev.filter(a => a.id !== id));
            if (selectedAsset?.id === id) setSelectedAsset(null);
            addLog(`Deleted asset ID ${id}.`);
        } catch (e) {
            console.error("Delete failed", e);
            addLog(`Failed to delete asset: ${e.message}`, 'error');
        }
    };

    const filteredAssets = React.useMemo(() => {
        const list = assets.filter(a => filter === 'all' || a.type === filter);
        return list.sort((a, b) => {
             const tA = new Date(a.created_at || a.id).getTime ? new Date(a.created_at || 0).getTime() : 0; 
             // ID fallback is weak, assuming createdAt exists or backend provides it.
             // Usually created_at is ISO string. 
             const dateA = new Date(a.created_at || 0).getTime();
             const dateB = new Date(b.created_at || 0).getTime();
             return sortOrder === 'desc' ? dateB - dateA : dateA - dateB;
        });
    }, [assets, filter, sortOrder]);

    const groupedSections = React.useMemo(() => {
        if (groupBy === 'none') return { 'All Assets': filteredAssets };
        
        const groups = {};
        const globalKey = 'Global / Unsorted';
        
        filteredAssets.forEach(asset => {
            const meta = asset.meta_info || {};
            let key = globalKey;
            
            if (groupBy === 'project') {
                if (meta.project_title) key = meta.project_title;
                else if (meta.project_id) key = `Project ${meta.project_id}`;
            } else if (groupBy === 'subject') {
                if (meta.entity_name) key = meta.entity_name;
                else if (meta.entity_id) key = `Entity ${meta.entity_id}`;
            } else if (groupBy === 'shot') {
                if (meta.shot_number) key = `Shot ${meta.shot_number}`;
                else if (meta.shot_id) key = `Shot ${meta.shot_id}`;
            }
            
            if (!groups[key]) groups[key] = [];
            groups[key].push(asset);
        });
        
        return groups;
    }, [filteredAssets, groupBy]);

    return (
        <div className="h-full flex flex-col p-6 animate-in fade-in">
            {/* Header Controls */}
            <div className="flex flex-col gap-4 mb-6">
                 <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                        <div className="flex space-x-2 bg-card/50 p-1 rounded-lg border border-white/5">
                            <button onClick={() => setFilter('all')} className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${filter === 'all' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}>All</button>
                            <button onClick={() => setFilter('image')} className={`px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${filter === 'image' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}><Image size={16} /> Images</button>
                            <button onClick={() => setFilter('video')} className={`px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${filter === 'video' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-white'}`}><Video size={16} /> Videos</button>
                        </div>
                        <button 
                            onClick={() => setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
                            className="p-2.5 rounded-lg bg-card/50 border border-white/5 text-muted-foreground hover:text-white hover:bg-white/10 transition-colors"
                            title={`Sort: ${sortOrder === 'desc' ? 'Newest First' : 'Oldest First'}`}
                        >
                            {sortOrder === 'desc' ? <ArrowDown size={18} /> : <ArrowUp size={18} />}
                        </button>
                    </div>
                    
                    <button onClick={() => setIsUploadOpen(true)} className="flex items-center gap-2 px-4 py-2 bg-primary text-black rounded-lg hover:bg-primary/90 transition-colors font-bold"><Plus size={18} /> Add Asset</button>
                </div>

                {/* Group By Controls */}
                <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
                    <span className="text-xs font-bold text-muted-foreground uppercase mr-2">Group By:</span>
                    {[
                        { id: 'none', label: 'None', icon: Layers },
                        { id: 'project', label: 'Project', icon: Folder },
                        { id: 'subject', label: 'Subject', icon: User },
                        { id: 'shot', label: 'Shot', icon: Film },
                    ].map(g => (
                         <button 
                            key={g.id}
                            onClick={() => setGroupBy(g.id)}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-all whitespace-nowrap ${groupBy === g.id ? 'bg-white text-black border-white' : 'bg-transparent text-muted-foreground border-white/10 hover:border-white/30'}`}
                        >
                            <g.icon size={12} /> {g.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Grid */}
            <div className="flex-1 overflow-y-auto min-h-0 pr-2">
                {Object.entries(groupedSections).map(([sectionTitle, sectionAssets]) => (
                    sectionAssets.length > 0 && (
                        <div key={sectionTitle} className="mb-8">
                            <h3 className="text-sm font-bold text-white/50 uppercase mb-4 sticky top-0 bg-black/95 backdrop-blur py-2 z-10 border-b border-white/5 flex items-center gap-2">
                                {groupBy === 'project' && <Folder size={14} />}
                                {groupBy === 'subject' && <User size={14} />}
                                {groupBy === 'shot' && <Film size={14} />}
                                {sectionTitle}
                                <span className="text-xs bg-white/10 text-white/50 px-2 py-0.5 rounded-full ml-auto">{sectionAssets.length}</span>
                            </h3>
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
                                {sectionAssets.map(asset => (
                                    <AssetItem 
                                        key={asset.id} 
                                        asset={asset} 
                                        onClick={setSelectedAsset} 
                                        onDelete={handleDelete} 
                                    />
                                ))}
                            </div>
                        </div>
                    )
                ))}
                
                {/* Empty State */}
                {filteredAssets.length === 0 && !loading && (
                    <div className="py-20 text-center text-muted-foreground border border-dashed border-white/10 rounded-xl">
                        <Image className="w-12 h-12 mx-auto mb-3 opacity-20" />
                        <p>No assets found. Upload some!</p>
                    </div>
                )}
            </div>

            {/* Modals */}
            <AnimatePresence>
                {isUploadOpen && (
                    <UploadModal onClose={() => setIsUploadOpen(false)} onUploadSuccess={() => { loadAssets(); setIsUploadOpen(false); }} />
                )}
                {selectedAsset && (
                    <AssetDetailModal asset={selectedAsset} onClose={() => setSelectedAsset(null)} onUpdate={loadAssets} />
                )}
            </AnimatePresence>
        </div>
    );
};

const UploadModal = ({ onClose, onUploadSuccess }) => {
    const { addLog } = useLog();
    const [mode, setMode] = useState('file'); // file, url
    const [url, setUrl] = useState('');
    const [file, setFile] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);
    const [meta, setMeta] = useState(null);
    const [type, setType] = useState('image');
    const [remark, setRemark] = useState('');
    const [uploading, setUploading] = useState(false);

    useEffect(() => {
        return () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
        }
    }, [previewUrl]);

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (!selectedFile) return;

        setFile(selectedFile);
        const objectUrl = URL.createObjectURL(selectedFile);
        setPreviewUrl(objectUrl);

        // Basic Meta
        const newMeta = {
            size: (selectedFile.size / 1024).toFixed(2) + ' KB',
            type: selectedFile.type,
            name: selectedFile.name
        };

        if (selectedFile.type.startsWith('image')) {
            setType('image');
            const img = new window.Image();
            img.onload = () => {
                setMeta({
                    ...newMeta,
                    resolution: `${img.width}x${img.height}`,
                    width: img.width,
                    height: img.height
                });
            };
            img.src = objectUrl;
        } else if (selectedFile.type.startsWith('video')) {
            setType('video');
            const video = document.createElement('video');
            video.preload = 'metadata';
            video.onloadedmetadata = () => {
                setMeta({
                    ...newMeta,
                    resolution: `${video.videoWidth}x${video.videoHeight}`,
                    duration: video.duration.toFixed(2) + 's'
                });
            };
            video.src = objectUrl;
        } else {
            setMeta(newMeta);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setUploading(true);
        addLog(`Starting upload (${mode})...`);
        try {
            if (mode === 'url') {
                await createAsset({ url, type, remark });
                addLog(`Asset created from URL: ${url}`);
            } else {
                if (!file) return;
                const formData = new FormData();
                formData.append('file', file);
                formData.append('type', type);
                formData.append('remark', remark);
                await uploadAsset(formData);
                addLog(`File uploaded successfully: ${file.name}`);
            }
            onUploadSuccess();
        } catch (e) {
            console.error(e);
            alert("Upload failed");
            addLog(`Upload failed: ${e.message}`, 'error');
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
            <motion.div 
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.9, opacity: 0 }}
                className="bg-[#121212] border border-white/10 rounded-2xl w-full max-w-md p-6 shadow-2xl"
            >
                <div className="flex justify-between items-center mb-6">
                    <h3 className="text-xl font-bold">Add New Asset</h3>
                    <button onClick={onClose} className="p-1 hover:bg-white/10 rounded-full"><X size={20} /></button>
                </div>

                <div className="flex gap-2 mb-6 p-1 bg-white/5 rounded-lg">
                    <button 
                        onClick={() => setMode('file')}
                        className={`flex-1 py-2 text-sm font-medium rounded-md transition-all flex justify-center items-center gap-2 ${mode === 'file' ? 'bg-secondary text-white' : 'text-muted-foreground'}`}
                    >
                        <Upload size={16} /> File Upload
                    </button>
                    <button 
                        onClick={() => setMode('url')}
                        className={`flex-1 py-2 text-sm font-medium rounded-md transition-all flex justify-center items-center gap-2 ${mode === 'url' ? 'bg-secondary text-white' : 'text-muted-foreground'}`}
                    >
                        <LinkIcon size={16} /> External URL
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-2 text-muted-foreground">Asset Type</label>
                        <div className="flex gap-4">
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input type="radio" checked={type === 'image'} onChange={() => setType('image')} className="accent-primary" />
                                <span>Image</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input type="radio" checked={type === 'video'} onChange={() => setType('video')} className="accent-primary" />
                                <span>Video</span>
                            </label>
                        </div>
                    </div>

                    {mode === 'url' ? (
                        <div>
                            <label className="block text-sm font-medium mb-2 text-muted-foreground">URL</label>
                            <input 
                                value={url} onChange={e => setUrl(e.target.value)}
                                className="w-full bg-black/40 border border-white/10 rounded-lg p-3 text-sm focus:border-primary outline-none"
                                placeholder="https://..."
                                required
                            />
                        </div>
                    ) : (
                        <div>
                             <label className="block text-sm font-medium mb-2 text-muted-foreground">File</label>
                             <div className="border-2 border-dashed border-white/10 rounded-xl p-4 text-center hover:border-white/30 transition-colors relative min-h-[160px] flex flex-col items-center justify-center bg-black/20 overflow-hidden group">
                                <input 
                                    type="file" 
                                    accept={type === 'image' ? "image/*" : "video/*"}
                                    onChange={handleFileChange}
                                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                                />
                                
                                {file ? (
                                    <div className="w-full flex flex-col items-center gap-2">
                                        {previewUrl && type === 'image' && (
                                            <img src={previewUrl} className="h-32 object-contain rounded-md shadow-lg border border-white/10" alt="Preview" />
                                        )}
                                        {previewUrl && type === 'video' && (
                                            <video src={previewUrl} className="h-32 object-contain rounded-md shadow-lg border border-white/10" controls />
                                        )}
                                        
                                        <div className="text-primary font-medium text-sm truncate max-w-full px-4">{file.name}</div>
                                        
                                        {/* Metadata Badge */}
                                        {meta && (
                                            <div className="flex gap-2 text-[10px] text-muted-foreground bg-black/40 px-2 py-1 rounded-full border border-white/5">
                                                <span>{meta.size}</span>
                                                {meta.resolution && <span className="border-l border-white/10 pl-2">{meta.resolution}</span>}
                                                {meta.duration && <span className="border-l border-white/10 pl-2">{meta.duration}</span>}
                                            </div>
                                        )}
                                        
                                        <div className="text-[10px] text-muted-foreground mt-1 group-hover:text-white transition-colors">Click to replace</div>
                                    </div>
                                ) : (
                                    <>
                                        <Upload className="w-8 h-8 text-muted-foreground mb-2 opacity-50" />
                                        <div className="text-muted-foreground text-sm">
                                            Click or drop to select {type}
                                        </div>
                                    </>
                                )}
                             </div>
                        </div>
                    )}

                    <div>
                        <label className="block text-sm font-medium mb-2 text-muted-foreground">Remark (Optional)</label>
                        <textarea 
                            value={remark} onChange={e => setRemark(e.target.value)}
                            className="w-full bg-black/40 border border-white/10 rounded-lg p-3 text-sm focus:border-primary outline-none resize-none h-20"
                            placeholder="Add notes..."
                        />
                    </div>

                    <button 
                        type="submit" 
                        disabled={uploading}
                        className="w-full py-3 bg-primary text-black font-bold rounded-lg hover:bg-primary/90 transition-all disabled:opacity-50 mt-4"
                    >
                        {uploading ? 'Processing...' : 'Add to Library'}
                    </button>
                </form>
            </motion.div>
        </div>
    );
};

const AssetDetailModal = ({ asset, onClose, onUpdate }) => {
    const [remark, setRemark] = useState(asset.remark || '');
    const [isEditing, setIsEditing] = useState(false);

    const handleSave = async () => {
        try {
            await updateAsset(asset.id, { remark });
            setIsEditing(false);
            onUpdate();
        } catch (e) {
            console.error(e);
        }
    };

    return (
         <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-md p-4" onClick={onClose}>
             <motion.div 
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="w-full max-w-5xl h-[80vh] flex bg-[#121212] border border-white/10 rounded-2xl overflow-hidden shadow-2xl"
                onClick={e => e.stopPropagation()}
            >
                {/* Preview Area */}
                <div className="flex-1 bg-black/50 flex items-center justify-center p-8 relative">
                    {asset.type === 'image' ? (
                        <img src={getFullUrl(asset.url)} alt="preview" className="max-w-full max-h-full object-contain rounded-lg shadow-2xl" />
                    ) : (
                        <video src={getFullUrl(asset.url)} controls className="max-w-full max-h-full rounded-lg shadow-2xl" />
                    )}
                    <div className="absolute top-4 left-4 p-2 bg-black/60 backdrop-blur rounded-lg text-xs text-white/50 font-mono">
                        {asset.type.toUpperCase()}
                    </div>
                </div>

                {/* Sidebar Info */}
                <div className="w-80 bg-card border-l border-white/10 p-6 flex flex-col">
                    <div className="flex justify-between items-start mb-6">
                        <h3 className="font-bold text-lg leading-tight break-all">{asset.filename || 'Untitled Asset'}</h3>
                        <button onClick={onClose} className="p-1 hover:bg-white/10 rounded-full ml-2"><X size={20} /></button>
                    </div>

                    <div className="space-y-6 flex-1 overflow-y-auto">
                        <div>
                            <label className="text-xs font-bold text-muted-foreground uppercase mb-2 block">Create Date</label>
                            <p className="text-sm font-mono text-white/80">{new Date(asset.created_at).toLocaleString()}</p>
                        </div>
                        
                        {asset.meta_info && Object.keys(asset.meta_info).length > 0 && (
                             <div>
                                <label className="text-xs font-bold text-muted-foreground uppercase mb-2 block">Metadata</label>
                                <div className="bg-black/30 rounded-lg p-3 space-y-1">
                                    {Object.entries(asset.meta_info).map(([k, v]) => (
                                        <div key={k} className="flex justify-between text-xs">
                                            <span className="text-white/40">{k}:</span>
                                            <span className="font-mono text-white/80">{v}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div>
                            <div className="flex justify-between items-center mb-2">
                                <label className="text-xs font-bold text-muted-foreground uppercase block">Usage Remark</label>
                                {!isEditing && (
                                    <button onClick={() => setIsEditing(true)} className="text-primary hover:text-primary/80"><Edit2 size={12} /></button>
                                )}
                            </div>
                            {isEditing ? (
                                <div className="space-y-2">
                                    <textarea 
                                        value={remark} 
                                        onChange={e => setRemark(e.target.value)}
                                        className="w-full bg-black/20 border border-white/10 rounded p-2 text-sm"
                                        rows={4}
                                    />
                                    <div className="flex gap-2 justify-end">
                                        <button onClick={() => setIsEditing(false)} className="text-xs px-2 py-1 bg-secondary rounded">Cancel</button>
                                        <button onClick={handleSave} className="text-xs px-2 py-1 bg-primary text-black rounded font-bold">Save</button>
                                    </div>
                                </div>
                            ) : (
                                <p className="text-sm text-white/70 italic bg-white/5 p-3 rounded-lg min-h-[4rem]">
                                    {asset.remark || "No remarks added."}
                                </p>
                            )}
                        </div>

                        {asset.type === 'image' && (
                            <div className="pt-6 border-t border-white/10">
                                <label className="text-xs font-bold text-muted-foreground uppercase mb-2 block">AI Modify</label>
                                <div className="text-[10px] text-white/40 mb-2">Original image will be used as reference. Result will be saved as new asset.</div>
                                <RefineControl 
                                    originalText="" 
                                    onUpdate={() => {}} 
                                    currentImage={asset.url}
                                    onImageUpdate={async (url) => {
                                        try {
                                             const res = await fetch(url);
                                             const blob = await res.blob();
                                             const fname = (asset.filename || 'asset').replace(/\.[^/.]+$/, "");
                                             const file = new File([blob], `${fname}_refined.png`, { type: 'image/png' });
                                             await uploadAsset(file);
                                             onUpdate();
                                             alert("Refined version saved as new asset!");
                                        } catch(e) { console.error(e); alert("Failed to save result"); }
                                    }}
                                    type="image"
                                />
                            </div>
                        )}
                        
                        {asset.type === 'image' && (
                             <AnalyzeSection asset={asset} />
                        )}
                    </div>
                </div>
            </motion.div>
         </div>
    );
};

const AnalyzeSection = ({ asset }) => {
    const [analyzing, setAnalyzing] = useState(false);
    const [result, setResult] = useState('');

    const handleAnalyze = async () => {
        setAnalyzing(true);
        try {
            const data = await analyzeAssetImage(asset.id);
            setResult(data.result);
        } catch (e) {
            console.error(e);
            setResult(`Analysis Failed: ${e.message}`);
        } finally {
            setAnalyzing(false);
        }
    };

    const copyToClipboard = () => {
        if (!result) return;
        navigator.clipboard.writeText(result);
        alert("Prompt copied to clipboard!"); 
    };

    return (
        <div className="pt-6 border-t border-white/10 mt-6">
            <div className="flex justify-between items-center mb-3">
                <label className="text-xs font-bold text-muted-foreground uppercase block flex items-center gap-2">
                    <Sparkles size={12} className="text-primary" />
                    Style Analysis
                </label>
                {result && (
                     <button onClick={copyToClipboard} className="text-white/60 hover:text-white" title="Copy">
                        <Copy size={12} />
                     </button>
                )}
            </div>
            
            {!result && !analyzing && (
                <button 
                    onClick={handleAnalyze}
                    className="w-full py-2 bg-secondary/50 border border-white/10 rounded-lg text-xs font-medium hover:bg-secondary hover:text-white transition-colors flex items-center justify-center gap-2"
                >
                    <Sparkles size={14} />
                    Extract Style & Prompt
                </button>
            )}

            {analyzing && (
                <div className="flex items-center justify-center py-4 text-xs text-muted-foreground gap-2">
                    <Loader2 size={14} className="animate-spin text-primary" />
                    Analyzing image...
                </div>
            )}

            {result && (
                <div className="relative group">
                    <p className="text-xs leading-relaxed text-white/80 p-3 bg-black/30 border border-white/5 rounded-lg max-h-40 overflow-y-auto font-mono">
                        {result}
                    </p>
                    <button 
                        onClick={() => setResult('')}
                        className="absolute right-2 top-2 p-1 text-white/20 hover:text-red-400 hidden group-hover:block"
                    >
                        <X size={10} />
                    </button>
                </div>
            )}
        </div>
    );
};

export default AssetsLibrary;
