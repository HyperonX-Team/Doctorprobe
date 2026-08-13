# Doctordrobe Docs (GitHub Pages)

This branch is the **published documentation website** for
[Doctordrobe](https://github.com/hyperonx-team/doctorprobe), served by
GitHub Pages at:

> https://hyperonx-team.github.io/doctorprobe/

## How to update

The canonical source of these pages lives in **`docs/` on `main`**.
To republish after editing the docs:

```bash
# on main
git checkout main
# edit docs/*, then rebuild this branch from the docs folder:
git checkout --orphan gh-pages
git rm -rf --quiet . 2>/dev/null; true
mv docs/* . && rmdir docs
git add -A
git commit -m "Rebuild docs site"
git push origin gh-pages
git checkout main
```

## Stack

Plain static HTML + CSS + a small vanilla JS file (`js/site.js` for the
sidebar search filter and code-block copy buttons). No build step, no
dependencies — pages are hand-written and MDN-style, with relative links
so they work under the repository's GitHub Pages sub-path.
