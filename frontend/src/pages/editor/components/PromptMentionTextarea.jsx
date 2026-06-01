import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Search } from 'lucide-react';
import { getFullUrl, getSafeMediaUrl } from '../editorHelpers';

export const LightweightMentionPicker = ({ isOpen, onClose, entities, uiLang, onSelect, position }) => {
    const [search, setSearch] = useState('');
    const inputRef = useRef(null);

    useEffect(() => {
        if (isOpen) {
            setSearch('');
            setTimeout(() => inputRef.current?.focus(), 10);
            
            const handleEscape = (e) => {
                if (e.key === 'Escape') onClose();
            };
            window.addEventListener('keydown', handleEscape, { capture: true });
            return () => window.removeEventListener('keydown', handleEscape, { capture: true });
        }
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    const filtered = (entities || []).filter(e => {
        if (!search) return true;
        const s = search.toLowerCase();
        return (e.name || '').toLowerCase().includes(s) || 
               (e.name_en || '').toLowerCase().includes(s) ||
               (e.type || '').toLowerCase().includes(s);
    }).slice(0, 50); // limit

    return createPortal(
        <div
            className="fixed z-[9999] bg-[#09090b] border border-white/20 rounded-lg shadow-2xl flex flex-col overflow-hidden w-64"
            style={{
                left: position?.x || 0,
                top: position?.y || 0,
                transform: 'translateY(10px)' // slight offset
            }}
        >
            <div className="p-2 border-b border-white/10 flex items-center gap-2 bg-white/5">
                <Search size={14} className="text-white/50" />
                <input 
                    ref={inputRef}
                    className="bg-transparent border-none text-xs text-white focus:outline-none w-full"
                    placeholder={uiLang === 'cn' ? '搜索实体...' : 'Search entities...'}
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    onKeyDown={e => {
                        if (e.key === 'Enter' && filtered.length > 0) {
                            e.preventDefault();
                            onSelect(filtered[0]);
                        }
                    }}
                />
            </div>
            <div className="max-h-64 overflow-y-auto custom-scrollbar p-1 z-[9999]">
                {filtered.length === 0 ? (
                    <div className="p-3 text-center text-xs text-white/40">
                        {uiLang === 'cn' ? '无匹配实体' : 'No entities found'}
                    </div>
                ) : filtered.map(entity => (
                    <button
                        key={entity.id}
                        className="w-full text-left p-2 hover:bg-white/10 rounded flex items-center gap-2 group transition-colors"
                        onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onSelect(entity);
                        }}
                    >
                        {entity.image_url ? (
                            <img src={getSafeMediaUrl(getFullUrl(entity.image_url))} className="w-6 h-6 rounded object-cover bg-white/5" alt="" />
                        ) : (
                            <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center text-[10px] text-white/50 lowercase">
                                {String(entity.type || '').substring(0, 1)}
                            </div>
                        )}
                        <div className="flex-1 min-w-0">
                            <div className="text-xs font-semibold text-white truncate">{entity.name}</div>
                            <div className="text-[10px] text-white/50 truncate flex justify-between">
                                <span>{entity.type}</span>
                                <span>{entity.name_en}</span>
                            </div>
                        </div>
                    </button>
                ))}
            </div>
        </div>,
        document.body
    );
};

export const PromptMentionTextarea = React.forwardRef(({
    value,
    onChange,
    entities,
    uiLang,
    className,
    placeholder,
    onBlur,
    ...props
}, ref) => {
    const internalRef = useRef(null);
    const resolvedRef = ref || internalRef;
    
    const [pickerOpen, setPickerOpen] = useState(false);
    const [pickerPos, setPickerPos] = useState({ x: 0, y: 0 });

    const handleKeyDown = (e) => {
        // If picker is open, let the user close it with Escape
        if (pickerOpen && e.key === 'Escape') {
            setPickerOpen(false);
            e.preventDefault();
        }
    };

    const handleChange = (e) => {
        const val = e.target.value;
        const selStart = e.target.selectionStart;
        
        // Pass change back to parent immediately
        onChange(e);

        const beforeCursor = val.substring(0, selStart);
        console.log('User typed:', { val, selStart, beforeCursor, lastChar: beforeCursor.slice(-1) });
        // Check if the last character typed was @
        if (beforeCursor.endsWith('@') || beforeCursor.endsWith('\uFF20')) {
            const rect = e.target.getBoundingClientRect();
            console.log('Triggering Mention Picker!', rect);
            // Try to place it near the textarea relative position
            setPickerPos({ x: rect.left, y: rect.bottom });
            setPickerOpen(true);
        } else if (pickerOpen && (!beforeCursor.includes('@') && !beforeCursor.includes('\uFF20'))) {
            // Close if we deleted the @
            setPickerOpen(false);
        }
    };

    const handleSelectEntity = (entity) => {
        if (!entity || !resolvedRef.current) {
            setPickerOpen(false);
            return;
        }

        const typeStr = String(entity.type || '').toLowerCase();
        const name = entity.name || 'Entity';
        
        let mentionTag = '';
        if (typeStr.includes('character') || typeStr.includes('\u89D2\u8272') || typeStr.includes('char')) {
            mentionTag = `CHAR:[@${name}]`;
        } else if (typeStr.includes('env') || typeStr.includes('scene') || typeStr.includes('\u573A\u666F') || typeStr.includes('\u73AF\u5883')) {
            mentionTag = `ENV:[${name}]`;
        } else {
            mentionTag = `PROP:[${name}]`;
        }

        // Get current values
        const currentVal = resolvedRef.current.value || '';
        const cursorPos = resolvedRef.current.selectionStart || 0;

        // Trace back from cursor to find the closest '@' or '＠'
        let insertPosStart = cursorPos;
        while (insertPosStart > 0 && currentVal[insertPosStart - 1] !== '@' && currentVal[insertPosStart - 1] !== '\uFF20') {
            insertPosStart--;
        }
        
        // If we found an '@', `insertPosStart` is just after it, so before the '@' is `insertPosStart - 1`
        let before = '';
        if (insertPosStart > 0) {
            before = currentVal.substring(0, insertPosStart - 1);
        } else {
            // Failsafe, no @ found, just append at cursor
            before = currentVal.substring(0, cursorPos);
        }
        
        const after = currentVal.substring(cursorPos);
        const finalVal = before + mentionTag + " " + after;

        const synthEvent = { 
            target: { 
                value: finalVal,
                name: resolvedRef.current.name
            } 
        };
        onChange(synthEvent);

        setPickerOpen(false);
        
        setTimeout(() => {
            if (resolvedRef.current) {
                resolvedRef.current.focus();
                const newPos = before.length + mentionTag.length + 1;
                resolvedRef.current.setSelectionRange(newPos, newPos);
            }
        }, 10);
    };

    return (
        <>
            <textarea
                ref={resolvedRef}
                value={value}
                onChange={handleChange}
                onKeyDown={handleKeyDown}
                onBlur={onBlur}
                className={className}
                placeholder={placeholder}
                {...props}
            />
            {pickerOpen && (
                <LightweightMentionPicker
                    isOpen={pickerOpen}
                    onClose={() => {
                        setPickerOpen(false);
                        if(resolvedRef.current) {
                            resolvedRef.current.focus();
                        }
                    }}
                    entities={entities}
                    uiLang={uiLang}
                    onSelect={handleSelectEntity}
                    position={pickerPos}
                />
            )}
        </>
    );
});

PromptMentionTextarea.displayName = 'PromptMentionTextarea';

export default PromptMentionTextarea;
