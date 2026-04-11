import re

with open('frontend/src/components/AssetsLibrary.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. State definitions
text = text.replace(
    'const [referencedIds, setReferencedIds] = useState(new Set());',
    'const [referencedIds, setReferencedIds] = useState(new Set());\n    const [isSourceIds, setIsSourceIds] = useState(new Set());\n    const [isDependentIds, setIsDependentIds] = useState(new Set());'
)

# 2. Dependency updates
text = text.replace(
    'setReferencedIds(new Set(data.referenced_ids || []));',
    'setReferencedIds(new Set(data.referenced_ids || []));\n            setIsSourceIds(new Set(data.is_source_ids || []));\n            setIsDependentIds(new Set(data.is_dependent_ids || []));'
)

# 3. AssetItem prop passage
text = re.sub(
    r'(<AssetItem\s+key=\{item\.id\}\s+item=\{item\}\s+onClick=\{[^}]+\}\s+viewMode=\{viewMode\}\s+isSelected=\{[^}]+\}\s+onSelect=\{[^}]+\}\s+isReferenced=\{)referencedIds\.has\(item\.id\)(\})',
    r'\g<1>referencedIds.has(item.id)\g<2>\n                                isSource={isSourceIds.has(item.id)}\n                                isDependent={isDependentIds.has(item.id)}',
    text
)

# 4. AssetItem definition
text = text.replace(
    'const AssetItem = ({ item, onClick, viewMode, isSelected, onSelect, isReferenced }) => {',
    'const AssetItem = ({ item, onClick, viewMode, isSelected, onSelect, isReferenced, isSource, isDependent }) => {'
)

# 5. UI rendering
old_ui = '''            {isReferenced && (
                <div 
                    className="absolute top-2 left-2 px-2 py-1 rounded bg-blue-500/80 text-white text-xs font-medium z-10"
                    title="被引用"
                >
                    REF
                </div>
            )}'''
new_ui = '''            <div className="absolute top-2 left-2 flex flex-col gap-1 z-10">
                {isReferenced && (
                    <div className="px-2 py-1 rounded bg-blue-500/80 text-white text-xs font-medium" title="被引用">REF</div>
                )}
                {isSource && (
                    <div className="px-2 py-1 rounded bg-green-500/80 text-white text-xs font-medium" title="被依赖">SRC</div>
                )}
                {isDependent && (
                    <div className="px-2 py-1 rounded bg-purple-500/80 text-white text-xs font-medium" title="有依赖">DER</div>
                )}
            </div>'''
text = text.replace(old_ui, new_ui)

with open('frontend/src/components/AssetsLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
