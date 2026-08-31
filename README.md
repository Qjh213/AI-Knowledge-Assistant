# AI Knowledge Assistant

一个支持文档上传、MinerU 解析、向量检索、RAG 问答、连续对话和流式输出的全栈知识库项目。

## 技术组成

- 前端：React、TypeScript、Vite、TanStack Query、Tailwind CSS
- 后端：FastAPI、SQLAlchemy、Alembic、PostgreSQL
- 检索：Milvus、BAAI/bge-m3（硅基流动）
- 对话：DeepSeek
- 文档解析：本地解析器或 MinerU API
- 部署：Docker Compose、Nginx

## 本地开发

基础设施：

```powershell
docker compose -f docker\docker-compose.yml up -d
```

后端：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

前端：

```powershell
Set-Location frontend
npm install
npm run dev
```

开发页面默认为 `http://127.0.0.1:5173`，API 文档默认为
`http://127.0.0.1:8000/docs`。

## Docker 一键部署

### 1. 创建部署配置

```powershell
Copy-Item docker\.env.example docker\.env
```

编辑 `docker/.env`，至少替换以下配置：

```env
POSTGRES_PASSWORD=使用一个强且仅含URL安全字符的密码
DEEPSEEK_API_KEY=你的DeepSeek密钥
SILICONFLOW_API_KEY=你的硅基流动密钥
MINERU_API_TOKEN=你的MinerU令牌
```

`docker/.env` 已被 Git 忽略，不要把真实密钥复制到 `.env.example`。

### 2. 构建并启动整套应用

```powershell
docker compose `
  --env-file docker\.env `
  -f docker\docker-compose.yml `
  --profile app `
  up -d --build
```

首次构建需要从 Docker Hub 下载 Python、Node 和 Nginx 基础镜像。

### 3. 查看状态

```powershell
docker compose `
  --env-file docker\.env `
  -f docker\docker-compose.yml `
  --profile app `
  ps
```

所有服务正常后访问：

- 应用页面：`http://localhost:8080`
- 健康检查：`http://localhost:8080/api/v1/health/ready`

执行端到端冒烟检查：

```powershell
.\docker\smoke-test.ps1
```

生产模式默认关闭 Swagger 和 ReDoc，只通过 Nginx 暴露前端的 `8080` 端口。

### 4. 查看日志

```powershell
docker compose `
  --env-file docker\.env `
  -f docker\docker-compose.yml `
  logs -f backend frontend
```

### 5. 停止服务

```powershell
docker compose `
  --env-file docker\.env `
  -f docker\docker-compose.yml `
  --profile app `
  down
```

普通 `down` 不会主动删除 PostgreSQL、Milvus、MinIO、etcd 和文档数据。

## 已有 PostgreSQL 数据的注意事项

如果 `docker/volumes/postgres` 已经使用默认密码 `postgres` 初始化，仅修改
`docker/.env` 不会自动修改数据库内部密码。进入 PostgreSQL 后更新密码：

```powershell
docker exec -it aka-postgres psql -U postgres -d knowledge
```

在 `psql` 中执行，并将相同密码写入 `docker/.env`：

```sql
ALTER USER postgres WITH PASSWORD '你的新密码';
```

随后输入 `\q` 退出。密码建议只使用大小写字母、数字、连字符和下划线，避免数据库
URL 转义问题。

## 数据位置

- PostgreSQL：`docker/volumes/postgres`
- Milvus：`docker/volumes/milvus`
- MinIO：`docker/volumes/minio`
- etcd：`docker/volumes/etcd`
- 上传文档：Docker 命名卷 `document-storage`

## 常见问题

### Docker Hub 下载超时

如果构建在 `auth.docker.io` 或拉取基础镜像时超时，请检查 Docker Desktop 的代理、
DNS、IPv6 网络或镜像加速器配置，然后重新执行 `up -d --build`。

### 后端容器启动失败

查看日志：

```powershell
docker logs aka-backend
```

生产配置缺少密钥、仍使用默认 PostgreSQL 密码或数据库/Milvus 未就绪时，后端会拒绝
启动并在日志中给出配置错误。

### 上传大文件返回 413

应用和 Nginx 当前均允许单文件最大 100 MB。调整时需要同时修改：

- `docker/.env` 中的 `MAX_UPLOAD_SIZE_MB`
- `frontend/nginx.conf` 中的 `client_max_body_size`

## 验证命令

后端：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic check
```

前端：

```powershell
Set-Location frontend
npm test -- --run
npm run build
npm run lint
```
