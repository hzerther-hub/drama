# novelwriter 整本生产线 — 外接工具与使用说明

参考 [AI-Novel-Writing-Assistant](https://github.com/ExplosiveCoderflome/AI-Novel-Writing-Assistant)
的功能主链，用 **纯 Tkinter + Python stdlib** 实现（零第三方 Python 依赖）。

> 全部交互在聊天输入框以 `/novel` 命令完成，进度实时流入聊天区。
> 早期版本有弹出式工作台面板，已在 commit `aa430c6` 移除——**没有面板**。

## 一、功能对照表

| 参考项目功能 | 本实现 | 状态 |
|---|---|---|
| 自动导演开书（一句灵感→整本方向） | `/novel start` 触发 setup 起跑 | ✅ |
| 项目设定 / 宏观规划 / 本书世界 / 故事合约 / 角色 / 卷战略 / 节奏拆章 | 流水线阶段 setup→outline→world→contract→characters→volume→chapter_plan | ✅ |
| 章节执行链（草稿→审校→修复→状态回灌） | chapters 阶段：逐章 草稿→五维审校→自动修复一次→事实/伏笔台账回灌→RAG 索引 | ✅ |
| 质量债（局部失败不阻断主链） | 引擎 fail="debt" 策略 + 章级 issues 台账 | ✅ |
| 检查点恢复（可暂停/续跑） | pipeline JSON 每阶段落盘 + `until` 逐阶段确认 + 断内循环恢复 | ✅ |
| 逐阶段调定（作者审阅后修订） | `/novel ok` 推进 / `/novel adjust <意见>` 重做当前阶段产出 | ✅ |
| 拆书工作台（题材/结构/人物/写法特征） | `/novel deconstruct <txt>` → 拆书报告 md | ✅ |
| 写法引擎（写法参考注入正文） | `new_pipeline(style=…)` → 注入每章提示词 | ✅ 接口就绪 |
| 短剧改编（章节→剧本+分镜） | `/novel drama 起-止` → 剧本+镜头表 md | ✅ |
| 封面生成 | `/novel cover` → 书稿同名 `-封面.png` | ✅ 需图像服务 |
| 多平台发布/导出 | `/novel publish txt\|md\|epub\|html\|wattpad\|webhook` | ✅ |
| RAG 知识召回 | vecstore：Qdrant REST 或内存降级；每章入索引、每章召回想前文 | ✅ |
| 角色形象图 / 漫画工坊 | imggen（OpenAI 兼容 `/images/generations`） | ✅ 接口就绪，需图像服务 |
| 多提供商模型 | llm.py 原生支持（OpenAI 兼容 + Anthropic） | ✅ |
| 提示词可维护 | 阶段提示词集中在 novel_chain.py 顶部常量 | ✅ |
| Web 版 / 文档站 / 多用户 | 不适用（本项目为 Tk 单机应用） | — |

## 二、外接工具安装与配置

### 1. Qdrant 向量库（RAG 持久召回）— 按需

- **位置**：Windows 官方二进制（本机 `%LOCALAPPDATA%\qdrant\qdrant.exe`）
- **环境变量**：`setx LAS_QDRANT_URL http://127.0.0.1:6333`（写入用户级，**新开的终端/重启后的应用生效**）
- **验证**：浏览器打开 http://127.0.0.1:6333/collections 有 JSON 即正常
- 不开 Qdrant 也能跑：自动降级为进程内内存检索（仅本次运行有效）

### 2. Embedding 端点（语义向量）— 建议配置

OpenAI 兼容 `/embeddings` 接口即可（SiliconFlow/DeepSeek/OpenAI/本地网关）：
```
setx LAS_EMBED_BASE_URL "https://api.siliconflow.cn/v1"
setx LAS_EMBED_MODEL  "BAAI/bge-m3"
setx LAS_EMBED_API_KEY "sk-..."
```
未配置 → 本地词袋哈希向量（确定性、零依赖，语义召回质量较弱）。
**长篇建议配置**：否则「每章召回想前文」基本退化为字面匹配，一致性主要靠事实台账与卷段摘要兜底。

### 3. 图像生成服务（封面 / 角色形象图）— 按需配置

`LAS_IMAGE_BASE_URL` / `LAS_IMAGE_MODEL` / `LAS_IMAGE_API_KEY`（OpenAI 兼容 images API）。
未配置时 `/novel cover` 会提示未配置，不影响写作主链。

### 4. 发布通道 — 按需配置

- Wattpad：`LAS_PUBLISH_WATTPAD_TOKEN`
- Webhook：`LAS_PUBLISH_WEBHOOK_URL`（POST `{title, chapters:[{idx,title,text}]}`）

## 三、使用方法

### 开书

```
/novel start 一句灵感 12          # 逐阶段暂停（默认），每阶段完成供审阅调定
/novel start 一句灵感 12 auto     # 一口气跑完不打断
```

- 章数 1–999（`_MAX_CHAPTERS`），省略默认 3；尾部 `auto`/`自动` 关闭逐阶段暂停。
- 灵感句越具体越好：写清主角性格、核心卖点、目标读者，规划阶段才有抓手。

### 逐阶段调定

前七个阶段（setup…chapter_plan）跑完一个就暂停，聊天区会显示该阶段产出：

```
/novel ok                         # 满意，推进下一个阶段
/novel adjust 主角改成女性，突出职场逆袭   # 按意见重做当前阶段产出
```

`adjust` 只重写该阶段产出与书稿对应段落，**已完成章节不受影响**；
章节的修改请用 `/novel rewrite`。

### 日常操作

```
/novel status                     # 全部书状态（▶ 标出当前书）、进度、质量债、检查点健康
/novel use [pid]                  # 切换当前书（省略=最近一本；支持 pid 前缀）
/novel stop                       # 当前章完成后暂停
/novel resume [pid]               # 从检查点恢复并继续跑
/novel rewrite 7 感情线太突兀       # 重写第 7 章并落实反馈
/novel extend 20                  # 加写 20 章（连载续写）
/novel drama 1-10                 # 已完成章节 → 短剧剧本+分镜 md
/novel deconstruct 某书.txt        # 拆书报告（题材/结构/人物/写法特征）
/novel cover                      # 生成封面
/novel publish epub               # 导出 epub（txt|md|html 同理）
/novel publish wattpad 1-50       # 发布到 Wattpad
/novel publish webhook            # 推送到 Webhook
```

**写多本书**：`/novel start` 开新书后，当前书会切到新书。想回到旧书用
`/novel use <pid>`（pid 从 `/novel status` 里复制，支持前缀，如 `use novel-20260908`）。
各命令也可用 `@pid` 直接指定书，不影响当前书，例如：

```
/novel extend 30 @novel-20260908-200622    # 给这本书加写 30 章
/novel rewrite 3 改一下结尾 @novel-20260906-234119
```

`_novel_pipe` 是内存态，重启后自动载入最近一本书；要操作别的书先 `/novel use`。

- 进度以工具提示样式实时渲染：🛠 阶段块、📖 章节完成块、⚠ 质量债、✅ 完成行
- `/novel status` 中出现 `⚠检查点落盘失败×N` 表示检查点未能写入磁盘
  （断点恢复不可靠），需检查磁盘空间/权限

### 书稿目录布局

每本书一个目录（**目录名 = 书名**），按内容类型分目录、每章一个独立 md：

```
工作区/novels/井通万界/
├── 说明.md                    # 书籍信息与目录导览（自动生成）
├── 大纲/总纲.md               # 项目设定→节奏拆章的全部规划
├── 设定集/                    # 世界观.md、故事合约.md、角色.md
├── 正文/
│   ├── 第0001章-开局.md
│   └── 第0002章-接触.md
└── 审查报告/                  # 有审校问题的章节才有报告
    └── 第0002章-坠井十年.md
```

- 目录名取大纲里的《书名》；同名冲突自动加序号（科学修仙、科学修仙-2）
- 大纲生成前用 pid 占位，拿到书名后自动重命名目录（含已写章节路径）
- 章节文件名 = `第NNNN章-标题.md`（章号补零 4 位，保证排序与批量导入正确）
- 章节标题优先取拆章阶段预定的《标题》，未预定则回退正文首行
- `审查报告/` 只在修复后仍有残余问题时落文件（质量债留档）
- 旧布局（`novels/<pid>.md` 或 `novels/<pid>/`）自动升级，无需手动迁移
- 导出（txt/md/html/epub）与封面落在本书目录下，以书名命名

### 结构化模板（固定字段）

规划阶段不是自由发挥，而是按固定字段骨架填写，产出可直接被下游解析：

| 阶段 | 模板字段（节选） |
|---|---|
| 宏观规划 | 故事一句话 / 创意约束 / 核心主线 / 核心暗线 / 反派分层 / 卷划分表 / 主角成长线 / 关键爽点里程碑 / 伏笔表 |
| 本书世界 | 世界一句话 / 世界结构 / 势力格局 / 社会结构 / 核心规则 / 世界运转机制 / 货币与经济 |
| 故事合约 | 必须始终一致的条款 / 禁写内容 / 称谓与地名约定 |
| 角色 | 主角卡：基本信息 / 核心标签 / 性格与底色 / 动机与目标 / 缺陷与代价 / 关键关系 / 金手指 / 行为模式 / 成长弧线 / OOC 警戒 |
| 卷战略 | 卷总览表 + 各卷节拍（开卷承诺 / 催化事件 / 升级危机链 / 中段反转 / 卷末最低谷 / 卷末兑现与新钩子） |

模板原文定义在 `novel_chain.py` 顶部 `_TEMPLATE_*` 常量，改提示词改这里即可。
总纲由 `_rebuild_plan` 按固定顺序重建（非追加），因此 `/novel adjust` 调定或
重跑阶段不会留下重复段落。

## 四、文件清单

| 文件 | 职责 |
|---|---|
| `pipeline.py` | 阶段状态机引擎：检查点/恢复/质量债/停链策略 + 落盘健康信号 |
| `novel_chain.py` | 小说主链阶段定义 + 审校修复回灌 + 调定/重写/拆书/短剧 + RAG 钩子 |
| `vecstore.py` | Qdrant REST 客户端 + embedding + 内存降级检索 |
| `imggen.py` | 图像生成客户端（OpenAI 兼容 images API） |
| `publisher.py` | 导出（txt/md/html/epub）+ 封面 + Wattpad/Webhook 发布 |
| `tests/test_pipeline.py` `tests/test_novel_chain.py` | 单元测试 |
