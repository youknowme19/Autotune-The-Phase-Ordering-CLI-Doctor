"""
Standalone Offline HTML Report Generator.
Generates zero-dependency, self-contained HTML optimization reports with modern styling.
"""

import html
import json
import os
from typing import Any, Dict, Optional
from pydantic import BaseModel


class HTMLReportGenerator:
    """Generates self-contained, styled HTML reports from SearchReport JSON data."""

    @staticmethod
    def generate_html(report_data: Dict[str, Any]) -> str:
        p_data = report_data.get("prescription", {})
        speedup = p_data.get("speedup_ratio", 1.0)
        classification = html.escape(str(p_data.get("classification", "NO_SIGNIFICANT_CHANGE")))
        evidence_grade = html.escape(str(p_data.get("evidence_grade", "B")))
        passes = p_data.get("pass_sequence", {}).get("passes", [])
        clang_cmd = html.escape(str(p_data.get("reproducible_clang_command", "clang -O3")))
        source = html.escape(str(report_data.get("source_path", "N/A")))
        gen = report_data.get("generations_searched", 0)
        pop = report_data.get("population_size", 0)

        w_prof = report_data.get("workload_profile", {})
        loop_cnt = w_prof.get("loop_count", 0)
        max_depth = w_prof.get("max_loop_depth", 0)
        mem_intensity = w_prof.get("memory_intensity", 0.0)
        comp_intensity = w_prof.get("compute_intensity", 0.0)

        doc = report_data.get("doctor_report", {})
        arch = html.escape(str(doc.get("arch", "arm64")))
        clang_ver = html.escape(str(doc.get("clang_version", "Clang")))

        pass_tags = "".join(f'<span class="pass-badge">{html.escape(str(p))}</span>' for p in passes)

        html_code = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autotune Optimization Report — {os.path.basename(source)}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 20px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background-color: #1e293b;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            border: 1px solid #334155;
        }}
        .hero {{
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #1e1b4b, #312e81);
            border-radius: 8px;
            margin-bottom: 25px;
            border: 1px solid #4338ca;
        }}
        .hero h1 {{
            margin: 0;
            font-size: 2.5rem;
            color: #38bdf8;
        }}
        .hero p {{
            font-size: 1.2rem;
            color: #c7d2fe;
            margin-top: 5px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }}
        .card {{
            background-color: #0f172a;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #334155;
        }}
        .card h3 {{
            margin-top: 0;
            color: #94a3b8;
            font-size: 0.9rem;
            text-transform: uppercase;
        }}
        .card .metric {{
            font-size: 1.8rem;
            font-weight: bold;
            color: #38bdf8;
        }}
        .pass-badge {{
            display: inline-block;
            background-color: #0284c7;
            color: #ffffff;
            padding: 4px 10px;
            border-radius: 4px;
            margin: 3px;
            font-family: monospace;
            font-weight: bold;
        }}
        pre {{
            background-color: #090d16;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            color: #4ade80;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="hero">
            <h1>Autotune Optimization Report</h1>
            <p>Target Workload: <strong>{source}</strong></p>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Observed Speedup</h3>
                <div class="metric">{speedup}x</div>
            </div>
            <div class="card">
                <h3>Evidence Grade</h3>
                <div class="metric">Grade {evidence_grade}</div>
            </div>
            <div class="card">
                <h3>Classification</h3>
                <div class="metric" style="font-size: 1.3rem;">{classification}</div>
            </div>
        </div>

        <div class="card" style="margin-bottom: 25px;">
            <h3>Workload Structural Profile</h3>
            <p><strong>Loops:</strong> {loop_cnt} (Max Depth: {max_depth}) | <strong>Memory Intensity:</strong> {mem_intensity} | <strong>Compute Intensity:</strong> {comp_intensity}</p>
        </div>

        <div class="card" style="margin-bottom: 25px;">
            <h3>Winning LLVM Pass Sequence</h3>
            <div>{pass_tags}</div>
        </div>

        <div class="card" style="margin-bottom: 25px;">
            <h3>Reproducible Clang Command</h3>
            <pre>{clang_cmd}</pre>
        </div>

        <div class="card">
            <h3>Environment & Search Metadata</h3>
            <p><strong>Architecture:</strong> {arch} | <strong>Compiler:</strong> {clang_ver}</p>
            <p><strong>Generations:</strong> {gen} | <strong>Population:</strong> {pop}</p>
        </div>
    </div>
</body>
</html>
"""
        return html_code
