import unittest
from dao import auth_user

class TestLogin(unittest.TestCase):
    def test_1(self):
        self.assertTrue(auth_user("admin", 123))

    def test_2(self):
        self.assertTrue(auth_user("admin", 123))


if __name__ == '__main__':
    unittest.main()
