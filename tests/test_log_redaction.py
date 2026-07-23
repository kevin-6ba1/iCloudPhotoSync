import logging
import os
import sys
import unittest

LIB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "spk", "icloudphotosync", "src", "lib",
)
sys.path.insert(0, LIB_DIR)

import log_redaction  # noqa: E402  (import after sys.path manipulation)


class MaskEmailTest(unittest.TestCase):
    def test_masks_local_part_keeps_domain(self):
        self.assertEqual(log_redaction.mask_email("someone@example.com"), "s***@example.com")

    def test_single_char_local_part(self):
        self.assertEqual(log_redaction.mask_email("a@example.com"), "a***@example.com")

    def test_empty_string_is_redacted(self):
        self.assertEqual(log_redaction.mask_email(""), "[REDACTED]")

    def test_no_at_sign_is_redacted(self):
        self.assertEqual(log_redaction.mask_email("not-an-email"), "[REDACTED]")

    def test_none_is_redacted(self):
        self.assertEqual(log_redaction.mask_email(None), "[REDACTED]")


class RedactTextTest(unittest.TestCase):
    def test_redacts_embedded_email(self):
        text = "Two-step authentication required for account: someone@example.com"
        self.assertEqual(
            log_redaction.redact_text(text),
            "Two-step authentication required for account: s***@example.com",
        )

    def test_redacts_session_token_json_value(self):
        text = '{"sessionToken": "abc123XYZ", "other": "value"}'
        result = log_redaction.redact_text(text)
        self.assertNotIn("abc123XYZ", result)
        self.assertIn('"sessionToken": "[REDACTED]"', result)
        self.assertIn('"other": "value"', result)

    def test_redacts_password_json_value(self):
        text = '{"password": "hunter2"}'
        result = log_redaction.redact_text(text)
        self.assertNotIn("hunter2", result)
        self.assertIn('"password": "[REDACTED]"', result)

    def test_redacts_cookie_header_line(self):
        text = "Cookie: X-APPLE-WEBAUTH-TOKEN=abcdef123"
        self.assertEqual(log_redaction.redact_text(text), "Cookie: [REDACTED]")

    def test_redacts_authorization_header_line(self):
        text = "Authorization: Bearer abcdef"
        self.assertEqual(log_redaction.redact_text(text), "Authorization: [REDACTED]")

    def test_redacts_apple_session_header_line(self):
        text = "X-Apple-ID-Session-Id: 1234567890abcdef"
        self.assertEqual(log_redaction.redact_text(text), "X-Apple-ID-Session-Id: [REDACTED]")

    def test_leaves_benign_text_unchanged(self):
        text = "Failed to initiate SRP authentication."
        self.assertEqual(log_redaction.redact_text(text), text)

    def test_empty_and_none_pass_through(self):
        self.assertEqual(log_redaction.redact_text(""), "")
        self.assertIsNone(log_redaction.redact_text(None))


class SafeLogExceptionTest(unittest.TestCase):
    def test_redacts_traceback_and_uses_masked_args(self):
        logger = logging.getLogger("test.log_redaction.safe_log_exception")
        try:
            raise Exception('someone@example.com leaked, "sessionToken": "abc123XYZ"')
        except Exception:
            with self.assertLogs(logger, level="ERROR") as captured:
                log_redaction.safe_log_exception(
                    logger,
                    logging.ERROR,
                    "Login error for %s",
                    log_redaction.mask_email("someone@example.com"),
                )
        output = "\n".join(captured.output)
        self.assertNotIn("someone@example.com", output)
        self.assertNotIn("abc123XYZ", output)
        self.assertIn("[REDACTED]", output)
        self.assertIn("s***@example.com", output)

    def test_logs_at_requested_level(self):
        logger = logging.getLogger("test.log_redaction.safe_log_exception.level")
        try:
            raise Exception("boom")
        except Exception:
            with self.assertLogs(logger, level="WARNING") as captured:
                log_redaction.safe_log_exception(logger, logging.WARNING, "Session restore failed")
        self.assertTrue(captured.output[0].startswith("WARNING:"))


if __name__ == "__main__":
    unittest.main()
