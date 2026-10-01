"""生成新闻简报；在软路由上可直接通过 Tink 发送。"""

import argparse
import fcntl
import json
import re
import shlex
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


CHINA_TIME = timezone(timedelta(hours=8))
NEWS_URL = 'https://news.topurl.cn/'
ICON_URL = 'https://raw.githubusercontent.com/coutureone/weather-action/master/assets/bark-news-icon.png?v=4'


class BriefParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.active = []
        self.headings = []
        self.news = []
        self.history = []
        self.progress = []
        self.lines = []

    def handle_starttag(self, tag, attrs):
        classes = set(dict(attrs).get('class', '').split())
        if tag == 'br':
            self.handle_data('\n')
            return
        if tag in {'img', 'input', 'meta', 'link', 'hr', 'source', 'area'}:
            return
        ancestors = [entry[1] for entry in self.stack]
        parent = ancestors[-1] if ancestors else set()
        kind = None
        if tag == 'span' and 'u' in classes:
            kind = 'headings'
        elif tag == 'div' and 'line' in classes and 'news-wrap' in parent:
            kind = 'news'
        elif tag == 'a' and 'line' in parent and any('history-wrap' in group for group in ancestors):
            kind = 'history'
        elif tag == 'div' and 'progress-bar' in classes:
            kind = 'progress'
        elif tag == 'div' and 'line' in classes:
            kind = 'lines'
        self.stack.append((tag, classes))
        if kind:
            self.active.append((len(self.stack), kind, []))

    def handle_startendtag(self, tag, attrs):
        if tag == 'br':
            self.handle_data('\n')

    def handle_data(self, data):
        for _depth, _kind, parts in self.active:
            parts.append(data)

    def handle_endtag(self, tag):
        match = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i][0] == tag), None)
        if match is None:
            return
        del self.stack[match:]
        while self.active and self.active[-1][0] > len(self.stack):
            _depth, kind, parts = self.active.pop()
            text = re.sub(r'\s+', ' ', ''.join(parts)).strip()
            if text:
                getattr(self, kind).append(text)


def parse_brief(source):
    parser = BriefParser()
    parser.feed(source)
    parser.close()
    if len(parser.headings) < 2 or len(parser.news) < 8 or not parser.history or not parser.progress:
        raise ValueError('新闻源页面结构不完整，停止发送')
    year_line = next((line for line in reversed(parser.lines) if re.search(r'\d{4}年.*使用了', line)), '')
    if not year_line:
        raise ValueError('新闻源缺少年度进度，停止发送')
    content = '\n'.join([
        parser.headings[0],
        '',
        *parser.news,
        '',
        parser.headings[1],
        '',
        *(f'{i}. {item}' for i, item in enumerate(parser.history, 1)),
        '',
        f'时间进度条: {parser.progress[0]}',
        year_line,
        '',
    ])
    return parser.headings[0], content


def read_shell_config(path):
    values = {}
    for raw_line in Path(path).read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, raw_value = line.split('=', 1)
        parsed = shlex.split(raw_value, comments=True)
        values[key] = parsed[0] if parsed else ''
    return values


def send_tink(title, body):
    tink = read_shell_config('/run/secrets/tink.conf')
    bark = read_shell_config('/run/secrets/bark.conf')
    api_url = tink.get('TINK_API_URL', 'https://tink.mrma.me/api/v1/messages')
    api_key = tink.get('TINK_API_KEY', '')
    devices = [item for item in re.split(r'[,\s]+', tink.get('TINK_DEVICE_IDS', '')) if item]
    bark_key = urlparse(bark.get('BARK_URL', '')).path.rstrip('/').rsplit('/', 1)[-1]
    if not (urlparse(api_url).scheme == 'https' and api_key and devices and bark_key):
        raise ValueError('Tink 三端配置不完整')
    payload = {
        'title': title,
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
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json; charset=utf-8'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.load(response)
    if result.get('code') != 0 or not (result.get('data') or {}).get('dispatched_bark'):
        raise RuntimeError('Tink 未确认三端通知发送成功')


def send_daily(state_dir):
    state_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(CHINA_TIME)
    today = now.strftime('%Y-%m-%d')
    with (state_dir / 'send.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sent_marker = state_dir / f'sent-{today}'
        if sent_marker.exists():
            print(f'{today} 已发送，跳过')
            return
        try:
            request = urllib.request.Request(NEWS_URL, headers={'User-Agent': 'weather-action/1.0'})
            with urllib.request.urlopen(request, timeout=12) as response:
                source = response.read(200_000).decode('utf-8')
            heading, content = parse_brief(source)
            if f'{now.month}月{now.day}日' not in heading:
                raise ValueError('新闻源仍是旧日期，稍后重试')
            send_tink(f'今日新闻简报 ({today})', content)
            (state_dir / 'latest.txt').write_text(content)
            sent_marker.write_text(now.isoformat() + '\n')
            print(f'{today} 新闻简报已通过 Tink 发送')
        except Exception as exc:
            print(f'{today} 新闻简报未发送: {type(exc).__name__}: {exc}', file=sys.stderr)
            if now.hour == 8 and now.minute >= 55:
                failed_marker = state_dir / f'failed-{today}'
                if not failed_marker.exists():
                    send_tink('今日新闻简报暂未送达', '截至 08:55，新闻源仍无法获取今日内容，请稍后检查。')
                    failed_marker.write_text(now.isoformat() + '\n')
            raise


if __name__ == '__main__':
    args = argparse.ArgumentParser()
    args.add_argument('--send-tink', action='store_true')
    args.add_argument('--state-dir', type=Path, default=Path('/state'))
    options = args.parse_args()
    if options.send_tink:
        send_daily(options.state_dir)
    else:
        _heading, text = parse_brief(Path('result.html').read_text(encoding='utf-8'))
        Path('result.txt').write_text(text, encoding='utf-8')
