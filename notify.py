"""Send the generated daily brief to two Tink desktops and one Bark phone."""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse


CHINA_TIME = timezone(timedelta(hours=8))
ICON_URL = 'https://raw.githubusercontent.com/coutureone/weather-action/master/assets/bark-news-icon.png?v=4'


def request_json(url, api_key, payload=None):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json; charset=utf-8',
            'Accept-Language': 'en',
        },
        method='POST' if payload is not None else 'GET',
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def send_tink(api_url, api_key, payload):
    try:
        result = request_json(api_url, api_key, payload)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        try:
            reason = json.loads(error.read(4096))
        except (ValueError, UnicodeDecodeError):
            raise error
        missing = re.fullmatch(r'device (.+) not found', reason.get('message') or '')
        if not missing or missing.group(1) not in payload['devices']:
            raise error
        devices_url = api_url.rstrip('/').rsplit('/', 1)[0] + '/devices'
        registry = request_json(devices_url, api_key)
        if registry.get('code') != 0 or not isinstance(registry.get('data'), list):
            raise RuntimeError('Tink 设备列表读取失败')
        registered = {device.get('id') for device in registry['data']}
        for index, device_id in enumerate(payload['devices'], 1):
            if device_id in registered:
                continue
            restored = request_json(devices_url, api_key, {
                'id': device_id, 'name': f'新闻通知 Mac {index}',
            })
            if restored.get('code') != 0:
                raise RuntimeError('Tink 设备注册恢复失败')
        result = request_json(api_url, api_key, payload)
    dispatched = result.get('data') or {}
    # 桌面消息先保存，再投递到在线客户端；离线 Mac 重连后补收。
    if result.get('code') != 0 or not dispatched.get('id') or dispatched.get('dispatched_bark', 0) < 1:
        raise RuntimeError('Tink 未确认桌面消息保存和 Bark 转发成功')
    return result


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
    send_tink(api_url, api_key, payload)
    print('Tink 已保存两台 Mac 的通知，手机 Bark 转发成功')


if __name__ == '__main__':
    main()
