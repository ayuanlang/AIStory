const fs = require('fs');

let content = fs.readFileSync('src/pages/ProjectList.jsx', 'utf8');

// The fields to remove based on `projectCreateOptions` map loops
const fieldsToRemove = ['resolution', 'color_tone', 'global_style', 'lighting'];
for (const field of fieldsToRemove) {
    const regex = new RegExp(`<div>\\s*<label[^>]*>{t\\('.*?'\\)}<\\/label>\\s*<select[^>]*value=\\{[^}]+\\}[^>]*>\\s*\\{projectCreateOptions\\.${field}\\.map[\\s\\S]*?<\\/select>\\s*<\\/div>`, 'g');
    content = content.replace(regex, '');
}

// Remove Planned completion time
const timeRegex = new RegExp(`<div>\\s*<label[^>]*>{t\\('计划完成时间', 'Planned Completion Time'\\)}<\\/label>\\s*<input[^>]*value=\\{newPlannedCompletionTime\\}[^>]*>\\s*<\\/div>`, 'g');
content = content.replace(timeRegex, '');

// Remove Budget
const budgetRegex = new RegExp(`<div>\\s*<label[^>]*>{t\\('项目预算', 'Budget'\\)}<\\/label>\\s*<input[^>]*value=\\{newBudget\\}[^>]*>\\s*<\\/div>`, 'g');
content = content.replace(budgetRegex, '');

// Update options mapping for internationalization logic
const fieldsToUpdateOptions = [
    'type', 'language', 'base_positioning', 'era', 'lens_preference',
    'broadcast_safety_level', 'aspect_ratio', 'video_generation_preference'
];

for (const field of fieldsToUpdateOptions) {
    // We are looking to replace exactly: "{opt}</option>" with "{t(opt.split('/')[0].trim(), opt.split('/')[1]?.trim() || opt.split('/')[0].trim())}</option>"
    // This occurs inside map block for each specific field. E.g.: `{projectCreateOptions.type.map((opt) => <option key={opt} value={opt}>{opt}</option>)}`
    
    // Using string replacement on specific lines:
    const targetSearch = `projectCreateOptions.${field}.map((opt) => <option key={opt} value={opt}>{opt}</option>)`;
    const targetReplace = `projectCreateOptions.${field}.map((opt) => <option key={opt} value={opt}>{t(opt.split('/')[0].trim(), opt.split('/')[1]?.trim() || opt.split('/')[0].trim())}</option>)`;
    
    // Apply globally (there should be only 1 match anyway per field)
    content = content.split(targetSearch).join(targetReplace);
}

fs.writeFileSync('src/pages/ProjectList.jsx', content);
console.log('Done replacement');
