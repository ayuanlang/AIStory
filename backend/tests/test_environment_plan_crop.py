# -*- coding: utf-8 -*-
from app.services.script_analysis_flow.environment_asset_brief import (
    build_environment_asset_design_brief,
)
from app.services.script_analysis_flow.environment_plan_crop import (
    crop_environment_plan_text,
)
from app.services.scene_subskill_pipeline_runner import _main_env_for_staging


_PLAN = """
[SCENE_ENV_IDENT_START:EP01_SC01]
[ENV] 名称=客栈大堂｜复用=否｜来源=新建｜匹配主环境=无｜依据=原文：“大堂”
定位=夜内对峙大厅
目标=本场空镜须=建立压迫｜服务=无｜可见落点=大门
情绪表达=主情绪=压迫｜光色倾向=暖灯
色光规划=本块对标片=英雄｜主冷暖=暖调主导｜主色=琥珀｜依据=夜内大厅
[SCENE_ENV_IDENT_END:EP01_SC01]
[ENV_BLOCK_START]
────【主环境】────
【主环境】客栈大堂｜日夜内外=夜·内｜色光规划=本块对标片=英雄｜光质=灯下
空间大小=档=常｜开间=6.5米｜进深=7.5米｜净高=2.9米｜依据=客栈
正北=0度=封闭面=墙皮｜大门｜依据=剧情明文｜落点=北｜大小=2.0×2.4×0.1｜朝向=南
中部相对=客椅｜参照=方桌｜沿边=长边北侧｜间距=贴身｜朝向=南｜依据=对坐
补光源=堂灯｜补光落点=舞台北沿外
挂靠锚点=柜台｜锚点落=南｜戏用标识=最中心｜空镜=无
【空镜规划】资格=专境
[ENV_BLOCK_END]
"""


def test_asset_keeps_light_and_geometry_and_drops_basis():
    cropped = crop_environment_plan_text(_PLAN, "asset")
    assert "依据=" not in cropped
    assert "色光规划=本块对标片=英雄" in cropped
    assert "光色倾向=暖灯" in cropped
    assert "开间=6.5米" in cropped
    assert "落点=北" in cropped
    assert "间距=贴身" in cropped
    assert "可见落点=大门" in cropped
    assert "补光源=堂灯" in cropped
    assert "挂靠锚点=" not in cropped
    assert "锚点落=" not in cropped
    assert "戏用标识=" not in cropped
    assert "空镜=" not in cropped
    assert "【空镜规划】" not in cropped


def test_staging_keeps_geometry_and_drops_light_and_basis():
    staged = _main_env_for_staging(_PLAN)
    assert "依据=" not in staged
    assert "色光规划=" not in staged
    assert "光色倾向=" not in staged
    assert "光质=" not in staged
    assert "开间=6.5米" in staged
    assert "落点=北" in staged
    assert "朝向=南" in staged
    assert "间距=贴身" in staged
    assert "补光源=堂灯" in staged
    assert "挂靠锚点=柜台" in staged
    assert "客栈大堂" in staged


def test_orchestration_drops_light():
    cropped = crop_environment_plan_text(_PLAN, "orchestration")
    assert "色光规划=" not in cropped
    assert "光色倾向=" not in cropped
    assert "开间=6.5米" in cropped
    assert "依据=" not in cropped


def test_quad_input_keeps_rotatable_keys_and_drops_essays():
    from app.services.script_analysis_flow.environment_quad_input import crop_quad_skill_input

    opening = (
        "【定位】场所风格=书斋｜术语系=无\n"
        "【主体外形】- [@南窗]外形=裱面，材质=宣纸，纹样=竹帘，颜色=牙白。\n"
        "【六面一次】面件数=北1｜动线=门到案｜长边平行=Y线｜交接=墙\n"
        "【南壁】[@南窗]壁关系=窗洞｜透=透｜开闭=全关\n"
        "【光学说明】出光口=南窗｜世界来向=南｜世界射向=北｜色温=3200K｜空气感=清透\n"
        "【色彩说明】主冷暖=暖调主导｜主色=牙白\n"
        "【构图】方法=纵深，倾向=三分留白\n"
    )
    text = f"【主环境设计稿】书斋\n{opening}【/主环境设计稿】"
    cropped = crop_quad_skill_input(text)
    assert "【定位】" not in cropped
    assert "【色彩说明】" not in cropped
    assert "纹样=" not in cropped
    assert "颜色=" not in cropped
    assert "动线=" not in cropped
    assert "交接=" not in cropped
    assert "面件数=" not in cropped
    assert "空气感=" not in cropped
    assert "材质=宣纸" in cropped
    assert "长边平行=Y线" in cropped
    assert "壁关系=窗洞" in cropped
    assert "出光口=南窗" in cropped
    assert "世界来向=南" in cropped
    assert "方法=纵深" in cropped
    assert "【主环境设计稿】书斋" in cropped


def test_asset_brief_drops_basis_and_keeps_light():
    brief = build_environment_asset_design_brief(_PLAN)
    assert "依据=" not in brief
    assert "色光规划=本块对标片=英雄" in brief
    assert "开间=6.5米" in brief
