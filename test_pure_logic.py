import unittest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "manhwa_reader"))

from manhwa_reader.reader import parse_chapter_filter, normalize_search_text, matches_search_query


class TestPureLogicFunctions(unittest.TestCase):
    def test_parse_chapter_filter_single(self):
        self.assertEqual(parse_chapter_filter("5"), {5})
        self.assertEqual(parse_chapter_filter(" 42 "), {42})

    def test_parse_chapter_filter_range_dash(self):
        self.assertEqual(parse_chapter_filter("1-5"), {1, 2, 3, 4, 5})
        self.assertEqual(parse_chapter_filter("5-1"), {1, 2, 3, 4, 5})
        self.assertEqual(parse_chapter_filter("10 - 12"), {10, 11, 12})

    def test_parse_chapter_filter_range_to(self):
        self.assertEqual(parse_chapter_filter("3 to 5"), {3, 4, 5})

    def test_parse_chapter_filter_multiple_spaces_commas(self):
        self.assertEqual(parse_chapter_filter("1 2 3"), {1, 2, 3})
        self.assertEqual(parse_chapter_filter("1, 5, 9"), {1, 5, 9})
        self.assertEqual(parse_chapter_filter("10,20,30"), {10, 20, 30})

    def test_parse_chapter_filter_empty(self):
        self.assertIsNone(parse_chapter_filter(""))
        self.assertIsNone(parse_chapter_filter("   "))
        self.assertIsNone(parse_chapter_filter("abc"))

    def test_normalize_search_text(self):
        self.assertEqual(normalize_search_text("Solo Leveling!"), "solo leveling")
        self.assertEqual(normalize_search_text("Tower of God (Season 2)"), "tower of god season 2")
        self.assertEqual(normalize_search_text("Підняття — рівня..."), "підняття рівня")
        self.assertEqual(normalize_search_text(""), "")

    def test_matches_search_query(self):
        title = "Solo Leveling"
        aliases = ["Підняття рівня наодинці", "I Alone Level Up"]
        tags = ["action", "fantasy"]

        self.assertTrue(matches_search_query("solo", title, aliases, tags))
        self.assertTrue(matches_search_query("підняття", title, aliases, tags))
        self.assertTrue(matches_search_query("leveling fantasy", title, aliases, tags))
        self.assertFalse(matches_search_query("romance", title, aliases, tags))
        self.assertTrue(matches_search_query("", title, aliases, tags))


if __name__ == "__main__":
    unittest.main()
