with open('frontend/src/pages/editor/components/ShotsView.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_str = '''    const [activeJob, setActiveJob] = useState(null);'''

new_str = '''    const [activeJob, setActiveJob] = useState(null);
    const isEphemeralProviderMediaUrl = useCallback((url) => {
        const rawUrl = String(url || '').trim();
        if (!rawUrl) return false;
        try {
            const parsed = new URL(rawUrl, window.location.origin);
            return /^file\d+\.aitohumanize\.com$/i.test(String(parsed.hostname || '').trim());
        } catch {
            return false;
        }
    }, []);'''


if old_str in content:
    content = content.replace(old_str, new_str)
    with open('frontend/src/pages/editor/components/ShotsView.jsx', 'w', encoding='utf-8') as f:
        f.write(content)
    print('isEphemeral injected in ShotsView')
else:
    print('Pattern not found')
