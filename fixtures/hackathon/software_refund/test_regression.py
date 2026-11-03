import unittest

from refund import refund_total


class RefundRegressionTest(unittest.TestCase):
    def test_negative_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            refund_total(25, -1)


if __name__ == "__main__":
    unittest.main()
