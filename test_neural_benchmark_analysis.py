import json
from pathlib import Path
import tempfile
import unittest

from paper.analysis.neural_benchmark_analysis import expected_metric_status, valid_output


class NeuralBenchmarkOutputValidationTests(unittest.TestCase):
    def write_output(
        self,
        path: Path,
        *,
        input_sha256: str = "expected-hash",
        row_start: int = 10,
        row_indexes: tuple[int, ...] = (10, 11),
        include_provenance: bool = True,
    ) -> None:
        payload = {
            "status": {"comet": expected_metric_status("comet")},
            "scores": [
                {"row_index": row_index, "comet": 0.75}
                for row_index in row_indexes
            ],
        }
        if include_provenance:
            payload["provenance"] = {
                "input_sha256": input_sha256,
                "row_start": row_start,
                "row_count": len(row_indexes),
            }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def is_valid(self, path: Path) -> bool:
        return valid_output(
            path,
            "comet",
            2,
            expected_input_sha256="expected-hash",
            expected_row_start=10,
        )

    def test_accepts_output_for_the_expected_input_shard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output.json"
            self.write_output(path)

            self.assertTrue(self.is_valid(path))

    def test_rejects_output_when_the_input_hash_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output.json"
            self.write_output(path, input_sha256="stale-hash")

            self.assertFalse(self.is_valid(path))

    def test_rejects_output_for_a_different_row_range(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output.json"
            self.write_output(path, row_start=20, row_indexes=(20, 21))

            self.assertFalse(self.is_valid(path))

    def test_rejects_legacy_output_without_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output.json"
            self.write_output(path, include_provenance=False)

            self.assertFalse(self.is_valid(path))


if __name__ == "__main__":
    unittest.main()
