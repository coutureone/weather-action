"""Send the generated daily brief to two Tink desktops and one Bark phone."""

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse


CHINA_TIME = timezone(timedelta(hours=8))
ICON_URL = 'https://raw.githubusercontent.com/coutureone/weather-action/master/assets/bark-news-icon.png?v=4'


def main():
    today = datetime.now(CHINA_TIME)
    body = Path('result.txt').read_text(encoding='utf-8').strip()
    heading = body.splitlines()[0]
    if f'{today.month}月{today.day}日' not in heading:
        raise ValueError('新闻源尚未更新到今天，停止发送旧简报')

    api_url = os.environ['TINK_API_URL']
    api_key = os.environ['TINK_API_KEY']
    devices = [item for item in re.split(r'[,\s]+', os.environ['TINK_DEVICE_IDS']) if item]
    bark_key = os.environ['TINK_BARK_DEVICE_KEY']
    if urlparse(api_url).scheme != 'https' or len(devices) != 2 or not api_key or not bark_key:
        raise ValueError('Tink 三端配置不完整')

    payload = {
        'title': f'今日新闻简报 ({today:%Y-%m-%d})',
        'body': body,
        'group': 'weather-action',
        'devices': devices,
        'bark_devices': [bark_key],
        'bark_params': {
            'body': body,
            'group': 'weather-action',
            'sound': 'minuet.caf',
            'icon': ICON_URL,
        },
    }
    request = urllib.request.Request(
        api_url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json; charset=utf-8',
        },
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.load(response)
    if result.get('code') != 0 or not (result.get('data') or {}).get('dispatched_bark'):
        raise RuntimeError('Tink 未确认 Bark 转发成功')
    print('Tink 已接受两台桌面设备和一台 Bark 手机的通知')


if __name__ == '__main__':
    main()
