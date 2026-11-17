import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from releasetoalt import core


class ApplyFilterTests(unittest.TestCase):
    @patch("releasetoalt.core.subprocess.run")
    def test_uses_active_python_instead_of_git_subcommand(self, run):
        repo_path = Path("/unused/repository")

        core.apply_filter(repo_path, ["old@example.com"], "Alt", "alt@example.com")

        args, kwargs = run.call_args
        self.assertEqual(
            args[0][:5],
            [sys.executable, "-m", "git_filter_repo", "--force", "--commit-callback"],
        )
        self.assertEqual(kwargs["cwd"], repo_path)
        self.assertTrue(kwargs["check"])
        self.assertTrue(kwargs["capture_output"])

    @patch("releasetoalt.core.subprocess.run")
    def test_empty_blacklist_does_not_run_filter(self, run):
        core.apply_filter(Path("/unused/repository"), [], "Alt", "alt@example.com")

        run.assert_not_called()

    @patch("releasetoalt.core.subprocess.run")
    def test_filter_failure_is_reported_as_git_error(self, run):
        run.side_effect = subprocess.CalledProcessError(
            1, ["filter"], stderr="filter failed"
        )

        with self.assertRaisesRegex(core.GitError, "filter failed"):
            core.apply_filter(
                Path("/unused/repository"), ["old@example.com"], "Alt", "alt@example.com"
            )

    def test_rewrites_selected_identities_and_preserves_whitelisted_ones(self):
        with tempfile.TemporaryDirectory() as directory:
            repo_path = Path(directory)
            core.run_git(["init", "--quiet"], cwd=repo_path)
            for name, email in [
                ("Original", "old@example.com"),
                ("Keep", "keep@example.com"),
            ]:
                env = dict(
                    os.environ,
                    GIT_AUTHOR_NAME=name,
                    GIT_AUTHOR_EMAIL=email,
                    GIT_COMMITTER_NAME=name,
                    GIT_COMMITTER_EMAIL=email,
                )
                subprocess.run(
                    ["git", "-c", "commit.gpgsign=false", "commit", "--allow-empty",
                     "--quiet", "-m", name],
                    cwd=repo_path,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )

            core.apply_filter(repo_path, ["old@example.com"], "Alt", "alt@example.com")

            history = core.run_git(
                ["log", "--reverse", "--format=%an|%ae|%cn|%ce"], cwd=repo_path
            ).stdout.splitlines()
            self.assertEqual(history, [
                "Alt|alt@example.com|Alt|alt@example.com",
                "Keep|keep@example.com|Keep|keep@example.com",
            ])
            self.assertTrue(core.verify_filter(repo_path, ["old@example.com"]))


if __name__ == "__main__":
    unittest.main()
