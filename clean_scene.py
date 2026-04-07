import sys

with open('backend/app/core/prompts/scene_analysis.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# I will write a script to intelligently clean up repeated mandatory/hard rules 
# in the JSON schema templates and examples 

clean = content
clean = clean.replace('（必须以数字标点或括号包围）', '')
clean = clean.replace('（禁止写成“看镜头/看我”）', '')
clean = clean.replace('（禁止纯动作罗列）', '')
clean = clean.replace('（必须符合全景/中景/特写/高级运镜等闭环要求）', '')
clean = clean.replace('（必须符合上文的黄金比例、女性体态优先级与服饰去平庸规则）', '')
clean = clean.replace('（必须符合正反反向、成对事物明确及所有安全规则）', '')
clean = clean.replace('（禁止任何角色词，仅描述物理空间与光照，如“... OTS_A”）', '')
clean = clean.replace('（禁止省略，必须逐条输出全量主体）', '')
clean = clean.replace('（四宫格严苛强制，只允许4个画面，第1格必须是面部特写）', '')
clean = clean.replace('（四视图严苛强制，只允许4个画面，第1格必须是微距/局部特写）', '')
clean = clean.replace('（必须符合前文的真实物理空间、去人物化与最高审美原则）', '')

with open('backend/app/core/prompts/scene_analysis.txt', 'w', encoding='utf-8') as f:
    f.write(clean)

print("Cleaned up repetitive comments inside templates.")
