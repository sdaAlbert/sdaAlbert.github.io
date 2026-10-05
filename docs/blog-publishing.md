# Blog publishing workflow

## Canonical locations

- Draft input: `C:\dev\opensource\<draft>.md`
- Website repository: `C:\dev\INFRA\sdaAlbert.github.io`
- Published posts: `_posts/YYYY-MM-DD-<slug>.md` and `_posts/YYYY-MM-DD-<slug>-en.md`
- Chinese URL: `/posts/<slug>/`
- English URL: `/posts/<slug>/en/`
- Archive URL: `/year-archive/`

## Front matter contract

Each bilingual post must have:

```yaml
date: YYYY-MM-DD
permalink: /posts/<slug>/
lang: zh-CN
translations:
  zh: /posts/<slug>/
  en: /posts/<slug>/en/
```

The English page uses the same date and slug, `permalink: /posts/<slug>/en/`, and `lang: en`.

## One article title per page

- Put the article title in front matter under `title:`. The `single` layout renders it above the body.
- Published `_posts` files must not repeat the article title in the body, whether as a Markdown heading, a bold line, or an HTML heading.
- Start the body with introductory prose or an H2 (`##`) section. Use H3 and lower levels for subsections; do not use an H1 in the body.
- A source draft may keep its H1 for standalone reading. When creating or updating its published copy, remove that draft title rather than copying the whole file verbatim. Preserve the draft itself.
- Keep headings inside code samples. They are examples, not rendered article titles.
- Run `python scripts/check_post_titles.py` before staging. The script checks all posts, including Markdown and HTML H1s, setext titles, and repeated title lines, while ignoring fenced and indented code.
- The `Check post titles` GitHub workflow runs the same check on relevant pushes and pull requests. It reports violations; it does not change the site's deployment configuration.

## Before publishing

1. Read the source draft and the style guide.
2. Confirm the Chinese and English versions have matching major headings.
3. Confirm both translation links point to existing pages.
4. Confirm `_pages/year-archive.html` filters out `lang: zh-CN` posts.
5. Run `python scripts/check_post_titles.py` and fix any violations.
6. Run `git diff --check`.
7. Run the Jekyll build when Ruby, Bundler, and Jekyll are available. If they are unavailable, report that limitation.

## Git publishing

Only publish after the user explicitly asks. Inspect the working tree first. Stage explicit article and template paths; never use `git add .` when unrelated changes are present. Check `gh auth status` before pushing. If authentication or network access fails, stop and report it.

The production result should be checked at:

- `https://sdaalbert.github.io/posts/<slug>/`
- `https://sdaalbert.github.io/posts/<slug>/en/`
- `https://sdaalbert.github.io/year-archive/`
