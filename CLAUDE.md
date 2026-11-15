# The Reading River

Peter's personal reading log: a single page that shows the books he finished each year as a timeline ("river"), each with its cover and a short note on what it left behind. It's for himself, not an audience.

**Goal of this project:** get the site live with Zola, and use the StoryGraph importer as Peter's first real Rust program.

## How to work with Peter

- **Zola templates, Sass and deploy config:** go ahead and write these.
- **The Rust importer (`importer/`):** Peter writes this himself to learn Rust. Explain concepts, review his code and help with compiler errors, but don't write the program for him unless he asks. Point him to the relevant crate docs.
- When he's confused or going back and forth, simplify the explanation or draw a flowchart.

## Non-negotiables

- **No counts anywhere**: no "12 books", no per-month or per-year totals. It shouldn't feel like tracking.
- **No ratings.**
- **Only finished books.**
- Adding a book must stay trivial: one Markdown file, then push.

## Hosting

- GitHub repo named **`reading`**, deployed with GitHub Pages at **`<username>.github.io/reading`**. Set `base_url` in `config.toml` to match.
- Deploy with a GitHub Actions workflow that builds with Zola on every push to `main`.
- A future homepage will live in a separate `<username>.github.io` repo, so this site stays at `/reading`.

## Repo layout

```
reading/
├── config.toml
├── content/books/_index.md
├── content/books/<year>/_index.md
├── content/books/<year>/<slug>.md      ← one file per finished read
├── templates/base.html                 ← fonts, page shell
├── templates/index.html                ← homepage: river for the newest year folder
├── templates/year.html                 ← one year's page
├── templates/components/river.html     ← the river itself, shared by both
├── sass/river.scss
├── static/covers/<isbn-or-slug>.jpg    ← downloaded once by the importer
├── importer/                           ← Peter's Rust crate (cargo project)
└── .github/workflows/deploy.yml
```

Zola is pinned to **0.23.6** (locally and in `deploy.yml`). 0.23 uses **Tera v2**: no macros or `import` (use global `{% component %}`s, called as `{{ <name arg={value} /> }}`), components only see the parameters passed in, and you can't chain `.field` onto a function call (`set` it first).

The StoryGraph CSV export holds ratings and other private data. Keep it **out of git** (put it under `importer/data/` and gitignore it).

## Book file format

```
+++
title = "How Democracies Die"
date = 2026-04-14            # finish date: decides year and month
[extra]
author = "Steven Levitsky & Daniel Ziblatt"
isbn = "9781524762933"       # optional
cover = "covers/9781524762933.jpg"
reread = false               # true shows a "read again" tag
+++
Peter's note goes here. Can be empty at first.
```

## The river page (design is locked)

The layout comes from Peter's Claude design canvas, board "E2 · Reading River": https://claude.ai/artifact/4EX1RUyH2ZjH1LoRnGJU4g. On 2026-11-15 Peter switched to a **dark** look (the canvas's "Night" theme) and dropped the kanga/kitenge styling ("not really me"). The canvas's cream and red colours are out of date; the palette below wins.

- **Opens on the current year.** Earlier years are plain links at the bottom ("2025 →", "2024 →") to their own year pages.
- **Header**, centred: title in italic EB Garamond, then just the year. (Peter dropped the Swahili proverb on 2026-11-15.)
  - The working title is "The Reading River". Peter is considering **"Mto wa Vitabu"** (Swahili for "river of books"), so ask him before finalising.
- **River:**
  - A 2px vertical line `#3A3F46` runs down the centre.
  - Months go newest to oldest.
  - A month with books gets a gold pill marker with the month name only (accent background, background-colour text, IBM Plex Mono, uppercase).
  - A month with no books gets a faint "<Month> · quiet month" label.
  - Books alternate left and right of the line, continuing across months. Each has a small gold dot on the line, an 80×120 cover next to the line, then the title, the author in italic, and the note.
  - The river ends with "January 1 · the river starts".
- **Palette** (dark only, no light mode):
  - Background `#121417`, ink `#ECEAE4`
  - Soft text `#C9C7C0`, muted `#A3A29C`, faint `#8C8B86` (dimmest that passes 4.5:1)
  - Rules `#2C3036`, river line `#3A3F46`, accent gold `#E8C27A`, link hover `#F2D9A6`
- **Fonts** (Google Fonts): EB Garamond for headings and body, IBM Plex Mono for labels.
- **Covers:** use real covers when available. Otherwise use a coloured block with the title and author.
- **Phones:** move the river line to the left edge and put every book on the right.

## StoryGraph import rules (decided with Peter)

1. Import only rows with `Read Status = read`. Skip `to-read` and `did-not-finish`.
2. A book's finish date is the end of a range in `Dates Read`. Its month decides where it goes on the river.
3. **Rereads appear in every year they were read.** `Dates Read` can hold several ranges separated by commas. Create one file per read; every read after the first gets `reread = true`.
4. Fix: *The Unbearable Lightness of Being* has a backwards range (2026/07/06–2026/06/20). Treat it as **finished July 2026**.
5. *A Hunger Artist* and *Young Zaphod Plays It Safe* have no dates. Peter will add them by hand, so skip them or flag them.
6. If a book has no ISBN, look up its cover on Open Library by title and author.
7. Drop the rating, moods and pace. Use the StoryGraph review as the starting note if there is one (currently they're all empty).
8. **Running it again must be safe:** never overwrite an existing file or note. Only add reads that are missing, matched by title and finish date.
9. Titles: drop subtitles after `:` (e.g. "How Democracies Die: What History Reveals…" becomes "How Democracies Die").

## Covers (decided 2026-11-15)

- The importer is a one-time move from StoryGraph. It writes `.md` files only and never downloads covers.
- A separate **cover fetcher** (Peter's second Rust binary, same cargo project) runs in the GitHub Action before Zola. It fetches covers for any book file that lacks one (ISBN first, then title + author search), saves them to `static/covers/`, and commits them back to `main`.
- Adding a book stays one `.md` file. An `isbn` is enough to get a cover with no manual work.

## Build order

See `ROADMAP.md`.
