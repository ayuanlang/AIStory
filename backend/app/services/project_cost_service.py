import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from datetime import datetime

_cost_log = logging.getLogger("project_cost_estimation")
_cost_log.setLevel(logging.WARNING)


_DEFAULT_PROJECT_COST_ESTIMATION_CONFIG: Dict[str, Any] = {
	"version": 1,
	"overview": {
		"word_rate": 0.012,
	},
	"suggested": {
		"base_scene_point": 1.0,
		"role_complexity": 1.0,
		"env_complexity": 0.8,
		"prop_complexity": 0.5,
		"entity_tier_ratios": {
			"tier1_max": 3,
			"tier2_max": 6,
			"tier3_max": 9,
			"tier1_factor": 1.0,
			"tier2_factor": 1.2,
			"tier3_factor": 1.5,
			"tier4_factor": 1.8,
		},
	},
	"budget": {
		"shot_unit_rate": 1.0,
		"duration_weight": 1.0,
		"asset_weight": 0.8,
	},
	"project_multiplier": {
		"default_factor": 1.0,
		"field_factors": {},
	},
	"dimension_rules": {
		"user_requirements": {
			"creativity": {
				"高": 1.12,
				"中": 1.0,
				"低": 0.92,
				"__default__": 1.0,
			},
			"video_generation_preference": {
				"质感优先": 1.1,
				"平衡": 1.0,
				"速度优先": 0.92,
				"__default__": 1.0,
			},
			"has_existing_assets": {
				"true": 0.9,
				"false": 1.08,
				"__default__": 1.0,
			},
			"notes_word_count_tiers": [
				{"min": 0, "max": 40, "factor": 1.0},
				{"min": 40, "max": 120, "factor": 1.05},
				{"min": 120, "max": 300, "factor": 1.1},
				{"min": 300, "max": None, "factor": 1.16},
			],
		},
		"script_complexity": {
			"word_count_tiers": [
				{"min": 0, "max": 3000, "factor": 0.9},
				{"min": 3000, "max": 8000, "factor": 1.0},
				{"min": 8000, "max": 15000, "factor": 1.12},
				{"min": 15000, "max": None, "factor": 1.25},
			],
			"scene_asset_density_tiers": [
				{"min": 0, "max": 3, "factor": 0.92},
				{"min": 3, "max": 6, "factor": 1.0},
				{"min": 6, "max": 10, "factor": 1.1},
				{"min": 10, "max": None, "factor": 1.2},
			],
			"shot_asset_density_tiers": [
				{"min": 0, "max": 2, "factor": 0.9},
				{"min": 2, "max": 4, "factor": 1.0},
				{"min": 4, "max": 7, "factor": 1.1},
				{"min": 7, "max": None, "factor": 1.2},
			],
		},
		"output_duration": {
			"expected_duration_seconds_tiers": [
				{"min": 0, "max": 60, "factor": 0.9},
				{"min": 60, "max": 300, "factor": 1.0},
				{"min": 300, "max": 900, "factor": 1.12},
				{"min": 900, "max": None, "factor": 1.25},
			],
			"episode_count_tiers": [
				{"min": 0, "max": 1, "factor": 0.95},
				{"min": 1, "max": 6, "factor": 1.0},
				{"min": 6, "max": 12, "factor": 1.08},
				{"min": 12, "max": None, "factor": 1.18},
			],
		},
		"quality_requirements": {
			"quality": {
				"超高 / Ultra High": 1.18,
				"高 / High": 1.08,
				"中 / Medium": 1.0,
				"低 / Low": 0.9,
				"草稿 / Draft": 0.82,
				"__default__": 1.0,
			},
			"resolution_pixels_tiers": [
				{"min": 0, "max": 921600, "factor": 0.92},
				{"min": 921600, "max": 2073600, "factor": 1.0},
				{"min": 2073600, "max": 8294400, "factor": 1.12},
				{"min": 8294400, "max": None, "factor": 1.25},
			],
			"frame_rate_tiers": [
				{"min": 0, "max": 24, "factor": 0.96},
				{"min": 24, "max": 30, "factor": 1.0},
				{"min": 30, "max": 60, "factor": 1.08},
				{"min": 60, "max": None, "factor": 1.16},
			],
			"style_count_tiers": [
				{"min": 0, "max": 1, "factor": 0.96},
				{"min": 1, "max": 3, "factor": 1.0},
				{"min": 3, "max": 6, "factor": 1.08},
				{"min": 6, "max": None, "factor": 1.14},
			],
		},
		"project_management": {
			"deadline_days_tiers": [
				{"min": -9999, "max": 7, "factor": 1.3},
				{"min": 7, "max": 14, "factor": 1.2},
				{"min": 14, "max": 30, "factor": 1.1},
				{"min": 30, "max": 9999, "factor": 1.0},
			],
			"reviewer_count_tiers": [
				{"min": 0, "max": 0, "factor": 1.0},
				{"min": 1, "max": 2, "factor": 1.05},
				{"min": 2, "max": 5, "factor": 1.1},
				{"min": 5, "max": None, "factor": 1.16},
			],
			"collaboration_count_tiers": [
				{"min": 0, "max": 2, "factor": 1.0},
				{"min": 2, "max": 5, "factor": 1.05},
				{"min": 5, "max": 10, "factor": 1.12},
				{"min": 10, "max": None, "factor": 1.2},
			],
			"broadcast_safety_level": {
				"S": 1.12,
				"A": 1.08,
				"B": 1.0,
				"C": 0.92,
				"__default__": 1.0,
			},
		},
	},
	"project_create_options": {
		"type": [
			"实拍（真人剧/电影感8K） / Live Action (Live-Action Drama/Cinematic 8K)",
			"二维动画 / 2D Animation",
			"三维动画 / 3D Animation",
			"定格动画 / Stop Motion",
			"特摄 / Tokusatsu",
			"舞台剧 / Stage Play",
			"CG动画 / CG Animation",
			"混合媒介 / Mixed Media",
			"纪录片 / Documentary",
			"商品宣传 / Product Promotion",
			"文旅宣传 / Cultural Tourism Promotion",
			"企业宣传 / Corporate Promotion",
		],
		"country_region": [
			"欧美 / Europe & America",
			"中国 / China",
			"日韩 / Japan & Korea",
			"泛亚 / Pan-Asia",
			"全球通用 / Global",
			"其他 / Other",
		],
		"language": [
			"中文 / Chinese",
			"英文 / English",
			"中英双语 / Bilingual (CN/EN)",
			"日语 / Japanese",
			"韩语 / Korean",
			"法语 / French",
			"西班牙语 / Spanish",
			"德语 / German",
			"其他 / Other",
		],
		"base_positioning": [
			"短剧快节奏 / Short Drama",
			"动作片 / Action Feature",
			"爱情情感 / Romance / Emotional",
			"悬疑惊悚 / Mystery / Thriller",
			"喜剧轻快 / Comedy / Light",
			"仙侠奇幻 / Xianxia / Fantasy",
			"青春成长 / Youth Coming-of-Age",
			"通用连续剧 / General Series",
			"都市情感 / Urban Romance",
			"科幻冒险 / Sci-Fi Adventure",
			"古装武侠 / Period / Wuxia",
			"仙侠修真 / Xianxia",
			"穿越 / Transmigration",
			"奇幻史诗 / Fantasy Epic",
			"现代职场 / Modern Workplace",
			"校园青春 / High School / Youth",
			"赛博朋克 / Cyberpunk",
			"恐怖 / Horror",
			"喜剧 / Comedy",
			"剧情 / Drama",
			"动作 / Action",
			"历史 / Historical",
		],
		"aspect_ratio": ["16:9", "2.35:1", "4:3", "9:16", "1:1"],
		"image_size": ["0.5K", "1K", "2K", "4K"],
		"era": ["当代", "近未来", "民国近代", "古代", "架空时代"],
		"season_occurrence": ["不限制 / No Limit", "春 / Spring", "夏 / Summer", "秋 / Autumn", "冬 / Winter", "全年 / All Seasons"],
		"lens_preference": ["长镜头 / Long Take", "中景 / Medium Shot", "特写 / Close-up"],
		"broadcast_safety_level": ["S", "A", "B", "C"],
		"video_generation_preference": ["质感优先", "速度优先", "平衡"],
		"creativity": ["低", "中", "高"],
		"resolution": ["720x1280", "1080x1920", "2160x3840"],
		"color_tone": ["冷色调 / Cool", "暖色调 / Warm", "中性色调 / Neutral"],
		"global_style": ["写实电影感", "动漫", "纪实", "广告风"],
		"lighting": ["自然光 / Natural Light", "电影光效 / Cinematic", "低调光 / Low Key"],
	},
}


