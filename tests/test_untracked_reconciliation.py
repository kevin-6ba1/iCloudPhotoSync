import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_DIR = os.path.join(REPO_ROOT, "spk", "icloudphotosync", "src", "lib")
VENDOR_DIR = os.path.join(LIB_DIR, "vendor")
sys.path.insert(0, LIB_DIR)
sys.path.insert(0, VENDOR_DIR)

try:
    import fcntl  # noqa: F401
except ImportError:
    import types
    _fake_fcntl = types.ModuleType("fcntl")
    _fake_fcntl.LOCK_EX = 2
    _fake_fcntl.LOCK_UN = 8
    _fake_fcntl.LOCK_NB = 4
    _fake_fcntl.flock = lambda *a, **k: None
    sys.modules["fcntl"] = _fake_fcntl

import sync_engine  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self._content = content

    def iter_content(self, chunk_size):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i:i + chunk_size]

    def close(self):
        pass


class _FakeSession:
    def __init__(self, blob, honor_range=True):
        self.blob = blob
        self.honor_range = honor_range
        self.requests = []

    def get(self, url, headers=None, timeout=None, stream=None):
        self.requests.append(headers or {})
        if not self.honor_range or not headers or "Range" not in headers:
            return _FakeResponse(200, self.blob)
        spec = headers["Range"].split("=", 1)[1]
        start, end = spec.split("-")
        start, end = int(start), int(end)
        return _FakeResponse(206, self.blob[start:end + 1])


class _ExpiredSession:
    def get(self, url, headers=None, timeout=None, stream=None):
        return _FakeResponse(410, b"")


def _write_temp(content):
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


class VerifyUntrackedMatchTest(unittest.TestCase):
    def test_small_file_matching_content_verifies(self):
        blob = b"x" * 1000
        path = _write_temp(blob)
        try:
            session = _FakeSession(blob)
            result = sync_engine._verify_untracked_match(
                "http://example.invalid/photo.jpg", path, len(blob), session=session)
            self.assertTrue(result)
        finally:
            os.remove(path)

    def test_small_file_same_size_different_content_is_rejected(self):
        local_blob = b"a" * 1000
        remote_blob = b"b" * 1000
        path = _write_temp(local_blob)
        try:
            session = _FakeSession(remote_blob)
            result = sync_engine._verify_untracked_match(
                "http://example.invalid/photo.jpg", path, len(local_blob), session=session)
            self.assertFalse(result)
        finally:
            os.remove(path)

    def test_large_file_matching_head_and_tail_verifies(self):
        size = sync_engine._VERIFY_CHUNK * 5 + 123
        blob = os.urandom(size)
        path = _write_temp(blob)
        try:
            session = _FakeSession(blob, honor_range=True)
            result = sync_engine._verify_untracked_match(
                "http://example.invalid/photo.jpg", path, size, session=session)
            self.assertTrue(result)
            for req_headers in session.requests:
                self.assertIn("Range", req_headers)
        finally:
            os.remove(path)

    def test_large_file_mismatched_tail_is_rejected(self):
        size = sync_engine._VERIFY_CHUNK * 5 + 123
        local_blob = bytearray(os.urandom(size))
        remote_blob = bytes(local_blob)
        remote_blob = remote_blob[:-10] + b"\x00" * 10
        path = _write_temp(bytes(local_blob))
        try:
            session = _FakeSession(remote_blob, honor_range=True)
            result = sync_engine._verify_untracked_match(
                "http://example.invalid/photo.jpg", path, size, session=session)
            self.assertFalse(result)
        finally:
            os.remove(path)

    def test_large_file_verifies_even_when_cdn_ignores_range(self):
        size = sync_engine._VERIFY_CHUNK * 3 + 7
        blob = os.urandom(size)
        path = _write_temp(blob)
        try:
            session = _FakeSession(blob, honor_range=False)
            result = sync_engine._verify_untracked_match(
                "http://example.invalid/photo.jpg", path, size, session=session)
            self.assertTrue(result)
        finally:
            os.remove(path)

    def test_large_file_mismatch_detected_even_when_cdn_ignores_range(self):
        size = sync_engine._VERIFY_CHUNK * 3 + 7
        local_blob = os.urandom(size)
        remote_blob = os.urandom(size)
        path = _write_temp(local_blob)
        try:
            session = _FakeSession(remote_blob, honor_range=False)
            result = sync_engine._verify_untracked_match(
                "http://example.invalid/photo.jpg", path, size, session=session)
            self.assertFalse(result)
        finally:
            os.remove(path)


class FetchCappedTest(unittest.TestCase):
    def test_runaway_tail_stream_is_aborted_at_hard_cap(self):
        class _RunawayResponse:
            status_code = 200
            chunks_yielded = 0

            def iter_content(self, chunk_size):
                while True:
                    self.chunks_yielded += 1
                    yield os.urandom(chunk_size)

            def close(self):
                pass

        runaway = _RunawayResponse()

        class _RunawaySession:
            def get(self, url, headers=None, timeout=None, stream=None):
                return runaway

        hard_cap = sync_engine._VERIFY_CHUNK * 3
        result = sync_engine._fetch_capped(
            _RunawaySession(), "http://example.invalid/photo.jpg", None,
            sync_engine._VERIFY_CHUNK, from_end=True, hard_cap=hard_cap)
        self.assertIsNone(result)
        self.assertLessEqual(runaway.chunks_yielded, (hard_cap // sync_engine._VERIFY_CHUNK) + 2)


class VerifyUntrackedMatchExpiryTest(unittest.TestCase):
    def test_expired_url_is_rejected(self):
        blob = b"x" * 1000
        path = _write_temp(blob)
        try:
            result = sync_engine._verify_untracked_match(
                "http://example.invalid/photo.jpg", path, len(blob), session=_ExpiredSession())
            self.assertFalse(result)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
