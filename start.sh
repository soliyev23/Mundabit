#!/bin/bash
# Mundabit'ni ishga tushirish: cloudflared tunnel (Mini App uchun HTTPS) + bot.
# systemd shu skriptni ishga tushiradi; tunnel URL'i WEBAPP_URL sifatida botga beriladi.
set -e
cd /opt/mundabit

LOG=/opt/mundabit/tunnel.log
: > "$LOG"
cloudflared tunnel --url http://localhost:8080 >"$LOG" 2>&1 &

URL=""
for _ in $(seq 1 40); do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1 || true)
  [ -n "$URL" ] && break
  sleep 1
done

if [ -n "$URL" ]; then
  export WEBAPP_URL="$URL/?v=$(date +%s)"
  echo "Mini App URL: $WEBAPP_URL"
else
  echo "Tunnel URL topilmadi — Mini App tugmasisiz davom etadi"
fi

exec /opt/mundabit/.venv/bin/python bot.py
