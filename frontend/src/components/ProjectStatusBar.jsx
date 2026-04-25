import React, { useMemo } from 'react';
import { Check, UploadCloud, UserCircle, Coins, ChevronRight, AlertCircle, Circle } from 'lucide-react';

export default function ProjectStatusBar({
  activeTab = 'overview',
  workflowStage = 'script',
  totalProjectCost = 0,
  userCost = 0,
  userBalance = 0,
  t,
  hasAssets = false,
  lensPreference = '',
  videoGenPreference = ''
}) {
  // Mapping active Tab to generalized stages
  const STAGES = useMemo(() => [
    { 
      id: 'script', 
      tabs: ['overview', 'script'], 
      label: t ? t('分析剧本', 'Analyze Script') : '分析剧本',
      tooltip: t ? t('导入并解析故事或长文本，得出整体的场景结构和主体', 'Import and analyze the story to extract scenes and subjects.') : '导入并解析故事，大纲与文本',
    },
    { 
      id: 'assets', 
      tabs: ['roles'], 
      label: t ? t('建立资产', 'Build Assets') : '建立资产',
      tooltip: t ? t('统一设定并生成项目中用到的角色、环境和道具资产', 'Define and generate roles, environments, and props.') : '设定并生成一致的角色、环境与道具库',
      isKeyNode: true, 
      actionHint: t ? t('需上传资产', 'Upload Assets') : '需上传资产', 
      actionDoneHint: t ? t('资产已就绪', 'Assets Ready') : '资产已就绪' 
    },
    { 
      id: 'storyboard', 
      tabs: ['assets', 'videos'], 
      label: t ? t('生成分镜', 'Storyboarding') : '生成分镜',
      tooltip: t ? t('为每场戏和极个别镜头生成画面与视频', 'Generate frames and videos for shots.') : '为每个分镜生成画面与视频段落'
    },
    { 
      id: 'post', 
      tabs: ['post'], 
      label: t ? t('剪辑成片', 'Post Production') : '剪辑成片',
      tooltip: t ? t('合并带有语音、音效的视频片段并最终导出视频', 'Merge video clips and export.') : '合并并导出带音效的最终成片',
    }
  ], [t]);

  const stageIndexMap = { 'script': 0, 'subjects': 1, 'shots': 2, 'montage': 3 };
  const currentStageIndex = stageIndexMap[workflowStage] !== undefined ? stageIndexMap[workflowStage] : Math.max(0, STAGES.findIndex(s => s.tabs.includes(activeTab)));

  return (
    <div className="flex flex-col md:flex-row items-center justify-between px-2 md:px-4 py-1.5 bg-background border-b border-border/50 text-xs shrink-0 relative gap-2 md:gap-0" style={{ minHeight: '32px' }}>
      
      <div className="flex-1 hidden md:block"></div>

      {/* 中心：居中型进度流 */}
      <div className="flex items-center space-x-1 sm:space-x-2 w-full md:w-auto md:absolute md:left-1/2 md:-translate-x-1/2 overflow-x-auto no-scrollbar pb-0">
        {STAGES.map((stage, index) => {
          const isCompleted = index < currentStageIndex;
          const isCurrent = index === currentStageIndex;
          const isPending = index > currentStageIndex;

          return (
            <React.Fragment key={stage.id}>
              <div 
                className={`
                  flex items-center space-x-1 px-2 py-0.5 rounded-sm whitespace-nowrap transition-colors cursor-help group
                  ${isCompleted ? 'text-muted-foreground hover:text-foreground' : ''}
                  ${isCurrent ? 'bg-primary/10 text-primary font-medium' : ''}
                  ${isPending ? 'text-muted-foreground/50 hover:text-muted-foreground' : ''}
                `}
                title={stage.tooltip}
              >
                {isCompleted && <Check className="w-3 h-3 text-green-500" />}
                {isCurrent && <Circle className="w-2.5 h-2.5 fill-primary text-primary animate-pulse" />}
                {isPending && <Circle className="w-2.5 h-2.5 text-muted-foreground/30" />}
                
                <span>{stage.label}</span>

                {stage.id === 'storyboard' && (lensPreference || videoGenPreference) && (
                  <div className="flex items-center space-x-1 ml-1" title={t ? t('项目偏好设置', 'Project Preferences') : '项目偏好设置'}>
                    {lensPreference && (
                      <span className="text-[10px] px-1 bg-purple-500/10 text-purple-500 rounded leading-none py-0.5 border border-purple-500/20">
                        {lensPreference}
                      </span>
                    )}
                    {videoGenPreference && (
                      <span className="text-[10px] px-1 bg-blue-500/10 text-blue-500 rounded leading-none py-0.5 border border-blue-500/20">
                        {videoGenPreference}
                      </span>
                    )}
                  </div>
                )}

                {isCurrent && stage.isKeyNode && hasAssets && (
                  <span className="flex items-center text-[10px] ml-1 px-1 bg-amber-500/20 text-amber-500 rounded leading-none py-0.5">
                    <UploadCloud className="w-2.5 h-2.5 mr-0.5" />
                    {stage.actionHint}
                  </span>
                )}
              </div>

              {index < STAGES.length - 1 && (
                <ChevronRight className="w-3 h-3 text-muted-foreground/30 flex-shrink-0" />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* 右侧：成本微型仪表盘 */}
      <div className="flex justify-center md:flex-1 md:justify-end items-center space-x-3 font-mono opacity-80 hover:opacity-100 transition-opacity w-full md:w-auto h-5">        {/* 当前积分余额 */}
        <div className="flex items-center space-x-1" title={t ? t('当前积分余额', 'Current Point Balance') : '当前积分余额'}>
          <Coins className="w-3.5 h-3.5 text-green-500" />
          <span className="text-green-500 font-medium">{userBalance ? userBalance.toLocaleString() : 0}</span>
        </div>
        {/* 用户消耗 */}
        <div className="flex items-center space-x-1" title={t ? t('我在该项目的消耗', 'My Cost in this Project') : '我的消耗'}>
          <UserCircle className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="text-foreground font-medium">{userCost.toLocaleString()}</span>
        </div>

        {/* 项目总消耗 */}
        <div className="flex items-center space-x-1 bg-amber-500/10 px-1.5 py-0.5 rounded" title={t ? t('项目总消耗', 'Total Project Cost') : '项目总消耗'}>
          <Coins className="w-3.5 h-3.5 text-amber-500" />
          <span className="text-amber-500 font-semibold">{totalProjectCost.toLocaleString()}</span>
        </div>
      </div>
    </div>
  );
}
