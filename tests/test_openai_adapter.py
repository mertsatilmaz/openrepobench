from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from openrepobench.adapters.openai_patch_agent import (
    apply_patch_block,
    build_prompt,
    normalize_patch,
    parse_patch_response,
    read_workspace_snapshot,
    run_adapter,
)


class FakeResponses:
    def __init__(self) -> None:
        self.params = None

    def create(self, **params):
        self.params = params
        return type(
            "FakeResponse",
            (),
            {
                "output_text": json.dumps(
                    {
                        "patch": "diff --git a/example.py b/example.py\n--- a/example.py\n+++ b/example.py\n@@ -1 +1 @@\n-bad\n+good\n",
                        "notes": "Fix example.",
                    }
                ),
                "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            },
        )()


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


class ApplyPatchFakeResponses:
    def __init__(self) -> None:
        self.params = None

    def create(self, **params):
        self.params = params
        return type(
            "FakeResponse",
            (),
            {
                "output_text": json.dumps(
                    {
                        "patch": (
                            "*** Begin Patch\n"
                            "*** Update File: calculator.py\n"
                            "@@\n"
                            " def add(a, b):\n"
                            "-    return a - b\n"
                            "+    return a + b\n"
                            "*** End Patch\n"
                        ),
                        "notes": "Fix add.",
                    }
                ),
                "usage": {"total_tokens": 30},
            },
        )()


class ApplyPatchFakeClient:
    def __init__(self) -> None:
        self.responses = ApplyPatchFakeResponses()


class OpenAIAdapterTests(unittest.TestCase):
    def test_parse_patch_response_accepts_json(self) -> None:
        parsed = parse_patch_response('{"patch": "diff --git a/x b/x\\n", "notes": "ok"}')

        self.assertEqual(parsed["patch"], "diff --git a/x b/x\n")
        self.assertEqual(parsed["notes"], "ok")

    def test_snapshot_reads_text_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "example.py").write_text("print('hi')\n", encoding="utf-8")
            (workspace / "binary.bin").write_bytes(b"\x00\x01")

            snapshot = read_workspace_snapshot(workspace)

        self.assertIn("example.py", snapshot.file_tree)
        self.assertEqual(snapshot.file_contents["example.py"], "print('hi')\n")
        self.assertNotIn("binary.bin", snapshot.file_contents)

    def test_build_prompt_contains_task_and_files(self) -> None:
        snapshot = read_workspace_snapshot(Path(__file__).resolve().parents[1] / "tasks" / "public" / "python" / "demo_bugfix" / "repo")

        prompt = build_prompt("Fix add.", snapshot)

        self.assertIn("Fix add.", prompt)
        self.assertIn("calculator.py", prompt)
        self.assertIn("Return only a git-apply-compatible unified diff", prompt)

    def test_run_adapter_writes_patch_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            output_dir = root / "output"
            workspace.mkdir()
            output_dir.mkdir()
            (workspace / "example.py").write_text("bad\n", encoding="utf-8")
            prompt_file = root / "prompt.md"
            prompt_file.write_text("Fix example.py", encoding="utf-8")
            patch_path = output_dir / "agent.patch"
            client = FakeClient()

            exit_code = run_adapter(
                workspace=workspace,
                prompt_file=prompt_file,
                patch_path=patch_path,
                output_dir=output_dir,
                model="gpt-test",
                max_file_bytes=10000,
                max_total_bytes=10000,
                temperature=None,
                client=client,
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("+good", patch_path.read_text(encoding="utf-8"))
            self.assertEqual(client.responses.params["model"], "gpt-test")
            self.assertEqual(client.responses.params["text"]["format"]["type"], "json_schema")
            self.assertTrue((output_dir / "openai_usage.json").exists())

    def test_apply_patch_block_updates_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            target = workspace / "calculator.py"
            target.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
            apply_patch_block(
                workspace,
                "*** Begin Patch\n"
                "*** Update File: calculator.py\n"
                "@@\n"
                " def add(a, b):\n"
                "-    return a - b\n"
                "+    return a + b\n"
                "*** End Patch\n",
            )

            self.assertEqual(target.read_text(encoding="utf-8"), "def add(a, b):\n    return a + b\n")

    def test_normalize_patch_converts_apply_patch_block_to_git_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            subprocess = __import__("subprocess")
            (workspace / "calculator.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=workspace, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, check=True)
            subprocess.run(["git", "add", "."], cwd=workspace, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=workspace, check=True, capture_output=True)

            patch, patch_format = normalize_patch(
                workspace,
                "*** Begin Patch\n"
                "*** Update File: calculator.py\n"
                "@@\n"
                " def add(a, b):\n"
                "-    return a - b\n"
                "+    return a + b\n"
                "*** End Patch\n",
            )

        self.assertEqual(patch_format, "converted_apply_patch_block")
        self.assertIn("diff --git a/calculator.py b/calculator.py", patch)
        self.assertIn("+    return a + b", patch)

    def test_run_adapter_converts_apply_patch_block_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            output_dir = root / "output"
            workspace.mkdir()
            output_dir.mkdir()
            subprocess = __import__("subprocess")
            (workspace / "calculator.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=workspace, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, check=True)
            subprocess.run(["git", "add", "."], cwd=workspace, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=workspace, check=True, capture_output=True)
            prompt_file = root / "prompt.md"
            prompt_file.write_text("Fix calculator.py", encoding="utf-8")
            patch_path = output_dir / "agent.patch"

            exit_code = run_adapter(
                workspace=workspace,
                prompt_file=prompt_file,
                patch_path=patch_path,
                output_dir=output_dir,
                model="gpt-test",
                max_file_bytes=10000,
                max_total_bytes=10000,
                temperature=None,
                client=ApplyPatchFakeClient(),
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("diff --git a/calculator.py b/calculator.py", patch_path.read_text(encoding="utf-8"))
            self.assertEqual((output_dir / "openai_patch_format.txt").read_text(encoding="utf-8"), "converted_apply_patch_block")


if __name__ == "__main__":
    unittest.main()
