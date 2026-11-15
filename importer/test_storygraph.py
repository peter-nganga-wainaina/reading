import tempfile
import tomllib
import unittest
from datetime import date
from pathlib import Path

from storygraph import (
    Read,
    clean_title,
    finish_dates,
    format_authors,
    problems_with_row,
    reads_from_row,
    slugify,
    valid_isbn,
    write_new_reads,
)


def storygraph_row(**overrides):
    """A row shaped like the StoryGraph export, with only the columns the importer reads."""
    row = {
        "Title": "How Democracies Die: What History Reveals About Our Future",
        "Authors": "Steven Levitsky, Daniel Ziblatt",
        "ISBN/UID": "9781524762933",
        "Read Status": "read",
        "Dates Read": "2026/04/07-2026/04/14",
        "Date Added": "2026/03/30",
        "Read Count": "1",
        "Review": "",
    }
    row.update(overrides)
    return row


class FinishDatesTest(unittest.TestCase):
    def test_finish_date_is_the_end_of_the_range(self):
        self.assertEqual(finish_dates("2026/04/07-2026/04/14"), [date(2026, 4, 14)])

    def test_several_ranges_give_one_finish_date_each_oldest_first(self):
        self.assertEqual(
            finish_dates("2026/07/14-2026/07/17, 2024/03/30-2024/03/30"),
            [date(2024, 3, 30), date(2026, 7, 17)],
        )

    def test_backwards_range_finishes_on_the_later_date(self):
        # The Unbearable Lightness of Being: 2026/07/06-2026/06/20 means finished July 2026.
        self.assertEqual(finish_dates("2026/07/06-2026/06/20"), [date(2026, 7, 6)])

    def test_empty_cell_has_no_finish_dates(self):
        self.assertEqual(finish_dates(""), [])

    def test_malformed_range_fails_loudly(self):
        with self.assertRaises(ValueError):
            finish_dates("sometime in April")


class CleanTitleTest(unittest.TestCase):
    def test_subtitle_after_colon_is_dropped(self):
        self.assertEqual(
            clean_title("How Democracies Die: What History Reveals About Our Future"),
            "How Democracies Die",
        )

    def test_title_without_subtitle_is_unchanged(self):
        self.assertEqual(clean_title("Why Read Moby-Dick?"), "Why Read Moby-Dick?")


class FormatAuthorsTest(unittest.TestCase):
    def test_single_author_is_unchanged(self):
        self.assertEqual(format_authors("Kevin Roose"), "Kevin Roose")

    def test_two_authors_are_joined_with_ampersand(self):
        self.assertEqual(
            format_authors("Steven Levitsky, Daniel Ziblatt"),
            "Steven Levitsky & Daniel Ziblatt",
        )

    def test_three_or_more_authors_use_commas_then_ampersand(self):
        self.assertEqual(
            format_authors("Daniel Huttenlocher, Henry Kissinger, Eric Schmidt"),
            "Daniel Huttenlocher, Henry Kissinger & Eric Schmidt",
        )


class SlugifyTest(unittest.TestCase):
    def test_slug_is_lowercase_words_joined_by_hyphens(self):
        self.assertEqual(slugify("Why Read Moby-Dick?"), "why-read-moby-dick")

    def test_accents_are_folded_to_plain_letters(self):
        self.assertEqual(slugify("Ngũgĩ’s Decolonising"), "ngugis-decolonising")


class ValidIsbnTest(unittest.TestCase):
    def test_isbn_13_and_isbn_10_are_kept(self):
        self.assertEqual(valid_isbn("9781524762933"), "9781524762933")
        self.assertEqual(valid_isbn("080419011X"), "080419011X")

    def test_empty_or_non_isbn_values_are_dropped(self):
        self.assertIsNone(valid_isbn(""))
        self.assertIsNone(valid_isbn("sg-1234-abcd"))


class ReadsFromRowTest(unittest.TestCase):
    def test_finished_book_becomes_one_read(self):
        [read] = reads_from_row(storygraph_row())
        self.assertEqual(read.title, "How Democracies Die")
        self.assertEqual(read.author, "Steven Levitsky & Daniel Ziblatt")
        self.assertEqual(read.isbn, "9781524762933")
        self.assertEqual(read.finished, date(2026, 4, 14))
        self.assertFalse(read.reread)

    def test_only_finished_books_are_imported(self):
        self.assertEqual(reads_from_row(storygraph_row(**{"Read Status": "to-read"})), [])
        self.assertEqual(reads_from_row(storygraph_row(**{"Read Status": "did-not-finish"})), [])

    def test_every_read_after_the_first_is_a_reread(self):
        reads = reads_from_row(
            storygraph_row(**{"Dates Read": "2026/07/14-2026/07/17, 2024/03/30-2024/03/30"})
        )
        self.assertEqual([(r.finished.year, r.reread) for r in reads], [(2024, False), (2026, True)])

    def test_book_without_read_dates_finishes_on_the_date_it_was_added(self):
        # A Hunger Artist and Young Zaphod have no read dates; Peter chose the date added instead.
        [read] = reads_from_row(storygraph_row(**{"Dates Read": "", "Date Added": "2024/02/25"}))
        self.assertEqual(read.finished, date(2024, 2, 25))
        self.assertFalse(read.reread)

    def test_review_becomes_the_starting_note(self):
        [read] = reads_from_row(storygraph_row(Review="Norms do the real work."))
        self.assertEqual(read.note, "Norms do the real work.")



