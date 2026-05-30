const regex1 = /(?:^|\b|\s)#{0,6}\s*(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)\s*(?:\*\*)?\s*\n[\s\S]*/i;
const regex2 = /#{1,6}\s*(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)[\s\S]*/i;
const regex3 = /(?:^|\b|\s)(?:\*\*)?\s*(?:Subject Index|Subjects? Index|角色索引|道具索引|场景索引|实体索引|设计资产索引|Entities Index|资产清单|实体清单|设计清单|Subject Extract|剧本实体分析|主要提取实体|实体|Entities|Subjects|Assets|资产|人物列表|提取实体)[\s\S]*/i;

const str = "```\n### Subject Index\nsubject_no | subject_type\n--- | ---\nS001 | character";

console.log(str.match(regex1)?.[0].slice(0, 50));
console.log(str.match(regex2)?.[0].slice(0, 50));
console.log(str.match(regex3)?.[0].slice(0, 50));
