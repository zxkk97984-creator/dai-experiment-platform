# Redis 持久化与故障语义（TASK-013）

## 配置

生产 Compose（`docker-compose.prod.yml`）中的 Redis：

- **AOF `everysec`**：每 1 秒 fsync 一次写操作；崩溃最坏丢失 1 秒写入。
- **命名卷 `redis_data:/data`**：数据位于 Compose 卷，容器删除/重建不丢数据，
  且被纳入 TASK-014 备份范围（备份输出到卷外目录）。

不使用 Cluster/Sentinel，不把认证事实迁出 MySQL——符合单机规模。

## 存储内容与丢失影响（事实清单，2026-08-14 代码核查）

| Redis 键 | 内容 | TTL | 数据卷丢失的影响 |
| --- | --- | --- | --- |
| `auth:refresh:{user_id}` | Refresh Token 会话（`auth_service.py` setex） | refresh_token_expire_days | 所有 Refresh Token 失效，全部用户需重新登录（Access Token 至多 `access_token_expire_minutes` 分钟后自然到期） |
| `blacklist:{jti}` | 已注销 Access Token 黑名单 | 原 Token 剩余 TTL | 注销记录丢失；被注销的 Access Token 恢复可用，最坏影响窗口 = Access Token TTL（分钟级） |
| `loginfail:{username}` / `loginfail:{ip}` | 登录失败限流计数（TASK-005） | 15 分钟窗口 | 限流计数清零，最坏影响 15 分钟窗口 |
| `judge:ai:queue` 等 | 判题/AI/环境构建唤醒信号（仅唤醒，`ai_grading_queue.py` 注释：先 commit 再 rpush） | 无 | 队列内消息丢失，但 **DB 是队列事实源**：stale recovery 定期把孤立 queued 记录重新推送，任务不丢 |
| 其他缓存 | 教学资源缓存等 | 各业务 TTL | 仅性能回退，首次请求重建 |

**结论**：数据卷完整时（正常重建/重启），上述状态全部保留；
数据卷丢失时，业务数据事实源（MySQL + 存储卷）不受影响，仅会话/限流/黑名单
短暂失效或回退，无数据完整性问题。

## 恢复演练证据

演练日期：2026-08-14（隔离环境，容器/卷名 `dai-redis-drill*`，演练后已清理）。

### 演练 1：SIGKILL 崩溃后 AOF 恢复

```text
1. docker volume create dai-redis-drill-data
2. 启动：redis:7-alpine + --appendonly yes --appendfsync everysec（挂载该卷）
3. SET drill:key hello-aof / INCR drill:counter × 3（counter=3）
4. docker kill -s KILL（模拟宿主机断电级崩溃，绕过优雅退出）
5. docker start（AOF 重放恢复）
6. GET drill:key → hello-aof；GET drill:counter → 3
```

结果：**通过**（见下方记录块）。

### 演练 2：容器删除后卷重建

```text
1. docker rm -f dai-redis-aof-drill（仅删容器，保留卷）
2. 用同一卷重新 run 相同镜像+命令
3. GET drill:key → hello-aof
```

结果：**通过**（见下方记录块）。

### 演练 3：卷丢失语义（预期行为验证）

```text
1. 用空卷启动新 Redis（等价 redis_data 卷被误删/丢失）
2. GET drill:key → (nil)
```

结果：键不存在，与上表「数据卷丢失的影响」一致；业务数据不受影响（事实源在 MySQL）。

### 演练原始记录

```
TIMESTAMP=2026-08-14 00:30:04 +0800
IMAGE=redis:7-alpine（本地已有，未拉取）
演练1 before-crash:  GET drill:key=hello-aof, drill:counter=3
演练1 SIGKILL+start: GET drill:key=hello-aof, drill:counter=3   ← 通过
演练2 rm+recreate:   GET drill:key=hello-aof                    ← 通过
演练3 volume-loss:   GET drill:key=(空)                          ← 与文档语义一致
卷内文件:            appendonlydir/ 存在（AOF 已落盘）
清理:                容器 dai-redis-aof-drill / dai-redis-empty-drill、
                     卷 dai-redis-drill-data / dai-redis-drill-empty 已删除
```
