"""从已下载的新闻页面生成简报。"""

import re
from html.parser import HTMLParser
from pathlib import Path


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


if __name__ == '__main__':
    _heading, text = parse_brief(Path('result.html').read_text(encoding='utf-8'))
    Path('result.txt').write_text(text, encoding='utf-8')
