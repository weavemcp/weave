# Weave Test Suite

This directory contains comprehensive tests for the Weave CLI tool, covering unit tests, integration tests, and end-to-end testing scenarios.

## Test Structure

```
tests/
├── conftest.py              # Pytest configuration and shared fixtures
├── utils.py                 # Test utilities and helpers
├── fixtures/                # Test data and mock objects
│   ├── __init__.py
│   ├── test_data.py        # Sample data for tests
│   └── mocks.py            # Mock objects and utilities
├── unit/                   # Unit tests (isolated, no network)
│   ├── __init__.py
│   ├── test_auth.py        # Authentication tests
│   ├── test_config.py      # Configuration tests
│   └── test_proxy.py       # Proxy functionality tests
└── integration/            # Integration tests (require network)
    ├── __init__.py
    └── test_e2e.py          # End-to-end integration tests
```

## Running Tests

### Prerequisites

1. Install test dependencies:
   ```bash
   uv sync --extra test
   ```

2. For integration tests, set up authentication:
   ```bash
   export WEAVE_TEST_TOKEN="your_weavemcp_api_token"
   ```

### Running Different Test Types

**Run all tests:**
```bash
uv run pytest
```

**Run only unit tests (fast, no network required):**
```bash
uv run pytest -m unit
```

**Run only integration tests (requires network and token):**
```bash
uv run pytest -m integration
```

**Run with verbose output:**
```bash
uv run pytest -v
```

**Run specific test file:**
```bash
uv run pytest tests/unit/test_auth.py
```

**Run specific test:**
```bash
uv run pytest tests/unit/test_auth.py::TestLoginCommand::test_login_manual_token_success
```

## Test Categories

### Unit Tests (`tests/unit/`)

Unit tests are isolated and don't require network access. They use mocked dependencies and test individual components.

**test_auth.py:**
- Login command with manual token entry
- Login command with browser OAuth flow
- Server management (add, remove, switch, list)
- Authentication helper functions
- Error handling for various scenarios

**test_config.py:**
- Setup command for Claude Desktop configuration
- Status command for checking configuration
- Remove command for cleaning up servers
- Upgrade command for updating old configurations
- Claude Desktop config file manipulation

**test_proxy.py:**
- Proxy command functionality
- MCP proxy client creation and management
- Proxy server startup and shutdown
- STDIO transport and HTTP communication
- Error handling and cleanup

### Integration Tests (`tests/integration/`)

Integration tests require network access and may need authentication tokens. They test the complete workflow against real or staging servers.

**test_e2e.py:**
- Full workflow: login → setup → status
- Real API connectivity testing
- Server management with actual WeaveMCP servers
- Proxy connection to virtual servers
- Configuration validation and cleanup
- Error handling for network issues

## Test Configuration

### Environment Variables

