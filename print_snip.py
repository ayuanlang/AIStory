import sys

with open("frontend/src/pages/ProjectList.jsx", "r", encoding="utf-8") as f:
    text = f.read()

def print_snip(idx, label):
    if idx == -1: return
    start = max(0, idx - 100)
    end = min(len(text), idx + 800)
    print(f"--- {label} ---")
    print(text[start:end])

print_snip(text.find("共享与审核（可选）"), "Old Share Block")
print_snip(text.find("场景分析全局维度预设"), "Old Scene Analysis Block")
print_snip(text.find("项目协作与管理"), "New Management Block")
print_snip(text.find("人员权限与分享"), "Collaborators Block")

