import pytest
import os


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment variables. No test_data directory needed with Supabase."""
    os.environ['DEBUG'] = 'True'
    os.environ['DISCORD_TOKEN'] = 'test-token'
    # Prevent real Supabase connections during tests
    os.environ['SUPABASE_URL'] = 'http://localhost:99999'
    os.environ['SUPABASE_KEY'] = 'test-key'
    yield
