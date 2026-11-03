import unittest
from decimal import Decimal

from aggregate import total_revenue


class RevenueBehaviorTest(unittest.TestCase):
    def test_fractional_values_remain_exact(self):
        result = total_revenue([Decimal("0.1"), Decimal("0.2")])
        self.assertEqual(result, Decimal("0.3"))
        self.assertIsInstance(result, Decimal)

    def test_empty_input_is_zero(self):
        self.assertEqual(total_revenue([]), 0)


if __name__ == "__main__":
    unittest.main()
