import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENU_STRINGS = os.path.join(REPO_ROOT, "spk", "icloudphotosync", "src", "app", "texts", "enu", "strings")
GER_STRINGS = os.path.join(REPO_ROOT, "spk", "icloudphotosync", "src", "app", "texts", "ger", "strings")

REQUIRED_WIZARD_KEYS = ("title_folder", "instruction_folder", "btn_finish")


def _keys_in_section(path, section):
    keys = set()
    current = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^\[(\w+)\]$", line)
            if m:
                current = m.group(1)
                continue
            if current == section:
                key = line.split("=", 1)[0].strip()
                if key:
                    keys.add(key)
    return keys


class WizardFolderStepStringsTest(unittest.TestCase):
    def test_enu_has_required_wizard_keys(self):
        keys = _keys_in_section(ENU_STRINGS, "wizard")
        for key in REQUIRED_WIZARD_KEYS:
            self.assertIn(key, keys, "enu strings missing wizard:%s" % key)

    def test_ger_has_required_wizard_keys(self):
        keys = _keys_in_section(GER_STRINGS, "wizard")
        for key in REQUIRED_WIZARD_KEYS:
            self.assertIn(key, keys, "ger strings missing wizard:%s" % key)


if __name__ == "__main__":
    unittest.main()
