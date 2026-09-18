# 翻墙者新闻自动邮件订阅

本项目每 2 小时抓取翻墙者新闻页，跟踪新出现的新闻；每天北京时间 18:30 将当天 18:30 前发现的新闻汇总发送到 QQ 邮箱。

## 工作方式

- 抓取：每 2 小时一次。
- 日报：每天 18:30。
- 18:30 之后首次发现的新闻自动归入下一天日报。
- 会尝试访问新闻原始媒体页面并提取公开可访问正文。
- 如果原站要求登录、付费或拒绝自动访问，不绕过限制，只保留标题和原文链接。
- `data/pending.json` 保存尚未发送的新闻，`data/sent.json` 防止重复发送。

## QQ 邮箱配置

在 GitHub 仓库 Settings -> Secrets and variables -> Actions 中新增：

- `SMTP_USER` = `pan.kan@qq.com`
- `SMTP_PASSWORD` = QQ 邮箱 SMTP 授权码，不是 QQ 登录密码
- `MAIL_TO` = `pan.kan@qq.com`

不要把 SMTP 授权码写进代码。

## 第一次运行

先在 Actions 中手动运行 `News scrape every 2 hours`，确认能够正常抓取。第一次运行只处理当天新闻，避免把历史页面一次性全部加入日报。

然后配置 Secrets，再手动运行 `Daily news digest` 测试邮件发送。

GitHub Actions 的定时任务使用北京时间时区配置；GitHub 官方文档说明 schedule 支持 IANA timezone。
