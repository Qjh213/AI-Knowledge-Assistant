# 临时云端部署：SSH 隧道演示

本方案用于个人学习部署流程。应用运行在云服务器，浏览器通过 SSH 隧道访问；它不是匿名公众可以访问的网站，也没有实现多用户数据隔离。

## 已准备的保护

- 前端仅发布到服务器 `127.0.0.1:8080`，不是公网网卡。
- 后端不发布宿主机端口；数据库和 Milvus 等端口仍只绑定 loopback。
- 浏览器到服务器之间通过 SSH 加密，访问权限来自 SSH 身份认证。
- PostgreSQL 初始化密码与后端连接密码统一读取 `POSTGRES_PASSWORD`，缺失时 Compose 拒绝解析。

这些配置只有在重新创建对应容器后才生效。修改文件不会立即改变已运行容器的端口。

## 1. 创建服务器之前

- 选择按量付费 CPU 服务器，确认磁盘、公网 IP、快照和流量的独立收费规则。
- 先确定服务器规格与预算，再购买；本项目调用远端模型，不需要本地 GPU。
- 使用支持当前 Docker 和 Milvus 镜像的 Linux/CPU 架构。
- 本次使用全新演示数据，不复制 Windows 虚拟环境、node_modules 或运行中的数据库目录。
- 服务器上只放公开样例资料；文档正文会按功能发送给模型/解析 API 提供方。
- 准备受限额度的模型 API Key，不在聊天、Git、截图或日志中展示密钥。

## 2. SSH 与安全组

- 使用 SSH 密钥登录，私钥只保存在自己的电脑。
- 云安全组仅允许你的当前公网 IP 访问 SSH 端口（通常是 22）。
- 不开放 8080、8000、5432、19530、9091、9000、9001。
- 本方案不需要开放 80/443，也不需要购买域名。
- 首次登录时核对服务器 SSH 主机指纹，不要关闭主机密钥校验。

不要把 Docker TCP 管理接口暴露公网。

## 3. 准备代码与配置（服务器 Linux 终端）

通过 Docker 官方安装说明安装 Engine 与 Compose 插件。不要复制来源不明的安装脚本。

```bash
docker --version
docker compose version
```

将包含本次部署修改的已提交代码放到服务器；可使用 Git 或 SFTP。以下命令均在项目根目录运行。

首次创建服务器专用环境文件（已有文件时不要覆盖）：

```bash
cp -n docker/.env.example docker/.env
chmod 600 docker/.env
nano docker/.env
```

填写新的随机 PostgreSQL 密码及 API Key；本次可将 `BACKGROUND_WORKER_COUNT` 设为 1，减少并行外部调用。

密码建议使用足够长的随机字母数字，避免 URL 特殊字符导致连接串解析错误。不要使用示例占位值。

注意：`POSTGRES_PASSWORD` 只在全新 PostgreSQL 数据目录初始化时设置数据库密码。对已有数据卷，必须填写其实际密码；不要为解决认证错误删除数据卷。

## 4. 构建启动

只检查配置有效性，避免打印含密钥的完整配置：

```bash
docker compose --env-file docker/.env -f docker/docker-compose.yml --profile app config --quiet
docker compose --env-file docker/.env -f docker/docker-compose.yml --profile app up -d --build
docker compose --env-file docker/.env -f docker/docker-compose.yml --profile app ps
curl --fail http://127.0.0.1:8080/healthz
curl --fail http://127.0.0.1:8080/api/v1/health/ready
```

首次启动会执行数据库迁移。当前保持一个后端实例；不要直接提高 Uvicorn workers 或部署多个副本。

## 5. 从 Windows 电脑访问

在本机新开 PowerShell，替换以下私钥路径、用户名与服务器地址：

```powershell
ssh -i "C:\path\to\server-key" -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 127.0.0.1:18080:127.0.0.1:8080 user@SERVER_IP
```

保持该终端运行，在浏览器打开：

```text
http://127.0.0.1:18080
```

本机使用 18080，避免与本地 Docker 的 8080 冲突。前端使用相对 `/api/v1` 地址，无需修改前端 API URL。

浏览器使用 HTTP 连接本机端口，远程传输由 SSH 加密；这不是为公网网站配置了 HTTPS。不要把服务器 8080 改为公网开放来代替隧道。

结束隧道按 Ctrl+C；这只关闭连接，不会停止云服务器或计费。

## 6. 验收

- 隧道开启后可以访问；关闭后本机 18080 不再可访问。
- 公网 `SERVER_IP:8080` 不可访问，数据库等端口也不可公网访问。
- 侧边栏显示服务正常。
- 创建演示知识库，上传一份小 TXT/Markdown 文件并处理。
- 进行带引用问答、连续追问和最近对话查看。
- 如需验证 MinerU，另用一份小型公开 PDF；该操作可能产生供应商费用。
- 重启前后端后，已完成文档、知识库和消息仍存在。
- 等文档任务与流式回答完成后再部署更新，避免中断进程内任务。

## 7. 更新、备份和回滚演练

先记录当前 Git 提交和镜像 ID，并在更新前做备份。仅源码兼容、没有破坏性迁移的更新才可简单切回旧镜像。

```bash
git rev-parse HEAD
docker compose --env-file docker/.env -f docker/docker-compose.yml --profile app images
docker compose --env-file docker/.env -f docker/docker-compose.yml --profile app logs --tail=100 backend frontend
```

日志可能包含用户内容，分享前检查脱敏。更新测试通过后再重建前后端。数据库迁移失败时先排查，不要删除 volumes。

备份范围：PostgreSQL 逻辑备份、原始文档卷，以及需要保留的 Milvus/etcd/MinIO 数据。运行中的数据库目录不能当普通文件直接复制作为可靠备份；完整恢复步骤需在实际服务器上演练。只使用可重新导入的公开演示数据时，也可以保留原文件并重建向量，代价是再次调用嵌入 API。

## 8. 结束实验

1. 保存演示截图、部署记录及需要的备份到本机。
2. 确认备份可读、需要保留的数据已恢复验证。
3. 在云控制台释放本次服务器。
4. 分别检查关联磁盘、公网 IP、快照、备份及其他计费资源是否仍保留。
5. 撤销不再使用的演示密钥或降低额度，核对账单。

不要假定“关机”或 `docker compose down` 会停止云平台全部计费。

## 后续公开网址

如果要让面试官直接访问，再增加域名、HTTPS、覆盖页面和 API 的访问认证以及演示操作/调用额度限制。当前 SSH 方案不承担这个目标。

## 本阶段边界

本文件描述临时演示部署流程，不代表任一环境已完成部署或生产验收。实际云端性能、备份恢复及更新回滚需在目标环境验证，不能仅凭健康检查通过宣称完整生产安全验收已通过。
