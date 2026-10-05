"""Check that published posts use the template's title and body headings start at H2."""

import argparse
import html
from pathlib import Path
import re
import sys


def plain_title(value):
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[*_`]", "", value)
    return " ".join(html.unescape(value).strip().split()).casefold()


def check_post(text):
    front = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not front:
        return [(1, "Missing YAML front matter.")]
    title_match = re.search(r"^title:[ \t]*(.+)$", front[1], re.M)
    if not title_match:
        return [(1, "Missing front matter title.")]
    title = plain_title(title_match[1].strip().strip("\"'"))
    errors = []
    fence = None
    previous = ""
    offset = text[:front.end()].count("\n") + 1
    for line_number, line in enumerate(text[front.end():].splitlines(), offset):
        if fence:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
                fence = None
            continue
        opening = re.match(r" {0,3}(`{3,}|~{3,})", line)
        if opening:
            fence = opening[1]
            previous = ""
            continue
        if line.startswith(("    ", "\t")):
            previous = ""
            continue
        heading = re.match(r" {0,3}(#{1,6})(?:\s+|$)(.*?)\s*#*\s*$", line)
        html_heading = re.match(r"\s*<h([1-6])\b[^>]*>(.*?)</h\1>\s*$", line, re.I)
        if heading and len(heading[1]) == 1:
            errors.append((line_number, "Body H1: the template already renders the article title; use H2 or lower."))
        elif re.match(r" {0,3}<h1\b", line, re.I):
            errors.append((line_number, "Body HTML H1: keep the article title in front matter."))
        elif previous and re.fullmatch(r" {0,3}=+\s*", line):
            errors.append((line_number - 1, "Body setext H1: use an H2 section heading instead."))
        else:
            candidate = heading[2] if heading else html_heading[2] if html_heading else line
            if candidate.strip() and plain_title(candidate) == title:
                errors.append((line_number, "Repeated article title in the body: remove it and keep the front matter title."))
        previous = line.strip()
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--posts-dir", type=Path, default=Path(__file__).resolve().parents[1] / "_posts")
    posts_dir = parser.parse_args().posts_dir
    posts = sorted(path for path in posts_dir.rglob("*") if path.suffix.lower() in {".md", ".markdown"})
    if not posts:
        print(f"No Markdown posts found in {posts_dir}.", file=sys.stderr)
        return 1
    failed = False
    for path in posts:
        for line, message in check_post(path.read_text(encoding="utf-8-sig")):
            print(f"{path}:{line}: {message}", file=sys.stderr)
            failed = True
    if failed:
        return 1
    print(f"Title checks passed for all {len(posts)} posts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
