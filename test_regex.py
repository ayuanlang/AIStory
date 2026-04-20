import json
import re

prompt = """[Global Style](Cinematic realism with high-contrast lighting, emphasizing a sleek, modern, and high-stakes urban environment.) Cinematic realism with high-contrast lighting, sleek, modern, high-stakes urban environment.
[Camera Movement] (P1) The camera starts at an Extreme Low Angle, then smoothly Cranes Up and Tilts Up from the marble floor of ENV:[Hotel Entrance Front](luxury hotel entrance, brass revolving door, marble steps, warm night lighting). As it rises, it performs a slow Rack Focus, shifting focus from the reflection to the real scene, settling into a Medium Shot of CHAR:[@Scarface](male gangster boss, prominent facial scar, black leather jacket, arrogant posture ) and CHAR:[@Doris Clark Drunk](female CEO, blonde wavy hair, blue silk evening gown, vulnerable drunk state ). (P2) The camera then smoothly Tracks left, following CHAR:[@Arno Janitor](middle-aged male janitor, powerful build, deep-set grey eyes, grey janitor uniform ) as he pushes his cleaning cart from the background into the midground, finally stopping and turning towards the conflict, landing in a loose over-the-shoulder shot behind him.
[Action Beat Chain] (P1) In ENV:[Hotel Entrance Front], CHAR:[@Scarface] physically blocks a swaying CHAR:[@Doris Clark Drunk], his hands roaming over her arms. (Dialogue (CHAR:[@Scarface]) (voice_type: raspy male voice, tone: sleazy, speed: medium, volume: normal): "Come on, Doris. I’ve already booked the room. Let’s go up and have some fun.") -> CHAR:[@Doris Clark Drunk] struggles weakly. (Dialogue (CHAR:[@Doris Clark Drunk]) (voice_type: weak female voice, tone: pained, speed: medium, volume: normal): "You... let me go.") -> resulting in CHAR:[@Scarface] starting to drag her. (P2) CHAR:[@Doris Clark Drunk] shouts. (Dialogue (CHAR:[@Doris Clark Drunk]) (voice_type: high-pitched female voice, tone: desperate, speed: fast, volume: loud): "Help me!") -> CHAR:[@Arno Janitor], who was passing by, stops his cart, turns. (Dialogue (CHAR:[@Arno Janitor]) (voice_type: deep male voice, tone: flat, speed: slow, volume: low): "Let her go.") -> resulting in all of CHAR:[@Scarface]'s men turning to look at CHAR:[@Arno Janitor].
[Dynamic Atmosphere] The warm, luxurious light of the hotel entrance contrasts sharply with the menacing tension of the scene.

实体参考映射: [Global Style]->图1; [Camera Movement]->图2; ENV:[Hotel Entrance Front]->图3; CHAR:[@@Scarface]->图4; CHAR:[@@Doris Clark Drunk]->图5; CHAR:[@@Arno Janitor]->图6; [Action Beat Chain]->图7; [Dynamic Atmosphere]->图8"""

entity_lookup = {
    "Global Style": {"entity_type": "subject", "image_url": "url1", "name": "Global Style"},
    "Camera Movement": {"entity_type": "subject", "image_url": "url2", "name": "Camera Movement"},
    "Hotel Entrance Front": {"entity_type": "env", "image_url": "url3", "name": "Hotel Entrance Front"},
    "@Scarface": {"entity_type": "character", "image_url": "url4", "name": "@Scarface"},
    "@Doris Clark Drunk": {"entity_type": "character", "image_url": "url5", "name": "@Doris Clark Drunk"},
    "@Arno Janitor": {"entity_type": "character", "image_url": "url6", "name": "@Arno Janitor"},
    "Action Beat Chain": {"entity_type": "subject", "image_url": "url7", "name": "Action Beat Chain"},
    "Dynamic Atmosphere": {"entity_type": "subject", "image_url": "url8", "name": "Dynamic Atmosphere"},
}

normalized_text = prompt.lower()
for key, row in entity_lookup.items():
    norm_key = key.lower()
    has_ascii = bool(re.search(r"[a-z0-9]", norm_key, flags=re.IGNORECASE))
    if has_ascii:
        pattern = rf"(?<![a-z0-9]){re.escape(norm_key)}(?![a-z0-9])"
        matched = re.search(pattern, normalized_text, flags=re.IGNORECASE) is not None
    else:
        matched = norm_key in normalized_text
        
    print(f"Key: {key}, Matched: {matched}, Type: {row['entity_type']}")