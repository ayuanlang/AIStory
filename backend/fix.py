import re

with open('app/api/settings.py', 'r', encoding='utf-8') as f:
    text = f.read()

part1_bad = '''# --- Function API Config Routes ---
from app.schemas.settings import FunctionAPIConfigUpdate, FunctionAPIConfigOut  

from app.models.all_models import APIRoutingConfig

@router.get(\"/settings/system/function_api_configs\", response_model=List[FunctionAPIConfigOut])

@router.get(\"/settings/system/api_routing_mode\")'''

part1_good = '''# --- Function API Config Routes ---
from app.schemas.settings import FunctionAPIConfigUpdate, FunctionAPIConfigOut  
from app.models.all_models import APIRoutingConfig

@router.get(\"/settings/system/api_routing_mode\")'''

text = text.replace(part1_bad, part1_good)

part2_bad = '''    return {\"use_function_based_routing\": conf.use_function_based_routing}      

def get_all_function_api_configs('''
part2_good = '''    return {\"use_function_based_routing\": conf.use_function_based_routing}

@router.get(\"/settings/system/function_api_configs\", response_model=List[FunctionAPIConfigOut])
def get_all_function_api_configs('''

text = text.replace(part2_bad, part2_good)

with open('app/api/settings.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
