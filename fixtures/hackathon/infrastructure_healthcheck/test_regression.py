import unittest

from deployment import SERVICE


class DeploymentRegressionTest(unittest.TestCase):
    def test_healthcheck_uses_live_endpoint(self):
        self.assertEqual(SERVICE["health_path"], "/healthz")


if __name__ == "__main__":
    unittest.main()
