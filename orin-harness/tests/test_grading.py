"""Deterministic grading: letters, aliases, words, and non-answers."""

from __future__ import annotations

import unittest

from magneto_harness.grading import grade


class GradingTests(unittest.TestCase):
    def test_exact_letter(self):
        self.assertEqual(grade("c", "c"), ("exact", "correct"))

    def test_spoken_letter_alias(self):
        self.assertEqual(grade("see", "c"), ("exact", "correct"))
        self.assertEqual(grade("bee", "b"), ("exact", "correct"))

    def test_letter_inside_phrase_is_partial(self):
        self.assertEqual(grade("I think it is a", "a"), ("partial", "correct"))

    def test_letter_substring_is_not_a_match(self):
        # "cat" must not match the letter c by substring.
        self.assertEqual(grade("cat", "c"), ("none", "incorrect"))

    def test_word_exact_and_inside_phrase(self):
        self.assertEqual(grade("cab", "cab"), ("exact", "correct"))
        self.assertEqual(grade("the cab again", "cab"), ("partial", "correct"))

    def test_wrong_and_empty(self):
        self.assertEqual(grade("z", "c"), ("none", "incorrect"))
        self.assertEqual(grade("", "c"), ("none", "unrecognized"))
        self.assertEqual(grade(None, "c"), ("none", "unrecognized"))

    def test_case_and_punctuation_insensitive(self):
        self.assertEqual(grade("C!", "c"), ("exact", "correct"))


if __name__ == "__main__":
    unittest.main()
