"""Module entry point for SCF repository validation."""

from pathlib import Path

from .cli import main

raise SystemExit(main(Path.cwd()))
