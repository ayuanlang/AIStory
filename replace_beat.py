with open('backend/app/core/prompts/skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md', 'r', encoding='utf-8') as f:
    text = f.read()

# Replacement 1
old1 = ÿ�� Beat **ǿ��**�� **`[BEAT_START:{n}]`** ��**`[BEAT_END:{n}]`** ֹ����ֹ��һ�£����������и��������д **- Beat {n}**
new1 = ÿ�� Beat ��֤����Ϊ **`Beat {n}��`** ����
text = text.replace(old1, new1)

# Replacement 2
old2 = ���԰ײ���ж����� `[BEAT_START:{n}]`��`- Beat {n}`��`[BEAT_END:{n}]`��**ÿ Beat ǿ����ֹ�ָ��������������и�**���ڲ����� `�������������á���������` / `������������Ϸ����������` / `����������Beat�л�˵������������` �ֶΣ�
new2 = ���԰ײ���ж����� `Beat {n}��`���ڲ����� `�������������á���������` / `������������Ϸ����������` / `����������Beat�л�˵������������` �ֶΣ�
text = text.replace(old2, new2)

# Replacement 3
old3 = **Beat �ָ�����ǿ�ƣ����������и**��ÿ�� Beat **����**����ֹ��ǰ�ס�������ġ�����`[BEAT_START:{n}]`��ֹ��`[BEAT_END:{n}]`��`{n}` �� `- Beat {n}` ���**���� һ��**����ֹʡ�ԡ���ֹ�� Beat Ƕ�ף������� Beat ֮��ɿ�һ�С�
new3 = **Beat �ָ�����ǿ�ƣ����������и**��ÿ�� Beat ��֤����Ϊ **`Beat {n}��`** ���ɡ����� Beat ֮��ɿ�һ�С�
text = text.replace(old3, new3)

# Replacement 4
old4 = [BEAT_START:{n}]\n- Beat {n}��{��ǩ}��
new4 = Beat {n}����{��ǩ}��
text = text.replace(old4, new4)

# Replacement 5
old5 = [BEAT_END:{n}]
new5 = "
text = text.replace(old5, new5)

with open('backend/app/core/prompts/skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md', 'w', encoding='utf-8') as f:
 f.write(text)

print(Done)
