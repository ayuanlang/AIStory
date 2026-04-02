const fs = require('fs');
let code = fs.readFileSync('backend/app/services/media_service.py', 'utf8');

let match = code.match(/def _get_fallback_api_config[\s\S]*?def _is_smart_routing/);
if(match) {
    fs.writeFileSync('temp_fallback.py', match[0], 'utf8');
}