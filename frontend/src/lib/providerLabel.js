export const formatProviderLabel = (provider, providerAlias, options = {}) => {
    const { showCodeWhenAliased = true } = options;
    const providerText = String(provider || '').trim();
    const aliasText = String(providerAlias || '').trim();

    if (aliasText) {
        const sameText = providerText && aliasText.toLowerCase() === providerText.toLowerCase();
        if (showCodeWhenAliased && providerText && !sameText) {
            return `${aliasText} (${providerText})`;
        }
        return aliasText;
    }

    return providerText || '-';
};
