import sys

with open('src/pages/UserAdmin.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. replace tab logic
text = text.replace(
    """if (activeTab === 'system_api' || activeTab === 'pricing_rules' || activeTab === 'supplier_ops') {""",
    """if (activeTab === 'system_api' || activeTab === 'pricing_rules' || activeTab === 'supplier_ops' || activeTab === 'oss_pools') {"""
)
text = text.replace(
    """if (activeTab === 'supplier_ops') {
                refreshSystemApiAdminViews({
                    includeSystemApi: true,
                    includeProviderPools: true,
                    includeOssPools: true,
                });
                return;
            }""",
    """if (activeTab === 'supplier_ops') {
                refreshSystemApiAdminViews({
                    includeSystemApi: true,
                    includeProviderPools: true,
                });
                return;
            }
            if (activeTab === 'oss_pools') {
                refreshSystemApiAdminViews({
                    includeSystemApi: true,
                    includeProviderPools: true,
                    includeOssPools: true,
                });
                return;
            }"""
)

# 2. Add Tab rendering
text = text.replace(
    """{ id: 'supplier_ops', label: t('供应商运营', 'Supplier Ops'), icon: Settings },""",
    """{ id: 'supplier_ops', label: t('供应商运营', 'Supplier Ops'), icon: Settings },
        { id: 'oss_pools', label: t('OSS 存储配置', 'OSS Storage'), icon: Database },"""
)

# 3. Handle icon if needed
if "Database" not in text[:1000] and "HardDrive" in text[:1000]:
    text = text.replace("HardDrive } from", "HardDrive, Database } from")

# 4. Extract {supplierOpsSubtab === 'oss_pools' && ( ... )} block using a bracket counter
start_idx = text.find("{supplierOpsSubtab === 'oss_pools' && (")
if start_idx != -1:
    bracket_count = 0
    in_expr = False
    end_idx = -1
    for i in range(start_idx, len(text)):
        if text[i] == '{':
            bracket_count += 1
            in_expr = True
        elif text[i] == '}':
            bracket_count -= 1
        
        if in_expr and bracket_count == 0:
            end_idx = i + 1
            break
            
    if end_idx != -1:
        oss_block = text[start_idx:end_idx]
        
        # We need to remove the button for supplierOpsSubtab('oss_pools')
        btn_start = text.find("<button\n                                    onClick={() => setSupplierOpsSubtab('oss_pools')}")
        if btn_start == -1:
            btn_start = text.find("setSupplierOpsSubtab('oss_pools')")
            # expand to nearest <button ...> and </button>
            b_s = text.rfind("<button", 0, btn_start)
            b_e = text.find("</button>", btn_start) + 9
            text = text[:b_s] + text[b_e:]
            
        # Update start_idx, end_idx since text length changed
        start_idx = text.find("{supplierOpsSubtab === 'oss_pools' && (")
        bracket_count = 0
        in_expr = False
        end_idx = -1
        for i in range(start_idx, len(text)):
            if text[i] == '{':
                bracket_count += 1
                in_expr = True
            elif text[i] == '}':
                bracket_count -= 1
            if in_expr and bracket_count == 0:
                end_idx = i + 1
                break
                
        oss_block = text[start_idx:end_idx]
        text = text[:start_idx] + text[end_idx:]
        
        # Change subtab to activeTab
        oss_block = oss_block.replace("supplierOpsSubtab === 'oss_pools'", "activeTab === 'oss_pools'")
        
        # Add it right before {activeTab === 'kie_pricing'
        kie_idx = text.find("{activeTab === 'kie_pricing' && (")
        text = text[:kie_idx] + oss_block + "\n\n                    " + text[kie_idx:]
        
        with open('src/pages/UserAdmin.jsx', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Success extracting")
    else:
        print("Could not find end of block")
else:
    print("Could not find start idx")
