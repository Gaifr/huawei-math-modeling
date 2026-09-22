# 华为杯研究生数学建模全流程 Skill 设计

## 1. 目标

创建一个只面向中国研究生数学建模竞赛（华为杯/NPGMCM）的 Codex Skill。它结合两类能力：

- 采用 `math-model-skills-v2` 的工程化思想，建立阶段状态、证据链、机器门禁、断点恢复、返工传播、LaTeX/DOCX 双路线和最终渲染检查。
- 重新实现 BZD 审稿体系中的通用方法，包括逐句读题、跨问题联动、多候选模型比较、模型适配检查、分章审查、AIGC 风险提示和题目专属评委式终审。

新 Skill 不承诺获奖，不把自动门禁等同于数学正确性，也不使用历史模型替代当前题目的独立判断。

## 2. 范围与边界

### 包含

- 当届赛题、附件、官方论文模板和 AI 工具规定的导入与来源登记。
- 题意分析、建模决策、真实计算、证据整理、论文写作、审稿和提交验收的完整流程。
- LaTeX 与 Word/DOCX 两种论文源稿路线，最终均以当届华为杯官方模板和提交要求为准。
- 四个必须由用户参与的人工确认点。
- 可恢复的状态、事件日志、产物哈希和上游变更后的返工传播。
- 技术审稿与评委式审稿双轨质量检查。

### 不包含

- 其他数学建模竞赛的模板、规则和奖项预测。
- 固定的模型推荐表或“某类题必须使用某模型”的规则。
- 对竞赛结果、获奖等级或官方合规性的保证。
- 将赛题、论文、队号、个人资料或 AI 使用记录提交到 Skill 源码仓库。
- 复制 BZD 仓库中无明确许可证的原文、模板、评分数据、模型字典、脚本或 HTML。

## 3. 架构选择

采用“主控路由＋阶段协议＋确定性脚本”。

- `SKILL.md` 只保存触发条件、阶段路由、人工确认规则、证据原则和异常处理入口。
- 每个阶段的详细工作方法放入 `references/stages/`，只在该阶段加载。
- LaTeX 与 DOCX 的特定规则放入 `references/formats/`，只加载当前选定路线。
- 可确定执行的状态、哈希、一致性、目录和清单检查放入 `scripts/`。
- JSON Schema 约束状态、结果证据和审稿报告。

不采用巨型单文件 Skill，以避免无关规则占用上下文；也不拆成大量相互独立的顶层 Skill，以避免触发冲突和版本漂移。

## 4. 工作流

正式阶段如下：

1. `INTAKE`：导入当届赛题、附件、官方模板和 AI 使用规定。
2. `DISCOVERY`：逐句读题，建立任务图、数据口径、歧义登记和跨问依赖。
3. `FORMULATION`：比较候选模型，明确模型身份、假设、公式、求解算法和验证方案。
4. `COMPUTATION`：完成数据审计、代码实现、基线求解、真实运行和结果固化。
5. `EVIDENCE`：生成结果表、数据图、流程图、敏感性和稳健性证据。
6. `MANUSCRIPT`：以官方模板为主，生成 LaTeX 或 DOCX 论文及代码附录。
7. `REVIEW`：执行分章审查、模型真实性检查、AIGC 风险提示和模拟评委终审。
8. `DELIVERY`：编译或导出 PDF，检查匿名性、目录、页数、附件、文件名和提交清单。

### 4.1 人工确认点

工作流必须在以下位置暂停：

1. `DISCOVERY` 后：用户确认题意、歧义处理和交付要求。
2. `FORMULATION` 后：用户选择主模型、备选模型和验证强度。
3. `COMPUTATION` 后：用户确认结果可信，并选择保持基线或进入增强。
4. `REVIEW` 后：用户确认 P1 风险是否均已解决或明确接受，批准终稿候选版本。

每次确认必须绑定相关产物哈希。绑定文件发生实质变化后，原确认失效。

## 5. 两类上游优势的融合

| 阶段 | 工程化能力 | 分析与审稿能力 | 融合结果 |
|---|---|---|---|
| INTAKE | 竞赛 Profile、模板来源、规则快照 | 材料完整性判断 | 缺少当届正式材料时限制后续合规声明 |
| DISCOVERY | 数据模式、附件审计、产物合同 | 逐句解释、隐含条件、任务映射 | 句子—任务—数据—产物追溯矩阵 |
| FORMULATION | 模型/机制/算法分离、基线优先 | 多候选比较、适配与失败条件 | 经人工确认冻结统一模型决策 |
| COMPUTATION | 真实运行、结果 JSON、源码哈希 | 数据能否支持模型的质询 | 结论绑定输入、程序、参数和输出证据 |
| EVIDENCE | 图表清单、尺寸与几何审计 | 图表是否支持论文论点 | 机器门禁与论证价值双重检查 |
| MANUSCRIPT | 双格式、代码附录、数值一致性 | 分章节专项标准 | 写作前锁证据，写作后定向检查 |
| REVIEW | 多轮审稿、严重级别、返工传播 | 题目专属评分、原子扣分、可读性 | 技术审稿与评委审稿双轨运行 |
| DELIVERY | 编译、匿名、目录、页数、附件 | 格式扣分视角 | 可提交包、遗留风险和人工批准记录 |

