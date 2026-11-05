from app.services.shot_markdown import strip_score_cues_from_video_prompt


def test_score_clause_drops_and_sfx_stays():
    raw = (
        "CHAR:[@甲] 右手推开雕花木门，<门轴近处吱呀> 与右手推门同拍，"
        "（低弦缓推）配乐起，音量=弱，质量=温暖，混响空间=短·室内，该人有首登名牌。"
        "人物面部稳定不变形，无背景音乐，无字幕。"
    )
    cleaned = strip_score_cues_from_video_prompt(raw)
    assert "配乐起" not in cleaned
    assert "低弦" not in cleaned
    assert "<门轴近处吱呀>" in cleaned
    assert "无背景音乐，无字幕" in cleaned
    assert "该人有首登名牌" in cleaned


def test_promo_score_sentence_drops():
    raw = (
        "无背景音乐不含已写入的宣传片配乐；运镜与动作流已写的配乐须响亮可闻，音量按上游，禁止压成听不见的垫底。"
        "人物面部稳定不变形，无背景音乐，无字幕。"
    )
    cleaned = strip_score_cues_from_video_prompt(raw)
    assert "配乐响亮可闻" not in cleaned
    assert "宣传片配乐" not in cleaned
    assert "无背景音乐，无字幕" in cleaned


def test_continue_and_change_drop_without_eating_action():
    raw = "他拍桌。配乐变／加压，（低弦加压），音量=强。她起身。"
    cleaned = strip_score_cues_from_video_prompt(raw)
    assert "配乐" not in cleaned
    assert "他拍桌。" in cleaned
    assert "她起身。" in cleaned
