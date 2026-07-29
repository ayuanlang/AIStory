# -*- coding: utf-8 -*-

with open('frontend/src/components/BillingReconcileAdmin.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# 1. Update imports
text = text.replace(
    'import { getAdminBillingReconcileCandidates, runAdminBillingReconcile } from \'../services/api\';',
    'import { getAdminBillingReconcileCandidates, runAdminBillingReconcile, runAdminBillingReconcileSingle } from \'../services/api\';'
)

# 2. Add State vars
state_vars = '''const [lastResult, setLastResult] = useState(null);
    const [singleTaskProvider, setSingleTaskProvider] = useState("");
    const [singleTaskId, setSingleTaskId] = useState("");
    const [singleTaskLoading, setSingleTaskLoading] = useState(false);
    const [singleTaskResult, setSingleTaskResult] = useState(null);'''

text = text.replace('const [lastResult, setLastResult] = useState(null);', state_vars)

# 3. Add handleRunSingle function before handleRun
func = '''    const handleRunSingle = async () => {
        if (!singleTaskProvider || !singleTaskId) {
            alert(t("填入提供商和任务ID", "Please fill both provider and task ID"));
            return;
        }
        setSingleTaskLoading(true);
        setSingleTaskResult(null);
        setError("");
        try {
            const result = await runAdminBillingReconcileSingle({
                provider: singleTaskProvider,
                task_id: singleTaskId
            });
            setSingleTaskResult(result);
            fetchCandidates();
        } catch (e) {
            console.error(e);
            setError(e?.response?.data?.detail || e.message || t("单笔对账失败", "Single Reconcile failed"));
        } finally {
            setSingleTaskLoading(false);
        }
    };

    const handleRun = async () => {'''
text = text.replace('    const handleRun = async () => {', func)


# 4. Add UI part
ui = '''            <div className="bg-black/30 border border-white/10 rounded-lg p-3 w-full mb-3">
                <h4 className="text-sm font-bold text-gray-200 mb-2">{t("单笔对账", "Single Reconcile")}</h4>
                <div className="flex flex-wrap gap-2 items-center text-xs">
                    <input
                        type="text"
                        placeholder={t("供应商", "Provider")}
                        value={singleTaskProvider}
                        onChange={(e) => setSingleTaskProvider(e.target.value)}
                        className="bg-black/40 border border-white/10 rounded px-2 py-1 flex-1 min-w-[150px]"
                    />
                    <input
                        type="text"
                        placeholder="taskId"
                        value={singleTaskId}
                        onChange={(e) => setSingleTaskId(e.target.value)}
                        className="bg-black/40 border border-white/10 rounded px-2 py-1 flex-1 min-w-[200px]"
                    />
                    <button
                        onClick={handleRunSingle}
                        disabled={singleTaskLoading || !singleTaskProvider || !singleTaskId}
                        className="bg-cyan-700 hover:bg-cyan-600 text-white px-4 py-1 rounded disabled:opacity-50"
                    >
                        {singleTaskLoading ? t("对账中...", "...") : t("执行", "Run")}
                    </button>
                </div>
                {singleTaskResult && (
                    <div className={mt-3 p-2 rounded text-xs }>
                        {singleTaskResult.status === "ok" || singleTaskResult.ok ? t("对账成功: 用量已补齐", "Success: Usage recorded") : ${t("对账失败", "Failed")}: }
                        {(singleTaskResult.status === "ok" || singleTaskResult.ok) && singleTaskResult.usage && (
                           <div className="mt-1 text-[10px] text-gray-500 break-all">
                               {JSON.stringify(singleTaskResult.usage)}
                           </div>
                        )}
                    </div>
                )}
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">'''

text = text.replace('            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">', ui)

with open('frontend/src/components/BillingReconcileAdmin.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
