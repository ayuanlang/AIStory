const fs = require("fs");
const filepath = "C:/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx";
let content = fs.readFileSync(filepath, "utf8");

content = content.replace(
    "const [llmRawResultContent, setLlmRawResultContent] = useState(\"\\\"\");",
    "const [llmRawResultContent, setLlmRawResultContent] = useState(\"\\\"\");\n    const [llmAssetRawResultContent, setLlmAssetRawResultContent] = useState(\"\\\"\");"
).replace(
    /const \[llmRawResultContent, setLlmRawResultContent\] = useState\('\);/,
    `const [llmRawResultContent, setLlmRawResultContent] = useState("");\n    const [llmAssetRawResultContent, setLlmAssetRawResultContent] = useState("");`
);

content = content.replace(
    "const resultText = response.data?.text || response.data?.message || \"\";",
    "const resultText = response.data?.text || response.data?.message || \"\";\n            setLlmAssetRawResultContent(resultText);"
).replace(
    /const resultText = response\.data\?\.text \|\| response\.data\?\.message \|\| ';/,
    `const resultText = response.data?.text || response.data?.message || "";\n            setLlmAssetRawResultContent(resultText);`
);

content = content.replace(
    /<textarea[\s\S]*?value=\{llmRawResultContent \|\| '\}\s+readOnly\s+\/>/,
    match => match + "\n          <div className=\"px-6 pb-2 pt-6 text-[10px] text-muted-foreground uppercase font-bold tracking-wide border-t border-white/5\">{t(\"设计资产 LLM 原文\", \"Asset Generation Response\")}</div>\n          <textarea\n              className=\"w-full h-44 px-6 pb-6 bg-transparent text-[#bdfada]/70 font-mono text-[11px] leading-relaxed focus:outline-none custom-scrollbar resize-none\"\n              placeholder={t(\"此处显示从 Subject Index 生成设计资产的原始输出。\", \"Asset generation LLM response text shows here.\")}\n              value={llmAssetRawResultContent || \"\"}\n              readOnly\n          />"
);

fs.writeFileSync(filepath, content);
console.log("ScriptEditor modified");

