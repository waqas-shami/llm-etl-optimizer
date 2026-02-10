#!/usr/bin/env python
"""
Quick launcher for the LLM ETL Optimizer Streamlit demo.

Usage:
    python run_demo.py

Or run directly with Streamlit:
    streamlit run app/streamlit_app.py
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)

    # Check if streamlit is installed
    try:
        import streamlit
        print(f"✓ Streamlit {streamlit.__version__} found")
    except ImportError:
        print("✗ Streamlit not found. Installing minimal requirements...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-demo.txt"])

    # Run the Streamlit app
    print("\n🚀 Launching LLM ETL Optimizer Demo...")
    print("   Open http://localhost:8501 in your browser\n")

    app_path = project_dir / "app" / "streamlit_app.py"

    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false"
    ])


if __name__ == "__main__":
    main()
