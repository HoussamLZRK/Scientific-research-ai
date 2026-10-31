"""Exécutable avec le Python de .venv ; aucune dépendance PySpark."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from spark_etl_utils import canonical_fallback, normalize_doi, report_success, verify_derived_path, verify_report_path


class SparkEtLUtilsTests(unittest.TestCase):
    def test_clean_doi(self):
        self.assertEqual(normalize_doi("  HTTPS://doi.org/10.1000/A1 "), "10.1000/a1")

    def test_doi_prefix(self):
        self.assertEqual(normalize_doi("DOI: 10.1234/ABC"), "10.1234/abc")

    def test_reject_invalid_doi(self):
        self.assertIsNone(normalize_doi("not a doi"))

    def test_fallback_uses_doi(self):
        self.assertEqual(canonical_fallback("10.1234/ABC", "paper8", "PMLR"), "doi:10.1234/abc")

    def test_fallback_uses_source_scoped_id(self):
        self.assertEqual(canonical_fallback(None, " 24.ABC ", "ACL Anthology"), "acl_anthology:24.abc")

    def test_never_fallback_to_title(self):
        self.assertIsNone(canonical_fallback(None, None, "PMLR"))

    def test_hdfs_output_allowed(self):
        verify_derived_path("hdfs://namenode:8020/scientific-research-ai/curated/spark_etl_v1",kind="hdfs")

    def test_reject_raw_hdfs_overwrite(self):
        with self.assertRaises(ValueError):
            verify_derived_path("hdfs://namenode:8020/scientific-research-ai/processed",kind="hdfs")

    def test_local_output_allowed(self):
        verify_derived_path("/project/data/processed/spark",kind="local")

    def test_reject_local_data_root(self):
        with self.assertRaises(ValueError):
            verify_derived_path("/project/data",kind="local")

    def test_report_name(self):
        verify_report_path("/project/data/reports/spark_etl_quality_report.json")

    def test_report_success_requires_real_counts(self):
        self.assertTrue(report_success({"status":"OK", "publications":{"output_rows":4},"chunks":{"output_rows":263}}))
        self.assertFalse(report_success({"status":"OK", "publications":{"output_rows":0},"chunks":{"output_rows":263}}))
        self.assertFalse(report_success({"status":"FAILED", "publications":{"output_rows":4},"chunks":{"output_rows":263}}))


if __name__ == "__main__":
    unittest.main()
