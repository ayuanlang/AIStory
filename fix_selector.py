import codecs
import re

text = codecs.open('frontend/src/components/FunctionApiSelector.jsx', 'r', 'utf-8').read()

# The original JSX option render:
# <option key={api.system_api_id} value={api.system_api_id}>  
#     {api.system_api_name} {api.is_fallback ? '(?꾤??)' : ''}
# </option>
# So let's replace the whole option tag block

new_content = '''<option key={api.system_api_id} value={api.system_api_id}>
                        {api.alias ? api.alias : (api.system_api_name || 'API ' + api.system_api_id)} 
                        {api.applicable_languages && api.applicable_languages.length > 0 ? \ (\)\ : ''}
                        {api.is_fallback ? ' (备用)' : ''}
                    </option>'''

text = re.sub(r'<option key=\{api\.system_api_id\}.*?</option>', new_content, text, flags=re.DOTALL)

codecs.open('frontend/src/components/FunctionApiSelector.jsx', 'w', 'utf-8').write(text)
