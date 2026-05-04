# Ruabot Test Suite

Comprehensive test suite for the Ruabot QQ Bot framework.

## Installation

Install test dependencies:

```bash
pip install pytest pytest-asyncio pytest-cov
```

## Running Tests

### Interactive Test Runner

Run the interactive test menu:

```bash
python tests/run_tests.py
```

This will display a menu with the following options:

1. **Core Module Tests** - Test core functionality (app, event_bus, config, database, storage)
2. **AI Module Tests** - Test AI functionality (ai_manager, model_manager, llm_client)
3. **Protocol Module Tests** - Test protocol adapters (OneBot, base protocol)
4. **Router Module Tests** - Test routing functionality (rules, handlers)
5. **Security Module Tests** - Test security features (auth, permissions, access control)
6. **Plugins Module Tests** - Test plugin system (interceptors, runtime)
7. **Run All Tests** - Execute all test suites sequentially
8. **Run All Tests with Coverage** - Execute all tests with code coverage report
9. **Run Failed Tests Only** - Re-run only the tests that failed
10. **List All Tests** - Display all available tests without running them
11. **Run Tests in Parallel** - Execute tests in parallel using pytest-xdist
12. **Run Tests with Detailed Output** - Execute tests with very verbose output

### Quick Test Options

From the main menu, type 'quick' or 'q' to access quick test options:

1. **Smoke Tests** - Quick sanity checks for critical functionality
2. **Unit Tests Only** - Run only unit tests (no integration tests)
3. **Integration Tests Only** - Run only integration tests
4. **Fast Tests Only** - Run only fast tests (skip slow ones)

### Command Line Options

You can also run tests directly using pytest:

```bash
# Run all tests
pytest tests/ -v

# Run specific test module
pytest tests/test_core/ -v

# Run specific test file
pytest tests/test_core/test_event_bus.py -v

# Run specific test
pytest tests/test_core/test_event_bus.py::TestEventBus::test_event_bus_initialization -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term

# Run in parallel (requires pytest-xdist)
pytest tests/ -n auto

# Run failed tests only
pytest tests/ --lf
```

## Test Structure

```
tests/
├── __init__.py
├── run_tests.py               # Interactive test runner
├── README.md                  # This file
├── test_core/                 # Core module tests
│   ├── __init__.py
│   ├── test_app.py            # Application lifecycle tests
│   ├── test_config_paths.py   # Runtime path tests
│   ├── test_config.py         # Configuration tests
│   ├── test_database.py       # Database tests
│   ├── test_event_bus.py      # Event bus tests
│   └── test_storage.py        # Storage tests
├── test_protocol/             # Protocol module tests
│   ├── __init__.py
│   └── test_onebot.py         # OneBot adapter tests
├── test_plugins/              # Plugins module tests
│   ├── __init__.py
│   ├── test_interceptor.py    # Interceptor tests
│   ├── test_manifest.py       # Manifest loading tests
│   ├── test_plugin_config_types.py
│   ├── test_runtime_connector.py
│   ├── test_runtime_handler.py
│   └── test_runtime_main_paths.py
├── test_sandbox/              # Sandbox module tests
│   └── test_local_shell_state.py
├── test_napcat/               # NapCat management tests
│   └── test_manager_config_persistence.py
└── test_ui/                   # Web UI API tests
    └── test_api_onebot_connectivity.py
```

## Writing Tests

### Test Organization

- Tests are organized by module under the `tests/` directory
- Each module has its own directory with `__init__.py`
- Test files are named `test_<module>.py`
- Test classes are named `Test<ClassName>`
- Test methods are named `test_<functionality>`

### Using Fixtures

Fixtures are defined in `tests/conftest.py` and can be used in any test:

```python
@pytest.mark.asyncio
async def test_my_feature(mock_event_bus, sample_message_event):
    # Use the fixtures
    await mock_event_bus.publish("test.event", sample_message_event)
```

### Async Tests

Use `@pytest.mark.asyncio` decorator for async tests:

```python
@pytest.mark.asyncio
async def test_async_functionality():
    result = await async_function()
    assert result is not None
```

### Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.unit
def test_unit_test():
    pass

@pytest.mark.integration
def test_integration_test():
    pass

@pytest.mark.slow
def test_slow_test():
    pass

@pytest.mark.smoke
def test_smoke_test():
    pass
```

## Coverage Reports

Generate coverage reports:

```bash
# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html

# View the report
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
xdg-open htmlcov/index.html # Linux
```

## Troubleshooting

### Tests Fail with Import Errors

Ensure you're running from the project root directory:

```bash
cd /path/to/XQNEXT
python tests/run_tests.py
```

### Async Tests Fail

Make sure pytest-asyncio is installed:

```bash
pip install pytest-asyncio
```

### Database Tests Fail

Database tests use in-memory SQLite databases and should not require any setup. If you encounter issues, ensure SQLite is available.

### Permission Errors

Make sure you have write permissions in the project directory for temporary test files.

## Contributing

When adding new features:

1. Write tests for the new functionality
2. Ensure all existing tests pass
3. Add documentation for new tests
4. Update this README if adding new test modules

## Best Practices

- Keep tests focused on a single functionality
- Use descriptive test names
- Mock external dependencies
- Clean up resources in fixtures
- Use pytest fixtures for common setup
- Write both positive and negative test cases
- Test edge cases and error conditions
- Keep tests fast and independent
