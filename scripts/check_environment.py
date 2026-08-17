#!/usr/bin/env python3
"""
Quick environment check script for Autotune.
"""
from autotune.doctor import run_doctor_checks
from autotune.ui import print_doctor_report

def main():
    report = run_doctor_checks()
    print_doctor_report(report)

if __name__ == "__main__":
    main()