def default_project_cost_estimation_config() -> Dict[str, Any]:
	return {
		"version": int(_DEFAULT_PROJECT_COST_ESTIMATION_CONFIG["version"]),
		"overview": dict(_DEFAULT_PROJECT_COST_ESTIMATION_CONFIG["overview"]),
		"suggested": dict(_DEFAULT_PROJECT_COST_ESTIMATION_CONFIG["suggested"]),
		"budget": dict(_DEFAULT_PROJECT_COST_ESTIMATION_CONFIG["budget"]),
		"project_multiplier": {
			"default_factor": float(_DEFAULT_PROJECT_COST_ESTIMATION_CONFIG["project_multiplier"]["default_factor"]),
			"field_factors": dict(_DEFAULT_PROJECT_COST_ESTIMATION_CONFIG["project_multiplier"]["field_factors"]),
		},
		"dimension_rules": _safe_dict(_DEFAULT_PROJECT_COST_ESTIMATION_CONFIG.get("dimension_rules")),
		"project_create_options": {
			key: list(values)
			for key, values in (
				_DEFAULT_PROJECT_COST_ESTIMATION_CONFIG.get("project_create_options") or {}
			).items()
		},
	}


def _safe_float(value: Any, fallback: float) -> float:
	try:
		parsed = float(value)
		if parsed != parsed:
			return float(fallback)
		return parsed
	except Exception:
		return float(fallback)


def _safe_int(value: Any, fallback: int) -> int:
	try:
		return int(value)
	except Exception:
		return int(fallback)


def _normalize_option_list(values: Any, fallback: Iterable[str]) -> List[str]:
	raw = values if isinstance(values, list) else list(fallback)
	seen = set()
	out: List[str] = []
	for item in raw:
		text = str(item or "").strip()
		if not text or text in seen:
			continue
		seen.add(text)
		out.append(text)
	return out


