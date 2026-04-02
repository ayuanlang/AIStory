const fs = require('fs');
const lines = fs.readFileSync('backend/app/api/endpoints.py', 'utf8').split("\n");
for(let i=0; i<lines.length; i++) {
    if(lines[i].includes('system_api_id_raw =') ) {
        console.log("Found system_api_id at", i);
        let fnDef = "";
        for(let k=i; k>i-50; k--) if(lines[k].startsWith("def ")) { fnDef = lines[k]; break; }
        console.log("Inside:", fnDef);
        console.log(lines.slice(i, i+30).join("\n"));
        break;
    }
}