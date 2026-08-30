"""
Unit tests for automatic C vs C++ compiler routing (Phase 16).
"""

from autotune.llvm.compiler import CompilerDriver


def test_compiler_routing():
    driver = CompilerDriver(clang_path="/opt/homebrew/opt/llvm/bin/clang", clangxx_path="/opt/homebrew/opt/llvm/bin/clang++")

    # C extensions
    assert driver.get_compiler_for_source("kernel.c") == driver.clang_path
    assert driver.get_compiler_for_source("/path/to/my_c_prog.c") == driver.clang_path

    # C++ extensions
    assert driver.get_compiler_for_source("kernel.cpp") == driver.clangxx_path
    assert driver.get_compiler_for_source("kernel.cc") == driver.clangxx_path
    assert driver.get_compiler_for_source("kernel.cxx") == driver.clangxx_path
    assert driver.get_compiler_for_source("kernel.C") == driver.clangxx_path
    assert driver.get_compiler_for_source("kernel.c++") == driver.clangxx_path
