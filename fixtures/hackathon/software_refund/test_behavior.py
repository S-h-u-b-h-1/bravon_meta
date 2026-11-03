import unittest

from refund import refund_total


class RefundBehaviorTest(unittest.TestCase):
    def test_positive_quantity_still_works(self):
        self.assertEqual(refund_total(25, 2), 50)

    def test_all_negative_quantities_are_rejected(self):
        with self.assertRaises(ValueError):
            refund_total(25, -2)


if __name__ == "__main__":
    unittest.main()