def normalize_project_cost_estimation_config(value: Any) -> Dict[str, Any]:
	base = default_project_cost_estimation_config()
	payload = value if isinstance(value, dict) else {}

	overview = payload.get("overview") if isinstance(payload.get("overview"), dict) else {}
	has_suggested = isinstance(payload.get("suggested"), dict)
	suggested = payload.get("suggested") if has_suggested else (payload.get("budget") if isinstance(payload.get("budget"), dict) else {})
	budget = payload.get("budget") if has_suggested else (payload.get("execution") if isinstance(payload.get("execution"), dict) else {})
	multiplier = payload.get("project_multiplier") if isinstance(payload.get("project_multiplier"), dict) else {}

	base["overview"]["word_rate"] = max(0.0, _safe_float(overview.get("word_rate"), base["overview"]["word_rate"]))

	# New per-scene formula params for suggested stage
	base["suggested"]["base_scene_point"] = max(0.0, _safe_float(suggested.get("base_scene_point"), base["suggested"]["base_scene_point"]))
	base["suggested"]["role_complexity"] = max(0.0, _safe_float(suggested.get("role_complexity"), base["suggested"]["role_complexity"]))
	base["suggested"]["env_complexity"] = max(0.0, _safe_float(suggested.get("env_complexity"), base["suggested"]["env_complexity"]))
	base["suggested"]["prop_complexity"] = max(0.0, _safe_float(suggested.get("prop_complexity"), base["suggested"]["prop_complexity"]))
	incoming_tiers = suggested.get("entity_tier_ratios") if isinstance(suggested.get("entity_tier_ratios"), dict) else {}
	default_tiers = base["suggested"]["entity_tier_ratios"]
	base["suggested"]["entity_tier_ratios"] = {
		"tier1_max": max(1, _safe_int(incoming_tiers.get("tier1_max"), default_tiers["tier1_max"])),
		"tier2_max": max(1, _safe_int(incoming_tiers.get("tier2_max"), default_tiers["tier2_max"])),
		"tier3_max": max(1, _safe_int(incoming_tiers.get("tier3_max"), default_tiers["tier3_max"])),
		"tier1_factor": max(0.0, _safe_float(incoming_tiers.get("tier1_factor"), default_tiers["tier1_factor"])),
		"tier2_factor": max(0.0, _safe_float(incoming_tiers.get("tier2_factor"), default_tiers["tier2_factor"])),
		"tier3_factor": max(0.0, _safe_float(incoming_tiers.get("tier3_factor"), default_tiers["tier3_factor"])),
		"tier4_factor": max(0.0, _safe_float(incoming_tiers.get("tier4_factor"), default_tiers["tier4_factor"])),
	}
	# Legacy compat: old suggested config fields are ignored silently

	base["budget"]["shot_unit_rate"] = max(0.0, _safe_float(budget.get("shot_unit_rate"), base["budget"]["shot_unit_rate"]))
	base["budget"]["duration_weight"] = max(0.0, _safe_float(budget.get("duration_weight"), base["budget"]["duration_weight"]))
	base["budget"]["asset_weight"] = max(0.0, _safe_float(budget.get("asset_weight"), base["budget"]["asset_weight"]))

	base["project_multiplier"]["default_factor"] = max(
		0.0,
		_safe_float(multiplier.get("default_factor"), base["project_multiplier"]["default_factor"]),
	)
	field_factors = multiplier.get("field_factors") if isinstance(multiplier.get("field_factors"), dict) else {}
	normalized_field_factors: Dict[str, Dict[str, float]] = {}
	for field_name, mapping in field_factors.items():
		field_key = str(field_name or "").strip()
		if not field_key or not isinstance(mapping, dict):
			continue
		normalized_mapping: Dict[str, float] = {}
		for option_value, factor_value in mapping.items():
			option_key = str(option_value or "").strip()
			if not option_key:
				continue
			normalized_mapping[option_key] = max(0.0, _safe_float(factor_value, 1.0))
		if normalized_mapping:
			normalized_field_factors[field_key] = normalized_mapping
	base["project_multiplier"]["field_factors"] = normalized_field_factors
	base["dimension_rules"] = _safe_dict(payload.get("dimension_rules") or base.get("dimension_rules") or {})

	incoming_options = payload.get("project_create_options") if isinstance(payload.get("project_create_options"), dict) else {}
	merged_options: Dict[str, List[str]] = {}
	for dim, defaults in (base.get("project_create_options") or {}).items():
		merged_options[dim] = _normalize_option_list(incoming_options.get(dim), defaults)
	for dim, custom_values in incoming_options.items():
		dim_key = str(dim or "").strip()
		if not dim_key or dim_key in merged_options:
			continue
		merged_options[dim_key] = _normalize_option_list(custom_values, [])
	base["project_create_options"] = merged_options
	return base


def extract_project_create_options(config: Dict[str, Any]) -> Dict[str, List[str]]:
	cfg = normalize_project_cost_estimation_config(config)
	return dict(cfg.get("project_create_options") or {})


def _safe_dict(value: Any) -> Dict[str, Any]:
	return value if isinstance(value, dict) else {}


def _flatten_project_info(global_info: Dict[str, Any]) -> Dict[str, str]:
	src = _safe_dict(global_info)
	out: Dict[str, str] = {}

	def put(key: str, value: Any):
		text = str(value or "").strip()
		if text:
			out[key] = text

	for k, v in src.items():
		if isinstance(v, (str, int, float, bool)):
			put(k, v)

	basic_info = _safe_dict(src.get("basic_info"))
	for k, v in basic_info.items():
		put(f"basic_info.{k}", v)

	tech_params = _safe_dict(src.get("tech_params"))
	visual = _safe_dict(tech_params.get("visual_standard"))
	for k, v in visual.items():
		put(f"tech_params.visual_standard.{k}", v)
		put(k, v)

	defaults = _safe_dict(src.get("project_generation_defaults"))
	for k, v in defaults.items():
		if isinstance(v, (str, int, float, bool)):
			put(f"project_generation_defaults.{k}", v)
			put(k, v)

	return out


def _count_words(text: Any) -> int:
	stable = str(text or "")
	if not stable.strip():
		return 0
	ascii_words = re.findall(r"[A-Za-z0-9_]+", stable)
	cjk_chars = re.findall(r"[\u4e00-\u9fff]", stable)
	return len(ascii_words) + len(cjk_chars)


def _parse_duration_seconds(value: Any) -> float:
	text = str(value or "").strip().lower()
	if not text:
		return 0.0
	text = text.replace("秒", "s")
	range_match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)?\s*$", text)
	if range_match:
		start = _safe_float(range_match.group(1), 0.0)
		end = _safe_float(range_match.group(2), 0.0)
		return max(0.0, (start + end) / 2.0)

	number_match = re.search(r"\d+(?:\.\d+)?", text)
	if not number_match:
		return 0.0
	return max(0.0, _safe_float(number_match.group(0), 0.0))


def _parse_bool(value: Any) -> Optional[bool]:
	if isinstance(value, bool):
		return value
	text = str(value or "").strip().lower()
	if text in {"true", "1", "yes", "y", "on"}:
		return True
	if text in {"false", "0", "no", "n", "off"}:
		return False
	return None


