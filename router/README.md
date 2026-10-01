# 软路由新闻通知

每天北京时间 08:00 开始抓取 `news.topurl.cn`，通过现有 Tink API 同时发送到两台 Mac 和 iPhone Bark。08:00–08:55 每五分钟重试；发送成功后按日期记录状态，后续尝试会跳过。若到 08:55 仍取不到当天内容，会发送一条失败通知。

脚本安装在 `/usr/local/lib/weather-news/getInfo.py`，启动器在 `/usr/local/bin/weather-news-send.sh`，状态保存在 `/var/lib/weather-news/`。凭据只读取路由器上已有的 `/etc/tink.conf` 和 `/etc/bark.conf`。使用 `weather-news-python:20261001` 本地 Docker 标签运行 Python，不依赖 Mac 开机。

路由器 crontab：

```cron
*/5 8 * * * /usr/local/bin/weather-news-send.sh >> /var/log/weather-news.log 2>&1
```

GitHub Actions 仅在 08:17 左右归档当天内容，不发送通知；实际归档时间受 GitHub 调度影响。