### 5.1 候选模型漏斗

候选模型按以下顺序收敛：

1. 从整题任务图出发提出真正不同的可行模型。
2. 按数据要求、假设、输出能力、可解释性、实现成本和跨问兼容性比较。
3. 为重要候选建立相同数据、约束、指标和计算预算下的公平对照。
4. 先选择可解释、可验证的基线，再提出增强机制。
5. 用户确认主模型和备选模型后，进入真实计算。

求解器或算法名称不得冒充数学模型。允许采用 Skill 未收录的新方法，但必须说明数学机制、数据支持、验证方案和失败条件。

### 5.2 双轨审稿与根因回退

技术审稿检查数据、模型、程序、数值、哈希、图表和论文的一致性。评委审稿检查任务覆盖、模型必要性、跨问连贯性、创新真实性、验证力度和外行可读性。

审稿发现问题时按根因回退：

- 表达问题返回 `MANUSCRIPT`。
- 图表证据不足返回 `EVIDENCE`。
- 数值不可复现返回 `COMPUTATION`。
- 模型不适配返回 `FORMULATION`。
- 题意理解错误返回 `DISCOVERY`。

不得只修改终稿文字掩盖上游问题。

## 6. 运行时工作区

Skill 仓库与每次参赛工作区分离。运行时工作区结构为：

```text
contest-workspace/
├── inputs/
│   ├── problem/
│   ├── attachments/
│   ├── official-template/
│   └── official-rules/
├── analysis/
│   ├── sentence-ledger.md
│   ├── task-graph.md
│   ├── data-audit.md
│   └── ambiguity-register.md
├── modeling/
│   ├── candidate-models.md
│   ├── model-decision.md
│   ├── formulation.md
│   └── validation-plan.md
├── code/
│   ├── main.py
│   ├── problems/
│   ├── tests/
│   └── code-manifest.json
├── results/
│   ├── result-evidence.json
│   ├── metrics/
│   ├── tables/
│   └── run-logs/
├── figures/
│   ├── figure-manifest.json
│   ├── data/
│   ├── schematics/
│   └── visual-qa.json
├── manuscript/
│   ├── source/
│   ├── paper.docx
│   ├── paper.pdf
│   └── ai-usage-record.json
├── review/
│   ├── issue-ledger.json
│   ├── technical-review.md
│   ├── judge-review.md
│   └── revision-rounds/
├── delivery/
│   ├── submission-manifest.json
│   └── final-check.md
└── .huawei-modeling/
    ├── state.json
    ├── events.jsonl
    ├── approvals.json
    ├── rule-snapshot.json
    └── gates/
```

## 7. 状态与证据合同

`state.json` 保存当前阶段、阶段状态、输入与产物哈希、过期产物、阻塞项、论文路线和规则版本。

`events.jsonl` 使用只追加事件记录阶段开始、完成、返工、脚本执行、文件变化和门禁结果。

`approvals.json` 保存四个确认点的选择、说明、时间和绑定哈希。
`rule-snapshot.json` 保存当届官方规则的机器可读条款（页数、目录深度、匿名要求、
命名规则等）；条款缺失时对应检查记为未验证，快照本身缺失或与官方规则哈希不一致时
禁止声明格式合规。

`result-evidence.json` 为每个关键结论登记：

- 结论标识与对应问题；
- 输入数据及哈希；
- 程序入口、源码哈希和运行命令；
- 模型身份、定制机制和求解算法；
- 参数、随机种子和运行环境；
- 结构化输出及精度；
- 校验、敏感性或稳健性证据；
- 被哪些表格、图形和论文位置引用。

## 8. 阶段门禁

| 阶段 | 自动门禁 | 人工判断 |
|---|---|---|
| INTAKE | 必要材料存在并登记来源与哈希 | 材料是否确属当届正式版本 |
| DISCOVERY | 题目句子和编号任务均有映射，无虚构字段 | 歧义解释和跨问关系是否合理 |
| FORMULATION | 主模型、备选、公式、输入输出和验证计划完整 | 模型是否值得投入计算 |
| COMPUTATION | 程序运行成功，结果合法，约束/误差/基线检查通过 | 结果是否符合领域常识 |
| EVIDENCE | 图表来源可追溯，字号、裁切、重叠和路径通过 | 图表是否支持实际论点 |
| MANUSCRIPT | 数值可追溯，章节、引用、附录完整，可编译或导出 | 论文是否清楚且有说服力 |
| REVIEW | P0 为零，问题去重，报告与论文哈希匹配 | P1 是否修复或明确接受 |
| DELIVERY | 当届规则快照存在且页数、目录深度、匿名、文件名、附件和清单通过 | 用户最终批准提交 |

