# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A collection of custom SideFX Houdini shelf tools written in Python. These scripts run inside Houdini's embedded Python interpreter (using the `hou` module) and are not standalone Python programs — they cannot be executed or tested outside of Houdini.

## Architecture

### Shelf Registration

`toolbar/mijo_tools.shelf` is an XML file that registers three tools in Houdini's shelf UI. Each tool entry uses `import` + `reload()` to hot-reload the corresponding Python module from `shelf_by_python/`, enabling rapid iteration without restarting Houdini.

### Tool Scripts (`shelf_by_python/`)

All scripts depend on the `hou` module (Houdini's Python API) and operate on the current scene/selection:

- **shelf_LocalCache.py** — Fusion-style local cache tool. Copies filecache node outputs between network drives and local drives using `robocopy` (Windows-specific). Creates companion `file` nodes pointing to the cached location. Uses drive letter matching (`localDrivers` list) to distinguish local vs network paths.
- **shelf_prj_abc_cam_preset_1.py** — Recursively scans selected node hierarchy for camera nodes and batch-sets resolution, aspect ratio, clipping, and shutter parameters.
- **shelf_Auto_show_info_on_comment.py** — For selected nodes, extracts useful info (e.g., fetch source path) and writes it into the node's comment field for quick visibility.

## Development Notes

- There is no build step, linter, or test suite. Development is done by editing scripts and using `reload()` in Houdini.
- All scripts assume a Windows environment (drive letters, backslash handling, `robocopy`).
- The `shelf_by_python/` directory must be on Houdini's `PYTHONPATH` for the shelf imports to work.
- Comments and UI strings are in Chinese (Traditional/Simplified).
