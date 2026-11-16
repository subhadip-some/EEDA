import io
import re
import unittest

import pandas as pd

from eeda_app import create_app
from eeda_app.core import (
    _column_cache,
    _stats_cache,
    chart_history,
    datasets,
    original_files,
    undo_stacks,
)
from eeda_app.reports import build_report_pdf


class ReportGenerationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        response = self.client.post(
            "/api/upload",
            data={"file": (io.BytesIO(
                b"score,group\n1,A\n2,B\n3,A\n100,B\n"
            ), "sample.csv")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.dataset_id = response.get_json()["dataset_id"]

    def tearDown(self):
        datasets.pop(self.dataset_id, None)
        undo_stacks.pop(self.dataset_id, None)
        original_files.pop(self.dataset_id, None)
        chart_history.pop(self.dataset_id, None)
        _column_cache.pop(self.dataset_id, None)
        _stats_cache.pop(self.dataset_id, None)

    def test_report_contains_selected_eeda_chart_image(self):
        chart_response = self.client.post(
            "/api/plot",
            json={
                "dataset_id": self.dataset_id,
                "type": "histogram",
                "column": "score",
            },
        )
        self.assertEqual(chart_response.status_code, 200)
        chart_id = chart_response.get_json()["chart_id"]

        report_response = self.client.post(
            "/api/report",
            json={
                "dataset_id": self.dataset_id,
                "charts": [{
                    "id": chart_id,
                    "title": "Score distribution",
                    "observation": "The values span a wide range.",
                }],
            },
        )

        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(report_response.mimetype, "application/pdf")
        self.assertTrue(report_response.data.startswith(b"%PDF-"))
        self.assertIn(b"/Subtype /Image", report_response.data)

    def test_report_uses_current_dataset_and_rejects_unavailable_charts(self):
        edit_response = self.client.post(
            "/api/rows",
            json={
                "dataset_id": self.dataset_id,
                "action": "delete",
                "row_ids": [0],
            },
        )
        self.assertEqual(edit_response.status_code, 200)

        report_response = self.client.post(
            "/api/report",
            json={"dataset_id": self.dataset_id},
        )
        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(report_response.mimetype, "application/pdf")

        invalid_chart_response = self.client.post(
            "/api/report",
            json={
                "dataset_id": self.dataset_id,
                "charts": [{"id": "not-generated-by-eeda"}],
            },
        )
        self.assertEqual(invalid_chart_response.status_code, 400)
        self.assertIn("no longer available", invalid_chart_response.get_json()["error"])

    def test_long_column_tables_continue_across_pages(self):
        long_dataset_id = "long-table-test"
        frame = pd.DataFrame({
            f"category_{index}": ["first", "second"]
            for index in range(90)
        })
        try:
            pdf = build_report_pdf(
                frame,
                "wide.csv",
                {"dataset_id": long_dataset_id},
                [],
                [],
            ).getvalue()
        finally:
            _stats_cache.pop(long_dataset_id, None)

        page_count = len(re.findall(rb"/Type\s*/Page\b", pdf))
        self.assertGreater(page_count, 1)


if __name__ == "__main__":
    unittest.main()
