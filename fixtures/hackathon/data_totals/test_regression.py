import unittest

from aggregate import total_revenue


class RevenueRegressionTest(unittest.TestCase):
    def test_final_row_is_included(self):
        self.assertEqual(total_revenue([10, 20]), 30)


if __name__ == "__main__":
    unittest.main()
