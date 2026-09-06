# novelwriter 整本生产工作台 — 外接工具与使用说明

参考 [AI-Novel-Writing-Assistant](https://github.com/ExplosiveCoderflome/AI-Novel-Writing-Assistant)
的功能主链，用 **纯 Tkinter + Python stdlib** 实现（零第三方 Python 依赖）。

## 一、功能对照表

| 参考项目功能 | 本实现 | 状态 |
|---|---|---|
| 自动导演开书（一句灵感→整本方向） | `/novel` 工作台「开书」页 | ✅ |
| 项目设定 / 宏观规划 / 本书世界 / 角色 / 卷战略 / 节奏拆章 | 流水线阶段 setup→outline→world→characters→volume→chapter_plan | ✅ |
| 章节执行链（草稿→审校→修复→状态回灌） | chapters 阶段：逐章 草稿→审校→自动修复一次→事实/伏笔台账回灌 | ✅ |
| 质量债（局部失败不阻断主链） | 引擎 fail="debt" 策略 + 章级 issues 台账 | ✅ |
| 检查点恢复（可暂停/续跑） | pipeline JSON 每阶段落盘 + `until` 逐阶段确认 + 断内循环恢复 | ✅ |
| 拆书工作台（题材/结构/人物/写法特征） | 衍生页：外部 txt → 拆书报告 md | ✅ |
| 写法引擎（写法参考注入正文） | 开书页「写法参考」→ 注入每章提示词 | ✅ |
| 短剧改编（章节→剧本+分镜） | 衍生页：选定章节范围 → 剧本+镜头表 md | ✅ |
| RAG 知识召回 | vecstore：Qdrant REST 或内存降级；每章入索引、每章召回想前文 | ✅ |
| 角色形象图 / 漫画工坊 | imggen（OpenAI 兼容 `/images/generations`） | ✅ 接口就绪，需图像服务 |
| 多提供商模型 | llm.py 原生支持（OpenAI 兼容 + Anthropic） | ✅ |
| 提示词可维护 | 阶段提示词集中在 novel_chain.py 顶部常量 | ✅ |
| Web 版 / 文档站 / 多用户 | 不适用（本项目为 Tk 单机应用） | — |

## 二、外接工具安装与配置

### 1. Qdrant 向量库（RAG 持久召回）— ✅ 已安装并正在运行

- **版本**：v1.19.1（Windows 官方二进制）
- **位置**：`%LOCALAPPDATA%\qdrant\qdrant.exe`
- **当前状态**：已在运行（REST 端口 127.0.0.1:6333，建/删集合验证通过）
- **开机自启**（可选）：把 qdrant.exe 的快捷方式放进
  `shell:startup` 文件夹，或用任务计划程序注册
- **环境变量**：已写入用户级（`setx LAS_QDRANT_URL http://127.0.0.1:6333`），
  **新开的终端/重启后的应用自动生效**
- **验证**：浏览器打开 http://127.0.0.1:6333/collections 有 JSON 即正常
- 不开 Qdrant 也能跑：自动降级为进程内内存检索（仅本次运行有效）

### 2. Embedding 端点（语义向量）— 按需配置

OpenAI 兼容 `/embeddings` 接口即可（SiliconFlow/DeepSeek/OpenAI/本地网关）：
```
setx LAS_EMBED_BASE_URL "https://api.siliconflow.cn/v1"
setx LAS_EMBED_MODEL  "BAAI/bge-m3"
setx LAS_EMBED_API_KEY "sk-..."
```
未配置 → 本地词袋哈希向量（确定性、零依赖，语义召回质量较弱）。

### 3. 图像生成服务（漫画工坊 / 角色形象图）— 按需配置

OpenAI 兼容 `/images/generations` 接口：
```
setx LAS_IMAGE_BASE_URL "https://api.openai.com/v1"
setx LAS_IMAGE_MODEL    "gpt-image-1"
setx LAS_IMAGE_API_KEY  "sk-..."
setx LAS_IMAGE_SIZE     "1024x1024"
```
未配置 → 漫画/形象图功能明确提示，不影响文字主链。

### 4. Python 依赖

**无。** 全部功能基于 Python 3.12+ 标准库实现。

## 三、使用方法

1. 应用内输入 `/novel` 打开「开书工作台」
2. 「开书」页：填一句灵感 → 设章数（1-12）→ 可选写法参考 → 点「开书（自动导演）」
   - 勾选「规划完成后暂停确认」= 专业模式：规划各阶段完成后停下，检查后再执行章节
3. 「运行」页：看阶段状态/质量债/日志；「继续」恢复暂停的流水线；「打开书稿」在编辑器查看全文
4. 「衍生」页：拆书（选一个 txt/md）；短剧改编（输入章节范围，输出剧本+分镜）
5. 书稿与衍生物都保存在工作区 `novels/` 目录下，可随时用编辑器打开

## 四、文件清单

| 文件 | 职责 |
|---|---|
| `pipeline.py` | 阶段状态机引擎：检查点/恢复/质量债/停链策略 |
| `novel_chain.py` | 小说主链阶段定义 + 审校修复回灌 + 拆书/短剧 + RAG 钩子 |
| `vecstore.py` | Qdrant REST 客户端 + embedding + 内存降级检索 |
| `imggen.py` | 图像生成客户端（OpenAI 兼容 images API） |
| `ui_panel_novel.py` | 开书工作台（纯 Tkinter 三标签页） |
| `tests/test_pipeline.py` `tests/test_novel_chain.py` | 单元测试 |
