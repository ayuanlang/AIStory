# -*- coding: utf-8 -*-
import re

with open('src/pages/UserAdmin.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add OSS Storage tab
if "{ id: 'oss_pools'" not in content:
    content = re.sub(
        r"(\{\s*id:\s*'supplier_ops'[^}]+})",
        r"\1,\n        { id: 'oss_pools', label: t('OSS 存储配置', 'OSS Storage'), icon: Database }",
        content
    )

# 2. Add triggering log logic
if "activeTab === 'oss_pools'" not in content:
    content = re.sub(
        r"(activeTab === 'system_api' \|\| activeTab === 'pricing_rules' \|\| activeTab === 'supplier_ops')",
        r"activeTab === 'system_api' || activeTab === 'pricing_rules' || activeTab === 'supplier_ops' || activeTab === 'oss_pools'",
        content
    )

    content = re.sub(
        r"(if \(activeTab === 'supplier_ops'\) \{[^}]+\n\s*return;\n\s*\})",
        r"\1\n            if (activeTab === 'oss_pools') {\n                refreshSystemApiAdminViews({\n                    includeSystemApi: true,\n                    includeProviderPools: true,\n                    includeOssPools: true,\n                });\n                return;\n            }",
        content
    )

# 3. Change subtab UI to activeTab UI
content = re.sub(
    r"\{\s*supplierOpsSubtab\s*===\s*'oss_pools'\s*&&\s*\(",
    r"{activeTab === 'oss_pools' && (",
    content
)

# 4. Remove old subtab button
content = re.sub(
    r"<button[^>]*onClick=\{\(\)\s*=>\s*setSupplierOpsSubtab\('oss_pools'\)\}[^>]*>[\s\S]*?</button>",
    r"",
    content
)

with open('src/pages/UserAdmin.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patched successfully')
