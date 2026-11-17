import base64
import io
import unittest

import matplotlib.pyplot as plt
import pandas as pd

from eeda_app import create_app
from eeda_app.charts import make_chart
from eeda_app.core import (
    _column_cache,
    _stats_cache,
    chart_history,
    datasets,
    original_files,
    undo_stacks,
)


class CategoricalChartTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        response = self.client.post(
            "/api/upload",
            data={"file": (io.BytesIO(
                b"group,segment,score\nA,X,1\nA,Y,3\nB,X,5\nB,Y,9\n"
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

    def test_categorical_and_numeric_chart_types_generate_pngs(self):
        requests = [
            {"type": "stacked_bar", "x": "group", "y": "segment"},
            {"type": "grouped_bar", "x": "group", "y": "segment"},
            {"type": "strip", "x": "group", "y": "score"},
            {"type": "bar", "x": "group", "y": "score"},
        ]
        for chart_request in requests:
            with self.subTest(chart_type=chart_request["type"]):
                response = self.client.post(
                    "/api/plot",
                    json={"dataset_id": self.dataset_id, **chart_request},
                )
                self.assertEqual(response.status_code, 200)
                image = base64.b64decode(response.get_json()["image"].split(",", 1)[1])
                self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_chart_types_reject_incompatible_column_types(self):
        response = self.client.post(
            "/api/plot",
            json={
                "dataset_id": self.dataset_id,
                "type": "grouped_bar",
                "x": "group",
                "y": "score",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("two categorical columns", response.get_json()["error"])

        response = self.client.post(
            "/api/plot",
            json={
                "dataset_id": self.dataset_id,
                "type": "strip",
                "x": "score",
                "y": "group",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("one categorical column and one numeric column", response.get_json()["error"])

    def test_bar_plot_shows_numeric_means_by_category(self):
        frame = pd.DataFrame({"group": ["A", "A", "B"], "score": [2, 4, 8]})
        figure, _ = make_chart(frame, {"type": "bar", "x": "group", "y": "score"})
        try:
            self.assertEqual([patch.get_height() for patch in figure.axes[0].patches], [3, 8])
        finally:
            plt.close(figure)


if __name__ == "__main__":
    unittest.main()
