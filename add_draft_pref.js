const fs = require('fs');
const path = require('path');
const p = path.join(__dirname, 'frontend/src/services/api.js');
let content = fs.readFileSync(p, 'utf8');
if (!content.includes('DRAFT_MODE_PREF_KEY_PREFIX')) {
content = content.replace(/const AUTO_DOWNLOAD_PREF_KEY_PREFIX = 'aistory.autoDownloadLocal';/,
const AUTO_DOWNLOAD_PREF_KEY_PREFIX = 'aistory.autoDownloadLocal';\nconst DRAFT_MODE_PREF_KEY_PREFIX = 'aistory.draftMode';);
content = content.replace(/auto_download_local: false,/, uto_download_local: false,\n    draft_mode: false,);
content = content.replace(/const autoDownloadPreferenceStorageKey = \(\) => \\:\\;/,
const autoDownloadPreferenceStorageKey = () => \\:\\;\nconst draftModePreferenceStorageKey = () => \\:\\;);

const replacementStr = export const getDraftModePreference = () => {
    const cached = getCachedUserPreferences();
    if (cached && typeof cached.draft_mode === 'boolean') {
        return cached.draft_mode;
    }
    try {
        const raw = localStorage.getItem(draftModePreferenceStorageKey());
        if (raw === '1') return true;
        if (raw === '0') return false;
    } catch {
        // ignore
    }
    return false; // Default to false
};

export const setDraftModePreference = (enabled) => {
    try {
        localStorage.setItem(draftModePreferenceStorageKey(), enabled ? '1' : '0');
        const current = getCachedUserPreferences() || DEFAULT_USER_PREFERENCES;
        setCachedUserPreferences({
            ...current,
            draft_mode: !!enabled,
        });
    } catch {
        // ignore storage failures
    }
};

export const getAutoDownloadLocalPreference = () => {;

content = content.replace(/export const getAutoDownloadLocalPreference = \(\) => {/, replacementStr);
fs.writeFileSync(p, content);
console.log('Added Draft Mode preference exports to api.js');
} else {
console.log('Already added');
}

