import re
import unittest


def strip(t):
    return re.sub(r"<[^>]*>", "", t).strip()


def pick(items, text):
    return [i for i in items if strip(i) == text]


class SubpagePick(unittest.TestCase):
    def test_one(self):
        self.assertEqual(pick(["Overview", "Eligibility"], "Eligibility"), ["Eligibility"])

    def test_zero(self):
        self.assertEqual(pick(["Overview"], "Eligibility"), [])

    def test_two(self):
        self.assertEqual(len(pick(["Eligibility", "Eligibility"], "Eligibility")), 2)

    def test_tags(self):
        raw = '<color=#FFFFFF><link="0">Eligibility</link></color>'
        self.assertEqual(pick([raw], "Eligibility"), [raw])


if __name__ == "__main__":
    unittest.main()
