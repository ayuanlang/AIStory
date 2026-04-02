const fs = require('fs');
let code = fs.readFileSync('backend/app/services/media_service.py', 'utf8');

const lines = code.split("\n");
let currentLevel = 0;
for (let i = 3832; i >= 0; i--) {
    if (lines[i].startsWith("    def ")) {
        console.log("Parent def:", lines[i]);
        const start = i;
        let end = i;
        for(let j=i+1; j<lines.length; j++) {
            if(lines[j].startsWith("    def ") && lines[j].trim() !== "") {
                end = j;
                break;
            }
        }
        fs.writeFileSync("temp_func.py", lines.slice(start, end).join("\n"), "utf8");
        break;
    }
}