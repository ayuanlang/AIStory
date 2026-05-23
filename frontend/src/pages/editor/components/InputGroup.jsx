import { useEffect, useRef, useState } from 'react';
import { CheckCircle, ChevronDown } from 'lucide-react';
import { getUiLang, tUI } from '../../../lib/uiLang';

const InputGroup = ({ label, value, onChange, list, placeholder, idPrefix, multi = false, strict = false }) => {
    const [isOpen, setIsOpen] = useState(false);
    const wrapperRef = useRef(null);

    const t = (zh, en) => tUI(getUiLang(), zh, en);

    const getDisplayString = (raw) => {
        if (!raw || typeof raw !== 'string') return raw;
        if (raw.includes(' / ')) {
            const parts = raw.split(' / ');
            // Provide a general rule to parse "Option / 选项"
            return t(parts[0].trim(), parts[1]?.trim() || parts[0].trim());
        }
        return raw;
    };

    const displayValue = () => {
        if (!value) return '';
        if (!multi) return getDisplayString(value);
        return value.split(',').map((s) => getDisplayString(s.trim())).join(', ');
    };

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const isSelected = (opt) => {
        if (!multi) return value === opt;
        const current = (value || '').split(',').map((s) => s.trim());
        return current.includes(opt);
    };

    return (
        <div className="flex flex-col gap-1" ref={wrapperRef}>
            <label className="text-xs text-muted-foreground uppercase font-bold">{label}</label>
            <div className="relative">
                <input
                    className={`bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none w-full ${list && strict ? 'cursor-pointer' : ''}`}
                    value={displayValue()}
                    readOnly={!!list && strict}
                    onChange={(e) => {
                        onChange(e.target.value);
                        if (list) setIsOpen(true);
                    }}
                    onClick={() => {
                        if (list) setIsOpen(!isOpen);
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
                        {list.map((opt) => {
                            const selected = isSelected(opt);
                            return (
                                <div
                                    key={opt}
                                    className={`px-3 py-2 text-sm cursor-pointer flex justify-between items-center ${selected ? 'bg-primary/20 text-primary' : 'text-white hover:bg-white/5'}`}
                                    onClick={() => {
                                        if (multi) {
                                            let current = (value || '').split(',').map((s) => s.trim()).filter(Boolean);
                                            if (current.includes(opt)) {
                                                current = current.filter((c) => c !== opt);
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
                                    <span>{getDisplayString(opt)}</span>
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

export default InputGroup;
