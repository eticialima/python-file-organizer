# Python File Organizer

A small automation project using `watchdog` and `pathlib`.

It watches an `inbox/` folder. When a file appears, the script moves it into `organized/` based on the file extension.

## Install

```bash
cd python-file-organizer
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Process Existing Files Once

```bash
file-organizer organize-once
```

## Watch For New Files

```bash
file-organizer watch
```

Then, in another terminal, create test files:

```bash
touch inbox/photo.jpg
touch inbox/notes.txt
touch inbox/archive.zip
```

The files will be moved to:

```txt
organized/images/photo.jpg
organized/documents/notes.txt
organized/archives/archive.zip
```

## Custom Folders

```bash
file-organizer watch --source ~/Downloads --target ~/Organized
file-organizer organize-once --source ./inbox --target ./organized
```

## What It Shows

- `watchdog`: listens for filesystem events.
- `pathlib`: handles paths in a clean, cross-platform way.
- `rich`: prints friendly logs and tables.
