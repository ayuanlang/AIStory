
import requests
import re
import urllib3
import time
import base64
import json
import hashlib
import hmac
import asyncio
import uuid
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.schemas.agent import AgentRequest, AgentResponse, AgentAction
from app.services.llm_service import llm_service
from app.db.session import SessionLocal
from app.models.all_models import APISetting, SystemAPISetting, Entity, User
from app.core.config import settings
from app.services.billing_service import billing_service
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
# from app.db.session import db as legacy_db 
# Mock legacy_db to prevent import error during refactor
class MockLegacyDB:
    projects = {}
    def save(self): pass
legacy_db = MockLegacyDB()

# Suppress InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class AgentService:
    def _safe_json_dict_or_none(self, value: Any) -> Optional[Dict[str, Any]]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                parsed = json.loads(raw)
            except Exception:
                return None
            return parsed if isinstance(parsed, dict) else None
        return None

    def _repair_invalid_user_config_rows(
        self,
        session: Session,
        user_id: int,
        category: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> None:
        q = session.query(
            APISetting.id,
            cast(APISetting.config, String).label("config_raw"),
        ).filter(APISetting.user_id == user_id)
        if category:
            q = q.filter(APISetting.category == category)
        if provider:
            q = q.filter(APISetting.provider == provider)

        bad_ids: List[int] = []
        for row in q.all():
            if self._safe_json_dict_or_none(row.config_raw) is None:
                bad_ids.append(row.id)

        if bad_ids:
            logger.warning(
                "Repair invalid api_settings.config rows | user_id=%s category=%s provider=%s ids=%s",
                user_id,
                category,
                provider,
                bad_ids,
            )
            session.query(APISetting).filter(APISetting.id.in_(bad_ids)).update(
                {APISetting.config: {}},
                synchronize_session=False,
            )
            session.commit()

    def _repair_invalid_system_config_rows(self, session: Session, category: Optional[str] = None) -> None:
        q = session.query(
            SystemAPISetting.id,
            cast(SystemAPISetting.config, String).label("config_raw"),
        )
        if category:
            q = q.filter(SystemAPISetting.category == category)

        bad_ids: List[int] = []
        for row in q.all():
            if self._safe_json_dict_or_none(row.config_raw) is None:
                bad_ids.append(row.id)

        if bad_ids:
            logger.warning(
                "Repair invalid system_api_settings.config rows | category=%s ids=%s",
                category,
                bad_ids,
            )
            session.query(SystemAPISetting).filter(SystemAPISetting.id.in_(bad_ids)).update(
                {SystemAPISetting.config: {}},
                synchronize_session=False,
            )
            session.commit()

    def get_api_config(self, provider: str, user_id: int = 1, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Resolves API configuration by:
        1) finding user's active api_settings row in the given category,
        2) using that row's provider+model to match system_api_settings.
        """
        defaults = {
            "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4-turbo-preview"},
            "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-3-opus-20240229"},
            "stability": {"base_url": "https://api.stability.ai", "model": "stable-diffusion-xl-1024-v1-0"},
            "runway": {"base_url": "https://api.runwayml.com", "model": "gen-2"},
            "elevenlabs": {"base_url": "https://api.elevenlabs.io/v1", "model": "premade/Adam"},
            "ark": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "deepseek-v3-2-251201"},
            "doubao": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "doubao-seedream-4-5-251128"},
            "grsai": {"base_url": "https://api.grsai.com/v1", "model": "g-image-v1"},
            "tencent": {"base_url": "https://hunyuan.tencentcloudapi.com", "model": "hunyuan-vision"},
        }

        try:
            with SessionLocal() as session:
                resolved_category = str(category or "").strip()
                if not resolved_category:
                    logger.warning("Missing category when resolving API config | user_id=%s", user_id)
                    return {}

                self._repair_invalid_user_config_rows(session, user_id, category=resolved_category)
                self._repair_invalid_system_config_rows(session, category=resolved_category)

                active_user_setting = session.query(APISetting).filter(
                    APISetting.user_id == user_id,
                    APISetting.category == resolved_category,
                    APISetting.is_active == True,
                ).order_by(APISetting.id.desc()).first()

                if not active_user_setting:
                    logger.warning(
                        "No active user api setting found | user_id=%s category=%s",
                        user_id,
                        resolved_category,
                    )
                    return {}

                target_provider = str(active_user_setting.provider or "").strip()
                target_model = str(active_user_setting.model or "").strip()
                if not target_provider or not target_model:
                    logger.warning(
                        "Active user setting missing provider/model | user_id=%s category=%s setting_id=%s provider=%s model=%s",
                        user_id,
                        resolved_category,
                        active_user_setting.id,
                        active_user_setting.provider,
                        active_user_setting.model,
                    )
                    return {}

                setting = session.query(SystemAPISetting).filter(
                    SystemAPISetting.category == resolved_category,
                    SystemAPISetting.provider == target_provider,
                    SystemAPISetting.model == target_model,
                ).order_by(SystemAPISetting.id.desc()).first()

                if setting:
                    return {
                        "provider": setting.provider,
                        "api_key": setting.api_key,
                        "base_url": setting.base_url or defaults.get(target_provider, {}).get("base_url"),
                        "model": setting.model or defaults.get(target_provider, {}).get("model"),
                        "config": setting.config or {}
                    }
                logger.warning(
                    "No matching system api setting by provider+model | user_id=%s category=%s provider=%s model=%s",
                    user_id,
                    resolved_category,
                    target_provider,
                    target_model,
                )
        except Exception as e:
            logger.error(f"Error fetching system settings for {provider}: {e}")

        return {}

    def get_active_llm_config(self, user_id: int = 1, category: str = "LLM") -> Dict[str, Any]:
        """
        Retrieves active API configuration by category by matching
        active user api_settings(provider+model) -> system_api_settings.
        """
        try:
            with SessionLocal() as session:
                resolved_category = str(category or "LLM").strip() or "LLM"

                self._repair_invalid_user_config_rows(session, user_id, category=resolved_category)
                self._repair_invalid_system_config_rows(session, category=resolved_category)

                def _is_endpoint_compatible(cfg: Dict[str, Any]) -> bool:
                    endpoint = str((cfg or {}).get("endpoint") or "").strip().lower()
                    if not endpoint:
                        return True
                    if resolved_category != "LLM":
                        return True
                    if "/chat/completions" in endpoint:
                        return True
                    media_tokens = ["/draw", "/video", "image2video", "video-synthesis", "generations/tasks"]
                    return not any(token in endpoint for token in media_tokens)

                active_user_setting = session.query(APISetting).filter(
                    APISetting.user_id == user_id,
                    APISetting.category == resolved_category,
                    APISetting.is_active == True
                ).order_by(APISetting.id.desc()).first()

                if not active_user_setting:
                    logger.warning(
                        "No active user api setting found | user_id=%s category=%s",
                        user_id,
                        resolved_category,
                    )
                    return {}

                selected: Optional[SystemAPISetting] = None
                selected_source = "none"

                target_provider = active_user_setting.provider if active_user_setting else None
                target_model = active_user_setting.model if active_user_setting else None

                if target_provider and target_model:
                    selected = session.query(SystemAPISetting).filter(
                        SystemAPISetting.category == resolved_category,
                        SystemAPISetting.provider == target_provider,
                        SystemAPISetting.model == target_model,
                    ).order_by(SystemAPISetting.id.desc()).first()
                    if selected:
                        selected_source = f"system_by_user_provider_model:{target_provider}/{target_model}->{selected.id}"

                if not selected and active_user_setting:
                    logger.warning(
                        "No matching system api setting by provider+model | user_id=%s category=%s user_setting_id=%s provider=%s model=%s",
                        user_id,
                        resolved_category,
                        active_user_setting.id,
                        target_provider,
                        target_model,
                    )

                if selected:
                    if not _is_endpoint_compatible(selected.config or {}):
                        logger.warning(
                            "Skipping incompatible %s setting | user_id=%s setting_id=%s provider=%s model=%s endpoint=%s",
                            resolved_category,
                            user_id,
                            selected.id,
                            selected.provider,
                            selected.model,
                            (selected.config or {}).get("endpoint"),
                        )
                        selected = None

                if selected:
                    from app.api.settings import DEFAULTS
                    default = DEFAULTS.get(selected.provider, {})
                    merged_config = dict(selected.config or default.get("config", {}) or {})
                    merged_config["__resolved_setting_id"] = selected.id
                    merged_config["__resolved_source"] = selected_source
                    merged_config["__resolved_category"] = getattr(selected, "category", resolved_category)
                    merged_config["__selection_source"] = "system_only"
                    if active_user_setting:
                        merged_config["__resolved_user_setting_id"] = active_user_setting.id

                    logger.info(
                        "Resolved active API config | user_id=%s category=%s source=%s selection_source=system_only setting_id=%s provider=%s model=%s endpoint=%s",
                        user_id,
                        resolved_category,
                        selected_source,
                        selected.id,
                        selected.provider,
                        selected.model,
                        selected.base_url or default.get("base_url"),
                    )

                    return {
                        "provider": selected.provider,
                        "api_key": selected.api_key,
                        "base_url": selected.base_url or default.get("base_url"),
                        "model": selected.model or default.get("model"),
                        "config": merged_config
                    }
        except Exception as e:
            logger.error(f"Error fetching active API config ({category}): {e}")

        return {}

    async def process_command(self, request: AgentRequest, db: Session, user_id: int) -> AgentResponse:
        project_id = request.context.get("project_id")
        
        # Resolve LLM Config
        llm_config = request.llm_config
        if not llm_config or not llm_config.get("api_key"):
            # Assuming user_id=1 for single user desktop app context, 
            # or extract from request if available in future
            llm_config = self.get_active_llm_config(user_id=user_id)

        if request.context.get("is_refinement"):
            llm_result = {
                "reply": "Refining asset based on your instructions...",
                "plan": [
                    {
                        "tool": "generate_project_asset",
                        "parameters": {
                            "prompt": request.query,
                            "target_id": request.context.get("target_id") or "",
                            "target_type": request.context.get("target_type"),
                            "target_field": request.context.get("target_field"),
                            "reference_image_url": request.context.get("reference_image_url") 
                        }
                    }
                ]
            }
        else:
            llm_result = await llm_service.analyze_intent(request.query, request.context, request.history, llm_config)

        actions: List[AgentAction] = []
        updated_data = None
        last_tool_result = None

        for plan_item in llm_result.get("plan", []):
            params = plan_item["parameters"]
            for k, v in params.items():
                if v == "__LAST_RESULT__" and last_tool_result:
                    params[k] = last_tool_result

            action = AgentAction(
                tool=plan_item["tool"],
                parameters=params
            )
            
            execution_result = await self._execute_tool(action, db, user_id, project_id, request.llm_config, request.context)
            
            action.result = execution_result["result"]
            action.status = execution_result["status"]
            
            if action.status == "completed":
                last_tool_result = action.result
            
            if execution_result.get("data_update"):
                updated_data = execution_result["data_update"]
                
            actions.append(action)

        final_reply = llm_result.get("reply", "")
        # ... logic to append images ...
            
        return AgentResponse(
            reply=final_reply,
            actions=actions,
            updated_data=updated_data,
            usage=llm_result.get("usage")
        )

    async def _execute_tool(self, action: AgentAction, db: Session, user_id: int, project_id: str = None, llm_config: Any = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        tool = action.tool
        params = action.parameters
        if context is None: context = {}
        
        # Helper for billing checks
        def check_and_deduct_callback(task_type, details, operation):
            provider = llm_config.get("provider") if llm_config else None
            model = llm_config.get("model") if llm_config else None
            # 1. Check Balance
            billing_service.check_balance(db, user_id, task_type, provider, model)
            # 2. Execute
            result = operation()
            # 3. Deduct
            billing_service.deduct_credits(db, user_id, task_type, provider, model, details)
            return result

        if tool == "generate_project_asset":
            print(f"DEBUG: Executing generate_project_asset. ProjectID: {project_id}, Target: {params.get('target_id')}")
            prompt = params.get("prompt", "")
            target_type = params.get("target_type")
            target_id = str(params.get("target_id") or "").strip().strip('"').strip("'")
            prompt = self._enrich_prompt_if_possible(prompt, project_id, target_id=target_id)
            target_field = params.get("target_field")
            reference_image_url = params.get("reference_image_url")

            # Resolve Visual Dependencies if Entity
            if (target_type == "entity" or target_type == "subject") and target_id:
                try:
                     with SessionLocal() as session:
                         # Try to find entity by ID
                         # Assuming target_id is the numeric ID
                         e_id = int(target_id) if target_id.isdigit() else None
                         entity = None
                         if e_id:
                             entity = session.query(Entity).filter(Entity.id == e_id).first()
                         
                         if entity and entity.visual_dependencies:
                             # If reference_image_url is None, init as list
                             if reference_image_url is None: reference_image_url = []
                             elif isinstance(reference_image_url, str): reference_image_url = [reference_image_url]
                             
                             deps = entity.visual_dependencies # List of names
                             if isinstance(deps, list):
                                 for dep_name in deps:
                                     # Try match by name or ID
                                     dep_entity = session.query(Entity).filter(
                                         Entity.project_id == int(project_id), 
                                         Entity.name == str(dep_name)
                                     ).first()
                                     if not dep_entity and str(dep_name).isdigit():
                                          dep_entity = session.query(Entity).filter(Entity.id == int(dep_name)).first()

                                     if dep_entity and dep_entity.image_url:
                                         print(f"DEBUG: Found dependency image for {dep_name}: {dep_entity.image_url}")
                                         if dep_entity.image_url not in reference_image_url:
                                             reference_image_url.append(dep_entity.image_url)
                except Exception as e:
                    print(f"Error resolving dependencies: {e}")

            if isinstance(reference_image_url, list):
                 if len(reference_image_url) == 0:
                     reference_image_url = None
            
            print(f"DEBUG: Cleaned Target ID: '{target_id}'")
            
            # --- Billing Injection ---
            # Determine provider/model used in internal generator
            # This is tricky because _generate_image_with_metadata resolves provider internally
            # We will use the main llm_config provider as a proxy OR default to 'stability' to be safe
            # But wait, _generate_image_with_metadata uses llm_config to pick provider
            gen_provider = llm_config.get("provider", "stability") if llm_config else "stability"
            gen_model = llm_config.get("model", "") if llm_config else ""
            
            # 1. Check Balance
            billing_service.check_balance(db, user_id, "image_gen", gen_provider, gen_model)
            
            try:
                gen_result = await self._generate_image_with_metadata(prompt, llm_config, user_id=user_id, reference_image_url=reference_image_url)
                
                # 2. Deduct Credits
                # Only if successful
                billing_service.deduct_credits(db, user_id, "image_gen", gen_provider, gen_model, {"item": "image_from_chat"})
                
                generated_url = gen_result["url"]
                gen_meta = gen_result["metadata"]
                
                return self._save_and_bind_asset(
                    project_id, generated_url, "image", prompt, 
                    {**gen_meta, "target_id": target_id, "target_type": target_type},
                    target_id, target_type, target_field
                )
            except Exception as e:
                # No Charge on Failure
                return {"status": "failed", "result": f"Failed to generate asset: {str(e)}"}
            
        elif tool == "generate_image_text_to_image":
            gen_provider = llm_config.get("provider", "stability") if llm_config else "stability"
            gen_model = llm_config.get("model", "") if llm_config else ""
            billing_service.check_balance(db, user_id, "image_gen", gen_provider, gen_model)
            
            try:
                prompt = params.get("prompt", "")
                prompt = self._enrich_prompt_if_possible(prompt, project_id)
                gen_result = await self._generate_image_with_metadata(prompt, llm_config, user_id=user_id)
                
                billing_service.deduct_credits(db, user_id, "image_gen", gen_provider, gen_model, {"item": "image_from_tool"})

                return self._save_and_bind_asset(
                    project_id, gen_result["url"], "image", prompt, 
                    gen_result["metadata"], 
                    None, "generic"
                )
            except Exception as e:
                return {"status": "failed", "result": f"Failed: {str(e)}"}

        elif tool == "generate_image_image_to_image":
            gen_provider = llm_config.get("provider", "stability") if llm_config else "stability"
            gen_model = llm_config.get("model", "") if llm_config else ""
            billing_service.check_balance(db, user_id, "image_gen", gen_provider, gen_model)
            
            try:
                prompt = params.get("prompt", "")
                prompt = self._enrich_prompt_if_possible(prompt, project_id)
                image_url = params.get("image_url", "")
                gen_result = await self._generate_image_with_metadata(prompt, llm_config, user_id=user_id, reference_image_url=image_url)
                
                billing_service.deduct_credits(db, user_id, "image_gen", gen_provider, gen_model, {"item": "i2i_from_tool"})
                
                return self._save_and_bind_asset(
                    project_id, gen_result["url"], "image", prompt, 
                    gen_result["metadata"], 
                    None, "generic"
                )
            except Exception as e:
                return {"status": "failed", "result": f"Failed: {str(e)}"}

        elif tool == "generate_video_text_to_video":
             gen_provider = llm_config.get("provider", "runway") if llm_config else "runway"
             gen_model = llm_config.get("model", "") if llm_config else ""
             billing_service.check_balance(db, user_id, "video_gen", gen_provider, gen_model)
             
             try:
                prompt = params.get("prompt", "")
                prompt = self._enrich_prompt_if_possible(prompt, project_id)
                target_id = context.get("target_id")
                target_type = context.get("target_type", "scene_item")
                duration = -1
                
                gen_result = await self._generate_video_with_metadata(prompt, llm_config, user_id=user_id, duration=duration)
                
                billing_service.deduct_credits(db, user_id, "video_gen", gen_provider, gen_model, {"item": "video_from_tool"})
                
                return self._save_and_bind_asset(
                    project_id, gen_result["url"], "video", prompt, 
                    {**gen_result["metadata"], "target_id": target_id, "target_type": target_type},
                    target_id, target_type
                )
             except Exception as e:
                return {"status": "failed", "result": f"Failed: {str(e)}"}

        elif tool == "generate_video_image_to_video":
            gen_provider = llm_config.get("provider", "runway") if llm_config else "runway"
            gen_model = llm_config.get("model", "") if llm_config else ""
            billing_service.check_balance(db, user_id, "video_gen", gen_provider, gen_model)
            
            try:
                prompt = params.get("prompt", "")
                prompt = self._enrich_prompt_if_possible(prompt, project_id)
                
                image_candidate = params.get("image_url")
                if not image_candidate:
                    image_candidate = context.get("start_frame") or context.get("reference_image_url")
                
                last_frame_candidate = params.get("last_frame_url")
                if not last_frame_candidate:
                    last_frame_candidate = context.get("end_frame")
                    
                target_id = context.get("target_id")
                video_mode = context.get("video_mode", "default")
                
                if video_mode == "cross_scene" and target_id:
                    pass # logic placeholder
                elif video_mode == "first_frame":
                    last_frame_candidate = None
                    
                image_url = None
                last_frame_url = last_frame_candidate
                
                if isinstance(image_candidate, list):
                    if len(image_candidate) > 0:
                        image_url = image_candidate[0]
                        if len(image_candidate) > 1 and not last_frame_url:
                            last_frame_url = image_candidate[1]
                else:
                    image_url = image_candidate

                if isinstance(last_frame_url, list):
                    last_frame_url = last_frame_url[0] if len(last_frame_url) > 0 else None

                target_type = context.get("target_type", "scene_item")
                duration = -1

                gen_result = await self._generate_video_with_metadata(
                    prompt, 
                    llm_config, 
                    user_id=user_id,
                    reference_image_url=image_url, 
                    last_frame_url=last_frame_url,
                    duration=duration
                )
                
                billing_service.deduct_credits(db, user_id, "video_gen", gen_provider, gen_model, {"item": "i2v_from_tool"})
                
                return self._save_and_bind_asset(
                    project_id, gen_result["url"], "video", prompt, 
                    {**gen_result["metadata"], "target_id": target_id, "target_type": target_type},
                    target_id, target_type
                )
            except Exception as e:
                return {"status": "failed", "result": f"Failed: {str(e)}"}
            
        elif tool == "create_project":
            new_id = f"proj_{uuid.uuid4().hex[:8]}"
            legacy_db.projects[new_id] = {
                "id": new_id,
                "title": params.get("title", "New Project"),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "subprojects": []
            }
            legacy_db.save()
            return {
                "status": "completed",
                "result": f"Project created: {new_id}",
                "data_update": {"type": "project_list_refresh"}
            }
        
        elif tool == "analyze_script":
             return {
                 "status": "completed",
                 "result": {
                     "screenplay_analysis": {
                        "genre": "Sci-Fi",
                        "logline": "A futuristic journey.",
                        "characters": ["Hero", "Villain"],
                        "scenes": [{"id": 1, "slug": "INT. LAB - DAY"}]
                     },
                     "visual_style_guide": {
                         "color_palette": ["#000000", "#FFFFFF"],
                         "lighting": "High Contrast"
                     }
                 },
                 "data_update": {"type": "analysis_result", "projectId": project_id}
             }

        return {"status": "failed", "result": f"Unknown tool: {tool}"}

    def _enrich_prompt_if_possible(self, prompt, project_id, target_id=None):
        if not project_id: return prompt
        # Future: Lookup scene context or character details to append to prompt
        return prompt

    def _find_previous_scene_end_frame(self, project_id, current_scene_id):
        # Implementation to find the end frame of the logically preceding scene
        # 1. Get project
        project = legacy_db.projects.get(project_id)
        if not project: return None
        # 2. Find index of current scene
        # (Simplified) Just return None for now as we don't have full scene graph traversal here
        return None

    def _save_and_bind_asset(self, project_id, url, asset_type, prompt, metadata, target_id, target_type, target_field=None):
        asset_id = f"asset_{uuid.uuid4().hex[:8]}"
        asset_data = {
            "id": asset_id,
            "url": url,
            "type": asset_type,
            "prompt": prompt,
            "metadata": metadata,
            "created_at": datetime.now()
        }
        
        # Save to Project Library
        if project_id:
             project = legacy_db.projects.get(project_id)
             if project:
                 if "assets" not in project: project["assets"] = []
                 project["assets"].append(asset_data)
                 
                 # Bind to Target if specified
                 if target_id:
                     # For now, just save to library. 
                     # Binding logic would go here (updating scene items)
                     pass 
                 
                 legacy_db.save()
        
        return {
            "status": "completed", 
            "result": url,
            "data_update": {
                "type": "asset_created", 
                "asset": asset_data,
                "projectId": project_id,
                "targetId": target_id
            }
        }

    async def _generate_image_with_metadata(self, prompt, llm_config, user_id: int, reference_image_url=None):
        provider = "stability"
        if llm_config and "provider" in llm_config:
            provider = llm_config["provider"]
        
        api_config = self.get_api_config(provider, user_id, category="Image")
        
        if provider == "doubao":
             return await self._handle_doubao_generation("image", prompt, api_config, reference_image_url)
        elif provider == "grsai":
             return await self._handle_grsai_generation("image", prompt, api_config, reference_image_url)
        elif provider == "tencent":
             return await self._handle_tencent_generation("image", prompt, api_config, reference_image_url)
        
        print(f"Mocking Image Gen for {provider}")
        return {
            "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/generated_image.png",
            "metadata": {"provider": provider, "model": api_config.get("model", "default")}
        }

    async def _generate_video_with_metadata(self, prompt, llm_config, user_id: int, reference_image_url=None, last_frame_url=None, duration=5):
        provider = "runway"
        if llm_config and "provider" in llm_config:
            provider = llm_config["provider"]
            
        api_config = self.get_api_config(provider, user_id, category="Video")

        if provider == "doubao":
             return await self._handle_doubao_generation("video", prompt, api_config, reference_image_url)
        elif provider == "grsai":
             return await self._handle_grsai_generation("video", prompt, api_config, reference_image_url, last_frame_url=last_frame_url)
        elif provider == "tencent":
             return await self._handle_tencent_generation("video", prompt, api_config, reference_image_url)

        print(f"Mocking Video Gen for {provider}")
        return {
            "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/generated_video.mp4",
            "metadata": {"provider": provider, "duration": duration}
        }
    
    # --- Provider Implementations ---
    
    async def _handle_doubao_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None):
        return {
            "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/doubao_gen.png" if gen_type == "image" else "https://pub-8415848529ba47329437b600ab383416.r2.dev/doubao_gen.mp4",
            "metadata": {"provider": "doubao", "ref": ref_image}
        }

    async def _handle_grsai_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None):
         return {
            "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/grsai_gen.png" if gen_type == "image" else "https://pub-8415848529ba47329437b600ab383416.r2.dev/grsai_gen.mp4",
            "metadata": {"provider": "grsai"}
        }

    async def _handle_tencent_generation(self, gen_type, prompt, config, ref_image=None, last_frame_url=None):
        return {
            "url": "https://pub-8415848529ba47329437b600ab383416.r2.dev/tencent_gen.png" if gen_type == "image" else "https://pub-8415848529ba47329437b600ab383416.r2.dev/tencent_gen.mp4",
            "metadata": {"provider": "tencent"}
        }
    
    def _log_generation(self, provider, prompt, status, result):
        print(f"[{provider.upper()}] {prompt[:30]}... -> {status}")

agent_service = AgentService()
