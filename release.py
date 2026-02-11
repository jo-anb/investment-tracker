#!/usr/bin/env python3
"""Wrapper script to run semantic-release with .env file support."""

from dotenv import load_dotenv
import subprocess
import sys

# Load environment variables from .env file
load_dotenv()

# Run semantic-release with all passed arguments
result = subprocess.run([sys.executable, "-m", "semantic_release"] + sys.argv[1:])
sys.exit(result.returncode)
