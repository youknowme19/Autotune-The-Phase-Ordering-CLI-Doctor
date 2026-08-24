"""
ReportService: Standalone offline HTML report builder service.
"""

import json
import os
from autotune.reporting.html import HTMLReportGenerator


class ReportService:
    """Renders self-contained offline HTML reports from JSON search reports."""

    @staticmethod
    def render_html_report(report_json_path: str, output_html_path: str) -> str:
        if not os.path.exists(report_json_path):
            raise FileNotFoundError(f"Search report JSON '{report_json_path}' not found.")

        with open(report_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        html_content = HTMLReportGenerator.generate_html(data)
        os.makedirs(os.path.dirname(os.path.abspath(output_html_path)), exist_ok=True)

        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_html_path
