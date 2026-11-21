"""Unit tests for application configuration."""

import os
import unittest

from config import Config


class TestConfig(unittest.TestCase):
    """Test suite for Config class."""

    def test_default_config_attributes(self):
        """Ensure critical config attributes exist."""
        self.assertTrue(hasattr(Config, "SECRET_KEY"))
        self.assertTrue(hasattr(Config, "WAQI_BASE_URL"))
        self.assertTrue(hasattr(Config, "WAQI_API_TOKEN"))
        self.assertTrue(hasattr(Config, "GEMINI_API_KEY"))
        self.assertEqual(Config.WAQI_BASE_URL, "https://api.waqi.info")


if __name__ == "__main__":
    unittest.main()
