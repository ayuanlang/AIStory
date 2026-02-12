
const parse = (text) => {
    const lines = text.split('\n');
    let sceneLines = [];
    let inShotTable = false;
    let inSceneTable = false;
    let importType = 'scene'; 

    console.log(`Total Lines: ${lines.length}`);

    for (let line of lines) {
        const trimmed = line.trim();
        let isTableRow = trimmed.startsWith('|');
        let cols = [];
        if (isTableRow || trimmed.includes('|')) { 
            cols = line.split('|').map(c => c.trim());
            // Standard trim
            if (trimmed.startsWith('|') && cols.length > 0 && cols[0] === "") cols.shift();
            if (trimmed.endsWith('|') && cols.length > 0 && cols[cols.length-1] === "") cols.pop();
        }

        const canScene = true;

        const isSceneKey = (isTableRow || line.includes('|')) && (line.includes('Scene No') || line.includes('场次序号'));

        // Header
        if (canScene && !inShotTable && (isSceneKey || (importType === 'scene' && !inSceneTable && line.includes('|') && cols.length > 2))) {
            inSceneTable = true;
            inShotTable = false;
            console.log("Found Header:", line);
            sceneLines.push(line);
            continue;
        }

        // Row
        if (isTableRow) {
            const isSeparator = /\|\s*:?-{3,}:?/.test(line) || /^[\s\|:\-]*$/.test(line);
            const isEmptyRow = cols.every(c => c === "");

            if (cols.length < 2 || isSeparator || isEmptyRow) {
                 console.log("Skipping Row (Sep/Empty/Short):", line, {length: cols.length, isSeparator, isEmptyRow});
                 continue; 
            }
            
            if (inSceneTable) {
                const scData = { scene_no: cols[0] };
                if (!scData.scene_no) {
                    console.log("Skipping Row (No ScNo):", line);
                    continue;
                }
                console.log("Adding Scene:", cols[0]);
                sceneLines.push(line);
            }
        } else {
            // console.log("Skipping Line (Not Table Row):", line);
        }
    }
};

const test1 = `| Scene No | Name |
| --- | --- |
| 1 | Test |
`; // Trailing newline

const test2 = `| Scene No | Name |
| --- | --- |
| 1 | Test |
| | |
`; // Empty row

const test3 = `| Scene No | Name |
| --- | --- |
| 1 | Test |
| | | 
`; // Empty row spaces

console.log("--- Test 1 ---");
parse(test1);

console.log("--- Test 2 ---");
parse(test2);

console.log("--- Test 3 ---");
parse(test3);
