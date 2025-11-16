"""
organizer_downloads_advanced.py
Advanced Downloads Organizer (GUI + CLI + Watch + Config + Logging + Summary)

Usage:
    python organizer_downloads_advanced.py        # GUI mode (default)
    python organizer_downloads_advanced.py --run  # headless immediate organize
    python organizer_downloads_advanced.py --watch # headless watch mode
"""

import os
import shutil
import time
import json
import threading
import argparse
from datetime import datetime
from pathlib import Path
import logging
import sys

# Colored terminal output
try:
    import colorama
    from colorama import Fore, Style
    colorama.init()
except Exception:
    # fallback: define no-op colors
    class _C:
        def __getattr__(self, name): return ""
    Fore = Style = _C()

# optional GUI + watchdog imports (only required for GUI/watch)
GUI_AVAILABLE = True
WATCHDOG_AVAILABLE = True
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except Exception:
    GUI_AVAILABLE = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except Exception:
    WATCHDOG_AVAILABLE = False

# ----------------------------
# Paths & defaults
# ----------------------------
HOME = Path.home()
DEFAULT_TARGET = HOME / "Downloads"
CONFIG_FILE = Path.cwd() / "organizer_config.json"
LOG_DIR = Path.cwd() / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "organizer.log"

# ----------------------------
# Default file type mapping
# ----------------------------
DEFAULT_RULES = {
    "Images": ["jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "heic"],
    "Videos": ["mp4", "mkv", "mov", "avi", "webm"],
    "Audio": ["mp3", "wav", "flac", "aac", "m4a"],
    "Documents": ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "rtf"],
    "Archives": ["zip", "rar", "7z", "tar", "gz", "bz2"],
    "Code": ["js", "jsx", "ts", "tsx", "py", "java", "c", "cpp", "html", "css", "json"],
    "Installers": ["exe", "msi", "deb", "rpm"],
    "Others": []
}

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(console_handler)


# ----------------------------
# Stats helper
# ----------------------------
def make_stats():
    return {
        "scanned": 0,
        "folders_created": 0,
        "files_moved": 0,
        "folders_deleted": 0,
        "errors": 0
    }


def print_summary(stats):
    print("\n" + "=" * 70)
    print(Fore.CYAN + Style.BRIGHT + "📦 DOWNLOAD ORGANIZER - TASK SUMMARY" + Style.RESET_ALL)
    print("=" * 70)

    print(Fore.GREEN + f"✔ Total Files Scanned       : {stats.get('scanned', 0)}" + Style.RESET_ALL)
    print(Fore.YELLOW + f"📁 Folders Created           : {stats.get('folders_created', 0)}" + Style.RESET_ALL)
    print(Fore.BLUE + f"📂 Files Moved               : {stats.get('files_moved', 0)}" + Style.RESET_ALL)
    print(Fore.RED + f"🗑 Folders Deleted (empty)   : {stats.get('folders_deleted', 0)}" + Style.RESET_ALL)
    if stats.get("errors", 0):
        print(Fore.MAGENTA + f"⚠ Errors encountered         : {stats.get('errors', 0)}" + Style.RESET_ALL)
    print("=" * 70)
    print(Fore.MAGENTA + "🎉 Task Completed Successfully!" + Style.RESET_ALL)
    print("=" * 70)


# ----------------------------
# Utilities and config
# ----------------------------
def load_config():
    default_config = {
        "target_folder": str(DEFAULT_TARGET),
        "method": "type_date",   # type_date | date_type | type
        "recursive": False,
        "delete_empty": True,
        "watch_mode": False,
        "custom_rules": {}
    }
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            merged = default_config.copy()
            merged.update(cfg)
            return merged
        except Exception as e:
            logging.warning(f"Failed to parse config.json; using defaults: {e}")
            return default_config
    else:
        CONFIG_FILE.write_text(json.dumps(default_config, indent=2), encoding="utf-8")
        logging.info(f"Created default config at {CONFIG_FILE}")
        return default_config


def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    logging.info("Configuration saved.")


def normalize_ext(p: str):
    return p.lstrip(".").lower()


def month_name_from_ts(ts):
    return datetime.fromtimestamp(ts).strftime("%b")


def ensure_dir(p: Path, stats: dict):
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
        stats["folders_created"] += 1