问题严重级别：

- `P0`：资格、题意、数据真实性、模型根本错误、结果伪造或关键文件缺失。
- `P1`：主要任务未回答、模型证据不足、结果不可复现或关键数值冲突。
- `P2`：验证不足、图表表达差、章节断裂、引用或格式问题。
- `P3`：语言、局部版式和非关键可读性问题。

终稿至少要求 `P0=0`。P1 必须逐项修复或由用户明确接受。

## 9. 论文路线

LaTeX 和 DOCX 共用同一份内容证据与审稿台账，只在排版阶段分流。

- DOCX 必须以用户提供的当届官方 Word 模板为底稿，保留其页面设置、标题、目录和必要字段。
- LaTeX 必须在最终 PDF 的页面结构、匿名要求、目录层级和视觉形式上对齐当届官方模板，不允许仅凭文档类名称宣称合规。
- 两条路线最终都生成 PDF，并接受相同的数值、引用、匿名、目录、页数和视觉检查。
- 当届正式要求始终高于 Skill 内部参考。规则快照变化后，受影响门禁必须重新执行。

## 10. 异常处理

- 缺少官方模板或规则时允许继续读题和建模，但禁止进入合规论文交付。
- 数据字段不明时生成条件式方案并登记阻塞项，不得虚构数据。
- 求解失败时保存日志和最后状态，只做有限重试，随后回到模型或算法选择。
- 论文数值冲突时以当前有效结构化计算结果为依据，不得修改结果迎合论文。
- DOCX 无法自动导出 PDF 时要求用户用 Word 导出后恢复视觉检查。
- LaTeX 编译失败时必须修复后重试；编译器不可用只能记录为未核验。
- 审稿发现上游问题时标记相应阶段需返工，并使依赖产物过期。

## 11. Skill 仓库结构

```text
huawei-math-modeling/
├── SKILL.md
├── agents/openai.yaml
├── scripts/
│   ├── workspace_init.py
│   ├── workflow.py
│   ├── gate_check.py
│   ├── evidence_check.py
│   ├── manuscript_check.py
│   └── quick_smoke.py
├── references/
│   ├── workflow.md
│   ├── human-checkpoints.md
│   ├── evidence-contract.md
│   ├── stages/
│   │   ├── intake.md
│   │   ├── discovery.md
│   │   ├── formulation.md
│   │   ├── computation.md
│   │   ├── evidence.md
│   │   ├── manuscript.md
│   │   ├── review.md
│   │   └── delivery.md
│   └── formats/
│       ├── latex.md
│       └── docx.md
├── assets/schemas/
│   ├── workflow-state.schema.json
│   ├── result-evidence.schema.json
│   ├── review-report.schema.json
│   └── rule-snapshot.schema.json
├── docs/superpowers/specs/
├── THIRD_PARTY_NOTICES.md
└── LICENSE
```

不创建无用途的占位目录或重复 README。阶段协议和脚本只在有明确运行价值时保留。

## 12. 验证

实现完成后至少执行：

1. `skill-creator` 的 `quick_validate.py`。
2. 初始化测试：生成完整工作区、状态和四个确认点。
3. 状态机测试：禁止跳阶段、支持恢复、上游变化正确传播过期状态。
4. 证据链测试：论文数字与结果证据冲突时必须失败。
5. 模型身份测试：求解算法不得登记为数学模型。
6. 审稿去重测试：同一根因不得由多个检查重复记分。
7. 双格式路由测试：LaTeX 和 DOCX 共用证据并加载各自协议。
8. 隐私测试：真实赛题、论文、队号、本地绝对路径和 AI 使用记录不得进入 Skill 仓库。
9. 使用合成小题运行最小端到端冒烟测试。

这些测试只验证流程与合同，不证明数学模型正确或保证获奖。

## 13. 来源、许可与发布

- 新代码和新写指令采用 MIT License。
- `THIRD_PARTY_NOTICES.md` 保留 `math-model-skills-v2` 的 MIT 版权与改造说明。
- 对 BZD 只注明方法设计参考，不复制其无明确许可的具体表达和资产。
- 远端目标为公开仓库 `Gaifr/huawei-math-modeling`。
- 在功能分支完成实现和验证后创建 Pull Request，不直接绕过审查合并到 `main`。
