import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('c:\\storyboard\\AIStory\\frontend\\src\\pages\\editor\\projectOptionConfig.js', 'r', encoding='utf-8') as f:
    text = f.read()

index = text.find("Handheld")
if index != -1:
    print(repr(text[max(0, index-200):index+200]))

index2 = text.find("High Quality")
if index2 != -1:
    print(repr(text[max(0, index2-200):index2+200]))

