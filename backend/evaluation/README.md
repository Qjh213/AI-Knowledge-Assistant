# 小型真实 RAG 评测基线

这套基线由用户提供的 10 份《尚硅谷 LangChain 从入门到实战（2026 版）》PDF 人工整理，共 20 道可回答问题和 3 道知识库外拒答题。仓库只保存题目、简短参考答案、预期来源文件与源文件 SHA256，不复制原课件正文。

## 指标边界

- `retrieval_hit_at_k`：Top-K 中是否出现标注的来源文件。
- `retrieval_mrr`：第一个标注来源文件的倒数排名。
- `unanswerable_retrieval_empty_rate`：知识库外问题未返回片段的比例。
- `context_source_precision`：接口提供给模型的候选上下文中，标注来源所占比例；旧字段 `citation_source_precision` 保留为兼容别名。
- `used_citation_source_precision`：只按答案正文实际出现的引用编号统计来源精度。
- 端到端模式还计算答案关键词组覆盖、来源命中、引用编号合法率和拒答准确率。
- 关键词覆盖只是一致、廉价的回归代理，不等于语义正确性；文件级来源标签也不等于完整的片段级相关性标注。报告必须结合失败样例人工复核，不能把结果表述为“模型准确率”。

## 准备语料

在一个专用知识库中上传数据集列出的 10 份 PDF，并等待全部显示“处理完成”。不要混入其他资料，否则知识库外题和来源精度不可比较。运行器会按文件名检查语料完整性；SHA256 用于追溯数据版本，可在上传前自行核对。

## 运行

从 `backend` 目录执行。密码通过隐藏输入读取，不放入参数、环境变量或报告。每个 `/search` 和 `/answer` 请求都会占用一次用户每日 AI 额度；检索模式共 23 次请求，端到端模式共 46 次请求，并会产生嵌入/模型接口费用。

先运行无生成成本的检索基线：

```powershell
.\.venv\Scripts\python.exe -m evaluation.run --knowledge-base-id <知识库UUID> --username admin --mode retrieval --source-dir "E:\课件所在目录"
```

确认检索结果合理后再运行端到端基线：

```powershell
.\.venv\Scripts\python.exe -m evaluation.run --knowledge-base-id <知识库UUID> --username admin --mode end-to-end
```

如后端不是 `http://127.0.0.1:8080`，追加 `--base-url http://主机:端口/api/v1`。报告默认写入项目的 `output/evaluation/`，其中包含检索片段和完整回答，可能含课件内容，不应提交 Git 或公开分享。

`--source-dir` 会在登录和产生调用费用前核对 10 份原始 PDF 的 SHA256，建议首次和课件变化后使用；后续确认数据版本未变时可以省略。

运行器只对 `429/502/503/504` 做有限退避重试，并逐题写入本地检查点；同参数重跑会跳过已完成题目。检查点和正式报告都位于 `output/evaluation/`，不应提交仓库。

首次结果只建立基线，不设“合格线”。人工复核失败样例后固定参数与数据版本，再在后续检索、切分、嵌入或提示词变更中比较同一批指标。调整 `--limit` 或 `--min-score` 时必须在报告中保留参数，不能直接和不同参数的结果混为一谈。

## 第二知识库：项目运维文档

`project_ops_baseline.json` 是不同于 LangChain 课程的第二套领域评测，共 4 份项目运维文档、9 道可回答题和 3 道库外拒答题。新建专用知识库并上传项目根目录中的 `README.md`、`docker/RETRIEVAL_UPGRADE.md`、`docker/AUTH_SETUP.md`、`docker/TEMPORARY_DEPLOYMENT.md`，等待处理完成后运行：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m evaluation.run --knowledge-base-id <知识库UUID> --username admin --mode retrieval --dataset evaluation/project_ops_baseline.json --source-dir ..
```

确认检索结果后，将 `--mode retrieval` 改为 `--mode end-to-end`。两次运行要保持相同的 `--limit` 与 `--min-score`。这套结果用于验证跨领域泛化，不应与原课程题混算成一个“准确率”。
