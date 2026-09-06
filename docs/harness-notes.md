# Harness 学习笔记：jcode / openclaude 的提示词、流程与上下文处理

> 参考仓库：
> - [openclaude](https://github.com/Gitlawb/openclaude) —— Claude Code 代码库血统的多 provider CLI（TypeScript，本地克隆于 `C:/source/.refs/openclaude`）
> - [jcode](https://github.com/1jehuang/jcode) —— "The most RAM efficient harness"（Rust）
>
> 目的：对照它们的提示词设计、Agent 主循环、上下文管理，改造我们（drama）的 harness。
> 整理日期：2026-09-06

---

## 1. openclaude 拆解（Claude Code 同源，最值得抄）

### 1.1 主循环与轮次上限：按「turn 预算」而不是「工具轮数」

- `src/query.ts`：主循环的每一「turn」= 一次 provider 往返（一轮里模型可以发多个工具调用）。
- 上限语义（`query.ts:810` 附近）：

```ts
if (maxTurns && state.turnCount > maxTurns) {
  yield createAttachmentMessage({ type: 'max_turns_reached', maxTurns, turnCount })
  return { reason: 'max_turns', turnCount: state.turnCount }
}
```

- 关键差异：Claude Code 的默认 turn 预算非常高（几十到上百），真正的硬约束是
  **上下文窗口** 而不是轮数；轮数上限只是防失控的保险丝。
- **对照我们**：`MAX_TOOL_ROUNDS = 24`（已从 12 上调）+ 撞上限后强制一次
  「无工具」汇总调用（`agent.py` 的 for-else 收尾）。方向一致，但 openclaude
  的预算维度是 token 而非轮数——长期应把预算改成「轮数 + token 双阈值」。

### 1.2 Auto-Compact：上下文快满时「先摘要、再继续」

`src/services/compact/autoCompact.ts` 的三个常数就是全部秘诀：

```ts
// 摘要输出预留（基于 compact 摘要输出的 p99.99 = 17,387 tokens）
const MAX_OUTPUT_TOKENS_FOR_SUMMARY = 20_000
// 触发阈值 buffer
export const AUTOCOMPACT_BUFFER_TOKENS = 30_000
// 兜底下限 buffer（防阈值变负、每条消息都触发）
const AUTOCOMPACT_FLOOR_BUFFER_TOKENS = 13_000
```

触发公式：

```
有效窗口   = context_window − min(max_output_tokens, 20_000)
触发阈值   = 有效窗口 − 30_000
每轮结束时估算 token，超过阈值 → 先做一次摘要压缩，再继续干活
```

- **触发后不是截断了事，而是调一次「压缩摘要」**（可以用不同的便宜模型，
  `compactModel` 配置项），把整个对话折叠成结构化摘要，然后摘要 +
  最近若干轮原文继续主循环。
- 失败保护：连续失败进入 cooldown 熔断（`consecutiveFailures`），避免
  `prompt_too_long` 时的重试风暴。

### 1.3 九段式压缩提示词（核心资产，`src/services/compact/prompt.ts`）

压缩时先发一条「禁用工具」的前导（他们实测发现推理模型会在摘要轮偷偷调工具）：

```
CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.
- Do NOT use Read, Bash, Grep, Glob, Edit, Write, or ANY other tool.
- You already have all the context you need in the conversation above.
- Tool calls will be REJECTED and will waste your only turn.
- Your entire response must be plain text: an <analysis> block followed by a <summary> block.
```

摘要要求先在 `<analysis>` 标签里打草稿（按时间线过一遍每条消息：用户意图、
自己的方案、关键决定、文件名、代码片段、报错与修复、**用户纠正过你的地方**），
然后输出九段式 `<summary>`：

1. **Primary Request and Intent** —— 用户全部显式需求和意图
2. **Key Technical Concepts** —— 涉及的技术概念/框架
3. **Files and Code Sections** —— 看过/改过的每个文件+关键代码片段+为什么重要
4. **Errors and fixes** —— 踩过的错和修法（尤其用户纠正的地方）
5. **Problem Solving** —— 已解决/排查中的问题
6. **All user messages** —— 所有非工具结果的用户消息原文
7. **Pending Tasks** —— 明确被要求但还没做的
8. **Current Work** —— 摘要请求前一刻正在做什么（带文件名和代码）
9. **Optional Next Step** —— 下一步（必须和用户最近的显式请求对齐；引用原话防跑偏）

### 1.4 Microcompact：工具结果级的「按时间清除」

`src/services/compact/microCompact.ts`：不动消息结构，只把**旧的工具结果**
原地替换成 `[Old tool result content cleared]`：

- 可清除的工具白名单：`Read / Bash / Grep / Glob / WebSearch`（+前缀匹配的 MCP）；
- 近期的工具结果原样保留，旧的清掉；
- 图片占位按 2000 token 计并替换为文本标记。

这就是「分析项目读了一堆文件之后还能继续」的第二层保障：全文级 compact 之前，
先把旧工具返回清掉，往往就够继续了。

### 1.5 其它值得记的

- **Reactive compaction**：收到 `prompt_too_long` 错误时自动压缩重试（带重试上限）。
- **上下文分区**（`contextPartitioning.ts` / `relevancePruning.ts`）：压缩保留
  「边界标记 + 摘要消息 + 近 N 轮原文 + 附件」，中间按相关性裁剪。
- **缓存意识**：压缩会打断 prompt cache，他们专门做了 `promptCacheBreakDetection`
  来通知/优化；压缩摘要与主模型同模型时尽量共享缓存前缀。

---

## 2. jcode 的可借鉴点（Rust，省内存流派）

来自其 README（网络原因未克隆到源码，以下为 README 描述的设计）：

1. **per-model `context_window` 写在 provider 配置里** —— 我们已有
   （`models.json` 的 `context_window` / `max_tokens` 字段）。
2. **工具返回自适应截断**：根据 agent 已经看过的内容决定截多少——同一文件
   第二次读就给增量/更少内容，省上下文。
3. **grep 返回文件结构摘要**（函数/类列表）而不只是行号命中——agent 不用
   再整读文件就能定位，天然省 token。我们的 `index_search`（TF-IDF 代码索引）
   思路相近，可以在 `read_file`/`grep` 类工具返回里加「文件结构头」。
4. **语义记忆/记忆图**：跨会话记忆做成可检索的图，而不是整个历史塞上下文。
5. **流空闲超时随推理等级缩放**：reasoning effort 越高，首 token 越慢，
   超时相应放大（我们 llm.py 固定 timeout=300，可借鉴为动态值）。

---

## 3. drama 自有逻辑现状（改动后）

### 3.1 架构

```
main.py → ui.launch() → App(Tkinter)
   │ 每条消息起一个 daemon worker 线程
   ▼
agent.Agent.run()   # 同步 function-calling 循环
   ├─ llm.py        # SSE 流式：openai_compatible | anthropic 双协议
   ├─ tools.py      # 内置 8 工具 + MCP 执行器；写操作沙箱
   ├─ context.py    # token 估算 + 预算 + 渐进压缩
   └─ cache.py      # 请求时消息列表为键的 LLM 响应缓存
```

### 3.2 主循环（agent.py）

- `for round_no in range(1, MAX_TOOL_ROUNDS+1)`：流式转发 text/reasoning/
  tool_calls/usage 事件；`return "break"` 式协作停止（按钮/Esc）。
- **轮次上限 24 + 强制收尾**（本次新增，参考 openclaude 的 no-tools 思路）：
  循环用 for-else 检测「跑满轮数仍无最终回答」，追加一条 system 提示
  （“轮次已达上限，立即基于已收集信息给出最终完整回答”），
  **不带工具 schema** 再调一次流式，保证分析类任务必有结论。
- 本地模型不可用 → 自动切云端重试本轮（`_cloud_fallback`，只回退一次）。
- LLM 响应缓存：键 = 请求时消息列表（不含回复），命中直接重放事件流。

### 3.3 上下文管理（context.py）

- `estimate_tokens`：CJK 1 字≈1 token、ASCII 4 字符≈1 token 的分级估算。
- `effective_budget(model)`：模型声明 `context_window` →
  `min(全局预算, 窗口 − max_tokens − 1024)`；gpulocal 兜底 131072。
- `maybe_compact`：超预算时**截断式**压缩——旧工具结果保留头尾共 3000 字符
  （带“已压缩”标记），最近 2 轮原文保留。
- **与 openclaude 的差距**：我们只有截断，没有「摘要式压缩」；触发靠预算而非
  「窗口 − buffer」的显式阈值。这是下一步最大的一项升级（见 §5）。

### 3.4 协议层（llm.py）

- OpenAI `/chat/completions` 与 Anthropic `/messages` 双协议，事件统一重映射为
  `{text, reasoning, tool_calls, finish, usage}`。
- `_ThinkFilter`（本次新增）：流式剥掉混进正文的 `<think>/<mm:think>` 推理块，
  支持跨 chunk 撕裂标签；无 `<` 的普通增量零延迟直通。
- `max_tokens`：模型声明 > gpulocal 16K > 全局 32768，下发前再夹一次 32768。

### 3.5 Provider/模型管理（config.py + ui_panel_models.py）

- provider-first 两栏管理器；provider 可重命名（name/id 唯一校验）、可编辑
  base_url/api_key/api_type；删除级联模型。
- 模型级字段：显示名/ID/vision/推理等级/上下文窗口/最大输出。
- `_refresh_models` 每次把 `current_model` 重绑到新加载对象——改完即生效。

---

## 4. 对照表：本次已落地 vs 待落地

| 能力 | openclaude 做法 | drama 现状 | 状态 |
|---|---|---|---|
| 轮次上限 | turn 预算（高）+ `max_turns_reached` 事件 | 24 轮 + 撞顶强制汇总 | ✅ 已落地 |
| 强制收尾 | NO_TOOLS_PREAMBLE + maxTurns:1 | system 提示 + 空 schema 重调 | ✅ 已落地 |
| 摘要式压缩 | 九段式 summary + analysis 草稿 | 只有截断 | ⬜ 待做（最高优先） |
| 触发阈值 | 窗口 − maxOutput(20K) − buffer(30K) | 全局预算/模型窗口差值 | ⬜ 待对齐 |
| 工具结果清除 | microcompact 按时间清白名单工具 | 旧工具结果截断到 3000 字符 | 🟡 半个 |
| prompt_too_long 重试 | reactive compact + 熔断 | 无（直接报错） | ⬜ 待做 |
| `<think>` 标签泄漏 | —（模型侧无此问题） | `_ThinkFilter` 流式剥离 | ✅ 已落地 |
| 结构化 grep | grep 带文件结构摘要 | index_search TF-IDF | 🟡 可增强 |
| 压缩模型可选 | compactModel 配置 | 无（用当前模型压） | ⬜ 待做 |
| 压缩打断缓存提示 | promptCacheBreakDetection | 无 | ⬜ 低优 |

---

## 5. 下一步落地路线（建议顺序）

1. **摘要式压缩（最重要）**：`context.py` 加 `summarize_compact(messages, model)`：
   - 触发：`estimated_tokens > effective_budget(model) − 30_000`（对齐 openclaude）；
   - 先发 NO_TOOLS 前导 + 九段式摘要提示（中文版照 §1.3 结构翻译），
     `<analysis>` 草稿在入上下文前剥掉；
   - 产物 = 摘要（作为第一条 system/user 消息）+ 最近 2 轮原文；旧的工具结果
     先经过现有截断再进摘要输入，控制压缩调用本身的成本；
   - 失败重试 ≤2 次，仍失败回退现有截断式压缩（永不因压缩失败而断流）。
2. **prompt_too_long 反应式压缩**：`agent.py` 捕获 400/`prompt_too_long` 类错误
   → 触发 1 的压缩 → 重试本轮；连续 2 次失败熔断报错。
3. **工具结果时间清除**：`maybe_compact` 里把「保留最近 2 轮」之外的旧工具结果
   直接替换为 `[旧工具结果已清除]`（比截断更省），白名单 read_file/run_shell/
   grep/index_search。
4. **预算双阈值**：轮数 + token 双保险（`MAX_TOOL_ROUNDS=24` 保留，
   加 `MAX_TURN_TOKENS` 每轮累计输出超限也触发强制收尾）。
5. **read_file/grep 返回加文件结构头**（借鉴 jcode）：返回内容前附该文件的
   函数/类清单（正则级即可），降低模型整读文件的次数。

---

## 6. 附：可直接复用的提示词片段

**强制收尾（已用于 agent.py，中文版）：**

```
工具调用轮次已达上限。请立即基于以上已收集的信息给出最终完整回答，不要再调用任何工具。
```

**九段式压缩摘要（中文版骨架，落地 summarize_compact 时使用）：**

```
你的任务是为迄今为止的对话创建一份详细摘要，紧密围绕用户的显式请求和你已执行的操作。
摘要必须完整保留继续工作所需的技术细节、代码模式与架构决策。

先在 <analysis> 标签中按时间线分析每条消息：用户的显式请求与意图；你的处理方式；
关键决定、技术概念与代码模式；具体细节（文件名、完整代码片段、函数签名、文件编辑）；
遇到的错误与修复；尤其注意用户纠正你做法的地方。然后检查技术准确性与完整性。

摘要在 <summary> 标签中输出，包含以下小节：
1. 主要请求与意图
2. 关键技术概念
3. 文件与代码段（含为什么重要）
4. 错误与修复（含用户纠正）
5. 问题解决过程
6. 所有用户消息（非工具结果的原文列表）
7. 待办任务
8. 当前工作（摘要请求前一刻正在做的事，带文件名/代码）
9. 可选的下一步（必须与用户最近的显式请求对齐，引用原话防跑偏）
```
