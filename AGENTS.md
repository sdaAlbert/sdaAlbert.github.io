# Blog repository instructions

## Repository

- GitHub repository: https://github.com/sdaAlbert/sdaAlbert.github.io
- Production site: https://sdaalbert.github.io/
- Blog archive: https://sdaalbert.github.io/year-archive/
- Source drafts are usually under `C:\dev\opensource`.
- Published posts are Jekyll files under `_posts/`.
- New blog initial drafts should be written under `blogwriting/` by default; only move them to `_posts/` when the user asks to add them to the site or publish them.

## Persistent working rules

- For blog writing, translation, revision, and publishing tasks, use the repository skill `blog-workflow` and read `docs/blog-style.md`.
- Keep the article’s main line clear: concrete problem →public industry examples → scale evolution → decision rules → concise takeaway.
- Write short, calm, explanatory sentences. Explain a not basic technical term the first time it appears. Avoid middleware name lists, marketing claims, and unsupported production claims.
- Write only the Chinese initial draft by default. Create an English version only after the user explicitly asks for translation.
- When the user asks to translate, the Chinese and English versions must describe the same argument, but the English version should read as natural technical English rather than a literal translation.
- When the user asks to publish or push, create the matching bilingual `_posts` files with the same date and slug. Front matter must include `lang` and matching `translations.zh` / `translations.en` paths.
- The blog archive should list only the English copy. The Chinese copy remains reachable through the language switcher.
- Published post titles belong in front matter and are rendered by the page template. Do not repeat the article title or use a body-level H1; use H2 for main sections. Before publishing, run `python scripts/check_post_titles.py`.
- Keep large or repeated process details in `docs/`; keep this file short and stable.

## Safety and scope

- Do not overwrite source drafts or unrelated posts unless the user asks for it.
- Do not stage `.learnings/`, temporary files, or unrelated working-tree changes.
- Do not commit or push unless the user explicitly asks to publish, push, or deploy.
- Before publishing, inspect `git status --short`, use explicit file paths with `git add`, and run `git diff --check`.
- Before pushing, inspect `git remote get-url origin` and check the authentication method that remote actually uses. An invalid `gh auth status` token alone does not mean Git push authentication is unavailable; SSH remotes use SSH credentials.
- If the execution environment disables the remote's transport, report that environment restriction and do not ask the user to log in. Ask for re-authentication only when the actual Git transport reports an authentication or permission error.
- If network access or the Jekyll toolchain is unavailable, report the exact limitation and do not claim deployment succeeded.