- `WEAVE_TEST_TOKEN`: API token for integration testing with atlaslabs.weavemcp.app
- `WEAVE_TEST_SERVER_URL`: Override default test server URL (default: https://atlaslabs.weavemcp.app)

### Pytest Markers

- `@pytest.mark.unit`: Unit tests (isolated, no network)
- `@pytest.mark.integration`: Integration tests (require network)
- `@pytest.mark.slow`: Tests that take longer to run

### Test Fixtures

**Configuration Fixtures:**
- `temp_config_dir`: Temporary directory for WeaveMCP config
- `temp_claude_config`: Temporary Claude Desktop config file
- `mock_config`: Mocked WeaveMCP configuration
- `sample_server_config`: Sample server configuration data

**Mock Fixtures:**
- `mock_api_client`: Mocked WeaveMCP API client
- `mock_auth_server`: Mocked OAuth authentication server
- `mock_webbrowser`: Mocked browser opening

**Integration Fixtures:**
- `integration_server_url`: URL for integration testing
- `integration_token`: Token for integration testing
- `skip_if_no_integration_token`: Skip test if no token available

## Writing New Tests

### Unit Test Example

```python
import pytest
from click.testing import CliRunner
from weave.cli import login

def test_login_success(mock_config, mock_webbrowser):
    """Test successful login"""
    runner = CliRunner()
    
    with patch("weave.cli.AuthServer") as mock_auth_server:
        # Setup mocks
        mock_auth_server.return_value.__enter__.return_value.wait_for_callback.return_value = ("token", "url")
        
        result = runner.invoke(login, ["--server-url", "https://test.com"])
        
        assert result.exit_code == 0
        assert "Successfully logged in" in result.output
```

### Integration Test Example

```python
@pytest.mark.integration
def test_api_connectivity(integration_server_url, skip_if_no_integration_token, integration_token):
    """Test real API connectivity"""
    from weave.api_client import WeaveMCPClient
    
    client = WeaveMCPClient(integration_server_url, integration_token)
    success, error = client.test_connection()
    
    if not success:
        pytest.skip(f"API connection failed: {error}")
    
    assert success is True
```

### Mock Usage

```python
from tests.fixtures.mocks import MockWeaveMCPClient

def test_with_mock_client():
    """Test using mock client"""
    mock_client = MockWeaveMCPClient()
    mock_client.set_failure_mode(True, "unauthorized")
    
    success, error = mock_client.test_connection()
    assert success is False
    assert "unauthorized" in error
```

## Test Data

Test data is centralized in `tests/fixtures/test_data.py`:

- `SAMPLE_ORGANIZATIONS_RESPONSE`: Mock API response for organizations
- `SAMPLE_DEFAULT_SERVER_RESPONSE`: Mock API response for default server
- `CLAUDE_CONFIG_*`: Various Claude Desktop configuration scenarios
- `TEST_SERVER_URLS`: Test server URLs for different environments
- `TEST_API_TOKENS`: Test tokens for various scenarios

## Troubleshooting

### Common Issues

**Tests fail with "No module named 'weave'":**
```bash
# Make sure you're running with uv
uv run pytest

# Or install in development mode
uv pip install -e .
```

**Integration tests skipped:**
```bash
# Set the integration token
export WEAVE_TEST_TOKEN="your_token_here"

# Or run without integration tests
uv run pytest -m "not integration"
```

**Tests hang during proxy testing:**
```bash
# Proxy tests use mocks by default, but if hanging:
# Check for missing async/await in test code
# Ensure proper cleanup in fixtures
```

### Debugging Tests

**Run with pdb debugger:**
```bash
uv run pytest --pdb
```

**Show print statements:**
```bash
uv run pytest -s
```

**Show coverage:**
```bash
uv run pytest --cov=weave --cov-report=html
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1
      
      - name: Install dependencies
        run: uv sync --extra test
      
      - name: Run unit tests
        run: uv run pytest -m unit
      
      - name: Run integration tests
        env:
          WEAVE_TEST_TOKEN: ${{ secrets.WEAVE_TEST_TOKEN }}
        run: uv run pytest -m integration
```

### Test Coverage Goals

- **Unit test coverage**: > 90% for core functionality
- **Integration test coverage**: All major user workflows
- **Error path coverage**: Common error scenarios and edge cases

## Performance Considerations

- Unit tests should complete in < 5 seconds total
- Integration tests may take 30-60 seconds depending on network
- Use `@pytest.mark.slow` for tests that take > 10 seconds
- Mock network calls in unit tests to maintain speed

## Best Practices

1. **Use descriptive test names** that explain what is being tested
2. **One assertion per test** when possible for clear failure messages
3. **Use fixtures** for common setup to avoid repetition
4. **Mock external dependencies** in unit tests
5. **Test both success and failure paths**
6. **Clean up resources** in test fixtures and teardown
7. **Use appropriate markers** (`unit`, `integration`, `slow`)
8. **Document complex test scenarios** with comments