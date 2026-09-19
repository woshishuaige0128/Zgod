from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from board20_step6_fs_protocol import (
    EXPECTED_FIXED_ROOTS,
    MANIFEST_NAME,
    MANIFEST_TEMP_NAME,
    atomic_commit_manifest,
    classify_output,
    prepare_output_root,
    sha256_file,
    validate_fixed_roots,
)


SCRIPT_PATH = Path(__file__).resolve()
BOARD_ROOT = SCRIPT_PATH.parent.parent
TEST_PARENT = BOARD_ROOT / "logs" / "step6_history_comparison" / "fs_protocol_tests"
EXPECTED_FILES = {
    "tables/a.csv",
    "figures/a.pdf",
    "summary.json",
}
EXPECTED_DIRECTORIES = {"tables", "figures"}
PAYLOADS = {
    "tables/a.csv": b"x,y\n1,2\n",
    "figures/a.pdf": b"deterministic-vector-placeholder\n",
    "summary.json": b'{"status":"PASS"}\n',
}


class ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_PARENT.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="case_", dir=TEST_PARENT))

    def tearDown(self) -> None:
        resolved = self.root.resolve(strict=False)
        if not resolved.is_relative_to(TEST_PARENT.resolve(strict=True)):
            raise RuntimeError(f"Unsafe test cleanup target: {resolved}")
        if self.root.exists():
            shutil.rmtree(self.root)

    def write_expected(self) -> None:
        prepare_output_root(self.root, EXPECTED_FILES, EXPECTED_DIRECTORIES)
        for relpath, payload in PAYLOADS.items():
            path = self.root / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

    def commit(self) -> None:
        atomic_commit_manifest(
            self.root, EXPECTED_FILES, EXPECTED_DIRECTORIES
        )

    def committed_hashes(self) -> dict[str, str]:
        return {
            relpath: sha256_file(self.root / relpath)
            for relpath in sorted(EXPECTED_FILES | {MANIFEST_NAME})
        }

    def test_repeat_commit_is_byte_identical(self) -> None:
        self.write_expected()
        self.commit()
        first = self.committed_hashes()
        self.write_expected()
        self.commit()
        self.assertEqual(first, self.committed_hashes())

    def test_recover_after_old_manifest_removed_and_partial_overwrite(self) -> None:
        self.write_expected()
        self.commit()
        prior = prepare_output_root(
            self.root, EXPECTED_FILES, EXPECTED_DIRECTORIES
        )
        self.assertEqual("COMMITTED", prior.state)
        self.assertFalse((self.root / MANIFEST_NAME).exists())
        (self.root / "tables/a.csv").write_bytes(b"partial")
        self.assertEqual(
            "RECOVERABLE_UNCOMMITTED",
            classify_output(
                self.root, EXPECTED_FILES, EXPECTED_DIRECTORIES
            ).state,
        )
        self.write_expected()
        self.commit()
        self.assertEqual(
            "COMMITTED",
            classify_output(
                self.root, EXPECTED_FILES, EXPECTED_DIRECTORIES
            ).state,
        )

    def test_recover_after_manifest_temp_fsync_interruption(self) -> None:
        self.write_expected()

        def fail_hook(phase: str) -> None:
            if phase == "after_manifest_temp_fsync":
                raise RuntimeError("injected interruption")

        with self.assertRaisesRegex(RuntimeError, "injected interruption"):
            atomic_commit_manifest(
                self.root,
                EXPECTED_FILES,
                EXPECTED_DIRECTORIES,
                fail_hook=fail_hook,
            )
        self.assertTrue((self.root / MANIFEST_TEMP_NAME).is_file())
        self.assertFalse((self.root / MANIFEST_NAME).exists())
        self.write_expected()
        self.commit()
        self.assertEqual(
            "COMMITTED",
            classify_output(
                self.root, EXPECTED_FILES, EXPECTED_DIRECTORIES
            ).state,
        )

    def test_replace_then_interruption_is_already_committed(self) -> None:
        self.write_expected()

        def fail_hook(phase: str) -> None:
            if phase == "after_manifest_replace":
                raise RuntimeError("injected interruption")

        with self.assertRaisesRegex(RuntimeError, "injected interruption"):
            atomic_commit_manifest(
                self.root,
                EXPECTED_FILES,
                EXPECTED_DIRECTORIES,
                fail_hook=fail_hook,
            )
        self.assertEqual(
            "COMMITTED",
            classify_output(
                self.root, EXPECTED_FILES, EXPECTED_DIRECTORIES
            ).state,
        )

    def test_rogue_file_is_rejected_without_manifest_change(self) -> None:
        self.write_expected()
        self.commit()
        manifest_hash = sha256_file(self.root / MANIFEST_NAME)
        (self.root / "rogue.txt").write_text("forbidden", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "tree drifted"):
            prepare_output_root(
                self.root, EXPECTED_FILES, EXPECTED_DIRECTORIES
            )
        self.assertEqual(manifest_hash, sha256_file(self.root / MANIFEST_NAME))

    def test_rogue_empty_directory_is_rejected_without_manifest_change(self) -> None:
        self.write_expected()
        self.commit()
        manifest_hash = sha256_file(self.root / MANIFEST_NAME)
        (self.root / "rogue_dir").mkdir()
        with self.assertRaisesRegex(RuntimeError, "tree drifted"):
            prepare_output_root(
                self.root, EXPECTED_FILES, EXPECTED_DIRECTORIES
            )
        self.assertEqual(manifest_hash, sha256_file(self.root / MANIFEST_NAME))

    def test_fixed_root_literal_drift_is_rejected_before_access(self) -> None:
        drifted = dict(EXPECTED_FIXED_ROOTS)
        drifted["run1"] = self.root.relative_to(BOARD_ROOT).as_posix()
        with self.assertRaisesRegex(RuntimeError, "literal contract drifted"):
            validate_fixed_roots(
                BOARD_ROOT,
                drifted,
            )

    def test_exact_fixed_root_literals_are_accepted(self) -> None:
        roots = validate_fixed_roots(BOARD_ROOT, EXPECTED_FIXED_ROOTS)
        self.assertEqual(set(EXPECTED_FIXED_ROOTS), set(roots))


if __name__ == "__main__":
    unittest.main(verbosity=2)
