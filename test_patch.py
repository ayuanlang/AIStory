import re 
updated_text = '场景：【@男主】走过来，【@桌子】(桌子)在那里。男主又走了。' 
anchor_text = '帅气的男主' 
prefix = '@Image1' 
escaped_entity = '男主' 
unprefixed_guard = r'(?<!@Image\d)(?<!@Video\d)' 
anchor_patterns = [ 
            rf'{unprefixed_guard}[\[【]\s*(?:CHAR|ENV|PROP)\s*:\s*@?{escaped_entity}\s*[\]】](?:\([\)]*\))?', 
            rf'{unprefixed_guard}(?:CHAR|ENV|PROP)\s*:\s*[\[【]\s*@?{escaped_entity}\s*[\]】](?:\([\)]*\))?', 
            rf'{unprefixed_guard}[\[【]\s*@?{escaped_entity}\s*[\]】](?:\([\)]*\))?', 
        ] 
for pattern in anchor_patterns: 
            def _prepend_prefix(match: re.Match[str]) -> str: 
                token = str(match.group(0) or '') 
                if token.startswith(prefix): 
                    return token 
                base = token 
                if anchor_text: 
                    if '(' in base and ')' in base: 
                        base = re.sub(r'\([)]*\)', f'({anchor_text})', base) 
                    else: 
                        base = f'{base}({anchor_text})' 
                return f'{prefix}{base}' 
 
            replaced_text, count = re.subn(pattern, _prepend_prefix, updated_text, flags=re.IGNORECASE) 
            if count > 0: 
                updated_text = replaced_text 
 
plain_pattern = rf'{unprefixed_guard}(?<![a-zA-Z0-9_]){escaped_entity}(?![a-zA-Z0-9_])' 
def _prepend_marker(match: re.Match[str]) -> str: 
            token = str(match.group(0) or '') 
            if token.startswith(prefix): 
                return token 
            base = token 
            if anchor_text: 
                if '(' in base and ')' in base: 
                    base = re.sub(r'\([)]*\)', f'({anchor_text})', base) 
                else: 
                    base = f'{prefix}[{base}]({anchor_text})' 
                    return base 
            return f'{prefix}{base}' 
 
replaced_text, count = re.subn(plain_pattern, _prepend_marker, updated_text, flags=re.IGNORECASE) 
if count > 0: 
    updated_text = replaced_text 
print(updated_text) 
