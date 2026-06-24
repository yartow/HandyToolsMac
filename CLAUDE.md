# HandyToolsMac — Developer Notes

## Repository Overview

A collection of standalone utility scripts and tools for macOS and Linux.
Each tool lives in its own numbered directory and is self-contained.

---

## Code Style (all tools)

- Shebang: `#!/usr/bin/env python3`
- Module docstring immediately after shebang
- CONFIG block delimited by `# ----- CONFIG -----` / `# ---------` comments
- Type hints on all functions
- `print()`-based progress (no logging framework)
- No comments unless the WHY is non-obvious