def safe_move(src: Path, dest_dir: Path, stats: dict):
    """Move file to dest_dir safely. Auto-rename if exists. Returns new path or raises."""
    ensure_dir(dest_dir, stats)
    stats["scanned"] += 1
    dest = dest_dir / src.name
    try:
        if not dest.exists():
            shutil.move(str(src), str(dest))
            stats["files_moved"] += 1
            logging.info(f"MOVED: {src} -> {dest}")
            return dest
        # auto rename
        name = src.stem
        ext = src.suffix
        i = 1
        while True:
            candidate = dest_dir / f"{name} ({i}){ext}"
            if not candidate.exists():
                shutil.move(str(src), str(candidate))
                stats["files_moved"] += 1
                logging.info(f"MOVED (renamed): {src} -> {candidate}")
                return candidate
            i += 1
    except Exception as e:
        stats["errors"] += 1
        logging.exception(f"Failed to move {src}: {e}")
        raise


# ----------------------------
# Rule building & resolving
# ----------------------------
def build_rules(custom_rules: dict):
    rules = []
    if custom_rules:
        for k, v in custom_rules.items():
            rules.append((k, [normalize_ext(x) for x in v]))
    for k, v in DEFAULT_RULES.items():
        if k not in custom_rules:
            rules.append((k, [normalize_ext(x) for x in v]))
    return rules


def resolve_folder_for_ext(ext: str, ordered_rules):
    for folder, exts in ordered_rules:
        if ext in exts:
            return folder
    return "Others"


# ----------------------------
# Organization methods (accept stats)
# ----------------------------
def organize_by_type_then_date(path: Path, target: Path, ordered_rules, stats: dict):
    ext = normalize_ext(path.suffix)
    folder_name = resolve_folder_for_ext(ext, ordered_rules)
    ts = path.stat().st_mtime
    year = str(datetime.fromtimestamp(ts).year)
    mon = month_name_from_ts(ts)
    dest = Path(target) / folder_name / year / mon
    return safe_move(path, dest, stats)


def organize_by_date_then_type(path: Path, target: Path, ordered_rules, stats: dict):
    ts = path.stat().st_mtime
    year = str(datetime.fromtimestamp(ts).year)
    mon = month_name_from_ts(ts)
    ext = normalize_ext(path.suffix)
    folder_name = resolve_folder_for_ext(ext, ordered_rules)
    dest = Path(target) / year / mon / folder_name
    return safe_move(path, dest, stats)


def organize_flat_type(path: Path, target: Path, ordered_rules, stats: dict):
    ext = normalize_ext(path.suffix)
    folder_name = resolve_folder_for_ext(ext, ordered_rules)
    dest = Path(target) / folder_name
    return safe_move(path, dest, stats)


# ----------------------------
# Deep scan and main runner
# ----------------------------
def deep_scan_and_organize(target_folder: str, method: str, recursive: bool, delete_empty: bool, cfg_rules, stats: dict, logger=None):
    target = Path(target_folder)
    ordered_rules = build_rules(cfg_rules or {})
    if not target.exists():
        logging.error(f"Target folder does not exist: {target}")
        return

    # Walk top-level or recursive depending on flag (Downloads typically top-level)
    for root, dirs, files in os.walk(target):
        # skip moving files that are inside our created category folders to avoid loops
        rel_root = Path(root).relative_to(target)
        # get top-level dir name if present
        top_dir = rel_root.parts[0] if len(rel_root.parts) > 0 else None
        if top_dir and top_dir in [r[0] for r in ordered_rules]:
            if not recursive:
                # skip scanning inside already organized top-level categories
                continue

        for f in files:
            src = Path(root) / f
            try:
                if method == "type_date":
                    organize_by_type_then_date(src, target, ordered_rules, stats)
                elif method == "date_type":
                    organize_by_date_then_type(src, target, ordered_rules, stats)
                else:
                    organize_flat_type(src, target, ordered_rules, stats)
            except Exception as e:
                logging.exception(f"Failed to move {src}: {e}")
        if not recursive:
            break

    if delete_empty:
        delete_empty_folders(target, stats)


def delete_empty_folders(path: Path, stats: dict):
    # remove empty directories under path
    for root, dirs, files in os.walk(path, topdown=False):
        for d in dirs:
            full = Path(root) / d
            try:
                if not any(full.iterdir()):
                    full.rmdir()
                    stats["folders_deleted"] += 1
                    logging.info(f"DELETED EMPTY: {full}")
            except Exception:
                logging.debug(f"Could not delete folder: {full}")


