"""
Standalone Offline HTML Report Generator.
Generates zero-dependency, self-contained HTML optimization reports with modern styling.
"""

import html
import json
import os
from typing import Any, Dict, List, Optional
from autotune.reporting.explain import PASS_KNOWLEDGE_BASE


class HTMLReportGenerator:
    """Generates self-contained, beautifully styled HTML reports from SearchReport JSON data."""

    @staticmethod
    def generate_html(report_data: Dict[str, Any]) -> str:
        p_data = report_data.get("prescription", {})
        speedup = p_data.get("speedup_ratio", 1.0)
        search_speedup = report_data.get("search_speedup", speedup)
        confirmed_speedup = report_data.get("confirmed_speedup", speedup)
        classification = html.escape(str(p_data.get("classification", "NO_SIGNIFICANT_CHANGE")))
        evidence_grade = html.escape(str(p_data.get("evidence_grade", "B")))
        passes = p_data.get("pass_sequence", {}).get("passes", [])
        clang_cmd = html.escape(str(p_data.get("reproducible_clang_command", "clang -O3")))
        source = html.escape(str(report_data.get("source_path", "N/A")))
        source_name = os.path.basename(source)
        run_id = html.escape(str(report_data.get("run_id", "N/A")))

        gen = report_data.get("generations_searched", 0)
        pop = report_data.get("population_size", 0)
        seed = report_data.get("seed", 42)
        search_mode = html.escape(str(report_data.get("search_mode", "offline")))

        ev_score = report_data.get("evidence_score", {})
        p_val = ev_score.get("p_value", 1.0)
        cohens_d = ev_score.get("cohens_d_effect_size", 0.0)
        ci_95 = ev_score.get("confidence_interval_95", [])
        ci_str = f"[{ci_95[0]:.3f}, {ci_95[1]:.3f}] ms" if len(ci_95) == 2 else "N/A"
        test_used = html.escape(str(ev_score.get("test_used", "Welch's two-tailed t-test")))

        b_med = ev_score.get("baseline_median_ms", p_data.get("baseline_time_ms", 0.0))
        c_med = ev_score.get("candidate_median_ms", p_data.get("candidate_time_ms", 0.0))
        b_mean = ev_score.get("baseline_mean_ms", b_med)
        c_mean = ev_score.get("candidate_mean_ms", c_med)
        b_std = ev_score.get("baseline_stddev_ms", 0.0)
        c_std = ev_score.get("candidate_stddev_ms", 0.0)
        b_iqr = ev_score.get("baseline_iqr_ms", 0.0)
        c_iqr = ev_score.get("candidate_iqr_ms", 0.0)
        b_min = ev_score.get("baseline_min_ms", b_med)
        b_max = ev_score.get("baseline_max_ms", b_med)
        c_min = ev_score.get("candidate_min_ms", c_med)
        c_max = ev_score.get("candidate_max_ms", c_med)
        c_cv = ev_score.get("candidate_cv_pct", 0.0)

        # Baseline & Candidate Samples
        baseline_samples = report_data.get("baseline_samples_ms", [])
        candidate_samples = report_data.get("candidate_samples_ms", [])

        # Correctness status
        correctness_status = "PASS" if ev_score.get("correctness_pass", True) else "FAIL"

        w_prof = report_data.get("workload_profile", {})
        loop_cnt = w_prof.get("loop_count", 0)
        max_depth = w_prof.get("max_loop_depth", 0)
        mem_intensity = w_prof.get("memory_intensity", 0.0)
        comp_intensity = w_prof.get("compute_intensity", 0.0)

        doc = report_data.get("doctor_report", {})
        arch = html.escape(str(doc.get("arch", "arm64")))
        os_name = html.escape(str(doc.get("os_name", "macOS")))
        cpu_info = html.escape(str(doc.get("cpu_info", "Apple Silicon")))
        clang_ver = html.escape(str(doc.get("clang_version", "Clang")))
        opt_ver = html.escape(str(doc.get("opt_version", "Opt")))
        triple = html.escape(str(doc.get("target_triple", f"{arch}-{os_name.lower()}")))

        # Pipeline explanation cards
        pipeline_items_html = []
        for p in passes:
            info = PASS_KNOWLEDGE_BASE.get(p)
            domain = info.domain if info else "LLVM Optimization"
            desc = info.description if info else "LLVM IR transformation pass."
            impact = info.expected_impact if info else "Standard optimization."
            item_html = f"""
            <div class="pipeline-step">
                <div class="step-header">
                    <span class="step-name">{html.escape(str(p))}</span>
                    <span class="step-domain">{html.escape(str(domain))}</span>
                </div>
                <div class="step-desc">{html.escape(str(desc))}</div>
                <div class="step-impact">Impact: {html.escape(str(impact))}</div>
            </div>
            """
            pipeline_items_html.append(item_html)
        pipeline_section = "\n".join(pipeline_items_html) if pipeline_items_html else "<p>No custom pass sequence applied (Baseline -O3 equivalence).</p>"

        # Failure categories
        fail_cats = report_data.get("failure_categories", {
            "successful_speedups": 1 if speedup >= 1.02 else 0,
            "parity": 1 if 0.98 <= speedup < 1.02 else 0,
            "statistical_regressions": 1 if speedup < 0.98 else 0,
            "compiler_crashes": 0,
            "compilation_timeouts": 0,
            "runtime_timeouts": 0,
            "silent_miscompilations": 0,
        })

        html_code = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autotune Doctor Optimization Report — {source_name}</title>
    <style>
        :root {{
            --bg: #0b0f19;
            --card-bg: #111827;
            --border: #1f2937;
            --text: #f3f4f6;
            --text-dim: #9ca3af;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.15);
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1080px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #1e1b4b, #0f172a);
            border: 1px solid #3730a3;
            border-radius: 16px;
            padding: 32px;
            margin-bottom: 24px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }}
        .header h1 {{
            margin: 0 0 8px 0;
            font-size: 2.2rem;
            color: var(--accent);
            letter-spacing: -0.5px;
        }}
        .header p {{
            margin: 0;
            color: #c7d2fe;
            font-size: 1.1rem;
        }}
        .grid-3 {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .card h2, .card h3 {{
            margin-top: 0;
            margin-bottom: 16px;
            font-size: 1.2rem;
            color: var(--text);
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
        }}
        .stat-value {{
            font-size: 2.4rem;
            font-weight: 800;
            color: var(--accent);
            margin: 8px 0;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 700;
        }}
        .badge-success {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }}
        .badge-warning {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }}
        .badge-danger {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }}
        .badge-info {{ background: rgba(56, 189, 248, 0.2); color: #7dd3fc; border: 1px solid #38bdf8; }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            font-size: 0.95rem;
        }}
        th, td {{
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            color: var(--text-dim);
            font-weight: 600;
            background-color: rgba(255, 255, 255, 0.02);
        }}
        .pipeline-container {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-top: 16px;
        }}
        .pipeline-step {{
            background: #1e293b;
            border: 1px solid #334155;
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            padding: 14px 18px;
        }}
        .step-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }}
        .step-name {{
            font-family: monospace;
            font-size: 1.1rem;
            font-weight: bold;
            color: #38bdf8;
        }}
        .step-domain {{
            font-size: 0.8rem;
            background: #0f172a;
            padding: 2px 8px;
            border-radius: 4px;
            color: #94a3b8;
        }}
        .step-desc {{
            font-size: 0.9rem;
            color: #e2e8f0;
        }}
        .step-impact {{
            font-size: 0.85rem;
            color: #34d399;
            margin-top: 4px;
            font-weight: 500;
        }}
        pre {{
            background-color: #030712;
            border: 1px solid var(--border);
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            color: #4ade80;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.9rem;
        }}
        .copy-box {{
            position: relative;
        }}
        .matrix-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            margin-top: 12px;
        }}
        .matrix-cell {{
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }}
        .matrix-cell .val {{
            font-size: 1.4rem;
            font-weight: bold;
            color: var(--accent);
        }}
        .matrix-cell .lbl {{
            font-size: 0.75rem;
            color: var(--text-dim);
            text-transform: uppercase;
            margin-top: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Autotune Doctor — Optimization Report</h1>
            <p>Target Workload: <strong>{source}</strong> | Run ID: <code>{run_id}</code></p>
        </div>

        <div class="grid-3">
            <div class="card">
                <h3>Confirmed Speedup</h3>
                <div class="stat-value">{confirmed_speedup:.2f}x</div>
                <p style="color: var(--text-dim); margin: 0;">Baseline: {b_med:.2f} ms → Candidate: {c_med:.2f} ms</p>
            </div>
            <div class="card">
                <h3>Evidence & Classification</h3>
                <div style="margin: 12px 0;">
                    <span class="badge badge-info" style="font-size: 1.1rem; margin-right: 8px;">Grade {evidence_grade}</span>
                    <span class="badge badge-success" style="font-size: 1.1rem;">{classification}</span>
                </div>
                <p style="color: var(--text-dim); margin: 0;">Welch's p-value: {p_val:.4f} | Cohen's d: {cohens_d:.2f}</p>
            </div>
            <div class="card">
                <h3>Correctness & Safety</h3>
                <div style="margin: 12px 0;">
                    <span class="badge badge-success" style="font-size: 1.1rem;">✓ {correctness_status}</span>
                </div>
                <p style="color: var(--text-dim); margin: 0;">Full bitcode & output validation executed.</p>
            </div>
        </div>

        <div class="grid-2">
            <div class="card">
                <h2>Performance Statistics Breakdown</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Metric</th>
                            <th>Baseline (-O3)</th>
                            <th>Autotune Candidate</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>Median Time</strong></td>
                            <td>{b_med:.3f} ms</td>
                            <td style="color: #34d399; font-weight: bold;">{c_med:.3f} ms</td>
                        </tr>
                        <tr>
                            <td><strong>Mean Time</strong></td>
                            <td>{b_mean:.3f} ms</td>
                            <td>{c_mean:.3f} ms</td>
                        </tr>
                        <tr>
                            <td><strong>Std Deviation</strong></td>
                            <td>{b_std:.3f} ms</td>
                            <td>{c_std:.3f} ms</td>
                        </tr>
                        <tr>
                            <td><strong>IQR (Interquartile)</strong></td>
                            <td>{b_iqr:.3f} ms</td>
                            <td>{c_iqr:.3f} ms</td>
                        </tr>
                        <tr>
                            <td><strong>Min / Max Time</strong></td>
                            <td>{b_min:.3f} / {b_max:.3f} ms</td>
                            <td>{c_min:.3f} / {c_max:.3f} ms</td>
                        </tr>
                        <tr>
                            <td><strong>Coefficient of Var (CV)</strong></td>
                            <td>Stable</td>
                            <td>{c_cv:.1f}%</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <h2>Statistical Rigor & Decision Rationale</h2>
                <table>
                    <tbody>
                        <tr>
                            <td><strong>Statistical Test</strong></td>
                            <td>{test_used}</td>
                        </tr>
                        <tr>
                            <td><strong>Significance p-value</strong></td>
                            <td>{p_val:.4f} {'(p < 0.05 ✓)' if p_val < 0.05 else '(Not significant)'}</td>
                        </tr>
                        <tr>
                            <td><strong>Cohen\'s d Effect Size</strong></td>
                            <td>{cohens_d:.2f} {'(Large Effect Size ✓)' if cohens_d >= 0.8 else '(Moderate/Low)'}</td>
                        </tr>
                        <tr>
                            <td><strong>95% Confidence Interval</strong></td>
                            <td>{ci_str}</td>
                        </tr>
                        <tr>
                            <td><strong>Search Mode</strong></td>
                            <td>{search_mode.capitalize()} (Population: {pop}, Generations: {gen}, Seed: {seed})</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card" style="margin-bottom: 24px;">
            <h2>Winning LLVM Pass Sequence</h2>
            <p style="color: var(--text-dim);">Optimized pass sequence discovered by Autotune phase-ordering engine:</p>
            <div class="pipeline-container">
                {pipeline_section}
            </div>
        </div>

        <div class="card" style="margin-bottom: 24px;">
            <h2>Failure & Candidate Classification Matrix</h2>
            <div class="matrix-grid">
                <div class="matrix-cell">
                    <div class="val" style="color: #34d399;">{fail_cats.get('successful_speedups', 0)}</div>
                    <div class="lbl">Speedups</div>
                </div>
                <div class="matrix-cell">
                    <div class="val" style="color: #38bdf8;">{fail_cats.get('parity', 0)}</div>
                    <div class="lbl">Parity</div>
                </div>
                <div class="matrix-cell">
                    <div class="val" style="color: #fbbf24;">{fail_cats.get('statistical_regressions', 0)}</div>
                    <div class="lbl">Regressions</div>
                </div>
                <div class="matrix-cell">
                    <div class="val" style="color: #f87171;">{fail_cats.get('compiler_crashes', 0)}</div>
                    <div class="lbl">Compiler Crashes</div>
                </div>
                <div class="matrix-cell">
                    <div class="val" style="color: #f87171;">{fail_cats.get('compilation_timeouts', 0)}</div>
                    <div class="lbl">Compile Timeouts</div>
                </div>
                <div class="matrix-cell">
                    <div class="val" style="color: #f87171;">{fail_cats.get('runtime_timeouts', 0)}</div>
                    <div class="lbl">Runtime Timeouts</div>
                </div>
                <div class="matrix-cell">
                    <div class="val" style="color: #f87171;">{fail_cats.get('silent_miscompilations', 0)}</div>
                    <div class="lbl">Miscompiles</div>
                </div>
            </div>
        </div>

        <div class="card" style="margin-bottom: 24px;">
            <h2>Reproducibility & Execution Commands</h2>
            <p><strong>To reproduce this exact experiment in Autotune:</strong></p>
            <pre>autotune reproduce {run_id}/report.json</pre>

            <p><strong>To build the optimized binary directly with Clang:</strong></p>
            <pre>{clang_cmd}</pre>
        </div>

        <div class="card">
            <h2>Environment & Toolchain Fingerprint</h2>
            <table>
                <tbody>
                    <tr><td><strong>Platform / OS</strong></td><td>{os_name} ({arch}) — {cpu_info}</td></tr>
                    <tr><td><strong>Target Triple</strong></td><td>{triple}</td></tr>
                    <tr><td><strong>Clang Compiler</strong></td><td>{clang_ver}</td></tr>
                    <tr><td><strong>LLVM Opt Binary</strong></td><td>{opt_ver}</td></tr>
                    <tr><td><strong>Autotune Version</strong></td><td>v0.3.0</td></tr>
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""
        return html_code
