"""Gate 1 Spec Lock & Packaging Tests."""

import os
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSpecLock(unittest.TestCase):
    def test_required_spec_files_exist(self):
        for f in ["pyproject.toml", "README.md", "LICENSE", "CHANGELOG.md", ".gitignore"]:
            path = os.path.join(ROOT_DIR, f)
            self.assertTrue(os.path.isfile(path), f"Missing required file: {f}")
            self.assertGreater(os.path.getsize(path), 0, f"File is empty: {f}")

    def test_changelog_has_unreleased_and_v010(self):
        changelog_path = os.path.join(ROOT_DIR, "CHANGELOG.md")
        with open(changelog_path, "r") as f:
            content = f.read()
        self.assertIn("## [Unreleased]", content)
        self.assertIn("## [0.1.0]", content)

    def test_license_is_apache_and_authored_by_zesun(self):
        lic_path = os.path.join(ROOT_DIR, "LICENSE")
        with open(lic_path, "r") as f:
            content = f.read()
        self.assertIn("Apache License", content)
        self.assertIn("Md Zesun Ahmed Mia", content)


if __name__ == "__main__":
    unittest.main()
