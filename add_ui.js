const fs = require('fs');
const content = fs.readFileSync('frontend/src/components/BillingReconcileAdmin.jsx', 'utf-8');

const singleTaskFunc = "    const handleRunSingle = async () => {\n" +
"        if (!singleTaskProvider || !singleTaskId) {\n" +
"            alert(t('填入提供商和任务ID', 'Please fill both provider and task ID'));\n" +
"            return;\n" +
"        }\n" +
"        setSingleTaskLoading(true);\n" +
"        setSingleTaskResult(null);\n" +
"        setError('');\n" +
"        try {\n" +
"            const result = await runAdminBillingReconcileSingle({\n" +
"                provider: singleTaskProvider,\n" +
"                task_id: singleTaskId\n" +
"            });\n" +
"            setSingleTaskResult(result);\n" +
"            fetchCandidates();\n" +
"        } catch (e) {\n" +
"            console.error(e);\n" +
"            setError(e?.response?.data?.detail || e.message || t('单笔对账失败', 'Single Reconcile failed'));\n" +
"        } finally {\n" +
"            setSingleTaskLoading(false);\n" +
"        }\n" +
"    };\n";

const uiPatch = "            <div className=\"bg-black/30 border border-white/10 rounded-lg p-3 w-full\">\n" +
"                <h4 className=\"text-sm font-bold text-gray-200 mb-2\">{t('单笔对账', 'Single Reconcile')}</h4>\n" +
"                <div className=\"flex flex-wrap gap-2 items-center text-xs\">\n" +
"                    <input\n" +
"                        type=\"text\"\n" +
"                        placeholder={t('供应商', 'Provider')}\n" +
"                        value={singleTaskProvider}\n" +
"                        onChange={(e) => setSingleTaskProvider(e.target.value)}\n" +
"                        className=\"bg-black/40 border border-white/10 rounded px-2 py-1 flex-1 min-w-[150px]\"\n" +
"                    />\n" +
"                    <input\n" +
"                        type=\"text\"\n" +
"                        placeholder=\"taskId\"\n" +
"                        value={singleTaskId}\n" +
"                        onChange={(e) => setSingleTaskId(e.target.value)}\n" +
"                        className=\"bg-black/40 border border-white/10 rounded px-2 py-1 flex-1 min-w-[200px]\"\n" +
"                    />\n" +
"                    <button\n" +
"                        onClick={handleRunSingle}\n" +
"                        disabled={singleTaskLoading || !singleTaskProvider || !singleTaskId}\n" +
"                        className=\"bg-cyan-700 hover:bg-cyan-600 text-white px-4 py-1 rounded disabled:opacity-50\"\n" +
"                    >\n" +
"                        {singleTaskLoading ? t('对账中...', '...') : t('执行', 'Run')}\n" +
"                    </button>\n" +
"                </div>\n" +
"                {singleTaskResult && (\n" +
"                    <div className={mt-3 p-2 rounded text-xs }>\n" +
"                        {singleTaskResult.status === 'ok' || singleTaskResult.ok ? t('对账成功: 用量已补齐', 'Success: Usage recorded') : ${t('对账失败', 'Failed')}: }\n" +
"                        {(singleTaskResult.status === 'ok' || singleTaskResult.ok) && singleTaskResult.usage && (\n" +
"                           <div className=\"mt-1 text-[10px] text-gray-500 break-all\">\n" +
"                               {JSON.stringify(singleTaskResult.usage)}\n" +
"                           </div>\n" +
"                        )}\n" +
"                    </div>\n" +
"                )}\n" +
"            </div>\n";

const newContent1 = content.replace('const handleRun = async () => {', singleTaskFunc + '\n    const handleRun = async () => {');
const newContent2 = newContent1.replace(
    /<div className="grid grid-cols-2 md:grid-cols-4 gap-3">/g,
    uiPatch + '\n            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">'
);

fs.writeFileSync('frontend/src/components/BillingReconcileAdmin.jsx', newContent2);
