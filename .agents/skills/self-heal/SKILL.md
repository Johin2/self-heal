# self-heal Development Patterns

> Auto-generated skill from repository analysis (manually corrected)

## Overview
This skill teaches you the development patterns and conventions used in the `self-heal` Python repository. You'll learn how to structure files, write imports and exports, follow commit message conventions, and write tests in alignment with the project's established practices.

## Coding Conventions

### File Naming
- Use **snake_case** for file names.
  - **Example:** `retry.py`, `loop.py`, `self_heal_core.py`

### Import Style
- Use **absolute imports** for the public package API and **relative imports** within a sub-package where appropriate.
  - **Example:**
    ```python
    from self_heal.retry import RetryConfig, with_retry
    from self_heal.events import emit, RepairEvent
    ```

### Export Style
- Use `__all__` to declare the public API explicitly.
  - **Example:**
    ```python
    __all__ = ["RepairLoop", "RetryConfig", "RepairResult"]
    ```

### Commit Messages
- Follow **conventional commit** format.
- Common prefixes: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.
  - **Examples:**
    ```
    fix(retry): use word-boundary regex for status code detection
    docs(contributing): add a "claim an issue" convention
    ```

## Testing Patterns

- **Framework:** pytest
- **Test location:** `tests/` directory at the repo root
- **File naming:** `test_<module>.py` (e.g., `test_retry.py`, `test_loop.py`)
- **Run tests:** `pytest` or `python -m pytest`
- **Run with coverage:** `pytest --cov=src --cov-report=term-missing`

Example test:
```python
# tests/test_retry.py
import pytest
from self_heal.retry import RetryConfig, with_retry

def test_with_retry_returns_immediately_on_success():
    result = with_retry(lambda: "ok", RetryConfig(max_retries=3))
    assert result == "ok"
```

## Workflows

### Add a New Module
1. Create a new file using snake_case naming (e.g., `new_feature.py`) under `src/self_heal/`.
2. Add the public symbols to `src/self_heal/__init__.py`'s `__all__`.
3. Write tests in `tests/test_<module>.py`.
4. Commit using conventional commit format.

### Write Tests
1. Create `tests/test_<module>.py`.
2. Import from the public `self_heal` package or from `self_heal.<module>` directly.
3. Use `pytest` fixtures and `unittest.mock.patch` for side effects.
4. Run `pytest` to verify all tests pass.

## Commands
| Command           | Purpose                                      |
|-------------------|----------------------------------------------|
| /commit-changes   | Guide for committing code or doc changes     |
| /add-module       | Steps for adding a new module                |
| /write-tests      | Instructions for writing and running tests   |
