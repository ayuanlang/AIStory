# coding: utf-8
import sys
filepath = 'C:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

b1_old = '''            const basePositioning = getInfoValue(['base_positioning']);




            if (language) {

            }

            const globalStyle = getInfoValue(['Global_Style', 'global_style', 'style']);
            const tone = getInfoValue(['tone', 'mood']);
            const lighting = getInfoValue(['lighting', 'light']);



            const eraField = getInfoValue(['era', 'era_setting', 'period', 'time_setting']);
            const regionField = getInfoValue(['region_culture', 'region', 'country', 'country_region']);



            if (Object.keys(projectInfo).length > 0) {'''

b1_new = '''            const basePositioning = getInfoValue(['base_positioning']);
            if (title) metaParts.push(\Title: \);
            if (episode) metaParts.push(\Episode: \);
            if (type) metaParts.push(\Type: \);
            if (basePositioning) metaParts.push(\Base Positioning: \);
            if (language) {
                metaParts.push(\Language: \);
            }
            metaParts.push('[Technical & Visual Parameters]');
            const globalStyle = getInfoValue(['Global_Style', 'global_style', 'style']);
            const tone = getInfoValue(['tone', 'mood']);
            const lighting = getInfoValue(['lighting', 'light']);
            if (globalStyle) metaParts.push(\Global Style: \);
            if (tone) metaParts.push(\Tone: \);
            if (lighting) metaParts.push(\Lighting: \);
            const eraField = getInfoValue(['era', 'era_setting', 'period', 'time_setting']);
            const regionField = getInfoValue(['region_culture', 'region', 'country', 'country_region']);
            if (eraField) metaParts.push(\Era / Period: \);
            if (regionField) metaParts.push(\Region / Country: \);
            
            metaParts.push('Use this project context as first-class constraints before generating the subjects.');

            if (Object.keys(projectInfo).length > 0) {'''

b2_old = '''                            const basePositioning = getInfoValue(['base_positioning']);




                            if (language) {

                            } else {


                            }

                            const aspectRatio = getVisualValue(['aspect_ratio']);
                            const imageSize = getVisualValue(['image_size']);
                            const horizontalResolution = getVisualValue(['horizontal_resolution']);
                            const verticalResolution = getVisualValue(['vertical_resolution']);
                            const frameRate = getVisualValue(['frame_rate']);
                            const quality = getVisualValue(['quality']);
                            const globalStyle = getInfoValue(['Global_Style', 'global_style', 'style']);
                            const tone = getInfoValue(['tone', 'mood']);
                            const lighting = getInfoValue(['lighting', 'light']);










                            const eraField = getInfoValue(['era', 'era_setting', 'period', 'time_setting']);
                            const regionField = getInfoValue(['region_culture', 'region', 'country', 'country_region']);
                            const shotPrefField = getInfoValue(['shot_preference', 'lens_preference', 'camera_preference']);
                            const broadcastSafetyField = getInfoValue(['broadcast_security_level', 'broadcast_safety_level', 'safety_level', 'broadcast_safety']);





                     if (metaParts.length > 1) {'''

b2_new = '''                            const basePositioning = getInfoValue(['base_positioning']);
                            if (title) metaParts.push(\Title: \);
                            if (episode) metaParts.push(\Episode: \);
                            if (type) metaParts.push(\Type: \);
                            if (basePositioning) metaParts.push(\Base Positioning: \);
                            if (language) {
                                metaParts.push(\Language: \);
                            } else {
                                metaParts.push('Language: (empty)');
                                metaParts.push('Language Warning: project language is empty. You MUST infer one target natural language from script context and keep all natural-language descriptions consistently in that single language.');
                            }
                            metaParts.push('[Technical & Visual Parameters]');
                            const aspectRatio = getVisualValue(['aspect_ratio']);
                            const imageSize = getVisualValue(['image_size']);
                            const horizontalResolution = getVisualValue(['horizontal_resolution']);
                            const verticalResolution = getVisualValue(['vertical_resolution']);
                            const frameRate = getVisualValue(['frame_rate']);
                            const quality = getVisualValue(['quality']);
                            const globalStyle = getInfoValue(['Global_Style', 'global_style', 'style']);
                            const tone = getInfoValue(['tone', 'mood']);
                            const lighting = getInfoValue(['lighting', 'light']);
                            if (aspectRatio) metaParts.push(\Aspect Ratio: \);
                            if (imageSize) metaParts.push(\Image Size: \);
                            if (horizontalResolution) metaParts.push(\Horizontal Resolution: \);
                            if (verticalResolution) metaParts.push(\Vertical Resolution: \);
                            if (frameRate) metaParts.push(\Frame Rate: \);
                            if (quality) metaParts.push(\Quality: \);
                            if (globalStyle) metaParts.push(\Global Style: \);
                            if (borrowedFilms.length > 0) metaParts.push(\Borrowed Films: \);
                            if (tone) metaParts.push(\Tone: \);
                            if (lighting) metaParts.push(\Lighting: \);

                            const eraField = getInfoValue(['era', 'era_setting', 'period', 'time_setting']);
                            const regionField = getInfoValue(['region_culture', 'region', 'country', 'country_region']);
                            const shotPrefField = getInfoValue(['shot_preference', 'lens_preference', 'camera_preference']);
                            const broadcastSafetyField = getInfoValue(['broadcast_security_level', 'broadcast_safety_level', 'safety_level', 'broadcast_safety']);
                            if (eraField) metaParts.push(\Era / Period: \);
                            if (regionField) metaParts.push(\Region / Country: \);
                            if (shotPrefField) metaParts.push(\Shot / Lens Preference: \);
                            if (broadcastSafetyField) metaParts.push(\Broadcast Security Level: \);
                            metaParts.push('Use this project context as first-class constraints before analyzing the script.');

                     if (metaParts.length > 1) {'''

text = text.replace(b1_old, b1_new)
text = text.replace(b2_old, b2_new)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print('Success!!')
