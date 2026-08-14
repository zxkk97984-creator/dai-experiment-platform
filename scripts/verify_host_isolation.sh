#!/usr/bin/env bash
# TASK-031：部署主机隔离现场验证——Socket 持有者、Docker API 不对外、沙箱基线。
#
# 在部署主机上运行：./scripts/verify_host_isolation.sh
# 输出报告；任一断言失败退出码 1（供发布前检查使用）。
set -u
cd "$(dirname "$0")/.."

REPO_ROOT="$(pwd)"
fail=0

echo "== 主机隔离验证（TASK-031）=="

# 1) Socket 持有者清单（compose 静态）
echo -n "1. Socket 持有者清单: "
holders=$(awk '
  /^  [a-z][a-z0-9-]*:$/ { svc=$1 }
  /\/var\/run\/docker\.sock/ { gsub(":", "", svc); print svc }
' docker-compose.prod.yml | sort -u | tr '\n' ' ' | sed 's/ *$//')
expected="api environment-builder worker"
if [ "$holders" = "$expected" ]; then
  echo "OK ($holders)"
else
  echo "FAIL：实际 [$holders]，预期 [$expected]"
  fail=1
fi

# 2) Docker API 不对网络开放（2375/2376 无监听）
echo -n "2. Docker API 网络暴露: "
if command -v ss >/dev/null 2>&1; then
  open_ports=$(ss -lnt 2>/dev/null | grep -E ':(2375|2376)\b' || true)
else
  open_ports=$(netstat -lnt 2>/dev/null | grep -E ':(2375|2376)\b' || true)
fi
if [ -z "$open_ports" ]; then
  echo "OK（无 2375/2376 监听）"
else
  echo "FAIL：$open_ports"
  fail=1
fi

# 2b) daemon 配置未启用 tcp hosts
echo -n "2b. dockerd 配置 hosts: "
daemon_conf="/etc/docker/daemon.json"
if [ -f "$daemon_conf" ] && grep -q '"hosts"' "$daemon_conf" 2>/dev/null; then
  echo "FAIL：$daemon_conf 含 hosts 配置，请确认不含 tcp://"
  fail=1
else
  echo "OK（未启用 tcp hosts）"
fi

# 3) 学生容器沙箱基线（代码静态断言）
echo -n "3. 判题容器隔离参数: "
missing=""
for flag in '"--network", "none"' '"--cap-drop", "ALL"' '"--security-opt", "no-new-privileges"' '"--read-only"' '"--pids-limit"' '"--user", "1000:1000"'; do
  grep -qF "$flag" backend/app/worker/judge_worker.py || missing="$missing $flag"
done
if [ -z "$missing" ]; then
  echo "OK"
else
  echo "FAIL：缺失$missing"
  fail=1
fi

# 4) 全仓无 --privileged / host 网络
echo -n "4. 仓库无 privileged/host 网络: "
hits=$(grep -rn -- "--privileged" backend/app/ 2>/dev/null | grep -v test || true)
hostnet=$(grep -rn '"--network", "host"' backend/app/ 2>/dev/null | grep -v test || true)
if [ -z "$hits$hostnet" ]; then
  echo "OK"
else
  echo "FAIL：$hits $hostnet"
  fail=1
fi

# 5) 运行时：存在运行中判题/内核容器时抽查其隔离参数
echo -n "5. 运行中沙箱容器抽查: "
running=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E '^dai-judge-' | head -3)
checked=0
for name in $running; do
  inspect=$(docker inspect --format '{{.HostConfig.NetworkMode}} {{.HostConfig.CapDrop}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.PidsLimit}}' "$name" 2>/dev/null)
  case "$inspect" in
    "none"*"ALL"*"true"*"50"*) checked=$((checked + 1)) ;;
    *) echo "FAIL：$name -> $inspect"; fail=1 ;;
  esac
done
if [ -z "$running" ]; then
  echo "跳过（当前无运行中判题容器）"
elif [ "$checked" -gt 0 ]; then
  echo "OK（抽查 $checked 个）"
fi

if [ "$fail" -eq 0 ]; then
  echo "全部通过。"
else
  echo "存在失败项，禁止发布。"
fi
exit "$fail"
