const fs = require('fs');

let content = fs.readFileSync('frontend/src/components/BillingReconcileAdmin.jsx', 'utf-8');

while (content.indexOf('    const handleRunSingle = async () => {') !== content.lastIndexOf('    const handleRunSingle = async () => {')) {
    const lastIdx = content.lastIndexOf('    const handleRunSingle = async () => {');
    const startOfNext = content.indexOf('    const handleRun = async () => {', lastIdx);
    if (startOfNext > lastIdx) {
        content = content.substring(0, lastIdx) + content.substring(startOfNext);
    } else {
        break; // safety
    }
}

while (content.indexOf('Single Reconcile') !== content.lastIndexOf('Single Reconcile')) {
    const lastIdx = content.lastIndexOf('<div className=\"bg-black/30 border border-white/10 rounded-lg p-3 w-full');
    if (lastIdx !== -1) {
        const startOfNext = content.indexOf('            <div className=\"grid grid-cols-2 md:grid-cols-4 gap-3\">', lastIdx + 10);
        if (startOfNext > lastIdx) {
            content = content.substring(0, lastIdx) + content.substring(startOfNext);
        } else {
            break;
        }
    } else {
        break;
    }
}

while (content.indexOf('const [singleTaskProvider') !== content.lastIndexOf('const [singleTaskProvider')) {
    const lastIdx = content.lastIndexOf('const [singleTaskProvider');
    const nextLineIdx = content.indexOf('\n', lastIdx);
    content = content.substring(0, lastIdx) + content.substring(nextLineIdx + 1);
}
while (content.indexOf('const [singleTaskId') !== content.lastIndexOf('const [singleTaskId')) {
    const lastIdx = content.lastIndexOf('const [singleTaskId');
    const nextLineIdx = content.indexOf('\n', lastIdx);
    content = content.substring(0, lastIdx) + content.substring(nextLineIdx + 1);
}
while (content.indexOf('const [singleTaskLoading') !== content.lastIndexOf('const [singleTaskLoading')) {
    const lastIdx = content.lastIndexOf('const [singleTaskLoading');
    const nextLineIdx = content.indexOf('\n', lastIdx);
    content = content.substring(0, lastIdx) + content.substring(nextLineIdx + 1);
}
while (content.indexOf('const [singleTaskResult') !== content.lastIndexOf('const [singleTaskResult')) {
    const lastIdx = content.lastIndexOf('const [singleTaskResult');
    const nextLineIdx = content.indexOf('\n', lastIdx);
    content = content.substring(0, lastIdx) + content.substring(nextLineIdx + 1);
}


fs.writeFileSync('frontend/src/components/BillingReconcileAdmin.jsx', content);
console.log('done');
