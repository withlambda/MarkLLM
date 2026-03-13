# `utils.py`

## Context
A utility module for file and directory validation. It provides helper functions starting with `check` and `is` to ensure the integrity of the input and output paths before processing.

## Interfaces

### Functions

#### `check_is_dir(path: str) -> None`
Checks if the given path is a directory.

```python
def check_is_dir(path: str) -> None:
```
*   **Args**: `path` (str) - The path to check.
*   **Raises**: `NotADirectoryError` if the path exists but is not a directory.

#### `check_is_not_file(path: str) -> None`
Checks if the given path is not a file.

```python
def check_is_not_file(path: str) -> None:
```
*   **Args**: `path` (str) - The path to check.
*   **Raises**: `ValueError` if the path exists and is a file.

#### `check_no_subdirs(path: str) -> None`
Ensures the given directory contains no subdirectories (excluding hidden ones).

```python
def check_no_subdirs(path: str) -> None:
```
*   **Args**: `path` (str) - The directory path.
*   **Raises**: `ValueError` if any non-hidden subdirectories are found.

#### `is_empty_dir(path: str) -> bool`
Checks if a directory is empty, ignoring hidden files.

```python
def is_empty_dir(path: str) -> bool:
```
*   **Args**: `path` (str) - The directory path.
*   **Returns**: `bool` - `True` if the directory is empty, `False` otherwise.

#### `check_is_empty_dir(path: str) -> None`
Checks if a directory is empty if it exists.

```python
def check_is_empty_dir(path: str) -> None:
```
*   **Args**: `path` (str) - The directory path.
*   **Raises**: `ValueError` if the directory exists and is not empty.

## Logic
These functions primarily rely on the `os` and `pathlib` modules to perform filesystem checks. They are designed to provide consistent error reporting for path-related validations.

## Dependencies
*   `os`
*   `pathlib.Path`
