import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('frontend/src/pages/editor/projectOptionConfig.js', 'r', encoding='utf-8') as f:
    text = f.read()

index = text.find("???? /")
if index != -1:
    print("Found????/")
    print(repr(text[index-50:index+50]))
else:
    print("No ?")

