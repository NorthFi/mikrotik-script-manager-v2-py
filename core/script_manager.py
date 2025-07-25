import os
import re
import json
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
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.scripts = data.get('scripts', {})
                    self.categories = data.get('categories', {'Uncategorized': []})
                    self.dark_mode = data.get('dark_mode', False)
                    self._migrate_script_categories()
        except Exception as e:
            print(f"Error loading data: {e}")
            self.scripts = {}
            self.categories = {'Uncategorized': []}
            self.dark_mode = False

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
        data = {
            'scripts': self.scripts,
            'categories': self.categories,
            'dark_mode': self.dark_mode
        }
        
        try:
            if os.path.exists(self.data_file):
                backup_file = self.data_file + '.bak'
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                os.rename(self.data_file, backup_file)
            
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error saving data: {e}")
            if os.path.exists(backup_file):
                os.rename(backup_file, self.data_file)
            raise

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