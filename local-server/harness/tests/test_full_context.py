import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from presence_acore.full_context import read_full_context, DIRECTORY


class FullContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.directory = self.data / DIRECTORY
        self.directory.mkdir()
        self.revision = "a"*32
        self.body = json.dumps({"input": "personality♥"*1000, "images": ["data:abc"]}, ensure_ascii=False).encode()
        self.sha = hashlib.sha256(self.body).hexdigest()
        self.meta = {"schema": "native-full-request/v1", "revision": self.revision, "character": "Vesper",
                     "lane": "social", "available": True, "body_sha256": self.sha, "body_bytes": len(self.body),
                     "encoding": "utf-8", "authentication_headers_captured": False,
                     "prepared_at": "2026-10-31T23:00:00Z", "capture_id": "b"*32}
        (self.directory / (self.revision+".body.json")).write_bytes(self.body)
        self.write_meta()
        (self.directory / "latest-social.json").write_text(json.dumps(self.meta))

    def write_meta(self):
        (self.directory / (self.revision+".meta.json")).write_text(json.dumps(self.meta))

    def read(self, **kwargs):
        return read_full_context(self.data, lane="social", **kwargs)

    def test_all_pages_reassemble_identical_request(self):
        page = self.read(limit_bytes=19)
        raw = b""
        while True:
            self.assertTrue(page["available"], page)
            raw += page["text"].encode()
            if page["complete"]:
                break
            page = self.read(revision=page["revision"], sha256=page["sha256"],
                             offset=page["next_offset"], limit_bytes=19)
        self.assertEqual(raw, self.body)

    def test_pin_ignores_rotation_of_latest(self):
        (self.directory / "latest-social.json").unlink()
        self.assertTrue(self.read(revision=self.revision, sha256=self.sha)["available"])

    def test_hash_tampering_not_returned(self):
        (self.directory / (self.revision+".body.json")).write_bytes(b"{}");
        self.assertEqual(self.read()["error"]["code"], "capture_body_mismatch")

    def test_cross_lane_or_character_not_returned(self):
        self.meta["character"] = "SomeoneElse"; self.write_meta()
        self.assertFalse(self.read()["available"])

    def test_newer_filtered_capture_cannot_be_misreported_as_exact(self):
        (self.data / "runtime-game-player-context-social.json").write_text(json.dumps({
            "character": "Vesper", "lane": "social", "capture_id": "c"*32, "prepared_at": "2026-11-01T00:00:00Z"}))
        self.assertEqual(self.read()["error"]["code"], "latest_full_capture_stale")

    def test_large_preview_does_not_hide_stale_capture(self):
        (self.data / "runtime-game-player-context-social.json").write_text(json.dumps({
            "character": "Vesper", "lane": "social", "capture_id": "c"*32,
            "prepared_at": "2026-11-01T00:00:00Z", "context": "x"*100000}))
        self.assertEqual(self.read()["error"]["code"], "latest_full_capture_stale")

    def test_invalid_offsets_and_arguments_are_explicit(self):
        for kwargs in ({"offset": 2}, {"revision": "../bad", "sha256": self.sha}, {"revision": 123},
                       {"limit_bytes": True}, {"revision": self.revision, "sha256": self.sha, "offset": len(self.body)+1}):
            self.assertFalse(self.read(**kwargs)["available"])

    def test_missing_historical_body_is_not_reconstructed(self):
        (self.directory / (self.revision+".body.json")).unlink()
        self.assertEqual(self.read(revision=self.revision, sha256=self.sha)["error"]["code"], "revision_unavailable")


if __name__ == "__main__": unittest.main()
