import unittest

from job_fit.evaluation import run_evaluation


class EvaluationTests(unittest.TestCase):
    def test_synthetic_corpus_meets_initial_gate(self):
        report = run_evaluation()
        self.assertEqual(report["case_count"], 15)
        self.assertTrue(report["regression_passed"], report["regression_failures"])
        metrics = report["metrics"]
        self.assertGreaterEqual(metrics["recommendation_accuracy"], 0.8)
        self.assertEqual(metrics["hard_blocker_false_positive_apply_rate"], 0.0)
        self.assertGreaterEqual(metrics["mean_evidence_coverage"], 0.8)


if __name__ == "__main__":
    unittest.main()
