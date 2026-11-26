# 微信公众号文章作为材料

支持两种输入：

```text
公众号文章 URL
用户保存下来的 article.html
```

## 抓取

```text
python -B scripts/fetch_wechat_article.py \
  --url "https://mp.weixin.qq.com/s/..." \
  --out work/wechat-source \
  --download-images
```

保存的 HTML：

```text
python -B scripts/fetch_wechat_article.py \
  --html-file article.html \
  --out work/wechat-source \
  --download-images
```

输出：

```text
source.html
article.md
manifest.json
images/
```

`manifest.json` 记录：

```text
title / account / source_url / source_sha256
text_chars
images[]：url、hash、尺寸、data-w/data-ratio、锚点文字、decision
sub_links[]：子文章 URL、标题
```

## 文章结构

- 正文取 `#js_content`；
- 图片优先读 `data-src`，再回退 `src`；
- 懒加载图片的 `src` 可能只是占位符；
- 图片按 URL/hash 去重；文件名不再固定为 `640`；
- 图片默认 `needs_review`，不自动生成 `[Pic#]`；
- 子文章链接单独列出，不默认无限抓取。

## 索引文章

如果当前文章是“30 天汇总”这类索引：

```text
先显示 sub_links 数量和标题
→ 问用户抓哪些天/哪些范围
→ 用户确认后再逐篇抓
```

不能看到 30 个链接就默认全抓。设置范围、页数上限和请求间隔。

## 图片处理

默认只保存并列入待审：

```text
正文内容图
封面/banner
二维码
分隔线/装饰
音频入口卡
```

对图片：

- 先按锚点文字判断它服务哪段；
- 二维码、banner、装饰不自动入卡；
- 内容图经用户确认后才进入 `[Pic#]`；
- 图片尺寸异常只作复核信号，不直接丢弃；
- 需要保留原始 URL、hash 和 `article.md` 中的位置。

## 来源与边界

- 只处理用户提供或有权使用的文章；
- 不绕过登录、付费墙、验证码或反爬；
- 不批量抓取整号；索引文章抓取前确认范围；
- 保留来源 URL、标题、公众号名和抓取时间；
- 不把公众号原文直接当成自己的知识内容；拆卡时保留出处；
- 抓取失败时请用户保存 HTML 或提供正文，不用伪造内容补。

## 后续流程

抓取完成后按普通材料处理：

```text
G1 目标/章节确认
→ 图片待审
→ 生成卡片
→ 媒体安全校验
→ 客户端抽查
```

微信公众号只是材料来源，不绕过章节确认、图片审查或写入授权。
