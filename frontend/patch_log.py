import re

with open('c:/AIStory/backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_code = '''            with SessionLocal() as session:
                resolved_category = str(category or "").strip()
                if not resolved_category:'''

new_code = '''            with SessionLocal() as session:
                resolved_category = str(category or "").strip()
                logger.info(f"[get_api_config] Entry | user_id={user_id} category={resolved_category} provider={provider} requested_model={requested_model} strict={strict_provider} function_name={function_name} system_api_id={system_api_id}")
                if not resolved_category:'''

text = text.replace(old_code, new_code)

old_code2 = '''                _debug_log(f"API_ROUTING_MODE mode={'new_function_based' if use_function_based_routing else 'old_legacy'} user_id={user_id} category={resolved_category} provider={provider or '<none>'} model={requested_model or '<none>'}")  '''

new_code2 = '''                logger.info(f"[get_api_config] API_ROUTING_MODE mode={'new_function_based' if use_function_based_routing else 'old_legacy'} user_id={user_id} category={resolved_category} provider={provider or '<none>'} model={requested_model or '<none>'} | function_name={function_name}, system_api_id={system_api_id}")'''

text = text.replace(old_code2, new_code2)

old_code3 = '''                    except Exception as e:
                        _debug_log(f"Error querying FunctionAPIConfig for function_name={function_name}: {e}", "warning")'''

new_code3 = '''                    except Exception as e:
                        logger.warning(f"[get_api_config] Error querying FunctionAPIConfig for function_name={function_name}: {e}")
                
                if use_function_based_routing and function_name:
                    logger.info(f"[get_api_config] target_setting found via function_name={function_name} -> selected_system_api_id={user_system_api_id}, fallback_ids={func_explicit_args.get('__function_fallback_ids', [])}")'''

text = text.replace(old_code3, new_code3)

with open('c:/AIStory/backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("patched media_service.py")
