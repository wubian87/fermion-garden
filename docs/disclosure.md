# Disclosure and public boundary

本仓库是白名单导出，不是私人实验母库的镜像。

## Included

- 标准库实现的 `ctx-key` v0.1 基线；
- 自造的离线示例与单元测试；
- 第 120 轮精选冻结判词、自造题、受控机械验证器和正式结果。

## Excluded

- API 凭证、`.env`、本机绝对路径；
- 模型原始 transcript、reasoning、私人会话与行为画像；
- 锁文件、运行日志、缓存与逐轮代码库；
- 第 121 轮尚未收口的在途结果；
- 来源或再发布权未逐项确认的外部材料。

私人实验曾调用闭源模型和商业 API。公开核心默认不联网，不能把“代码可离线运行”改写成“所有实验均使用开源模型”。

**商业 API 与闭源模型清单（分两层，⛔ 不用「只报本赛」盖过历史）**

**A 层 · 本赛结论所依赖的实验（第 118–121 轮，逐实验目录复核）**

- **DeepSeek-V4-Flash** — 火山方舟 Agent Plan（`ark.cn-beijing.volces.com/api/plan`，商业套餐）；第 118–121 轮全部主跑（第 120 轮全链合计约 1830 万 output tokens）。
- **DeepSeek-V4-Pro** — 同平台，仅早期小批难度探针。
- **BAAI/bge-m3** — 硅基流动（`api.siliconflow.cn/v1/embeddings`，商业 API），判据选读的相似度尺，结果带本地缓存。

**B 层 · 项目历史上接入并调用过的商业 API 与闭源模型（⛔ 不构成本赛证据，不在任何结论链上）**

- **火山方舟 Agent Plan 聚合口**：`doubao-seed-2.1-turbo`、`minimax-m3`、`glm-5.2`、`kimi-k2.7-code`、`deepseek-v4-flash`（第 116–117 轮，审这个口本身）。
- **硅基流动聚合口**（`/v1/chat/completions`）：`Pro/MiniMaxAI/MiniMax-M2.5`、`Qwen/Qwen3.5-397B-A17B`、`Qwen/Qwen3.5-122B-A10B`、`Pro/moonshotai/Kimi-K2.6`、`zai-org/GLM-5.2`。
- **DeepSeek 官方 API**（`api.deepseek.com`）：`deepseek-chat`。
- **小米 MiMo ／ Kimi coding ／ GLM coding ／ 阿里云 DashScope**：模型选型与「跨厂位」对照（第 26、80、100、109 轮）。

**口径与限度**

- 全部为按量或套餐计费的推理 API；**无任何闭源权重本地部署**。
- 密钥一律走环境变量，不落仓库、不进 Skill 记录、不进本公开副本。
- **B 层未逐模型重建调用量账**：它是按实验目录与代码复核出的接入清单，不是 token 账。只有 A 层带可核用量。
- 公开核心默认零网络，不把任何一家闭源模型写成 `ctx-key` 的运行条件。换模型＝换配置。
