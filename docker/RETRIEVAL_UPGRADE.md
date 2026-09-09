# 混合检索升级与回滚

当前检索链路为：Milvus 稠密向量召回 + Milvus 原生 BM25 召回 → RRF 融合 → SiliconFlow 语义重排 → RAG 上下文去重。

## 已有环境升级

更新并重建后端后执行：

```bash
docker compose --env-file docker/.env -f docker/docker-compose.yml --profile app up -d --build backend
docker exec aka-backend python -m app.backfill_lexical
```

回填使用 chunk ID 幂等 upsert，可安全重跑。成功输出必须显示可见的 dense/lexical chunk 数量一致。回填过程不删除或覆盖原 `document_chunks` 稠密集合；BM25 数据写入 `${MILVUS_COLLECTION_NAME}_lexical`。

随后检查：

```bash
docker compose --env-file docker/.env -f docker/docker-compose.yml --profile app ps
curl --fail --max-time 15 http://127.0.0.1:8080/api/v1/health/ready
```

## 配置

```env
RERANKER_ENABLED=true
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_CANDIDATE_LIMIT=20
```

重排调用失败时服务自动回退到 RRF 顺序。紧急禁用外部重排可设置 `RERANKER_ENABLED=false` 并重建后端；BM25 与向量双路召回仍然保留。

## 数据一致性

新文档处理成功时同时写入稠密集合和 BM25 集合；删除文档或知识库时同步删除两边记录。备份 Milvus 数据卷时，两套集合会一并包含。恢复旧镜像不会读取 BM25 旁路集合，但原稠密集合仍可工作。

## 验收

升级前后使用同一数据集、知识库、`limit` 与 `min_score` 运行 `backend/evaluation`。不要为了单一评测题修改检索规则；至少再用一个不同领域知识库验证泛化效果。
