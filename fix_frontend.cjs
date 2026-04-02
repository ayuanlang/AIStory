const fs = require('fs');
let code = fs.readFileSync('frontend/src/components/FunctionApiConfigTab.jsx', 'utf8');

// 1. Add import
code = code.replace(
    /import \{ getFunctionApiConfigs, updateFunctionApiConfig, getSystemSettingsManage \} from '\.\.\/services\/api';/,
    `import { getFunctionApiConfigs, updateFunctionApiConfig, getSystemSettingsManage, getApiRoutingMode, updateApiRoutingMode } from '../services/api';`
);

// 2. Add state
code = code.replace(
    /const \[isLoading, setIsLoading\] = useState\(true\);/,
    `const [isLoading, setIsLoading] = useState(true);
    const [routingMode, setRoutingMode] = useState(false);`
);

// 3. fetch mode
code = code.replace(
    /                const \[funcData, sysData\] = await Promise\.all\(\[\n                    getFunctionApiConfigs\(\),\n                    getSystemSettingsManage\(\)\n                \]\);/,
    `                const [funcData, sysData, modeData] = await Promise.all([
                    getFunctionApiConfigs(),
                    getSystemSettingsManage(),
                    getApiRoutingMode().catch(() => ({ use_function_based_routing: false }))
                ]);
                setRoutingMode(modeData?.use_function_based_routing || false);`
);

// 4. GUI Element to toggle (Insert before the table or just after the title)
const uiInsert = `
    const toggleRoutingMode = async () => {
        try {
            await updateApiRoutingMode({ use_function_based_routing: !routingMode });
            setRoutingMode(!routingMode);
            showNotification('Routing mode updated!', 'success');
        } catch (e) {
            showNotification('Failed to update routing mode', 'error');
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-white/90">Function API Configurations</h3>
                <label className="flex items-center space-x-2 cursor-pointer bg-white/5 border border-white/10 px-3 py-1.5 rounded text-sm hover:bg-white/10 transition-colors">
                    <input 
                        type="checkbox" 
                        checked={routingMode} 
                        onChange={toggleRoutingMode} 
                        className="form-checkbox text-primary rounded outline-none w-4 h-4" 
                    />
                    <span className="text-white">Enable Function-based API Routing (vs Legacy Category Routing)</span>
                </label>
            </div>
`;

code = code.replace(
    /    return \(\n        <div className="space-y-6">\n            <h3 className="text-lg font-medium text-white\/90">\S+<\/h3>/,
    uiInsert
);

code = code.replace(
    /    return \(\n        <div className="space-y-6">\n            <div>/,
    uiInsert + "\n            <div>"
);

fs.writeFileSync('frontend/src/components/FunctionApiConfigTab.jsx', code, 'utf8');
console.log('Added UI toggle');