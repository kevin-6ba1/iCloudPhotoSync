import os
import re
import subprocess
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_SH = os.path.join(REPO_ROOT, "build.sh")
MAKEFILE = os.path.join(REPO_ROOT, "spk", "icloudphotosync", "Makefile")
VERSION_FILE = os.path.join(REPO_ROOT, "spk", "icloudphotosync", "VERSION")

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


class VersionConsistencyTest(unittest.TestCase):
    def test_version_file_exists_and_is_semver(self):
        with open(VERSION_FILE) as f:
            version = f.read().strip()
        self.assertRegex(version, SEMVER_RE)

    def test_build_sh_has_no_hardcoded_pkg_ver_literal(self):
        with open(BUILD_SH) as f:
            text = f.read()
        match = re.search(r'^PKG_VER="(\d+\.\d+\.\d+)"', text, re.MULTILINE)
        self.assertIsNone(
            match,
            "build.sh hardcodes PKG_VER instead of reading spk/icloudphotosync/VERSION",
        )

    def test_makefile_has_no_hardcoded_spk_vers_literal(self):
        with open(MAKEFILE) as f:
            text = f.read()
        match = re.search(r"^SPK_VERS\s*=\s*(\d+\.\d+\.\d+)\s*$", text, re.MULTILINE)
        self.assertIsNone(
            match,
            "Makefile hardcodes SPK_VERS instead of reading spk/icloudphotosync/VERSION",
        )

    def test_build_sh_and_version_file_resolve_to_same_version(self):
        with open(BUILD_SH) as f:
            lines = f.readlines()
        pkg_ver_line = next(l for l in lines if l.startswith("PKG_VER=")).rstrip('\n')

        result = subprocess.run(
            ["bash", "-c", f'cd "{REPO_ROOT}" && {pkg_ver_line} && echo "$PKG_VER"'],
            capture_output=True,
            text=True,
            check=True,
        )
        resolved = result.stdout.strip()

        with open(VERSION_FILE) as f:
            expected = f.read().strip()

        self.assertEqual(resolved, expected)

    def test_makefile_and_version_file_resolve_to_same_version(self):
        with open(MAKEFILE) as f:
            lines = f.readlines()
        spk_vers_line = next(l for l in lines if l.startswith("SPK_VERS"))

        pkg_dir = os.path.dirname(MAKEFILE)
        probe_name = ".test_version_probe.mk"
        probe_path = os.path.join(pkg_dir, probe_name)
        with open(probe_path, "w") as f:
            f.write(spk_vers_line)
            f.write("probe:\n\t@echo $(SPK_VERS)\n")
        try:
            result = subprocess.run(
                ["make", "--no-print-directory", "-C", pkg_dir, "-f", probe_name, "probe"],
                capture_output=True,
                text=True,
                check=True,
            )
        finally:
            os.remove(probe_path)
        resolved = result.stdout.strip()

        with open(VERSION_FILE) as f:
            expected = f.read().strip()

        self.assertEqual(resolved, expected)


if __name__ == "__main__":
    unittest.main()
