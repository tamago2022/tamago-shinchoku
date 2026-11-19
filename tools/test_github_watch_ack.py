#!/usr/bin/env python3
"""Offline tests: no GitHub API requests and no queue mutations."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch

MODULE = pathlib.Path(__file__).with_name("github_watch.py")
spec = importlib.util.spec_from_file_location("github_watch", MODULE)
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class AckTests(unittest.TestCase):
    def test_queue_number(self):
        self.assertEqual(watch._extract_queue_n("965番として発車待ちに追加しました（P2）"), "965")
        self.assertEqual(watch._extract_queue_n("done but no ticket"), "unknown")
        self.assertEqual(watch._extract_queue_n(None), "unknown")

    def test_ack_marker_fields_and_skip(self):
        body = watch._ack_body("comment", 5804079920,
            "156343番として発車待ちに追加しました",
            accepted_at="2026-10-22T19:00:00+09:00")
        self.assertTrue(body.startswith("<!-- tamago-factory -->\naccepted\n"))
        self.assertIn("accepted_at: 2026-10-22T19:00:00+09:00", body)
        self.assertIn("local_queue_n: 156343", body)
        self.assertIn("source: comment:5804079920", body)
        self.assertTrue(watch._skip_body(body))

    def test_unknown_and_issue(self):
        body = watch._ack_body("issue", 437, "bad", accepted_at="2026-10-22T19:00:00+09:00")
        self.assertIn("local_queue_n: unknown", body)
        self.assertIn("source: issue:437", body)

    def test_fold_existing_route(self):
        body = watch._ack_body("comment", 17, "123番として発車待ちに追加しました",
                               accepted_at="2026-10-22T19:00:00+09:00", route="fold_existing")
        self.assertIn("route: fold_existing", body)
        self.assertIn("local_queue_n: 123", body)

    def test_post_failure_never_raises(self):
        with patch.object(watch.urllib.request, "urlopen", side_effect=OSError("offline")):
            with patch.object(watch, "log"):
                self.assertFalse(watch.api_post_issue_comment("owner/repo", 437, "fake", "ACK"))

    def test_send_ack_failure_does_not_raise(self):
        with patch.object(watch, "api_post_issue_comment", return_value=False):
            with patch.object(watch, "log"):
                watch._send_ack("owner/repo", 437, "fake", "issue", 437, "965番として発車待ちに追加しました")


if __name__ == "__main__":
    unittest.main()
