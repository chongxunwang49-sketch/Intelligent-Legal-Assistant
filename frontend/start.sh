#!/bin/sh
# 等待后端就绪后再启动 nginx
echo "[frontend] 等待后端 backend:8000 ..."
i=0
while [ $i -lt 60 ]; do
  if wget -q --spider http://backend:8000/health 2>/dev/null; then
    echo "[frontend] 后端已就绪，启动 nginx"
    break
  fi
  i=$((i + 1))
  sleep 3
done
exec nginx -g "daemon off;"
