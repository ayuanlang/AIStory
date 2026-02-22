import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';

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

export default MarkdownCell;