# ----------------------------
# Watch handler
# ----------------------------
class NewFileHandler(FileSystemEventHandler):
    def __init__(self, target, method, recursive, delete_empty, ordered_rules, stats: dict):
        super().__init__()
        self.target = Path(target)
        self.method = method
        self.recursive = recursive
        self.delete_empty = delete_empty
        self.ordered_rules = ordered_rules
        self.stats = stats

    def on_created(self, event):
        # skip directories
        if event.is_directory:
            return
        time.sleep(0.8)  # let writing finish
        src = Path(event.src_path)
        try:
            if self.method == "type_date":
                organize_by_type_then_date(src, self.target, self.ordered_rules, self.stats)
            elif self.method == "date_type":
                organize_by_date_then_type(src, self.target, self.ordered_rules, self.stats)
            else:
                organize_flat_type(src, self.target, self.ordered_rules, self.stats)
            if self.delete_empty:
                # small cleanup if needed
                delete_empty_folders(self.target, self.stats)
        except Exception:
            logging.exception(f"Error handling new file {src}")


# ----------------------------
# GUI wrapper (if available)
# ----------------------------
if GUI_AVAILABLE:
    class OrganizerGUI(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Downloads Organizer - Advanced")
            self.geometry("820x600")
            cfg = load_config()

            self.target_var = tk.StringVar(value=cfg.get("target_folder", str(DEFAULT_TARGET)))
            self.method_var = tk.StringVar(value=cfg.get("method", "type_date"))
            self.recursive_var = tk.BooleanVar(value=cfg.get("recursive", False))
            self.delete_var = tk.BooleanVar(value=cfg.get("delete_empty", True))
            self.watch_var = tk.BooleanVar(value=cfg.get("watch_mode", False))
            self.custom_rules = cfg.get("custom_rules", {})

            self.observer = None
            self.stats = make_stats()

            self.create_widgets()

        def create_widgets(self):
            frm = ttk.Frame(self, padding=12)
            frm.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frm, text="Target Folder:").grid(column=0, row=0, sticky=tk.W)
            ttk.Entry(frm, width=68, textvariable=self.target_var).grid(column=1, row=0, columnspan=3, sticky=tk.W)
            ttk.Button(frm, text="Browse", command=self.browse).grid(column=4, row=0, padx=6)

            ttk.Label(frm, text="Organize Mode:").grid(column=0, row=1, sticky=tk.W, pady=(8,0))
            ttk.Radiobutton(frm, text="Type → Date", variable=self.method_var, value="type_date").grid(column=1, row=1, sticky=tk.W)
            ttk.Radiobutton(frm, text="Date → Type", variable=self.method_var, value="date_type").grid(column=2, row=1, sticky=tk.W)
            ttk.Radiobutton(frm, text="Flat: Type only", variable=self.method_var, value="type").grid(column=3, row=1, sticky=tk.W)

            ttk.Checkbutton(frm, text="Recursive", variable=self.recursive_var).grid(column=1, row=2, sticky=tk.W, pady=(6,0))
            ttk.Checkbutton(frm, text="Delete empty folders", variable=self.delete_var).grid(column=2, row=2, sticky=tk.W)
            ttk.Checkbutton(frm, text="Watch mode (auto)", variable=self.watch_var).grid(column=3, row=2, sticky=tk.W)

            ttk.Button(frm, text="Run Now", command=self.run_now).grid(column=1, row=3, pady=12)
            ttk.Button(frm, text="Start Watch", command=self.start_watch).grid(column=2, row=3)
            ttk.Button(frm, text="Stop Watch", command=self.stop_watch).grid(column=3, row=3)
            ttk.Button(frm, text="Save Config", command=self.save_config).grid(column=4, row=3)

            self.logbox = tk.Text(frm, height=24, width=95, state=tk.DISABLED)
            self.logbox.grid(column=0, row=4, columnspan=5, pady=(12,0))

        def log(self, text):
            logging.info(text)
            self.logbox.config(state=tk.NORMAL)
            now = datetime.now().strftime("%H:%M:%S")
            self.logbox.insert(tk.END, f"[{now}] {text}\n")
            self.logbox.see(tk.END)
            self.logbox.config(state=tk.DISABLED)

        def browse(self):
            p = filedialog.askdirectory()
            if p:
                self.target_var.set(p)

        def run_now(self):
            target = self.target_var.get()
            method = self.method_var.get()
            rec = self.recursive_var.get()
            delete = self.delete_var.get()
            cfg = load_config()
            cfg["target_folder"] = target
            cfg["method"] = method
            cfg["recursive"] = rec
            cfg["delete_empty"] = delete
            save_config(cfg)

            # reset stats for this run
            self.stats = make_stats()

            def threaded_run():
                self.log(f"Starting organize: {target} (mode={method}, recursive={rec}, delete_empty={delete})")
                deep_scan_and_organize(target, method, rec, delete, cfg.get("custom_rules"), self.stats, self.log)
                delete_empty_folders(Path(target), self.stats)
                self.log("Organize thread finished.")
                print_summary(self.stats)

            thread = threading.Thread(target=threaded_run, daemon=True)
            thread.start()

        def start_watch(self):
            if not WATCHDOG_AVAILABLE:
                messagebox.showerror("Error", "watchdog package not available.")
                return

            if self.observer:
                self.log("Watcher already running.")
                return
            target = self.target_var.get()
            method = self.method_var.get()
            rec = self.recursive_var.get()
            delete = self.delete_var.get()
            cfg = load_config()
            ordered_rules = build_rules(cfg.get("custom_rules", {}))
            handler = NewFileHandler(target, method, rec, delete, ordered_rules, self.stats)
            observer = Observer()
            observer.schedule(handler, target, recursive=rec)
            observer.start()
            self.observer = observer
            self.log("Watch mode started.")

        def stop_watch(self):
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None
                self.log("Watch stopped.")
            else:
                self.log("Watch not running.")

        def save_config(self):
            cfg = load_config()
            cfg["target_folder"] = self.target_var.get()
            cfg["method"] = self.method_var.get()
            cfg["recursive"] = self.recursive_var.get()
            cfg["delete_empty"] = self.delete_var.get()
            save_config(cfg)
            self.log("Config saved.")


