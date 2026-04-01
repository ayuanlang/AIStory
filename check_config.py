import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('c:\\storyboard\\AIStory\\frontend\\src\\pages\\editor\\projectOptionConfig.js', 'r', encoding='utf-8') as f:
    content = f.read()

index = content.find("PROJECT_EP_TYPE_OPTIONS")
if index != -1:
    print(repr(content[index:index+500]))
