# 如何更新这个博客

这个站点使用 Jekyll 和 GitHub Pages。每篇文章都是 `_posts` 目录中的一个 Markdown 文件；推送到 GitHub 后，页面会自动重新发布。

## 写一篇新文章

1. 在 `_posts` 目录新建文件，名称必须是 `年-月-日-英文短标题.md`，例如：

   ```text
   _posts/2026-09-18-my-first-agent.md
   ```

2. 将下面的模板复制进去：

   ```markdown
   ---
   title: "文章标题"
   date: 2026-09-18
   description: "显示在首页和文章列表里的一句话摘要。"
   tags:
     - AI
     - 随笔
   ---

   这里开始写正文。

   ## 一个小标题

   继续写……
   ```

3. 提交并推送：

   ```bash
   git add _posts
   git commit -m "Add post: 文章标题"
   git push origin master
   ```

通常等待一两分钟后，文章就会出现在首页和 `/blog/` 页面。

## 常用 Markdown

```markdown
## 二级标题

**粗体**、*斜体*、[链接文字](https://example.com)

> 一段引用

- 列表项目
- 另一个项目

![图片说明](/images/example.jpg)
```

图片先放进 `images` 目录，再用 `/images/文件名` 引用。

## 发布前在本地预览

首次使用先安装 Ruby 与 Bundler，然后在仓库目录运行：

```bash
bundle install
bundle exec jekyll serve
```

浏览器打开 `http://127.0.0.1:4000`。修改 Markdown 后刷新即可看到结果；修改 `_config.yml` 后需要重启服务。

## 修改首页文字

- 首页内容：`_layouts/home.html`
- 姓名、邮箱、社交账号：`_config.yml`
- 导航：`_data/navigation.yml`
- 整体视觉：`assets/css/albert.scss`

## 草稿

暂时不想发布的文章可以放进 `_drafts`，文件名不需要日期。本地预览草稿：

```bash
bundle exec jekyll serve --drafts
```