class ProblemsWithRowTest(unittest.TestCase):
    def test_finished_book_with_no_dates_at_all_is_flagged(self):
        self.assertTrue(problems_with_row(storygraph_row(**{"Dates Read": "", "Date Added": ""})))

    def test_book_with_only_a_date_added_is_not_flagged(self):
        self.assertEqual(problems_with_row(storygraph_row(**{"Dates Read": ""})), [])

    def test_normal_finished_book_has_no_problems(self):
        self.assertEqual(problems_with_row(storygraph_row()), [])

    def test_unfinished_books_are_never_flagged(self):
        self.assertEqual(problems_with_row(storygraph_row(**{"Read Status": "to-read", "Dates Read": ""})), [])


def a_read(**overrides):
    fields = dict(
        title="How Democracies Die",
        author="Steven Levitsky & Daniel Ziblatt",
        isbn="9781524762933",
        finished=date(2026, 4, 14),
        reread=False,
        note="",
    )
    fields.update(overrides)
    return Read(**fields)


def front_matter(path):
    _, toml_text, body = path.read_text().split("+++\n", 2)
    return tomllib.loads(toml_text), body


class WriteNewReadsTest(unittest.TestCase):
    def setUp(self):
        self.books_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_read_is_written_to_its_year_folder_in_the_book_format(self):
        write_new_reads([a_read(note="Norms do the real work.")], self.books_dir)

        fields, body = front_matter(self.books_dir / "2026" / "how-democracies-die.md")
        self.assertEqual(fields["title"], "How Democracies Die")
        self.assertEqual(fields["date"], date(2026, 4, 14))
        self.assertEqual(
            fields["extra"],
            {"author": "Steven Levitsky & Daniel Ziblatt", "isbn": "9781524762933", "reread": False},
        )
        self.assertEqual(body.strip(), "Norms do the real work.")

    def test_isbn_is_left_out_when_there_is_none(self):
        write_new_reads([a_read(isbn=None)], self.books_dir)
        fields, _ = front_matter(self.books_dir / "2026" / "how-democracies-die.md")
        self.assertNotIn("isbn", fields["extra"])

    def test_quotes_in_titles_survive(self):
        write_new_reads([a_read(title='The "Real" Story')], self.books_dir)
        fields, _ = front_matter(self.books_dir / "2026" / "the-real-story.md")
        self.assertEqual(fields["title"], 'The "Real" Story')

    def test_missing_year_folder_gets_a_year_page(self):
        write_new_reads([a_read(finished=date(2024, 3, 30))], self.books_dir)
        year_page = tomllib.loads((self.books_dir / "2024" / "_index.md").read_text().strip().strip("+"))
        self.assertEqual(year_page["title"], "2024")
        self.assertEqual(year_page["template"], "year.html")

    def test_existing_year_page_is_left_alone(self):
        (self.books_dir / "2026").mkdir()
        (self.books_dir / "2026" / "_index.md").write_text("hand-written")
        write_new_reads([a_read()], self.books_dir)
        self.assertEqual((self.books_dir / "2026" / "_index.md").read_text(), "hand-written")

    def test_running_again_writes_nothing_and_keeps_notes(self):
        write_new_reads([a_read()], self.books_dir)
        book = self.books_dir / "2026" / "how-democracies-die.md"
        book.write_text(book.read_text() + "My own note.\n")

        written = write_new_reads([a_read()], self.books_dir)

        self.assertEqual(written, [])
        self.assertIn("My own note.", book.read_text())

    def test_read_already_on_the_river_under_another_file_name_is_skipped(self):
        write_new_reads([a_read()], self.books_dir)
        (self.books_dir / "2026" / "how-democracies-die.md").rename(self.books_dir / "2026" / "hdd.md")

        self.assertEqual(write_new_reads([a_read()], self.books_dir), [])

    def test_same_book_twice_in_one_year_gets_a_second_file(self):
        first = a_read(finished=date(2026, 2, 1))
        second = a_read(finished=date(2026, 9, 1), reread=True)

        write_new_reads([first, second], self.books_dir)

        fields, _ = front_matter(self.books_dir / "2026" / "how-democracies-die-2.md")
        self.assertEqual(fields["date"], date(2026, 9, 1))
        self.assertTrue(fields["extra"]["reread"])


if __name__ == "__main__":
    unittest.main()
