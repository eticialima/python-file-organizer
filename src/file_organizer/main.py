import argparse
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


console = Console()
DATABASE = Path("organizer.db")

EXTENSION_GROUPS = {
    "images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
    "documents": {".txt", ".md", ".pdf", ".doc", ".docx", ".csv", ".xlsx"},
    "archives": {".zip", ".tar", ".gz", ".rar", ".7z"},
    "audio": {".mp3", ".wav", ".ogg"},
    "video": {".mp4", ".mov", ".mkv"},
    "code": {".py", ".js", ".ts", ".html", ".css", ".json"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize files automatically with watchdog and pathlib.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    watch_parser = subparsers.add_parser("watch", help="Watch a folder and organize new files.")
    add_common_options(watch_parser)

    once_parser = subparsers.add_parser("organize-once", help="Organize files already in the source folder.")
    add_common_options(once_parser)

    history_parser = subparsers.add_parser("history", help="Show recently moved files.")
    history_parser.add_argument("--limit", type=int, default=10, help="How many rows to show.")

    return parser.parse_args()


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", type=Path, default=Path("inbox"), help="Folder to watch or scan.")
    parser.add_argument("--target", type=Path, default=Path("organized"), help="Folder that receives organized files.")


def category_for(path: Path) -> str:
    suffix = path.suffix.lower()

    for category, extensions in EXTENSION_GROUPS.items():
        if suffix in extensions:
            return category

    return "others"


def unique_destination(destination: Path) -> Path:
    if not destination.exists():
        return destination

    # Evita sobrescrever: "photo.jpg" vira "photo-1.jpg", "photo-2.jpg", etc.
    counter = 1
    while True:
        candidate = destination.with_name(f"{destination.stem}-{counter}{destination.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def wait_until_ready(path: Path, retries: int = 10, delay: float = 0.2) -> bool:
    last_size = -1

    for _ in range(retries):
        if not path.exists() or not path.is_file():
            return False

        current_size = path.stat().st_size
        if current_size == last_size:
            return True

        last_size = current_size
        time.sleep(delay)

    return True


def init_db() -> None:
    # SQLite fica em um arquivo local simples, sem servidor e sem configuracao.
    with sqlite3.connect(DATABASE) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                destination TEXT NOT NULL,
                category TEXT NOT NULL,
                moved_at TEXT NOT NULL
            )
            """
        )


def record_move(source: Path, destination: Path, category: str) -> None:
    init_db()
    with sqlite3.connect(DATABASE) as connection:
        connection.execute(
            "INSERT INTO moves (source, destination, category, moved_at) VALUES (?, ?, ?, ?)",
            (str(source), str(destination), category, datetime.now().isoformat(timespec="seconds")),
        )


def fetch_history(limit: int) -> list[tuple[str, str, str, str]]:
    init_db()
    with sqlite3.connect(DATABASE) as connection:
        cursor = connection.execute(
            """
            SELECT source, destination, category, moved_at
            FROM moves
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return list(cursor.fetchall())


def organize_file(path: Path, target: Path) -> Path | None:
    if not path.is_file():
        return None

    if path.name.startswith("."):
        return None

    if not wait_until_ready(path):
        return None

    category = category_for(path)
    category_dir = target / category
    category_dir.mkdir(parents=True, exist_ok=True)

    destination = unique_destination(category_dir / path.name)
    shutil.move(str(path), destination)
    record_move(path, destination, category)
    return destination


def organize_once(source: Path, target: Path) -> list[tuple[Path, Path]]:
    source.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)

    moved = []
    for path in sorted(source.iterdir()):
        destination = organize_file(path, target)
        if destination:
            moved.append((path, destination))

    return moved


def print_moved_files(moved: list[tuple[Path, Path]]) -> None:
    if not moved:
        console.print("[yellow]No files to organize.[/yellow]")
        return

    table = Table(title="Moved Files")
    table.add_column("From")
    table.add_column("To")

    for source, destination in moved:
        table.add_row(str(source), str(destination))

    console.print(table)


def print_history(limit: int) -> None:
    rows = fetch_history(limit)

    if not rows:
        console.print("[yellow]No history yet.[/yellow]")
        return

    table = Table(title="Move History")
    table.add_column("Moved At")
    table.add_column("Category")
    table.add_column("From")
    table.add_column("To")

    for source, destination, category, moved_at in rows:
        table.add_row(moved_at, category, source, destination)

    console.print(table)


class OrganizerHandler(FileSystemEventHandler):
    def __init__(self, target: Path) -> None:
        self.target = target

    def on_created(self, event) -> None:
        # O watchdog chama esse metodo sempre que algo novo aparece na pasta.
        if event.is_directory:
            return

        source = Path(event.src_path)
        destination = organize_file(source, self.target)

        if destination:
            console.print(f"[green]Moved[/green] {source.name} -> {destination}")


def watch(source: Path, target: Path) -> None:
    source.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)

    handler = OrganizerHandler(target)
    observer = Observer()
    observer.schedule(handler, str(source), recursive=False)
    observer.start()

    console.print(Panel.fit(f"Watching [bold]{source}[/bold]\nOrganizing into [bold]{target}[/bold]", title="File Organizer"))

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("[yellow]Stopping watcher...[/yellow]")
        observer.stop()

    observer.join()


def main() -> None:
    args = parse_args()

    if args.command == "organize-once":
        moved = organize_once(args.source, args.target)
        print_moved_files(moved)
        return

    if args.command == "history":
        print_history(args.limit)
        return

    if args.command == "watch":
        watch(args.source, args.target)
