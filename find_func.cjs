const fs = require('fs');
let code = fs.readFileSync('backend/app/services/media_service.py', 'utf8');

const regex = /def _get_fallback_api_config[\s\S]+?def _is_smart_routing/g;
let match = regex.exec(code);
if (match) {
    fs.writeFileSync('temp_func.py', match[0], 'utf8');
} else {
    // try finding the method containing _trace_default_vs_selected
    const lines = code.split("\n");
    let start = 0;
    for(let i=0; i<lines.length; i++) {
        if(lines[i].trim().startsWith("def ")) start = i;
        if(lines[i].includes("_trace_default_vs_selected")) {
            console.log("Def is at line", start, lines[start]);
            break;
        }
    }
}