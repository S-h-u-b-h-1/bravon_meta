import unittest

from deployment import SERVICE


class DeploymentBehaviorTest(unittest.TestCase):
    def test_container_root_is_read_only(self):
        self.assertIs(SERVICE["read_only_root"], True)

    def test_admin_listener_is_loopback_only(self):
        self.assertEqual(SERVICE["admin_bind"], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
