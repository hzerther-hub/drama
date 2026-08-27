# 宁波易到救援开发平台

产品 5（见根目录 `PLAN-五产品矩阵.md`）。把**公司多个代码仓库 + 文档目录**建成一个
持久化、可配置的知识库 RAG，开发对话时由**云端模型**调用（**纯云端版，不依赖本地
模型服务器**；界面**仅中文**，无中英切换）。检索 = TF-IDF 兜底 + 可选 embedding 增强；
RAG 接入 = `kb_search` 工具 + 可开关的自动注入。

## 能力

- `codera.py` —— 公司多根知识库：把 N 个目录（代码 + 文档）增量建进一个 SQLite 库，
  TF-IDF 余弦检索；配置了 embedding 模型时叠加向量打分（混合评分）。
- `embed.py` —— stdlib `urllib` 调 OpenAI-compatible `/v1/embeddings`（本地
  llama.cpp / 云端都兼容），失败自动退回纯 TF-IDF。
- 工具 `kb_search` —— 模型按需检索知识库（返回 root/文件/行号/得分/片段）。
- 自动注入 —— 开关打开后每次提问自动检索 top 片段注入模型上下文（默认关，省 token）。
- 面板「📚 知识库」—— 增删知识根目录、建/重建索引、开关启用/自动注入、选 embedding
  模型、测试查询。

## 运行

```bash
LOCAL_AI_PRODUCT=devrag python3 main.py          # Linux/macOS
set LOCAL_AI_PRODUCT=devrag && python main.py    # Windows
python3 products/devrag/run.py                   # 或直接走产品入口
```

## 检索方案

TF-IDF 兜底（零新依赖，纯 numpy）；`kb_embedding` 模型 key 非空时启用向量增强，
混合分 = TF-IDF 余弦 + `EMBED_WEIGHT` × embedding 余弦。embedding 不可用/失败 →
自动退回纯 TF-IDF。
