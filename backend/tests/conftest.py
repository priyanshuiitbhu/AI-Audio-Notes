import os
# Ensure test suite runs in isolated SQLite test database
os.environ["DATABASE_URL"] = "sqlite:///./test_audionotes.db"
