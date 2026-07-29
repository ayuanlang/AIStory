const fs = require('fs');
let content = fs.readFileSync('backend/app/api/billing_reconcile_admin.py', 'utf-8');

content = content.replace(
    '        log_action(',
    '    log_action('
);

fs.writeFileSync('backend/app/api/billing_reconcile_admin.py', content);
