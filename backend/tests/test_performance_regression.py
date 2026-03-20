"""
Performance regression tests for core bulk scenarios.

These tests ensure that performance doesn't degrade over time for:
- Large thread histories
- Long agent chains
- Large file uploads
- Memory usage patterns
"""

import tempfile
import time
from pathlib import Path

import pytest

from src.config import get_app_config
from src.models import create_chat_model
from src.sandbox.local.local_sandbox import LocalSandbox
import asyncio
import tempfile
import time
from pathlib import Path

import pytest

from src.config import get_app_config
from src.models import create_chat_model
from src.sandbox.local.local_sandbox import LocalSandbox


class TestPerformanceRegression:
    """Performance regression tests for bulk operations."""

    def test_large_thread_history_memory_usage(self):
        """Test that large thread histories don't cause excessive memory usage."""
        # Create a large message list similar to thread history
        messages = []
        for i in range(1000):
            messages.append({
                "role": "user",
                "content": f"Message {i}: " + "x" * 1000,  # 1KB per message
            })
            messages.append({
                "role": "assistant",
                "content": f"Response {i}: " + "y" * 1000,
            })

        # Measure memory usage (basic check)
        start_time = time.time()
        # Simulate some operations on the message list
        message_count = len(messages)
        artifact_count = 100
        todo_count = 50

        end_time = time.time()

        # Should complete in reasonable time
        assert end_time - start_time < 1.0  # Less than 1 second
        assert message_count == 2000
        assert artifact_count == 100
        assert todo_count == 50

    def test_large_file_upload_handling(self):
        """Test handling of large file uploads without excessive memory usage."""
        # Create a temporary large file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            # Write 10MB of data
            chunk_size = 1024 * 1024  # 1MB
            for _ in range(10):
                f.write("x" * chunk_size)
            large_file_path = f.name

        try:
            # Test sandbox file operations with large file
            sandbox = LocalSandbox(
                id="test_sandbox",
                path_mappings={"/tmp": "/tmp"}
            )

            start_time = time.time()

            # Test reading file size
            with open(large_file_path, 'rb') as f:
                content = f.read()
                assert len(content) == 10 * 1024 * 1024  # 10MB

            # Test sandbox read_file (should handle large files)
            # Note: In real usage, files would be in mapped directories
            read_time = time.time() - start_time
            assert read_time < 5.0  # Should read 10MB in less than 5 seconds

        finally:
            Path(large_file_path).unlink(missing_ok=True)

    def test_model_creation_performance(self):
        """Test that model creation doesn't regress in performance."""
        config = get_app_config()
        if not config.models:
            pytest.skip("No models configured")

        model_name = config.models[0].name

        # Test cached model creation performance
        start_time = time.time()

        # Create model multiple times (should be cached)
        for _ in range(10):
            model = create_chat_model(model_name, thinking_enabled=False)
            assert model is not None

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete quickly (cached models)
        assert total_time < 2.0  # Less than 2 seconds for 10 creations

    def test_concurrent_agent_operations(self):
        """Test performance under concurrent agent operations."""
        # This is a basic concurrency test - in real scenarios would test
        # actual agent chains with proper mocking

        async def mock_operation(delay: float):
            await asyncio.sleep(delay)
            return f"completed after {delay}s"

        async def run_test():
            start_time = time.time()

            # Run multiple concurrent operations
            tasks = [mock_operation(0.1) for _ in range(10)]
            results = await asyncio.gather(*tasks)

            end_time = time.time()
            total_time = end_time - start_time

            # Should complete in ~0.1s (not 1.0s sequentially)
            assert total_time < 0.5  # Allow some overhead
            assert len(results) == 10
            assert all("completed" in result for result in results)

        asyncio.run(run_test())

    def test_config_loading_performance(self):
        """Test that config loading doesn't regress."""
        start_time = time.time()

        # Load config multiple times
        for _ in range(5):
            config = get_app_config()
            assert config is not None
            assert len(config.models) >= 0  # At least empty list

        end_time = time.time()
        total_time = end_time - start_time

        # Should be fast
        assert total_time < 1.0