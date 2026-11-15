"""Save a cover image for every book file that doesn't have one yet.

Looks the book up on Open Library (by ISBN first, then by title and author), saves the image to
static/covers/, and adds a `cover = "covers/<name>.jpg"` line to the book's front matter. Only that
line is added: the rest of the file, including the note, is never touched. An image already in the
covers folder is never replaced, so dropping in your own image overrides Open Library's.

Usage: python3 importer/covers.py content/books static/covers
"""

import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from storygraph import book_paths, front_matter

# Open Library asks API users to identify themselves.
USER_AGENT = "reading-river (https://github.com/peter-nganga-wainaina/reading)"
# urlopen waits forever by default; a stuck request must not hang the deploy.
TIMEOUT_SECONDS = 20
JPEG_MAGIC = b"\xff\xd8\xff"

Fetch = Callable[[str], bytes | None]


@dataclass
class CoverReport:
    added: list[Path] = field(default_factory=list)
    missing: list[Path] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)


def edition_url(isbn: str) -> str:
    return f"https://openlibrary.org/isbn/{isbn}.json"


def search_url(title: str, author: str) -> str:
    query = urlencode({"title": title, "author": author, "fields": "cover_i", "limit": 5})
    return f"https://openlibrary.org/search.json?{query}"


def id_cover_url(cover_id: int) -> str:
    # Covers fetched by ID aren't rate-limited; covers fetched by ISBN are (100 per 5 minutes).
    return f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg?default=false"


def isbn_cover_url(isbn: str) -> str:
    # Rate-limited, so only tried when the other lookups find nothing.
    return f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"


def fetch_from_open_library(url: str) -> bytes | None:
    """The response body, or None when Open Library has nothing at that URL."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read()
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


def first_author(author: str) -> str:
    return re.split(r"\s*[,&]\s*", author)[0]


def cover_id_from_edition(isbn: str, fetch: Fetch) -> int | None:
    body = fetch(edition_url(isbn))
    # Open Library lists missing covers as -1.
    ids = [cover_id for cover_id in json.loads(body).get("covers", []) if cover_id > 0] if body else []
    return ids[0] if ids else None


def cover_id_from_search(title: str, author: str, fetch: Fetch) -> int | None:
    # Names are written differently in different places ("H.G. Wells" vs "H. G. Wells"),
    # so if the full name finds nothing, try the surname alone.
    full_name = first_author(author)
    for name in dict.fromkeys([full_name, full_name.split()[-1] if full_name else ""]):
        body = fetch(search_url(title, name))
        docs = json.loads(body).get("docs", []) if body else []
        cover_id = next((doc["cover_i"] for doc in docs if doc.get("cover_i")), None)
        if cover_id:
            return cover_id
    return None


def find_cover(title: str, author: str, isbn: str | None, fetch: Fetch) -> bytes | None:
    """The cover image as JPEG bytes, or None if Open Library has none."""
    cover_id = (isbn and cover_id_from_edition(isbn, fetch)) or cover_id_from_search(title, author, fetch)
    image_urls = ([id_cover_url(cover_id)] if cover_id else []) + ([isbn_cover_url(isbn)] if isbn else [])
    for url in image_urls:
        image = fetch(url)
        if image and image.startswith(JPEG_MAGIC):
            return image
    return None


def with_cover_line(book_text: str, cover: str) -> str:
    """The book file with a cover line added to its [extra] table."""
    cover_line = f'cover = "{cover}"\n'
    if "\n[extra]\n" in book_text:
        return book_text.replace("\n[extra]\n", "\n[extra]\n" + cover_line, 1)
    _, toml_text, body = book_text.split("+++\n", 2)
    return f"+++\n{toml_text}[extra]\n{cover_line}+++\n{body}"


def fetch_missing_covers(books_dir: Path, covers_dir: Path, fetch: Fetch) -> CoverReport:
    report = CoverReport()
    for path in book_paths(books_dir):
        fields = front_matter(path)
        extra = fields.get("extra", {})
        if extra.get("cover"):
            continue

        isbn = extra.get("isbn")
        image_path = covers_dir / f"{isbn or path.stem}.jpg"
        if not image_path.exists():
            try:
                image = find_cover(fields["title"], extra.get("author", ""), isbn, fetch)
            except (OSError, json.JSONDecodeError) as error:  # URLError and timeouts are both OSErrors
                report.errors.append((path, str(error)))
                continue
            if image is None:
                report.missing.append(path)
                continue
            covers_dir.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(image)

        path.write_text(with_cover_line(path.read_text(), f"covers/{image_path.name}"))
        report.added.append(path)
    return report


def main(books_dir: Path, covers_dir: Path) -> None:
    report = fetch_missing_covers(books_dir, covers_dir, fetch_from_open_library)
    for path in report.added:
        print(f"cover   {path}")
    for path in report.missing:
        print(f"none    {path} (Open Library has no cover; add your own to {covers_dir})")
    for path, error in report.errors:
        # Reported but not fatal: a missing cover must never block a deploy. The next run retries.
        print(f"error   {path}: {error}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
