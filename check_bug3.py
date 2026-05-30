import sys, os, re
sys.path.append('backend')
from app.api.endpoints import _append_video_api_ref_mapping

prompt = """项目视觉类型：实拍（真人剧/电影感8K） / Live Action (Live-Action Drama/Cinematic 8K)
电影质感，暗黑奇幻，真人写实仙侠，紧张粗粝；[按时间编排的运镜与动作流] (P1) 镜头在 ENV:[@Servant Room Reverse](broken wooden door, splintered wood, dark night courtyard outside, backlighting) 开启。伴随一声巨响，破旧的木门被猛烈撞开。CHAR:[@Wang You](ordinary young male servant, round face, yellowish skin, messy topknot, earthy-yellow coarse linen outfit, straw sandals) 跌跌撞撞地冲入屋内两步，脚踩在粗糙泥地上，身体疯狂前倾。(P2) 在前景右侧，CHAR:[@Lu Chen Servant Glowing Hand](young male servant, right palm glowing with dark-gold light, tanned skin with dust, coarse grey-brown linen outfit) 立即将左手指甲狠狠掐入发光的右掌心以彻底熄灭光芒，随后迅速将双手扫向背后藏起，身体状态完全退化回 CHAR:[@Lu Chen Servant](young male servant, tanned skin with dust, black hair tied with cloth, coarse grey-brown linen outfit, worn cloth shoes)。CHAR:[@Wang You](ordinary young male servant, round face, yellowish skin, messy topknot, earthy-yellow coarse linen outfit, straw sandals) 止住冲势，低头直视床铺方向并大喊：(P2) {前倾大喊} — Dialogue (CHAR:[@Wang You](ordinary young male servant, round face, yellowish skin, messy topknot, earthy-yellow coarse linen outfit, straw sandals)) (voice_type: 清亮男声, tone: 急促, speed: 快速, volume: 高声): "内门出事了！" — {CHAR:[@Lu Chen Servant](young male servant, tanned skin with dust, black hair tied with cloth, coarse grey-brown linen outfit, worn cloth shoes) 眼神中的杀意瞬间收敛，垂下视线，展现出怯懦顺从的姿态}。镜头停留在这一充满压迫感的高低对峙状态上。"""

refs = ['https://a', 'https://b', 'https://c', 'https://d']
entity_lookup = {
    'wang you': {'entity_type': 'char', 'image_url': 'https://c'},
    'lu chen servant glowing hand': {'entity_type': 'char', 'image_url': 'https://a'},
    'lu chen servant': {'entity_type': 'char', 'image_url': 'https://b'},
    'servant room reverse': {'entity_type': 'env', 'image_url': 'https://d'}
}

result = _append_video_api_ref_mapping(
    prompt=prompt, refs=refs, ref_image_url=None, last_frame_url=None, keyframes=None, reference_video_urls=None,
    entity_lookup=entity_lookup, use_prev_video=False, provider='seedance', model='seedance'
)
print('----RESULT----')
print(result)
