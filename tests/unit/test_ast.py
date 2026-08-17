"""
Unit tests for AST source code analysis and feature extraction.
"""

import os
import pytest
from autotune.analysis.ast import SourceAnalyzer
from autotune.analysis.features import FeatureExtractor


def test_ast_analysis_simple_loop():
    analyzer = SourceAnalyzer()
    simple_loop_path = os.path.abspath("examples/simple_loop/kernel.c")
    assert os.path.exists(simple_loop_path)

    summary = analyzer.analyze_source_file(simple_loop_path)
    assert summary.lines_of_code > 0
    assert summary.loop_count >= 1
    assert summary.nested_loop_max_depth >= 1
    assert summary.function_count >= 1


def test_ast_analysis_vector_sum():
    analyzer = SourceAnalyzer()
    vector_sum_path = os.path.abspath("examples/vector_sum/kernel.c")
    assert os.path.exists(vector_sum_path)

    summary = analyzer.analyze_source_file(vector_sum_path)
    assert summary.lines_of_code > 0
    assert summary.loop_count >= 2
    assert summary.has_arrays_or_pointers
    assert summary.array_accesses > 0 or summary.estimated_memory_intensity > 0


def test_feature_extractor():
    extractor = FeatureExtractor()
    simple_loop_path = os.path.abspath("examples/simple_loop/kernel.c")

    features = extractor.extract_from_file(simple_loop_path)
    assert features.filename == "kernel.c"
    assert len(features.suggested_focus_areas) > 0

    compact_json = features.to_compact_json()
    assert "lines_of_code" in compact_json
    assert "loop_count" in compact_json
