with open('src/pages/editor/components/ProjectOverview.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
div_depth = 0

for i, line in enumerate(lines):
    if not skip:
        # Check if this line is the start of a block we want to cut
        if '<div className="mt-6 space-y-6">' in line or '<div className="mt-8">' in line:
            # We must look ahead to see what's inside
            lookahead = "".join(lines[i:i+30])
            if 'Scene Analysis Dimensions' in lookahead or 'Collaborators' in lookahead:
                skip = True
                div_depth = 1 # We just entered the div
                # Count inner divs on the same line if any (probably 1)
                div_depth += line.count('<div') - 1
                div_depth -= line.count('</div')
                continue
        
        new_lines.append(line)
    else:
        # We are skipping
        div_depth += line.count('<div')
        div_depth -= line.count('</div')
        if div_depth <= 0:
            skip = False

with open('src/pages/editor/components/ProjectOverview.jsx', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Removed sections safely from overview.")
