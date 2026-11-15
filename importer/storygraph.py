"""Import finished reads from a StoryGraph CSV export into the reading river.

One Markdown file per read goes into content/books/<year>/. Safe to run again: existing files
are never touched, and a read already on the river (same title and finish date) is skipped.

Usage: python3 importer/storygraph.py importer/data/storygraph.csv content/books
"""

import csv
import json
import re
import sys
import tomllib
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DATE_FORMAT = "%Y/%m/%d"
ISBN_PATTERN = re.compile(r"^(\d{13}|\d{9}[\dX])$")


@dataclass(frozen=True)
class Read:
    title: str
    author: str
    isbn: str | None
    finished: date
    reread: bool
    note: str


def finish_dates(dates_read: str) -> list[date]:
    """Finish dates from a 'Dates Read' cell, oldest first.

    The cell holds comma-separated 'start-end' ranges. A range that runs backwards
    (end before start) was typed the wrong way round, so the later date is the finish.
    """
    finished = []
    for date_range in filter(None, (part.strip() for part in dates_read.split(","))):
        try:
            start, end = (datetime.strptime(d, DATE_FORMAT).date() for d in date_range.split("-"))
        except ValueError as error:
            raise ValueError(f"Can't read the date range {date_range!r}") from error
        finished.append(max(start, end))
    return sorted(finished)


def clean_title(title: str) -> str:
    return title.split(":", 1)[0].strip()


def format_authors(authors: str) -> str:
    names = [name.strip() for name in authors.split(",") if name.strip()]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " & " + names[-1]


def slugify(title: str) -> str:
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower().replace("'", "")).strip("-")


def valid_isbn(value: str) -> str | None:
    value = value.strip()
    return value if ISBN_PATTERN.match(value) else None


def dates_finished(row: dict[str, str]) -> list[date]:
    """When a finished book was read, oldest first.

    A book marked read with no read dates finishes on the day it was added to StoryGraph
    (Peter's choice). Reads StoryGraph counts but never dated are left out.
    """
    try:
        dates = finish_dates(row["Dates Read"])
        if not dates and row["Date Added"].strip():
            dates = [datetime.strptime(row["Date Added"].strip(), DATE_FORMAT).date()]
    except ValueError as error:
        raise ValueError(f"{row['Title']}: {error}") from error
    return dates


def reads_from_row(row: dict[str, str]) -> list[Read]:
    """Every read of one book. Rows that aren't finished books give none."""
    if row["Read Status"] != "read":
        return []
    return [
        Read(
            title=clean_title(row["Title"]),
            author=format_authors(row["Authors"]),
            isbn=valid_isbn(row["ISBN/UID"]),
            finished=finished,
            reread=index > 0,
            note=row["Review"].strip(),
        )
        for index, finished in enumerate(dates_finished(row))
    ]


def problems_with_row(row: dict[str, str]) -> list[str]:
    """Things about a finished book that Peter has to fix by hand."""
    if row["Read Status"] == "read" and not dates_finished(row):
        return [f"{row['Title']}: no read date or date added, add it by hand"]
    return []


def toml_string(value: str) -> str:
    # A JSON string is also a valid TOML basic string, escapes included.
    return json.dumps(value, ensure_ascii=False)


def book_file(read: Read) -> str:
    lines = [
        "+++",
        f"title = {toml_string(read.title)}",
        f"date = {read.finished.isoformat()}",
        "[extra]",
        f"author = {toml_string(read.author)}",
    ]
    if read.isbn:
        lines.append(f"isbn = {toml_string(read.isbn)}")
    lines += [f"reread = {str(read.reread).lower()}", "+++"]
    return "\n".join(lines) + "\n" + (read.note + "\n" if read.note else "")


def year_page(year: int) -> str:
    return f'+++\ntitle = "{year}"\ntemplate = "year.html"\nsort_by = "date"\n+++\n'


def reads_on_river(books_dir: Path) -> set[tuple[str, date]]:
    """(title, finish date) of every book file already there, however it was named."""
    on_river = set()
    for path in books_dir.glob("*/*.md"):
        if path.name == "_index.md":
            continue
        try:
            _, toml_text, _ = path.read_text().split("+++\n", 2)
            fields = tomllib.loads(toml_text)
            on_river.add((fields["title"], fields["date"]))
        except (ValueError, KeyError) as error:
            raise ValueError(f"Can't read the front matter of {path}") from error
    return on_river


def free_path(year_dir: Path, slug: str) -> Path:
    """The book's file path, numbered if another read already has that name."""
    path, number = year_dir / f"{slug}.md", 2
    while path.exists():
        path, number = year_dir / f"{slug}-{number}.md", number + 1
    return path


def write_new_reads(reads: list[Read], books_dir: Path) -> list[Path]:
    """Write each read not already on the river. Never overwrites a file. Returns the new files."""
    on_river = reads_on_river(books_dir)
    written = []
    for read in reads:
        if (read.title, read.finished) in on_river:
            continue
        year_dir = books_dir / str(read.finished.year)
        year_dir.mkdir(parents=True, exist_ok=True)
        if not (year_dir / "_index.md").exists():
            (year_dir / "_index.md").write_text(year_page(read.finished.year))
        path = free_path(year_dir, slugify(read.title))
        path.write_text(book_file(read))
        on_river.add((read.title, read.finished))
        written.append(path)
    return written


def main(csv_path: Path, books_dir: Path) -> None:
    with csv_path.open(newline="", encoding="utf-8-sig") as export:
        rows = list(csv.DictReader(export))

    reads = [read for row in rows for read in reads_from_row(row)]
    written = write_new_reads(reads, books_dir)
    for path in written:
        print(f"added   {path}")
    for problem in (p for row in rows for p in problems_with_row(row)):
        print(f"check   {problem}")
    if not written:
        print("Nothing new: every read is already on the river.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
