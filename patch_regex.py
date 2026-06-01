import os
import re

path = 'C:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(
    r'(\s+)phase2GenerationInFlightRef\.current = true;\s+'
    r'setAnalysisFlowStatus\(\{\s+'
    r'phase: "assets_gen",\s+'
    r'message: t\("✨ 正在执行第四阶段资产设计 \(共 3 项并发推演\)\.\.\.", "Running Stage 4 asset design\.\.\."\),\s+'
    r'\}\);\s+'
    r'const targetAssetsCount = 3;\s+'
    r'let assetsGenCompletedCount = 0;\s+'
    r'try \{\s+'
    r'onLog\?\.?\(`\[Stage 3 Asset Design\] Preparing to fetch 3 entity_design prompts`\);\s+'
    r'const promptFiles = \[\s+'
    r'\{ key: \'characters\', path: \'skills/scene_analysis_feature_stack/entity_design_character\.md\' \},\s+'
    r'\{ key: \'environments\', path: \'skills/scene_analysis_feature_stack/entity_design_environment\.md\' \},\s+'
    r'\{ key: \'props\', path: \'skills/scene_analysis_feature_stack/entity_design_prop\.md\' \}\s+'
    r'\]\.filter\(p => !options\.targetEntityTypes \|\| options\.targetEntityTypes\.includes\(p\.key\)\);\s+'
    r'const commonPromptRes = await fetchPrompt\("skills/scene_analysis_feature_stack/entity_design_common\.md"\)\.catch\(\(\) => null\);'
)

match = pattern.search(content)
if match:
    # Build replacement
    indent = match.group(1)
    
    repl = f'''{indent}phase2GenerationInFlightRef.current = true;

{indent}const promptFilesRaw = [
{indent}    {{ key: 'characters', path: 'skills/scene_analysis_feature_stack/entity_design_character.md' }},
{indent}    {{ key: 'environments', path: 'skills/scene_analysis_feature_stack/entity_design_environment.md' }},
{indent}    {{ key: 'props', path: 'skills/scene_analysis_feature_stack/entity_design_prop.md' }}
{indent}];

{indent}let targetFilters = options.targetEntityTypes;
{indent}if (targetFilters && targetFilters.includes('posters') && !targetFilters.includes('environments')) {{
{indent}    targetFilters = [...targetFilters, 'environments'];
{indent}}}

{indent}const promptFiles = promptFilesRaw.filter(p => !targetFilters || targetFilters.includes(p.key));
{indent}const targetAssetsCount = promptFiles.length;

{indent}setAnalysisFlowStatus({{
{indent}    phase: "assets_gen",
{indent}    message: t(`✨ 正在执行第四阶段资产设计 (共 ${{targetAssetsCount}} 项并发推演)...`, `Running Stage 4 asset design (${{targetAssetsCount}} tasks)...`),
{indent}}});

{indent}let assetsGenCompletedCount = 0;

{indent}try {{
{indent}    onLog?.(`[Stage 3 Asset Design] Preparing to fetch ${{targetAssetsCount}} entity_design prompts`);

{indent}    const commonPromptRes = await fetchPrompt("skills/scene_analysis_feature_stack/entity_design_common.md").catch(() => null);'''

    content = content[:match.start()] + repl + content[match.end():]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully replaced with regex.")
else:
    print("Regex not matched!")
