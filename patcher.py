import re

with open('frontend/src/pages/editor/components/SceneManager.jsx', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace(
    'className="bg-primary/90 hover:bg-primary text-black px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 shadow-lg"',
    'className={`${shotsBusy && onStopGenerateShots ? \'bg-red-500/90 hover:bg-red-500 text-white\' : \'bg-primary/90 hover:bg-primary text-black\'} px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 shadow-lg ${shotsBusy && !onStopGenerateShots ? \'opacity-60\' : \'\'}`}'
)

code = code.replace(
    'className="bg-primary/85 hover:bg-primary text-black px-2 py-1.5 rounded text-[11px] font-semibold flex items-center justify-center gap-1 disabled:opacity-60"',
    'className={`${shotsBusy && onStopGenerateShots ? \'bg-red-500/90 hover:bg-red-500 text-white\' : \'bg-primary/85 hover:bg-primary text-black\'} px-2 py-1.5 rounded text-[11px] font-semibold flex items-center justify-center gap-1 ${shotsBusy && !onStopGenerateShots ? \'opacity-60\' : \'\'}`}'
)

code = code.replace(
    "title={t('AI 生成镜头列表', 'AI Generate Shot List')}",
    "title={shotsBusy ? t('停止生成', 'Stop Generating') : t('AI 生成镜头列表', 'AI Generate Shot List')}"
)

code = code.replace(
    '{shotsBusy ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}',
    '{shotsBusy ? (onStopGenerateShots ? <X className="w-3 h-3" /> : <Loader2 className="w-3 h-3 animate-spin"/>) : <Wand2 className="w-3 h-3"/>}'
)

code = code.replace(
    "{shotsBusy ? t('生成中...', 'Generating...') : t('AI 镜头', 'AI Shots')}",
    "{shotsBusy ? (onStopGenerateShots ? t('停止...', 'Stop') : t('生成中...', 'Generating...')) : t('AI 镜头', 'AI Shots')}"
)

with open('frontend/src/pages/editor/components/SceneManager.jsx', 'w', encoding='utf-8') as f:
    f.write(code)