def _resolve_tier_factor(value: float, tiers: Any, default_factor: float = 1.0) -> float:
	if not isinstance(tiers, list):
		return float(default_factor)
	numeric = float(value)
	for tier in tiers:
		if not isinstance(tier, dict):
			continue
		min_v = tier.get("min", None)
		max_v = tier.get("max", None)
		min_ok = True if min_v is None else numeric >= float(_safe_float(min_v, numeric))
		max_ok = True if max_v is None else numeric < float(_safe_float(max_v, numeric + 1))
		if min_ok and max_ok:
			return max(0.0, _safe_float(tier.get("factor", default_factor), default_factor))
	return float(default_factor)


def _parse_resolution_pixels(global_info: Dict[str, Any]) -> int:
	src = _safe_dict(global_info)
	tech = _safe_dict(src.get("tech_params"))
	visual = _safe_dict(tech.get("visual_standard"))
	w = _safe_int(visual.get("horizontal_resolution"), 0)
	h = _safe_int(visual.get("vertical_resolution"), 0)
	if w > 0 and h > 0:
		return int(w * h)
	return 0


def _parse_expected_duration(global_info: Dict[str, Any]) -> int:
	src = _safe_dict(global_info)
	raw = src.get("expected_duration") or src.get("duration") or ""
	val = _parse_duration_seconds(raw)
	return int(max(0, round(val)))


def _parse_multi_value_count(value: Any) -> int:
	if isinstance(value, list):
		return len([x for x in value if str(x or "").strip()])
	text = str(value or "").strip()
	if not text:
		return 0
	normalized = re.sub(r"[，、；;\n\r]+", ",", text)
	parts = [str(x).strip() for x in normalized.split(",")]
	return len([x for x in parts if x])


def _safe_entity_id(value: Any) -> Optional[int]:
	try:
		parsed = int(value)
		if parsed <= 0:
			return None
		return parsed
	except Exception:
		return None


def _resolve_entity_tier_ratio(entity_total: int, tier_cfg: Dict[str, Any]) -> float:
	"""Return the entity-count tier ratio for the per-scene suggested cost formula.
	Tier boundaries (inclusive upper): tier1_max, tier2_max, tier3_max, else tier4.
	"""
	t1 = max(1, _safe_int(tier_cfg.get("tier1_max"), 3))
	t2 = max(t1 + 1, _safe_int(tier_cfg.get("tier2_max"), 6))
	t3 = max(t2 + 1, _safe_int(tier_cfg.get("tier3_max"), 9))
	f1 = max(0.0, _safe_float(tier_cfg.get("tier1_factor"), 1.0))
	f2 = max(0.0, _safe_float(tier_cfg.get("tier2_factor"), 1.2))
	f3 = max(0.0, _safe_float(tier_cfg.get("tier3_factor"), 1.5))
	f4 = max(0.0, _safe_float(tier_cfg.get("tier4_factor"), 1.8))
	n = max(0, int(entity_total))
	if n <= t1:
		return f1
	if n <= t2:
		return f2
	if n <= t3:
		return f3
	return f4


def _compute_scene_suggested_cost(
	scene_row: Any,
	suggested_cfg: Dict[str, Any],
	project_info_multiplier: float,
) -> float:
	"""Compute per-scene suggested cost.
	Formula:
	  duration * base_scene_point
	    * ( (role_count - 1) * role_complexity
	      + (env_count - 1)  * env_complexity
	      + (prop_count - 1) * prop_complexity )
	    * entity_tier_ratio(total_entity_count)
	    * project_info_multiplier
	"""
	duration = _parse_duration_seconds(getattr(scene_row, "equivalent_duration", None))
	base_scene_point = max(0.0, _safe_float(suggested_cfg.get("base_scene_point"), 1.0))
	role_complexity = max(0.0, _safe_float(suggested_cfg.get("role_complexity"), 1.0))
	env_complexity = max(0.0, _safe_float(suggested_cfg.get("env_complexity"), 0.8))
	prop_complexity = max(0.0, _safe_float(suggested_cfg.get("prop_complexity"), 0.5))
	tier_cfg = suggested_cfg.get("entity_tier_ratios") if isinstance(suggested_cfg.get("entity_tier_ratios"), dict) else {}

	role_count = max(1, _count_assets(getattr(scene_row, "linked_characters", None)))
	# environment_name is a single string value; split by comma/separator for multi-env count
	raw_env = getattr(scene_row, "environment_name", None)
	env_count = max(1, _count_assets(raw_env) if raw_env else 1)
	prop_count = max(0, _count_assets(getattr(scene_row, "key_props", None)))

	entity_total = role_count + env_count + prop_count
	tier_ratio = _resolve_entity_tier_ratio(entity_total, tier_cfg)

	complexity_score = 1.0 + (
		(role_count - 1) * role_complexity
		+ (env_count - 1) * env_complexity
		+ prop_count * prop_complexity
	)
	# Guard: ensure a minimum positive complexity score
	complexity_score = max(1.0, complexity_score)

	raw = duration * base_scene_point * complexity_score * tier_ratio * max(0.0, float(project_info_multiplier))
	result = max(0.0, raw)
	scene_id = getattr(scene_row, "id", "?")
	scene_no = getattr(scene_row, "scene_no", "?")
	_cost_log.debug(
		"[scene cost] scene_id=%s scene_no=%s dur=%.2fs roles=%d envs=%d props=%d "
		"entity_total=%d tier_ratio=%.2f complexity=%.4f proj_mul=%.4f => %.4f",
		scene_id, scene_no, duration, role_count, env_count, prop_count,
		entity_total, tier_ratio, complexity_score, project_info_multiplier, result,
	)
	return result


