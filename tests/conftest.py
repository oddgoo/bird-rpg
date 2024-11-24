import pytest
import os
import json
from pathlib import Path

@pytest.fixture(autouse=True)
def setup_test_environment():
    # Set up test environment variables
    os.environ['DEBUG'] = 'True'
    os.environ['DISCORD_TOKEN'] = 'test-token'
    
    # Create test data directory
    test_data_dir = Path('test_data')
    test_data_dir.mkdir(exist_ok=True)
    
    yield
    
    # Cleanup
    if test_data_dir.exists():
        for file in test_data_dir.glob('*'):
            file.unlink()
        test_data_dir.rmdir()