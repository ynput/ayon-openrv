# OpenRV Typing Stubs

This directory contains type stubs for the RV API to enable better IDE integration and type checking. This had been generated  from [`main`](https://github.com/AcademySoftwareFoundation/OpenRV/blob/673f2b7d37c222ab0400105163a466131102ab1f/src/lib/app/RvApp/CommandsModule.cpp) branch
at 25/05/22

## How to Use

### 1. Update your pyproject.toml

To make these typing stubs available to your IDE, add the ayon_openrv typing directory to your `pyproject.toml` file. Add this path to the `extraPaths` section of your `executionEnvironments`:

```toml
[tool.pyright]
executionEnvironments = [
    { root = ".", extraPaths = [
        # ... existing paths
        "ayon-openrv/client",
        # ... other paths
    ] },
]
```

### 2. Import in your code

When writing code that uses RV modules, you can import them as usual:

```python
import rv.commands
import rv.qtutils
import rv.rvtypes
```

The type stubs will provide autocomplete and type checking in compatible IDEs.

### 3. Type annotations in your code

You can use type annotations in your code:

```python
def my_function(node: str) -> None:
    """Example function using RV commands with type annotations."""
    # RV commands will have proper type hints
    current_frame = rv.commands.frame()
    rv.commands.setStringProperty(f"{node}.name", ["my_name"], True)
```

## What's Included

- `rv.commands` - Core RV commands module with functions for managing sources, properties, etc.
- `rv.qtutils` - Qt utility functions for interacting with the RV UI
- `rv.rvtypes` - Base types used by RV for creating packages and modes
- `rv.extra_commands` - Additional RV commands, such as annotation management

## Notes

- These stubs are based on the OpenRV version 2023.0.0 API
- Not all functions may be fully typed yet - contributions welcome!
- If you find discrepancies between the stubs and actual behavior, please report them
