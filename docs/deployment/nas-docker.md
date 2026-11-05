# DO 研判管理中心：NAS Docker 部署

这套部署包默认将网页开放在 NAS 的 45819 端口，并把数据库、报告和历史归档放在项目目录的独立挂载文件夹中。容器更新不会覆盖这些数据。

## 1. 准备目录

将整个项目复制到 NAS，例如：

    /volume1/docker/digital-oracle/
    ├── compose.yaml
    ├── Dockerfile
    ├── data/
    ├── reports/
    └── archive/

确保 data 和 reports 可由容器中的 UID 10001 写入；archive 仅需读取。不同 NAS 的权限界面不同，可以在文件管理器或容器管理器中完成授权。

## 2. 配置分析模型

在项目根目录创建 .env，至少填写：

    DEEPSEEK_API_KEY=你的密钥
    DO_PORT=45819

.env 已被 Docker 构建上下文排除，不会打进镜像。若只查看已有报告，可以暂不配置密钥。

## 3. 启动与验收

    docker compose up -d --build
    docker compose ps

浏览器访问 http://NAS_IP:45819/，健康检查地址为 http://NAS_IP:45819/healthz。

正常时会返回 status: ok，并分别显示时间线数据库与分析记录数据库状态。

## 4. 数据目录

- data/timeline.db：历史报告索引、结构化趋势和变化事件。
- data/digital_oracle.db：网页分析工作台记录。
- reports/：DO 新生成或手工放入的报告。
- archive/：已有历史报告，只读挂载。

备份时先停止容器，再完整复制 data、reports 和 archive。升级前保留上一版镜像或项目目录，即可快速回滚。

## 5. 更新与排查

    docker compose up -d --build
    docker compose logs --tail=200 digital-oracle

如果健康检查失败，先确认挂载目录权限，再查看日志中是 timeline_db 还是 chat_db 不可访问。
