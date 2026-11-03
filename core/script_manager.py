# root/core/script_manager.py
import os
import re
import json
import tempfile
import shutil
from collections import OrderedDict

class ScriptManager:
    def __init__(self):
        self.EDIT_CUTOFF_MARKER = "### DO NOT EDIT FROM HERE ###"
        self.VAR_PATTERN = re.compile(r':global\s+(\S+)')
        self.DEFAULT_PATTERN = re.compile(r':global\s+(\S+)\s+"?([^"\n]+)"?')
        self.DESC_PATTERN = re.compile(r'#\s*(\S+)\s*-\s*(.+)')
        self.SET_PATTERN = re.compile(r':set\s+\$(\S+)\s+"?([^"\s]+)"?')
        
        self.scripts = {}
        self.categories = {'Uncategorized': []}
        self.dark_mode = False
        self.data_file = os.path.join("data", "mikrotik_data.json")
        self.load_data()

    def load_data(self):
        """Load existing data, refusing to hide corruption behind an empty library."""
        if not os.path.exists(self.data_file):
            return
        try:
            with open(self.data_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("Library root must be an object")
            scripts = data.get("scripts", {})
            categories = data.get("categories", {"Uncategorized": []})
            if not isinstance(scripts, dict) or not isinstance(categories, dict):
                raise ValueError("Invalid script/category structure")
            if any(not isinstance(v, dict) or not isinstance(v.get("code"), str)
                   or not isinstance(v.get("description", ""), str)
                   or not isinstance(v.get("category", "Uncategorized"), str)
                   for v in scripts.values()):
                raise ValueError("Invalid script entry")
            if any(not isinstance(k, str) or not isinstance(v, list)
                   or any(not isinstance(item, str) for item in v)
                   for k, v in categories.items()):
                raise ValueError("Invalid category entry")
            self.scripts = scripts
            self.categories = categories
            self.dark_mode = bool(data.get("dark_mode", False))
            self._migrate_script_categories()
        except (OSError, UnicodeError, ValueError) as exc:
            raise RuntimeError(
                "Cannot load script library at {!r}; original file was not changed. "
                "Restore a verified backup or repair the JSON before starting."
                .format(self.data_file)
            ) from exc

    def _migrate_script_categories(self):
        for script_name, script_data in self.scripts.items():
            category = script_data.get('category', 'Uncategorized')
            if category not in self.categories:
                self.categories[category] = []
        
        for script_name, script_data in self.scripts.items():
            category = script_data.get('category', 'Uncategorized')
            if script_name not in self.categories[category]:
                self.categories[category].append(script_name)
        
        for category in list(self.categories.keys()):
            if category != 'Uncategorized' and not self.categories[category]:
                del self.categories[category]

    def save_data(self):
        """Write JSON atomically and preserve a valid previous version as .bak."""
        data = {
            "scripts": self.scripts,
            "categories": self.categories,
            "dark_mode": self.dark_mode,
        }
        directory = os.path.dirname(os.path.abspath(self.data_file))
        os.makedirs(directory, exist_ok=True)
        temp_path = None
        backup_temp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=directory,
                prefix=".mikrotik-", suffix=".tmp", delete=False
            ) as handle:
                temp_path = handle.name
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())

            # Never rotate a corrupt original into the known-good backup.
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as existing:
                    previous = json.load(existing)
                if not isinstance(previous, dict):
                    raise ValueError("Existing library is not a JSON object")
                with tempfile.NamedTemporaryFile(
                    mode="wb", dir=directory, prefix=".mikrotik-backup-",
                    suffix=".tmp", delete=False
                ) as backup:
                    backup_temp = backup.name
                    with open(self.data_file, "rb") as source:
                        shutil.copyfileobj(source, backup)
                    backup.flush()
                    os.fsync(backup.fileno())
                os.replace(backup_temp, self.data_file + ".bak")
                backup_temp = None

            os.replace(temp_path, self.data_file)
            temp_path = None
        finally:
            for candidate in (temp_path, backup_temp):
                if candidate and os.path.exists(candidate):
                    os.unlink(candidate)

    def extract_ordered_vars(self, code):
        part = code.split(self.EDIT_CUTOFF_MARKER)[0]
        seen = OrderedDict()
        for match in self.VAR_PATTERN.finditer(part):
            seen[match.group(1)] = None
        return list(seen.keys())

    def extract_var_defaults(self, code):
        part = code.split(self.EDIT_CUTOFF_MARKER)[0]
        defaults = {}
        for var, val in self.DEFAULT_PATTERN.findall(part):
            defaults[var] = val.strip('"')
        for var, val in self.SET_PATTERN.findall(part):
            defaults[var] = val.strip('"')
        return defaults

    def extract_var_descriptions(self, code):
        lines = code.splitlines()
        descs = {}
        for i, line in enumerate(lines):
            match = self.VAR_PATTERN.match(line)
            if match:
                var = match.group(1)
                for j in range(i - 1, max(i - 4, -1), -1):
                    comment_match = self.DESC_PATTERN.match(lines[j])
                    if comment_match and comment_match.group(1) == var:
                        descs[var] = comment_match.group(2)
                        break
        return descs