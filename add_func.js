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
"        } catch (e) {\n" +
"            console.error(e);\n" +
"            setError(e?.response?.data?.detail || e.message || t('单笔对账失败', 'Single Reconcile failed'));\n" +
"        } finally {\n" +
"            setSingleTaskLoading(false);\n" +
"        }\n" +
"    };\n";

const newContent = content.replace('const handleRun = async () => {', singleTaskFunc + '\n    const handleRun = async () => {');
fs.writeFileSync('frontend/src/components/BillingReconcileAdmin.jsx', newContent);
