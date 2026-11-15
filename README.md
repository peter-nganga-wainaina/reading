# Marginalia

The books I've finished, year by year, each with a note on what it left behind.

**https://peter-nganga-wainaina.github.io/reading/**

Built with [Zola](https://www.getzola.org/) and deployed to GitHub Pages on every push to `main`.

## Add a book

Create `content/books/<year>/<slug>.md`:

```toml
+++
title = "Piranesi"
date = 2026-11-20          # the day I finished it
[extra]
author = "Susanna Clarke"
isbn = "9781635575637"     # optional, helps find the cover
reread = false
+++
What it left behind.
```

Push it. The deploy fetches the cover and commits it back, so `git pull` a minute later.

A new year also needs `content/books/<year>/_index.md`: copy last year's and change the year.

## Add a note

Write below the second `+++` in the book's file, then push. Markdown works.

## Fix a cover

Covers live in `static/covers/`. To replace a wrong one, overwrite the file with your own `.jpg`. The cover fetcher never replaces an existing image.

## Run it locally

```sh
zola serve                                    # preview at http://127.0.0.1:1111
python3 -m unittest discover -s importer      # tests
python3 importer/covers.py content/books static/covers
```

`importer/storygraph.py` did the one-time import from my StoryGraph export. The export itself stays out of git.
