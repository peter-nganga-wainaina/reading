import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError

from covers import edition_url, fetch_missing_covers, id_cover_url, isbn_cover_url, search_url
from storygraph import front_matter

JPEG = b"\xff\xd8\xff\xe0 a real cover"
OTHER_JPEG = b"\xff\xd8\xff\xe0 another cover"


class FakeOpenLibrary:
    """Answers like Open Library: known URLs give their bytes, anything else is a 404 (None)."""

    def __init__(self, responses=None, down=False):
        self.responses = responses or {}
        self.down = down

    def fetch(self, url):
        if self.down:
            raise URLError("Open Library is down")
        return self.responses.get(url)


def edition(cover_id):
    return json.dumps({"covers": [cover_id]}).encode()


def search_result(cover_id):
    return json.dumps({"docs": [{"cover_i": cover_id}]}).encode()


class FetchMissingCoversTest(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.books_dir = root / "content" / "books"
        self.covers_dir = root / "static" / "covers"
        (self.books_dir / "2026").mkdir(parents=True)

    def book(self, slug, title="How Democracies Die", isbn=None, cover=None, note=""):
        extra = ['author = "Steven Levitsky & Daniel Ziblatt"']
        if isbn:
            extra.append(f'isbn = "{isbn}"')
        if cover:
            extra.append(f'cover = "{cover}"')
        path = self.books_dir / "2026" / f"{slug}.md"
        path.write_text(
            f'+++\ntitle = "{title}"\ndate = 2026-04-14\n[extra]\n' + "\n".join(extra) + "\nreread = false\n+++\n" + note
        )
        return path

    def run_fetcher(self, open_library):
        return fetch_missing_covers(self.books_dir, self.covers_dir, open_library.fetch)

    def test_isbn_cover_is_saved_and_linked_from_the_book(self):
        book = self.book("how-democracies-die", isbn="9781524762933", note="My note.\n")

        self.run_fetcher(FakeOpenLibrary({edition_url("9781524762933"): edition(42), id_cover_url(42): JPEG}))

        self.assertEqual((self.covers_dir / "9781524762933.jpg").read_bytes(), JPEG)
        self.assertEqual(front_matter(book)["extra"]["cover"], "covers/9781524762933.jpg")
        self.assertTrue(book.read_text().endswith("+++\nMy note.\n"))

    def test_title_search_is_used_when_the_isbn_has_no_cover(self):
        self.book("how-democracies-die", isbn="9781524762933")
        open_library = FakeOpenLibrary({
            edition_url("9781524762933"): json.dumps({"title": "no covers listed"}).encode(),
            search_url("How Democracies Die", "Steven Levitsky"): search_result(42),
            id_cover_url(42): JPEG,
        })

        self.run_fetcher(open_library)

        self.assertEqual((self.covers_dir / "9781524762933.jpg").read_bytes(), JPEG)

    def test_isbn_cover_is_the_last_resort(self):
        # Open Library's ISBN cover endpoint sometimes knows covers its edition data doesn't list.
        self.book("the-divine-farce", title="The Divine Farce", isbn="9781935248040")

        self.run_fetcher(FakeOpenLibrary({isbn_cover_url("9781935248040"): JPEG}))

        self.assertEqual((self.covers_dir / "9781935248040.jpg").read_bytes(), JPEG)

    def test_search_falls_back_to_the_surname_when_the_full_name_finds_nothing(self):
        # "H.G. Wells" in the book file is "H. G. Wells" on Open Library.
        (self.books_dir / "2026" / "the-first-men-in-the-moon.md").write_text(
            '+++\ntitle = "The First Men in the Moon"\ndate = 2024-12-25\n[extra]\nauthor = "H.G. Wells"\n+++\n'
        )
        open_library = FakeOpenLibrary({
            search_url("The First Men in the Moon", "Wells"): search_result(8081288),
            id_cover_url(8081288): JPEG,
        })

        self.run_fetcher(open_library)

        self.assertTrue((self.covers_dir / "the-first-men-in-the-moon.jpg").exists())

    def test_book_without_isbn_is_searched_and_named_after_its_file(self):
        book = self.book("the-agi-chronicles", title="The AGI Chronicles")
        open_library = FakeOpenLibrary({
            search_url("The AGI Chronicles", "Steven Levitsky"): search_result(7),
            id_cover_url(7): JPEG,
        })

        self.run_fetcher(open_library)

        self.assertEqual(front_matter(book)["extra"]["cover"], "covers/the-agi-chronicles.jpg")
        self.assertTrue((self.covers_dir / "the-agi-chronicles.jpg").exists())

    def test_book_with_no_cover_anywhere_is_left_unchanged(self):
        book = self.book("how-democracies-die", isbn="9781524762933")
        before = book.read_text()

        report = self.run_fetcher(FakeOpenLibrary())

        self.assertEqual(book.read_text(), before)
        self.assertEqual(report.missing, [book])

    def test_image_already_in_covers_folder_is_kept_and_linked(self):
        # Peter's own image (e.g. a better Mortality cover) must never be replaced.
        self.covers_dir.mkdir(parents=True)
        (self.covers_dir / "9781524762933.jpg").write_bytes(OTHER_JPEG)
        book = self.book("how-democracies-die", isbn="9781524762933")

        self.run_fetcher(FakeOpenLibrary({edition_url("9781524762933"): edition(42), id_cover_url(42): JPEG}))

        self.assertEqual((self.covers_dir / "9781524762933.jpg").read_bytes(), OTHER_JPEG)
        self.assertEqual(front_matter(book)["extra"]["cover"], "covers/9781524762933.jpg")

    def test_book_that_already_has_a_cover_is_left_alone(self):
        book = self.book("how-democracies-die", isbn="9781524762933", cover="covers/mine.jpg")
        before = book.read_text()

        self.run_fetcher(FakeOpenLibrary({edition_url("9781524762933"): edition(42), id_cover_url(42): JPEG}))

        self.assertEqual(book.read_text(), before)
        self.assertFalse(self.covers_dir.exists() and any(self.covers_dir.iterdir()))

    def test_response_that_is_not_a_jpeg_is_not_saved(self):
        book = self.book("how-democracies-die", isbn="9781524762933")

        self.run_fetcher(FakeOpenLibrary({edition_url("9781524762933"): edition(42), id_cover_url(42): b"<html>error</html>"}))

        self.assertFalse((self.covers_dir / "9781524762933.jpg").exists())
        self.assertNotIn("cover", front_matter(book)["extra"])

    def test_open_library_being_down_is_reported_not_fatal(self):
        book = self.book("how-democracies-die", isbn="9781524762933")

        report = self.run_fetcher(FakeOpenLibrary(down=True))

        self.assertEqual([path for path, _ in report.errors], [book])
        self.assertNotIn("cover", front_matter(book)["extra"])


if __name__ == "__main__":
    unittest.main()
