"""
Unit tests for LLVM PassSequence, validation, formatting, and mutators.
"""

import pytest
from autotune.llvm.passes import PassSequence, PassValidator


def test_pass_sequence_to_opt_string():
    seq = PassSequence(passes=["mem2reg", "instcombine", "gvn"])
    assert seq.to_opt_string() == "mem2reg,instcombine,gvn"

    empty_seq = PassSequence(passes=[])
    assert empty_seq.to_opt_string() == "mem2reg"


def test_pass_sequence_insertion():
    seq = PassSequence(passes=["mem2reg", "gvn"])
    new_seq = seq.insert("licm", 1)
    assert new_seq.passes == ["mem2reg", "licm", "gvn"]


def test_pass_sequence_deletion():
    seq = PassSequence(passes=["mem2reg", "licm", "gvn"])
    new_seq = seq.delete(1)
    assert new_seq.passes == ["mem2reg", "gvn"]


def test_pass_sequence_swap():
    seq = PassSequence(passes=["mem2reg", "gvn"])
    swapped = seq.swap(0, 1)
    assert swapped.passes == ["gvn", "mem2reg"]


def test_pass_sequence_crossover():
    seq1 = PassSequence(passes=["p1", "p2", "p3", "p4"])
    seq2 = PassSequence(passes=["q1", "q2", "q3", "q4"])
    child = seq1.crossover(seq2, 1, 3)
    assert child.passes == ["p1", "q2", "q3", "p4"]


def test_pass_sequence_validate_method():
    valid_seq = PassSequence(passes=["mem2reg", "gvn", "instcombine"])
    assert valid_seq.validate()

    invalid_seq = PassSequence(passes=["mem2reg", "nonexistent-pass-1234"])
    assert not invalid_seq.validate()


def test_pass_validator_rejection():
    validator = PassValidator()
    assert validator.is_valid_pass("mem2reg")
    assert validator.is_valid_pass("gvn")
    assert not validator.is_valid_pass("fake-hallucinated-pass-123")

    seq = PassSequence(passes=["mem2reg", "fake-pass", "gvn"])
    filtered = validator.filter_sequence(seq)
    assert filtered.passes == ["mem2reg", "gvn"]
