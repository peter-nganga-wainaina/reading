# Roadmap

```
Phase 1 ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4 ──▶ Phase 5
 live       river       importer    cover        notes
 (Claude)   (Claude)    (Peter)     fetcher      (Peter)
                                    (Peter)
```

The site is live after Phase 1 and stays live. Every phase after that is a push to `main`.

## Open decisions

- [ ] Title: "The Reading River" for now; "Mto wa Vitabu" still under consideration
- [x] Until the cover fetcher exists: link covers straight from Open Library by ISBN (title block when there is no ISBN)

## Phase 1: live on day one (Claude)

- [x] `config.toml` with `base_url = "https://peter-nganga-wainaina.github.io/reading"`
- [x] `.gitignore`: `public/`, `importer/data/`, `importer/target/`
- [x] `templates/base.html`: Google Fonts, page shell
- [x] `templates/year.html`, `templates/index.html`, `templates/components/river.html`: header (title + year), empty river, "January 1 · the river starts"
- [x] `sass/river.scss`: dark palette
- [x] `.github/workflows/deploy.yml`: build with Zola on every push to `main`
- [ ] Peter: turn on GitHub Pages (Settings → Pages → Source: GitHub Actions)

**Done when** the Pages URL shows the dark page with the 2026 header.

## Phase 2: the full river (Claude)

Built against two or three hand-written sample books so it can be checked before the importer exists.

- [ ] Month grouping, newest to oldest, with gold pill markers
- [ ] "<Month> · quiet month" for empty months
- [ ] Books alternate left and right across months
- [ ] Cover, or a coloured title block when there is none
- [ ] "read again" tag when `reread = true`
- [ ] Earlier years as plain links at the bottom; each year has its own page
- [ ] Phone layout: line on the left, every book on the right
- [ ] No counts and no ratings anywhere

**Done when** the river matches the mockup on desktop and phone.

## Phase 3: the importer, the one-time move from StoryGraph (Peter)

- [ ] Install Rust (`rustup`), `cargo new importer`
- [ ] Read the CSV with `csv` + `serde`, keep only `Read Status = read`
- [ ] Parse `Dates Read` with `chrono`: one read per range, finish date = end of range
- [ ] Rereads: one file per read, later reads get `reread = true`
- [ ] Special cases: Unbearable Lightness (July 2026), skip and flag A Hunger Artist and Young Zaphod
- [ ] Drop subtitles after `:`
- [ ] Write `content/books/<year>/<slug>.md` with the ISBN when there is one
- [ ] Safe to rerun: never overwrite, match by title + finish date
- [ ] Unit tests for date parsing, titles and rerun safety

**Done when** the old reads are on the live river, and a second run changes nothing.

## Phase 4: the cover fetcher (Peter writes it, Claude wires up the Action)

A second binary in the same cargo project, so it can share the book-file code with the importer. It covers imported books and new ones alike, so the importer never downloads anything.

- [ ] Find book files without a cover image
- [ ] ISBN → `covers.openlibrary.org/b/isbn/<isbn>-L.jpg?default=false`
- [ ] No ISBN → Open Library search by title + author → `cover_i`
- [ ] Save to `static/covers/<isbn-or-slug>.jpg`, never overwrite an existing image
- [ ] Decide how the template learns about the image (e.g. the fetcher adds a `cover` line to the front matter only when it's missing)
- [ ] Action: run the fetcher before Zola, commit new images back to `main`
- [ ] Template switches from Open Library links (if used) to local files

**Done when** pushing a new `.md` with only an ISBN produces a cover on the live site without doing anything by hand.

## Phase 5: notes (Peter)

- [ ] Write what each book left behind.
