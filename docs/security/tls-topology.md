# TLS 责任层与安全响应头（TASK-030 / F-20）

> 状态：**拓扑待确认**——仓库内已完成的头部均属于 HTTP 内层职责；
> HSTS 与证书管理属于真实 HTTPS 终止层（仓库外），待部署方确认后回填 §3。

## 1. 当前拓扑与头部责任层（代码事实，2026-08-14 核查）

```
浏览器 ──HTTPS──> [真实 TLS 终止层：学校网关/云 LB/Ingress——外部事实，见 §3]
                        │ HTTP
                        ▼
              frontend nginx（本仓库，listen 80，纯 HTTP 内层）
                        │ proxy_pass
                        ▼
              api（FastAPI，无 TLS 监听）
```

| 头部 | 责任层 | 状态 |
| --- | --- | --- |
| `X-Content-Type-Options: nosniff` | 内层 nginx（`always`，含错误响应） | ✅ 已实施 |
| `Referrer-Policy: strict-origin-when-cross-origin` | 内层 nginx | ✅ 已实施 |
| `X-Frame-Options: SAMEORIGIN` | 内层 nginx | ✅ 已实施 |
| `Content-Security-Policy-Report-Only`（基线见 §2） | 内层 nginx | ✅ 已实施（仅报告，不阻断） |
| `Strict-Transport-Security` | **仅真实 HTTPS 终止层** | ⛔ 内层禁止（回归脚本断言其不存在）；待 §3 确认后由部署方在边界配置 |

## 2. CSP 收紧路径

当前基线（report-only，与真实资源使用一致：Google Fonts 外链、Vue 运行时
内联样式、Notebook 同源 iframe、media blob）：

```
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob:;
connect-src 'self'; media-src 'self' blob:; frame-src 'self'; object-src 'none';
base-uri 'self'; form-action 'self'; frame-ancestors 'self'
```

收紧步骤（禁止跳过观察直接强制）：观察浏览器控制台违规 ≥ 2 周 →
替换 `style-src 'unsafe-inline'`（如可行）→ 移除 Report-Only 改为强制 →
如学校门户需要 iframe 嵌入本平台，`frame-ancestors`/`X-Frame-Options`
须同步放宽并评审（当前按“禁止非预期 frame”处理）。

## 3. 外部待办（部署方确认后回填并签字）

| # | 待确认事实 | 负责方 | 状态 |
| --- | --- | --- | --- |
| 1 | TLS 终止位置（学校网关/云 LB/Ingress 具体产品与配置入口） | 部署方 | 待确认 |
| 2 | 在终止层配置 HSTS：`max-age=31536000; includeSubDomains`（preload 视需要评估） | 部署方 | 待执行 |
| 3 | 证书签发/续期与到期监控责任方 | 部署方 | 待确认 |
| 4 | 若存在上游 CDN/缓存层，确认缓存键不受安全头影响（`Vary` 需要时补充） | 部署方 | 待确认 |
| 5 | 学校门户是否要求 iframe 嵌入本平台（影响 frame 策略，见 §2） | 学校教务 | 待确认 |

## 4. 回归护栏与演练记录

- `scripts/check_security_headers.sh`：对 `/`、`/login`、`/api/v1/health/live`、
  `/api/v1/media/x` 断言四头存在且 **HSTS 不存在**（内层越界即失败）；
- CI `docker-smoke` job 在 compose 栈上运行该脚本（TASK-030）。

演练记录（2026-08-14，隔离 compose 项目 `dai-t030`，`FRONTEND_PORT=18080`）：
- 全新 MySQL 卷两步迁移（`upgrade b4c5d6e7f890` → basic 种子 → `upgrade head`）成功，
  全栈 6 容器 healthy；
- `check_security_headers.sh` 4 条路径全部通过，HSTS 断言通过（内层无 HSTS）；
- 浏览器实测（Playwright）：登录页渲染正常、admin 登录成功进入 `/admin/users`、
  控制台 0 错误 0 警告——CSP report-only 无功能阻断（截图 `t030-admin-dashboard.png`）；
- 功能回归：登录/Notebook/媒体路径由 e2e 套件守护（CSP 为 report-only，
  按设计不产生任何阻断）。
