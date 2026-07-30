# Project Reset：100 天职业重启计划

从销售运营转型为 **Business Automation Specialist** 的项目制作品集。

## 执行原则

- 不以“学完知识”为目标，只交付能运行、能展示、能解释的项目；
- 每天完成一个可验证成果；
- 遇到不会的问题，使用 AI 协作解决；
- 用 GitHub 保存项目文件，用 Notion 展示业务案例和每日复盘；
- 每个自动化项目都要说明业务问题、流程、风险和实际验证结果。

## 项目进度

| Day | 项目 | 业务方向 | 当前状态 | 证据 |
| --- | --- | --- | --- | --- |
| 1 | [企业微信称呼助手](projects/wecom-name-helper/README.md) | 销售流程自动化 | 📌 已展示 | 语法检查、合成 OCR 自测通过；已交付同事真实使用并确认运行准确 |
| 2 | [销售线索自动评分器](projects/lead-scoring-assistant/README.md) | 销售线索优先级自动化 | 📌 已展示 | 30 条虚拟线索全部成功评分；结果严格降序，业务规则通过验收 |
| 3 | [销售跟进计划生成器](projects/follow-up-planner/README.md) | 销售任务编排自动化 | ✅ 完成 | 30 条评分结果全部转换为带截止日期、动作和渠道的跟进任务 |
| 4 | [销售跟进状态检查器](projects/follow-up-status-checker/README.md) | 销售任务提醒自动化 | ✅ 完成 | 30 条任务完成状态检查；今日待跟进 7 条、逾期 12 条、未到期 10 条、已完成 1 条 |

## Day 1：企业微信称呼助手

读取企业微信客户聊天窗口中的姓名，自动生成称呼，并把“称呼＋今日话术”填入聊天框。程序不会自动发送，最终消息由销售人员检查后手动发送。

- [本地项目说明](projects/wecom-name-helper/README.md)
- [Notion 项目记录](https://app.notion.com/p/3aadf5b1d9e8815d815ffe03657766b0)

## Day 2：销售线索自动评分器

读取销售线索 CSV，根据公司规模、职位、预算、紧迫度和互动程度计算 0–100 分，自动划分 A/B/C 等级，并输出按优先级排列的跟进名单。

- [项目说明](projects/lead-scoring-assistant/README.md)
- [Notion 项目记录](https://app.notion.com/p/3aadf5b1d9e88147baafc428d3b16446)

## Day 3：销售跟进计划生成器

连接 Day 2 的评分结果，把 A/B/C 等级继续转换成明确的跟进日期、优先级、动作、渠道和任务状态，形成从“判断优先级”到“安排执行”的连续自动化流程。

- [项目说明](projects/follow-up-planner/README.md)
- [Notion 项目记录](https://app.notion.com/p/3addf5b1d9e881449831d96e3fd1d279)

## Day 4：销售跟进状态检查器

读取 Day 3 的跟进计划，根据中国当前日期、任务截止日期和完成状态，自动区分今日待跟进、逾期、未到期和已完成任务，并按照销售行动顺序输出检查表。

- [项目说明](projects/follow-up-status-checker/README.md)
- [Notion 项目记录](https://app.notion.com/p/39edf5b1d9e880ff9890c7abc72215e7?pvs=1)

## 作品集质量标准

项目只有同时满足以下条件，才标记为“完成”：

1. 有明确的业务使用场景；
2. 有可运行或可演示的交付物；
3. 有验证证据，而不只是代码；
4. 有安全边界或异常处理说明；
5. 有 GitHub 项目说明；
6. 有 Notion 案例页和复盘。
