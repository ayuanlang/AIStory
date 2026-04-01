import re

with open('src/pages/Editor.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '''            <ProjectStatusBar \n                activeTab={activeTab} \n                workflowStage={project?.global_info?.workflow_stage}\n\n                workflowStage={project?.global_info?.workflow_stage}\n\n                totalProjectCost={project?.total_tokens || 158400}''',
    '''            <ProjectStatusBar \n                activeTab={activeTab} \n                workflowStage={project?.global_info?.workflow_stage}\n                totalProjectCost={project?.total_tokens || 158400}'''
)

with open('src/pages/Editor.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
