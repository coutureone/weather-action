#!/bin/sh
set -eu

mkdir -p /var/lib/weather-news
today=$(date +%F)
[ -f "/var/lib/weather-news/sent-$today" ] && exit 0

/usr/bin/docker run --rm --network host --user 0:0 \
  --entrypoint python3 \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v /usr/local/lib/weather-news/getInfo.py:/app/getInfo.py:ro \
  -v /etc/tink.conf:/run/secrets/tink.conf:ro \
  -v /etc/bark.conf:/run/secrets/bark.conf:ro \
  -v /var/lib/weather-news:/state \
  weather-news-python:20261001 \
  /app/getInfo.py --send-tink --state-dir /state
