#!/bin/sh
set -eu

cleanup() {
    kill "$backend_pid" "$frontend_pid" "$nginx_pid" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

port="${PORT:-7860}"
case "$port" in
    ''|*[!0-9]*)
        echo "PORT must be a numeric TCP port."
        exit 1
        ;;
esac
if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
    echo "PORT must be between 1 and 65535."
    exit 1
fi
sed "s/__SPACE_PORT__/$port/g" /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
nginx -t

cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
backend_pid=$!

cd /app/frontend
HOST=127.0.0.1 PORT=3000 node .output/server/index.mjs &
frontend_pid=$!

nginx -g 'daemon off;' &
nginx_pid=$!

while kill -0 "$backend_pid" 2>/dev/null \
    && kill -0 "$frontend_pid" 2>/dev/null \
    && kill -0 "$nginx_pid" 2>/dev/null; do
    sleep 1
done

echo "A required service stopped; shutting down the Space container."
exit 1
