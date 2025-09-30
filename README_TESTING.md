# Testing Guide for Agent PM

This document describes the testing infrastructure and how to run tests.

## Overview

The project has comprehensive test coverage for both backend (Python/Flask) and frontend (React/TypeScript).

### Test Statistics
- **Backend**: ~70+ tests covering routes, managers, DTOs, and utilities
- **Frontend**: ~35+ tests covering dataProvider, authProvider, and components
- **Test Framework**: pytest (backend), Jest + React Testing Library (frontend)
- **Coverage Target**: >80% code coverage

## Running Tests

### Backend Tests (Python)

```bash
# Run all backend tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/routes/test_learnings.py

# Run tests matching a pattern
pytest -k "test_create"

# Run with verbose output
pytest -v

# Run only unit tests (fast)
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Frontend Tests (React)

```bash
cd frontend

# Run all tests
npm test

# Run tests with coverage
npm test -- --coverage

# Run tests in watch mode
npm test -- --watch

# Run specific test file
npm test -- dataProvider.test.ts

# Update snapshots
npm test -- -u
```

## Test Structure

### Backend (`/tests`)

```
tests/
├── conftest.py              # Shared fixtures
├── routes/
│   ├── test_auth.py         # Authentication endpoints
│   ├── test_health.py       # Health check endpoints
│   ├── test_jira.py         # Jira integration endpoints
│   ├── test_learnings.py    # Learning management endpoints
│   └── test_todos.py        # Todo management endpoints
├── managers/
│   └── test_learning_manager.py  # Business logic tests
├── models/
│   └── test_dtos.py         # Data transfer object tests
└── utils/
    └── test_encryption.py   # Utility function tests
```

### Frontend (`/frontend/src`)

```
frontend/src/
├── dataProvider.test.ts     # API data layer tests
├── authProvider.test.ts     # Authentication tests
└── App.test.tsx             # Component tests
```

## Test Fixtures

Common test fixtures are defined in `tests/conftest.py`:

- `app`: Flask application instance
- `client`: Flask test client
- `db_engine`: In-memory database engine
- `db_session`: Database session
- `mock_user`: Sample user for testing
- `mock_admin_user`: Sample admin user
- `sample_learning`: Sample learning entry
- `sample_todo`: Sample todo item
- `mock_jira_client`: Mocked Jira client
- `mock_fireflies_client`: Mocked Fireflies client

## Writing New Tests

### Backend Test Example

```python
def test_create_learning(client, mocker):
    """Test creating a new learning."""
    mocker.patch('src.routes.learnings.auth_required', lambda f: f)

    mock_manager = mocker.patch('src.routes.learnings.LearningManager')
    mock_manager.return_value.create_learning.return_value = Mock(
        to_dict=lambda: {'id': 1, 'content': 'Test'}
    )

    response = client.post('/api/learnings', json={
        'content': 'New learning',
        'category': 'technical'
    })

    assert response.status_code == 200
    assert response.json['success'] is True
```

### Frontend Test Example

```typescript
it('should fetch and return meeting data', async () => {
    const mockResponse = {
        json: { data: [{ id: 1, title: 'Meeting 1' }], total: 1 },
        status: 200
    };

    mockFetchJson.mockResolvedValueOnce(mockResponse);

    const result = await dataProvider.getList('meetings', {
        pagination: { page: 1, perPage: 10 },
        sort: { field: 'date', order: 'DESC' },
        filter: {}
    });

    expect(result.data).toHaveLength(1);
    expect(result.total).toBe(1);
});
```

## Test Markers

Backend tests can be marked with custom markers:

```python
@pytest.mark.unit
def test_something():
    pass

@pytest.mark.integration
@pytest.mark.requires_api
def test_api_integration():
    pass

@pytest.mark.slow
def test_slow_operation():
    pass
```

Run specific markers:
```bash
pytest -m unit          # Run only unit tests
pytest -m "not slow"    # Skip slow tests
```

## Continuous Integration

Tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`

CI Pipeline includes:
1. Backend tests with coverage
2. Frontend tests with coverage
3. Linting (flake8, black, ESLint)
4. Type checking (mypy)
5. Integration tests (on main branch only)

View CI status: `.github/workflows/tests.yml`

## Coverage Reports

### Backend Coverage

After running `pytest --cov`, view HTML report:
```bash
open htmlcov/index.html
```

### Frontend Coverage

After running `npm test -- --coverage`:
```bash
open frontend/coverage/lcov-report/index.html
```

## Mocking External Services

### Jira API
```python
def test_with_jira(mocker):
    mock_jira = mocker.patch('src.routes.jira.JiraMCPClient')
    mock_instance = mock_jira.return_value.__aenter__.return_value
    mock_instance.get_projects = AsyncMock(return_value=[...])
```

### Fireflies API
```python
def test_with_fireflies(mock_fireflies_client):
    mock_fireflies_client.get_transcripts.return_value = [...]
```

### Database
```python
def test_with_db(db_session, sample_learning):
    # sample_learning is automatically in db_session
    learning = db_session.query(Learning).first()
```

## Best Practices

1. **Test Naming**: Use descriptive names starting with `test_`
2. **Arrange-Act-Assert**: Structure tests clearly
3. **Mock External Dependencies**: Don't make real API calls
4. **Use Fixtures**: Reuse common test data
5. **Test Edge Cases**: Not just happy path
6. **Keep Tests Fast**: Use in-memory database
7. **Isolate Tests**: Each test should be independent
8. **Coverage Goals**: Aim for >80% coverage

## Troubleshooting

### Import Errors
```bash
# Make sure you're in the project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Database Errors
```bash
# Tests use in-memory SQLite, no setup needed
# If you see errors, check conftest.py fixtures
```

### Frontend Test Fails
```bash
# Clear Jest cache
cd frontend
npm test -- --clearCache
```

### Async Test Issues
```python
# Use pytest-asyncio for async tests
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result
```

## Next Steps

- [ ] Add E2E tests with Playwright
- [ ] Add performance tests
- [ ] Add security tests
- [ ] Increase coverage to 90%
- [ ] Add mutation testing

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [Jest documentation](https://jestjs.io/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Best Practices](https://testingjavascript.com/)
