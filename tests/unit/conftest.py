"""Add the backend directory to sys.path so unit tests can import app modules."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