# ----------------------------
# CLI runner
# ----------------------------
def run_headless(args):
    if not WATCHDOG_AVAILABLE and args.watch:
        logging.error("watchdog package not installed; watch mode not available. Install with: pip install watchdog")
        return

    cfg = load_config()
    target = args.target if args.target else cfg.get("target_folder", str(DEFAULT_TARGET))
    method = cfg.get("method", "type_date") if not args.method else args.method
    recursive = cfg.get("recursive", False) if args.recursive is None else args.recursive
    delete_empty = cfg.get("delete_empty", True) if args.delete_empty is None else args.delete_empty
    custom_rules = cfg.get("custom_rules", {})

    stats = make_stats()

    if args.run:
        logging.info(f"Running organize -> target={target}, method={method}, recursive={recursive}")
        deep_scan_and_organize(target, method, recursive, delete_empty, custom_rules, stats)
        delete_empty_folders(Path(target), stats)
        print_summary(stats)

    if args.watch:
        ordered = build_rules(custom_rules)
        handler = NewFileHandler(target, method, recursive, delete_empty, ordered, stats)
        observer = Observer()
        observer.schedule(handler, target, recursive=recursive)
        observer.start()
        logging.info("Watch started (headless). Press CTRL+C to stop.")
        try:
            while True:
                time.sleep(2)
                # print a small live summary occasionally
                print(Fore.CYAN + f"[Live] scanned={stats['scanned']} moved={stats['files_moved']} folders={stats['folders_created']}" + Style.RESET_ALL)
        except KeyboardInterrupt:
            observer.stop()
            observer.join()
            logging.info("Watch stopped.")
            logging.info("Final summary:")
            print_summary(stats)


# ----------------------------
# Argument parsing
# ----------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Downloads Organizer - Advanced")
    parser.add_argument("--run", action="store_true", help="Run organize once (headless)")
    parser.add_argument("--watch", action="store_true", help="Run watch mode (headless)")
    parser.add_argument("--target", type=str, help="Target folder (overrides config)")
    parser.add_argument("--method", choices=["type_date", "date_type", "type"], help="Organize method")
    parser.add_argument("--recursive", type=bool, nargs="?", const=True, help="Enable recursive scan")
    parser.add_argument("--delete-empty", dest="delete_empty", type=bool, nargs="?", const=True, help="Delete empty folders")
    return parser.parse_args()


# ----------------------------
# Entrypoint
# ----------------------------
def main():
    args = parse_args()
    if args.run or args.watch:
        run_headless(args)
    else:
        if GUI_AVAILABLE:
            app = OrganizerGUI()
            app.protocol("WM_DELETE_WINDOW", lambda: (app.stop_watch(), app.destroy()))
            app.mainloop()
        else:
            logging.error("GUI not available in this Python environment. Use --run / --watch for headless mode.")


if __name__ == "__main__":
    main()
