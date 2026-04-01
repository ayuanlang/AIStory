import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('src/pages/ProjectList.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

index = text.find("import {", text.find("'./editor/projectOptionConfig'") - 1000)
end_index = text.find("} from './editor/projectOptionConfig';", index)

if end_index != -1:
    idx2 = text.rfind("import {", 0, end_index)
    import_block = text[idx2:end_index + 40]
    print(import_block)
else:
    print("Could not find the full block")