def _build_episode_cost_breakdown(
	episodes: List[Any],
	scenes: List[Any],
	shots: List[Any],
	*,
	overview_rate: float,
	suggested_cfg: Dict[str, Any],
	budget_cfg: Dict[str, Any],
	total_multiplier: float,
	project_info_multiplier: float = 1.0,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
	"""Returns (episode_costs_rows, scene_costs_rows)."""
	_cost_log.info(
		"[episode breakdown] episodes=%d scenes=%d shots=%d "
		"overview_rate=%.4f total_mul=%.4f proj_info_mul=%.4f",
		len(episodes or []), len(scenes or []), len(shots or []),
		overview_rate, total_multiplier, project_info_multiplier,
	)
	episode_meta: Dict[int, Dict[str, Any]] = {}
	ordered_episode_ids: List[int] = []
	for idx, ep in enumerate(episodes or []):
		episode_id = _safe_entity_id(getattr(ep, "id", None))
		if not episode_id:
			continue
		number = _safe_int(getattr(ep, "episode_number", None), idx + 1)
		title = str(getattr(ep, "title", "") or "").strip() or f"Episode {number}"
		episode_meta[episode_id] = {
			"episode_id": episode_id,
			"episode_number": number,
			"episode_title": title,
			"word_count": _count_words(getattr(ep, "script_content", "") or ""),
			"suggested_cost_sum": 0.0,
			"shot_complexity_sum": 0.0,
			"scene_count": 0,
			"shot_count": 0,
		}
		ordered_episode_ids.append(episode_id)

	scene_to_episode: Dict[int, int] = {}
	scene_cost_rows: List[Dict[str, Any]] = []
	for row in scenes or []:
		episode_id = _safe_entity_id(getattr(row, "episode_id", None))
		scene_id = _safe_entity_id(getattr(row, "id", None))
		if scene_id and episode_id:
			scene_to_episode[scene_id] = episode_id
		if not episode_id or episode_id not in episode_meta:
			continue

		scene_suggested_raw = _compute_scene_suggested_cost(row, suggested_cfg, project_info_multiplier)
		scene_suggested_cost = round(scene_suggested_raw, 4)

		role_count = max(1, _count_assets(getattr(row, "linked_characters", None)))
		raw_env = getattr(row, "environment_name", None)
		env_count = max(1, _count_assets(raw_env) if raw_env else 1)
		prop_count = max(0, _count_assets(getattr(row, "key_props", None)))
		entity_total = role_count + env_count + prop_count
		tier_cfg = suggested_cfg.get("entity_tier_ratios") if isinstance(suggested_cfg.get("entity_tier_ratios"), dict) else {}

		scene_cost_rows.append({
			"scene_id": scene_id,
			"episode_id": episode_id,
			"scene_no": str(getattr(row, "scene_no", "") or ""),
			"scene_name": str(getattr(row, "scene_name", "") or ""),
			"role_count": role_count,
			"env_count": env_count,
			"prop_count": prop_count,
			"entity_total": entity_total,
			"entity_tier_ratio": _resolve_entity_tier_ratio(entity_total, tier_cfg),
			"equivalent_duration": _parse_duration_seconds(getattr(row, "equivalent_duration", None)),
			"suggested_cost": scene_suggested_cost,
		})

		episode_meta[episode_id]["suggested_cost_sum"] += scene_suggested_raw
		episode_meta[episode_id]["scene_count"] += 1

	for row in shots or []:
		episode_id = _safe_entity_id(getattr(row, "episode_id", None))
		if not episode_id:
			scene_id = _safe_entity_id(getattr(row, "scene_id", None))
			if scene_id:
				episode_id = scene_to_episode.get(scene_id)
		if not episode_id or episode_id not in episode_meta:
			continue
		duration = _parse_duration_seconds(getattr(row, "duration", None))
		asset_count = _count_assets(getattr(row, "associated_entities", None)) + _count_assets(getattr(row, "keyframes", None))
		shot_complexity = (
			duration * _safe_float(budget_cfg.get("duration_weight"), 1.0)
			+ asset_count * _safe_float(budget_cfg.get("asset_weight"), 0.0)
		)
		episode_meta[episode_id]["shot_complexity_sum"] += shot_complexity
		episode_meta[episode_id]["shot_count"] += 1

	# dimension_multiplier_only = total_multiplier / project_info_multiplier
	# The per-scene cost already includes project_info_multiplier; we scale by dimension_multiplier_only
	dimension_multiplier_only = total_multiplier / max(1e-9, float(project_info_multiplier))
	_cost_log.debug("[episode breakdown] dimension_multiplier_only=%.4f", dimension_multiplier_only)

	episode_rows: List[Dict[str, Any]] = []
	for episode_id in ordered_episode_ids:
		meta = episode_meta[episode_id]
		overview_raw = float(meta["word_count"]) * overview_rate
		suggested_raw = float(meta["suggested_cost_sum"]) * dimension_multiplier_only
		budget_raw = float(meta["shot_complexity_sum"]) * _safe_float(budget_cfg.get("shot_unit_rate"), 0.0)
		overview_cost = round(overview_raw * total_multiplier, 4)
		suggested_cost = round(suggested_raw, 4)
		budget_cost = round(budget_raw * total_multiplier, 4)
		if int(meta["shot_count"]) > 0:
			current_estimated_cost = budget_cost
			current_stage = "budget"
		elif int(meta["scene_count"]) > 0:
			current_estimated_cost = suggested_cost
			current_stage = "suggested"
		else:
			current_estimated_cost = overview_cost
			current_stage = "overview"
		_cost_log.info(
			"[episode cost] ep_id=%s ep_no=%s stage=%s overview=%.4f suggested=%.4f budget=%.4f current=%.4f",
			meta["episode_id"], meta["episode_number"], current_stage,
			overview_cost, suggested_cost, budget_cost, current_estimated_cost,
		)
		episode_rows.append({
			"episode_id": meta["episode_id"],
			"episode_number": int(meta["episode_number"]),
			"episode_title": meta["episode_title"],
			"word_count": int(meta["word_count"]),
			"scene_count": int(meta["scene_count"]),
			"shot_count": int(meta["shot_count"]),
			"overview_cost": overview_cost,
			"suggested_cost": suggested_cost,
			"budget_cost": budget_cost,
			"current_stage": current_stage,
			"current_estimated_cost": current_estimated_cost,
			"total_cost": current_estimated_cost,
		})

	return episode_rows, scene_cost_rows


def _parse_episode_count(global_info: Dict[str, Any], episodes: List[Any]) -> int:
	src = _safe_dict(global_info)
	if src.get("story_generator_global_input") and isinstance(src.get("story_generator_global_input"), dict):
		cnt = _safe_int(_safe_dict(src.get("story_generator_global_input")).get("episodes_count"), 0)
		if cnt > 0:
			return cnt
	series_episode = _safe_int(src.get("series_episode"), 0)
	if series_episode > 0:
		return series_episode
	return max(1, len(episodes or []))


def _parse_deadline_days(global_info: Dict[str, Any]) -> Optional[int]:
	src = _safe_dict(global_info)
	raw = str(src.get("planned_completion_time") or "").strip()
	if not raw:
		return None
	stable = raw.replace("/", "-")
	for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
		try:
			dt = datetime.strptime(stable[:19], fmt)
			days = int((dt.date() - datetime.utcnow().date()).days)
			return days
		except Exception:
			continue
	return None


def _extract_dimension_factors(
	global_info: Dict[str, Any],
	cfg: Dict[str, Any],
	*,
	word_count: int,
	scene_rows: List[Any],
	shot_rows: List[Any],
	episodes: List[Any],
) -> Tuple[float, List[Dict[str, Any]], Dict[str, float], List[str]]:
	rules = _safe_dict(cfg.get("dimension_rules"))
	flattened = _flatten_project_info(global_info)
	factors: List[Dict[str, Any]] = []
	suggestions: List[str] = []

	def add_factor(group: str, key: str, metric_value: Any, factor_value: float):
		resolved = max(0.0, float(factor_value))
		factors.append({
			"group": group,
			"key": key,
			"metric": metric_value,
			"factor": round(resolved, 6),
		})

	# 1) User requirements
	user_rules = _safe_dict(rules.get("user_requirements"))
	creativity_map = _safe_dict(user_rules.get("creativity"))
	creativity_val = str(flattened.get("creativity", "")).strip()
	creativity_factor = _safe_float(creativity_map.get(creativity_val, creativity_map.get("__default__", 1.0)), 1.0)
	add_factor("user_requirements", "creativity", creativity_val, creativity_factor)

	pref_map = _safe_dict(user_rules.get("video_generation_preference"))
	pref_val = str(flattened.get("video_generation_preference", "")).strip()
	pref_factor = _safe_float(pref_map.get(pref_val, pref_map.get("__default__", 1.0)), 1.0)
	add_factor("user_requirements", "video_generation_preference", pref_val, pref_factor)

	assets_map = _safe_dict(user_rules.get("has_existing_assets"))
	assets_val_bool = _parse_bool(flattened.get("has_existing_assets"))
	assets_val = "true" if assets_val_bool is True else "false" if assets_val_bool is False else ""
	assets_factor = _safe_float(assets_map.get(assets_val, assets_map.get("__default__", 1.0)), 1.0)
	add_factor("user_requirements", "has_existing_assets", assets_val, assets_factor)

	notes_word_count = _count_words(_safe_dict(global_info).get("notes") or "")
	notes_factor = _resolve_tier_factor(float(notes_word_count), user_rules.get("notes_word_count_tiers"), 1.0)
	add_factor("user_requirements", "notes_word_count", notes_word_count, notes_factor)

	# 2) Script complexity
	complexity_rules = _safe_dict(rules.get("script_complexity"))
	wc_factor = _resolve_tier_factor(float(word_count), complexity_rules.get("word_count_tiers"), 1.0)
	add_factor("script_complexity", "word_count", int(word_count), wc_factor)

	scene_assets_total = 0
	for row in (scene_rows or []):
		scene_assets_total += _count_assets(getattr(row, "linked_characters", None)) + _count_assets(getattr(row, "key_props", None))
	scene_density = (float(scene_assets_total) / float(len(scene_rows))) if scene_rows else 0.0
	scene_density_factor = _resolve_tier_factor(scene_density, complexity_rules.get("scene_asset_density_tiers"), 1.0)
	add_factor("script_complexity", "scene_asset_density", round(scene_density, 4), scene_density_factor)

	shot_assets_total = 0
	for row in (shot_rows or []):
		shot_assets_total += _count_assets(getattr(row, "associated_entities", None)) + _count_assets(getattr(row, "keyframes", None))
	shot_density = (float(shot_assets_total) / float(len(shot_rows))) if shot_rows else 0.0
	shot_density_factor = _resolve_tier_factor(shot_density, complexity_rules.get("shot_asset_density_tiers"), 1.0)
	add_factor("script_complexity", "shot_asset_density", round(shot_density, 4), shot_density_factor)

	# 3) Output duration
	duration_rules = _safe_dict(rules.get("output_duration"))
	expected_duration_sec = _parse_expected_duration(global_info)
	expected_duration_factor = _resolve_tier_factor(float(expected_duration_sec), duration_rules.get("expected_duration_seconds_tiers"), 1.0)
	add_factor("output_duration", "expected_duration_seconds", expected_duration_sec, expected_duration_factor)

	episode_count = _parse_episode_count(global_info, episodes)
	episode_count_factor = _resolve_tier_factor(float(episode_count), duration_rules.get("episode_count_tiers"), 1.0)
	add_factor("output_duration", "episode_count", episode_count, episode_count_factor)

	# 4) Quality requirements
	quality_rules = _safe_dict(rules.get("quality_requirements"))
	quality_map = _safe_dict(quality_rules.get("quality"))
	quality_val = str(flattened.get("quality", "")).strip()
	quality_factor = _safe_float(quality_map.get(quality_val, quality_map.get("__default__", 1.0)), 1.0)
	add_factor("quality_requirements", "quality", quality_val, quality_factor)

	resolution_pixels = _parse_resolution_pixels(global_info)
	resolution_factor = _resolve_tier_factor(float(resolution_pixels), quality_rules.get("resolution_pixels_tiers"), 1.0)
	add_factor("quality_requirements", "resolution_pixels", resolution_pixels, resolution_factor)

	frame_rate = _safe_int(flattened.get("frame_rate"), 0)
	frame_rate_factor = _resolve_tier_factor(float(frame_rate), quality_rules.get("frame_rate_tiers"), 1.0)
	add_factor("quality_requirements", "frame_rate", frame_rate, frame_rate_factor)

	style_count = _parse_multi_value_count(_safe_dict(global_info).get("Global_Style"))
	style_factor = _resolve_tier_factor(float(style_count), quality_rules.get("style_count_tiers"), 1.0)
	add_factor("quality_requirements", "style_count", style_count, style_factor)

	# 5) Project management requirements
	mgmt_rules = _safe_dict(rules.get("project_management"))
	deadline_days = _parse_deadline_days(global_info)
	deadline_factor = _resolve_tier_factor(float(deadline_days if deadline_days is not None else 9999), mgmt_rules.get("deadline_days_tiers"), 1.0)
	add_factor("project_management", "deadline_days", deadline_days if deadline_days is not None else "", deadline_factor)

	reviewer_users = _safe_dict(global_info).get("project_reviewer_users")
	reviewer_count = len(reviewer_users) if isinstance(reviewer_users, list) else 0
	reviewer_factor = _resolve_tier_factor(float(reviewer_count), mgmt_rules.get("reviewer_count_tiers"), 1.0)
	add_factor("project_management", "reviewer_count", reviewer_count, reviewer_factor)

	share_users = _safe_dict(global_info).get("project_share_users")
	share_count = len(share_users) if isinstance(share_users, list) else 0
	collaboration_count = reviewer_count + share_count
	collaboration_factor = _resolve_tier_factor(float(collaboration_count), mgmt_rules.get("collaboration_count_tiers"), 1.0)
	add_factor("project_management", "collaboration_count", collaboration_count, collaboration_factor)

	safety_map = _safe_dict(mgmt_rules.get("broadcast_safety_level"))
	safety_val = str(flattened.get("broadcast_safety_level", "")).strip()
	safety_factor = _safe_float(safety_map.get(safety_val, safety_map.get("__default__", 1.0)), 1.0)
	add_factor("project_management", "broadcast_safety_level", safety_val, safety_factor)

	grouped: Dict[str, float] = {}
	total = 1.0
	for item in factors:
		group = str(item.get("group") or "").strip() or "other"
		factor = max(0.0, _safe_float(item.get("factor"), 1.0))
		grouped[group] = float(grouped.get(group, 1.0)) * factor
		total *= factor

	if grouped.get("script_complexity", 1.0) >= 1.15:
		suggestions.append("剧本复杂度偏高：建议在场景分析后先做'高复杂场景优先级清单'，并提前锁定关键资产复用策略。")
	if grouped.get("quality_requirements", 1.0) >= 1.12:
		suggestions.append("质量要求偏高：建议按A/B镜头分层产出，先保证主叙事镜头质量，再迭代次要镜头。")
	if grouped.get("user_requirements", 1.0) >= 1.1:
		suggestions.append("需求复杂度较高：建议将需求拆解为必须项/可选项，并对可选项设置冻结节点，控制范围蔓延。")
	if grouped.get("project_management", 1.0) >= 1.12:
		suggestions.append("项目管理约束较强：建议设置固定周审节奏与冻结窗口，减少中途返工。")
	if grouped.get("output_duration", 1.0) >= 1.12:
		suggestions.append("产出时长压力较大：建议按集建立里程碑并拆分批量生成任务，降低单批失败影响。")
	if not suggestions:
		suggestions.append("当前成本因子整体平稳：建议维持既有流程，并在分镜阶段重点监控资产密度与时长偏差。")

	return total, factors, grouped, suggestions


def _count_assets(text: Any) -> int:
	raw = str(text or "").strip()
	if not raw:
		return 0
	normalized = re.sub(r"[，、；;|/]+", ",", raw)
	normalized = normalized.replace("\n", ",").replace("\r", ",")
	parts = [str(x).strip() for x in normalized.split(",")]
	return len([x for x in parts if x])


def _resolve_project_multiplier(global_info: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
	multiplier_cfg = _safe_dict(cfg.get("project_multiplier"))
	field_factors = multiplier_cfg.get("field_factors") if isinstance(multiplier_cfg.get("field_factors"), dict) else {}
	flattened = _flatten_project_info(global_info)

	total = max(0.0, _safe_float(multiplier_cfg.get("default_factor"), 1.0))
	detail: List[Dict[str, Any]] = []
	for field_name, mapping in field_factors.items():
		if not isinstance(mapping, dict):
			continue
		field_key = str(field_name or "").strip()
		if not field_key:
			continue
		value = str(flattened.get(field_key, "")).strip()
		factor = None
		if value:
			factor = mapping.get(value)
		if factor is None:
			factor = mapping.get("__default__", 1.0)
		resolved = max(0.0, _safe_float(factor, 1.0))
		total *= resolved
		detail.append({
			"field": field_key,
			"value": value,
			"factor": resolved,
		})
	return total, detail


def compute_project_cost_estimation(
	project_title: str,
	global_info: Dict[str, Any],
	episodes: List[Any],
	scenes: List[Any],
	shots: List[Any],
	config: Dict[str, Any],
) -> Dict[str, Any]:
	_cost_log.info(
		"[compute] project='%s' episodes=%d scenes=%d shots=%d",
		project_title, len(episodes or []), len(scenes or []), len(shots or []),
	)
	cfg = normalize_project_cost_estimation_config(config)

	all_script_text = "\n".join([str(getattr(ep, "script_content", "") or "") for ep in (episodes or [])])
	word_count = _count_words(all_script_text)

	scene_rows = scenes or []
	shot_rows = shots or []

	overview_rate = _safe_float(_safe_dict(cfg.get("overview")).get("word_rate"), 0.0)
	suggested_cfg = _safe_dict(cfg.get("suggested"))
	budget_cfg = _safe_dict(cfg.get("budget"))

	project_multiplier, multiplier_detail = _resolve_project_multiplier(_safe_dict(global_info), cfg)
	_cost_log.info("[compute] project_info_multiplier=%.4f", project_multiplier)
	dimension_multiplier, dimension_factor_detail, grouped_dimension_factors, suggestions = _extract_dimension_factors(
		_safe_dict(global_info),
		cfg,
		word_count=word_count,
		scene_rows=scene_rows,
		shot_rows=shot_rows,
		episodes=episodes,
	)
	total_multiplier = float(project_multiplier) * float(dimension_multiplier)
	_cost_log.info(
		"[compute] dimension_multiplier=%.4f total_multiplier=%.4f word_count=%d scenes=%d shots=%d",
		dimension_multiplier, total_multiplier, word_count, len(scene_rows), len(shot_rows),
	)

	# --- Suggested stage: per-scene formula ---
	# scene_cost = duration * base_scene_point
	#   * (1.0 + (role_count-1) * role_complexity + (env_count-1) * env_complexity + prop_count * prop_complexity)
	#   * entity_tier_ratio * project_info_multiplier
	# Then scale by dimension_multiplier_only for project total.
	dimension_multiplier_only = total_multiplier / max(1e-9, float(project_multiplier))
	suggested_cost_sum_raw = 0.0  # sum of per-scene raw costs (includes project_info_multiplier)
	for row in scene_rows:
		suggested_cost_sum_raw += _compute_scene_suggested_cost(row, suggested_cfg, project_multiplier)

	# Budget stage: shot-based
	shot_complexity_sum = 0.0
	for row in shot_rows:
		duration = _parse_duration_seconds(getattr(row, "duration", None))
		asset_count = _count_assets(getattr(row, "associated_entities", None)) + _count_assets(getattr(row, "keyframes", None))
		shot_complexity_sum += (
			duration * _safe_float(budget_cfg.get("duration_weight"), 1.0)
			+ asset_count * _safe_float(budget_cfg.get("asset_weight"), 0.0)
		)

	overview_raw = float(word_count) * overview_rate
	suggested_raw = suggested_cost_sum_raw * dimension_multiplier_only
	budget_raw = shot_complexity_sum * _safe_float(budget_cfg.get("shot_unit_rate"), 0.0)

	overview_cost = round(overview_raw * total_multiplier, 4)
	suggested_cost = round(suggested_raw, 4)
	budget_cost = round(budget_raw * total_multiplier, 4)
	if len(shot_rows) > 0:
		current_stage = "budget"
		current_estimate = budget_cost
	elif len(scene_rows) > 0:
		current_stage = "suggested"
		current_estimate = suggested_cost
	else:
		current_stage = "overview"
		current_estimate = overview_cost
	_cost_log.info(
		"[compute] stage=%s overview=%.4f suggested=%.4f budget=%.4f current=%.4f",
		current_stage, overview_cost, suggested_cost, budget_cost, current_estimate,
	)

	episode_costs, scene_costs = _build_episode_cost_breakdown(
		episodes,
		scene_rows,
		shot_rows,
		overview_rate=overview_rate,
		suggested_cfg=suggested_cfg,
		budget_cfg=budget_cfg,
		total_multiplier=total_multiplier,
		project_info_multiplier=project_multiplier,
	)

	return {
		"project_title": str(project_title or ""),
		"config_version": int(cfg.get("version") or 1),
		"project_multiplier": round(total_multiplier, 6),
		"project_info_multiplier": round(project_multiplier, 6),
		"dimension_multiplier": round(dimension_multiplier, 6),
		"project_multiplier_detail": multiplier_detail,
		"dimension_factor_detail": dimension_factor_detail,
		"dimension_group_factors": {k: round(v, 6) for k, v in grouped_dimension_factors.items()},
		"execution_suggestions": suggestions,
		"episode_costs": episode_costs,
		"scene_costs": scene_costs,
		"stages": {
			"overview": {
				"ready": word_count > 0,
				"word_count": int(word_count),
				"word_rate": overview_rate,
				"raw_cost": round(overview_raw, 4),
				"estimated_cost": overview_cost,
			},
			"suggested": {
				"ready": len(scene_rows) > 0,
				"scene_count": len(scene_rows),
				"base_scene_point": _safe_float(suggested_cfg.get("base_scene_point"), 1.0),
				"role_complexity": _safe_float(suggested_cfg.get("role_complexity"), 1.0),
				"env_complexity": _safe_float(suggested_cfg.get("env_complexity"), 0.8),
				"prop_complexity": _safe_float(suggested_cfg.get("prop_complexity"), 0.5),
				"suggested_cost_sum_raw": round(suggested_cost_sum_raw, 4),
				"raw_cost": round(suggested_raw, 4),
				"estimated_cost": suggested_cost,
			},
			"budget": {
				"ready": len(shot_rows) > 0,
				"shot_count": len(shot_rows),
				"complexity_sum": round(shot_complexity_sum, 4),
				"shot_unit_rate": _safe_float(budget_cfg.get("shot_unit_rate"), 0.0),
				"raw_cost": round(budget_raw, 4),
				"estimated_cost": budget_cost,
			},
		},
		"summary": {
			"estimated_total": current_estimate,
			"progressive_total": current_estimate,
			"current_stage": current_stage,
			"current_estimate": current_estimate,
			"overview_estimate": overview_cost,
			"suggested_estimate": suggested_cost,
			"budget_estimate": budget_cost,
			"scene_count": len(scene_rows),
			"shot_count": len(shot_rows),
			"episode_count": len(episodes or []),
		},
	}
