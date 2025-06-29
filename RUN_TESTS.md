# Running Weave Tests

This document describes how to run the complete test suite for the Weave CLI tool.

## Quick Start

### Run All Unit Tests
```bash
uv run pytest tests/unit/ -v
```

### Run with Test Dependencies
```bash
# Install test dependencies
uv sync --extra test

# Run unit tests
uv run pytest tests/unit/ -v

# Check test collection
uv run pytest --collect-only
```

### Use the Test Runner Script
```bash
python test_runner.py
```

## Test Categories

### Unit Tests (Fast, No Network)
- **Location**: `tests/unit/`
- **Runtime**: ~1 second
- **Requirements**: None (uses mocks)

```bash
uv run pytest tests/unit/ -v
```

### Integration Tests (Require Network & Token)
- **Location**: `tests/integration/`
- **Runtime**: ~30-60 seconds
- **Requirements**: Network access, API token

```bash
# Set up integration token
export WEAVE_TEST_TOKEN="your_weavemcp_api_token"

# Run integration tests
uv run pytest tests/integration/ -v
```

## Test Results Summary

### Current Test Coverage

- **Total Tests**: 74 tests
- **Unit Tests**: 64 tests ✅
- **Integration Tests**: 10 tests ⚠️  (require token)

### Test Breakdown

#### Unit Tests (64 tests)
- **Authentication Tests**: 20 tests
  - Login command (manual token, browser OAuth)
  - Server management (add, remove, switch, list)
  - Configuration helpers
  - Error handling

- **Configuration Tests**: 20 tests  
  - Setup command for Claude Desktop
  - Status command
  - Remove and upgrade commands
  - Configuration validation

- **Proxy Tests**: 24 tests
  - Proxy command functionality
  - MCP proxy client operations
  - Proxy server lifecycle
  - STDIO transport and HTTP communication

#### Integration Tests (10 tests)
- **E2E Workflow**: 3 tests
  - Full login → setup → status workflow
  - API connectivity with real server
  - Server management operations

- **Proxy Integration**: 2 tests
  - Real proxy server connections
  - Proxy command with live server

- **Configuration Integration**: 2 tests
  - Claude config backup/restore
  - Configuration validation

- **Error Handling**: 3 tests
  - Invalid URLs and network timeouts
  - Invalid token format handling

## Running Specific Test Scenarios

### Test Authentication Only
```bash
uv run pytest tests/unit/test_auth.py -v
```

### Test Configuration Management  
```bash
uv run pytest tests/unit/test_config.py -v
```

### Test Proxy Functionality
```bash
uv run pytest tests/unit/test_proxy.py -v
```

### Test with Real atlaslabs.weavemcp.app Server
```bash
export WEAVE_TEST_TOKEN="your_token_here"
uv run pytest tests/integration/test_e2e.py::TestE2EIntegration::test_api_connectivity -v
```

### Test Error Handling
```bash
uv run pytest tests/integration/test_e2e.py::TestErrorHandling -v
```

## Test Configuration

### Environment Variables
- `WEAVE_TEST_TOKEN`: Required for integration tests
- `WEAVE_TEST_SERVER_URL`: Override default test server (optional)

### Pytest Configuration
The `pyproject.toml` includes pytest configuration:
- **Test directory**: `tests/`
- **Async mode**: Auto-enabled
- **Markers**: `unit`, `integration`, `slow`

### Test Markers Usage
```bash
# Run only unit tests
uv run pytest -m unit

# Run only integration tests (requires token)
uv run pytest -m integration

# Exclude slow tests
uv run pytest -m "not slow"
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Test Weave CLI
on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1
      
      - name: Install dependencies
        run: uv sync --extra test
      
      - name: Run unit tests
        run: uv run pytest tests/unit/ -v

  integration-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1
      
      - name: Install dependencies
        run: uv sync --extra test
      
      - name: Run integration tests
        env:
          WEAVE_TEST_TOKEN: ${{ secrets.WEAVE_TEST_TOKEN }}
        run: uv run pytest tests/integration/ -v
```

## Test Development

### Adding New Tests

1. **Unit Tests**: Add to appropriate file in `tests/unit/`
2. **Integration Tests**: Add to `tests/integration/test_e2e.py`
3. **Test Data**: Add to `tests/fixtures/test_data.py`
4. **Mocks**: Add to `tests/fixtures/mocks.py`

### Test Utilities
Use `tests/utils.py` for:
- Configuration management helpers
- Mock response builders
- Test data generators
- Async test helpers

### Example Test
```python
import pytest
from click.testing import CliRunner
from weave.cli import login

def test_login_success(mock_config, mock_webbrowser):
    """Test successful login"""
    runner = CliRunner()
    
    with patch("weave.cli.AuthServer") as mock_auth_server:
        mock_auth_server.return_value.__enter__.return_value.wait_for_callback.return_value = ("token", "url")
        
        result = runner.invoke(login, ["--server-url", "https://test.com"])
        
        assert result.exit_code == 0
        assert "Successfully logged in" in result.output
```

## Troubleshooting

### Common Issues

**"No module named 'weave'"**
```bash
uv sync --extra test
```

**Integration tests skipped**
```bash
export WEAVE_TEST_TOKEN="your_token_here"
```

**Tests hang during proxy testing**
- Check for proper async/await usage
- Ensure mock cleanup in fixtures

### Debug Mode
```bash
# Run with debugging
uv run pytest --pdb

# Show all output
uv run pytest -s -v

# Coverage report
uv run pytest --cov=weave --cov-report=html
```

## Performance

### Expected Runtimes
- **Unit Tests**: ~0.5 seconds (64 tests)
- **Integration Tests**: ~30-60 seconds (10 tests)
- **Full Suite**: ~1-2 minutes (with integration token)

### Optimization
- Unit tests use mocks for speed
- Integration tests can be skipped without token
- Parallel execution possible with pytest-xdist