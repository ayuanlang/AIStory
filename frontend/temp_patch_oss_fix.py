import re

with open('src/pages/UserAdmin.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the block
match = re.search(r"(\{activeTab === 'oss_pools' && \([\s\S]*?\n\s*\)\})", content)
if match:
    oss_block = match.group(1)
    
    # Remove it from its current location
    content = content.replace(oss_block, "/* OSS_BLOCK_PLACEHOLDER */")
    
    # We want to put it right after the supplier_ops block.
    # The supplier_ops block ends somewhere. It's too hard to parse brackets with regex, so I'll just append it right before {activeTab === 'kie_pricing'
    content = content.replace("{activeTab === 'kie_pricing'", oss_block + "\n\n                    {activeTab === 'kie_pricing'")
    
    # clean up the placeholder
    content = content.replace("/* OSS_BLOCK_PLACEHOLDER */", "")
    
    with open('src/pages/UserAdmin.jsx', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Fixed nesting!")
else:
    print("Could not find moss_pools block")

