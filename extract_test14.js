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
        if (match.index < 15) continue;
        endIndex = endIndex < 0 ? match.index : Math.min(endIndex, match.index);
    }

    if (endIndex > 0) {
        candidate = candidate.slice(0, endIndex).trim();
    }

    return candidate.trim();
};

const extractAnalysisSections = (rawText) => {
    let authoritativeSubjectText = String(rawText || '');
    authoritativeSubjectText = authoritativeSubjectText.replace(/<think>[\s\S]*?<\/think>\n*/gi, '').trim();

    let extractedText = '';
    let extractedAdaptationText = '';
    let hasStructuredSubjectIndex = false;

    if (!authoritativeSubjectText) {
        return { authoritativeSubjectText, subjectIndexText: '', adaptationText: '', hasStructuredSubjectIndex: false };
    }

    const dashMatch = authoritativeSubjectText.match(/-{4,}\s*\n([\s\S]*?)\n\s*-{4,}/);
    if (dashMatch && looksLikeSubjectIndex(dashMatch[1])) {
        extractedText = trimSubjectIndexSection(dashMatch[1]);
        hasStructuredSubjectIndex = !!extractedText;
    } else {
        const match = authoritativeSubjectText.match(/(?:^|\b|\s)#{0,6}\s*(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)\s*(?:\*\*)?\s*\n[\s\S]*/i)
            || authoritativeSubjectText.match(/#{1,6}\s*(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)[\s\S]*/i)
            || authoritativeSubjectText.match(/(?:^|\b|\s)(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)[\s\S]*/i);
        if (match) {
            extractedText = trimSubjectIndexSection(match[0]);
            hasStructuredSubjectIndex = !!extractedText;
        } else {
            const pipeMatch = authoritativeSubjectText.match(/(?:^|\n)\s*(subject_no\s*=\s*[A-Za-z]?\d+[\s\S]*)/i);
            if (pipeMatch && String(pipeMatch[1] || '').trim()) {
                extractedText = trimSubjectIndexSection(String(pipeMatch[1] || ''));
                hasStructuredSubjectIndex = !!extractedText;
            } else {
                const subjectTypeLine = authoritativeSubjectText.match(/(?:^|\n)(.*subject_type\s*=\s*(?:character|prop|environment|cover_poster).*(?:\|.*)+)/i);
                if (subjectTypeLine && String(subjectTypeLine[1] || '').trim()) {
                    const idx = authoritativeSubjectText.indexOf(subjectTypeLine[1]);
                    extractedText = trimSubjectIndexSection(authoritativeSubjectText.slice(idx));
                    hasStructuredSubjectIndex = !!extractedText;
                } else if (looksLikeSubjectIndex(authoritativeSubjectText)) {
                    extractedText = trimSubjectIndexSection(authoritativeSubjectText);
                    hasStructuredSubjectIndex = !!extractedText;
                }
            }
        }
    }

    if (!hasStructuredSubjectIndex && looksLikeSubjectIndex(authoritativeSubjectText)) {
        extractedText = trimSubjectIndexSection(authoritativeSubjectText);
        hasStructuredSubjectIndex = !!extractedText;
    }

    return {
        authoritativeSubjectText,
        subjectIndexText: hasStructuredSubjectIndex ? extractedText : '',
        adaptationText: extractedAdaptationText,
        hasStructuredSubjectIndex,
    };
};

console.log(extractAnalysisSections('``` ### Subject Index subject_no | subject_type | subject_name_zh | subject_name_en | dependency_reference | entity_attributes | script_entity_coverage --- | --- | --- | --- | --- | --- | --- S001 | character | 布鲁克·海斯 | Brooke Hayes | None | Protagonist'));
