import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_DIR = os.path.join(REPO_ROOT, "spk", "icloudphotosync", "src", "lib")
VENDOR_DIR = os.path.join(LIB_DIR, "vendor")


class VendorImportTest(unittest.TestCase):
    def test_scheduler_startup_import_chain(self):
        """Mirrors service-setup.sh's service_prestart() sanity check --
        the exact import chain DSM runs before starting the scheduler
        daemon (`import config_manager, notifier, sync_engine`). A missing
        or incomplete vendored dependency here means the package fails to
        start with nothing more specific than DSM's generic "Failed to
        start" -- the only place the real error shows up is
        startup-error.log, so this must be caught before it ships.
        """
        script = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "sys.path.insert(0, %r)\n"
            "import config_manager, notifier, sync_engine\n"
        ) % (LIB_DIR, VENDOR_DIR)
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            "Scheduler startup import chain failed:\n%s" % result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
