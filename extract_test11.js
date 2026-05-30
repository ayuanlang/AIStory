module.exports = function(rawText) {
        let authoritativeSubjectText = String(rawText || '');
        // Erase any <think> blocks before doing regex to prevent huge text matching failures
        authoritativeSubjectText = authoritativeSubjectText.replace(/<think>[\s\S]*?<\/think>\n*/gi, '').trim();

        let extractedText = '';
        let extractedAdaptationText = '';
        let hasStructuredSubjectIndex = false;

                const looksLikeSubjectIndex = (candidateText) => {
            const candidate = String(candidateText || '');
            return /subject_no\s*=|subject_type\s*=|subject_name_(?:zh|en|exact)\s*=|subject_type\s*\|/i.test(candidate)
            || /(?:^|\n)\s*\|?\s*[A-Za-z]?\d{1,}\s*\|\s*(?:character|prop|environment|cover_poster|角色|道具|场景|服装|特效)\b/i.test(candidate)
            || /(?:^|\n)\s*(?:#{0,6}\s*)?(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)/i.test(candidate);
        };

        const trimSubjectIndexSection = (candidateText) => {
            let candidate = String(candidateText || '').replace(/\r\n/g, '\n').trim();
            if (!candidate) return '';

            const subjectHeaderMatch = candidate.match(/(?:^|\n)\s*(?:#{0,6}\s*)?(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)\s*(?:\*\*)?\s*\n?/i);
            if (subjectHeaderMatch?.index >= 0) {
                candidate = candidate.slice(subjectHeaderMatch.index).trim();
            }

            const endMarkers = [
                /^\s*-{4,}\s*$/im,
                /^\s*(?:###?\s*)?(?:Project\s*Visual\s*Backfill|第三部分|Final\s*Consistency\s*Report|一致性检查)\b/im,
                /^\s*\{\s*"project_visual_backfill"\s*:/im,
                /^\s*(?:(?:##|###)\s*(?:-1\)|Scenes?|场景列表))/im,
                /^\s*(?:###?\s*(?:-1\)\s*类型研判|Scenes|场景列表))/im,
                /^###?\s*(?:(?:第二|第一)部分)?\s*(?:Adapted\s*Script|参考改编|修改(?:后?)的剧本)/im
            ];

            let endIndex = -1;
            for (const pattern of endMarkers) {
                const match = pattern.exec(candidate);
                if (!match || typeof match.index !== 'number' || match.index <= 0) continue;
                // If it matched within the first 15 chars, it probably matched our own header mistakenly or there's no actual table content
                if (match.index < 15) continue;
                endIndex = endIndex < 0 ? match.index : Math.min(endIndex, match.index);
            }

            if (endIndex > 0) {
                candidate = candidate.slice(0, endIndex).trim();
            }

            return candidate.trim();
        };

        if (!authoritativeSubjectText) {
            return {hasStructuredSubjectIndex, extractedText}; }