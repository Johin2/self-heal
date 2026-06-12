```markdown
# self-heal Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the development patterns and conventions used in the `self-heal` Python repository. You'll learn how to structure files, write imports and exports, follow commit message conventions, and write tests in alignment with the project's established practices. This guide is ideal for contributors seeking to maintain consistency and code quality in the `self-heal` codebase.

## Coding Conventions

### File Naming
- Use **camelCase** for file names.
  - **Example:** `selfHealCore.py`, `errorHandler.py`

### Import Style
- Use **relative imports** within the package.
  - **Example:**
    ```python
    from .utils import parseData
    from .errorHandler import handleError
    ```

### Export Style
- Use **named exports** (explicitly listing what is exported).
  - **Example:**
    ```python
    __all__ = ['selfHealCore', 'handleError']
    ```

### Commit Messages
- Follow **conventional commit** format.
- Use prefixes like `docs` and `fix`.
- Keep commit messages concise (average ~57 characters).
  - **Examples:**
    ```
    docs: update README with installation instructions
    fix: handle edge case in selfHealCore.py
    ```

## Workflows

### Commit Changes
**Trigger:** When making any code or documentation changes.
**Command:** `/commit-changes`

1. Make your code or documentation updates.
2. Stage your changes with `git add`.
3. Write a commit message using the conventional commit format:
   - Prefix with `docs:` for documentation changes.
   - Prefix with `fix:` for bug fixes.
4. Keep the commit message concise and descriptive.
5. Commit your changes.

### Add a New Module
**Trigger:** When adding new functionality to the codebase.
**Command:** `/add-module`

1. Create a new file using camelCase naming (e.g., `newFeature.py`).
2. Use relative imports to bring in dependencies from within the package.
3. Explicitly list new exports in the module's `__all__` variable.
4. Write or update tests for the new module (see Testing Patterns).
5. Commit your changes using the conventional commit format.

### Write Tests
**Trigger:** When adding or updating code that requires testing.
**Command:** `/write-tests`

1. Create a test file matching the pattern `*.test.*` (e.g., `selfHealCore.test.py`).
2. Write test cases for new or modified functionality.
3. Use the project's preferred (but currently unknown) testing framework.
4. Run tests to ensure correctness.
5. Commit your test files.

## Testing Patterns

- Test files follow the pattern `*.test.*` (e.g., `module.test.py`).
- The specific testing framework is not detected; review existing test files for framework clues.
- Place tests close to the code they cover or in a dedicated test directory.
- Example test file:
  ```python
  # selfHealCore.test.py
  from .selfHealCore import someFunction

  def test_someFunction():
      assert someFunction(2) == 4
  ```

## Commands
| Command           | Purpose                                      |
|-------------------|----------------------------------------------|
| /commit-changes   | Guide for committing code or doc changes     |
| /add-module       | Steps for adding a new module                |
| /write-tests      | Instructions for writing and running tests   |
```
