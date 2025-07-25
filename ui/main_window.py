import os
import tempfile
import subprocess
import platform
import requests
from urllib.parse import urlparse
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                            QWidget, QLabel, QLineEdit, QPushButton, QComboBox,
                            QScrollArea, QGroupBox, QFileDialog, QMessageBox,
                            QTextEdit, QTabWidget, QInputDialog, QTreeWidget,
                            QTreeWidgetItem, QSplitter, QAction, QSizePolicy,
                            QDialog, QDialogButtonBox, QMenu)
from PyQt5.QtCore import Qt, QRegularExpression, QSize
from PyQt5.QtGui import (QFont, QTextCharFormat, QColor, QSyntaxHighlighter,
                        QPalette, QIcon, QPixmap)
from PyQt5.QtCore import pyqtSignal

from ui.highlighter import MikroTikHighlighter
from ui.styles import apply_dark_style, apply_light_style
from core.script_manager import ScriptManager
from core.github_importer import GitHubImporter

class MikroTikScriptManager(QMainWindow):
    styleChanged = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MikroTik Script Manager")
        self.setWindowIcon(QIcon("ui/logo.png"))
        self.setGeometry(100, 100, 1200, 900)
        
        self.script_manager = ScriptManager()
        self.current_vars = []
        self.final_script = ""
        self.dark_mode = self.script_manager.dark_mode
        self.temp_files = []
        
        self.init_ui()
        self.apply_style()
        self.styleChanged.connect(self.on_style_changed)
        self.update_script_tree()

    def init_ui(self):
        self.tabs = QTabWidget()
        self.init_main_tab()
        self.init_help_tab()
        self.init_about_tab()
        self.init_menu_bar()
        self.setCentralWidget(self.tabs)
        self.setWindowIcon(QIcon.fromTheme('text-x-script'))

    def init_menu_bar(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu('File')
        file_menu.addAction(self.create_action('Import Script', self.import_script))
        file_menu.addAction(self.create_action('Import from GitHub', self.import_from_github))
        # file_menu.addAction(self.create_action('Export to GitHub', self.export_to_github))
        file_menu.addSeparator()
        file_menu.addAction(self.create_action('Exit', self.close))

        view_menu = menubar.addMenu('View')
        self.dark_mode_action = QAction('Dark Mode', self, checkable=True)
        self.dark_mode_action.setChecked(self.dark_mode)
        self.dark_mode_action.triggered.connect(self.toggle_dark_mode)
        view_menu.addAction(self.dark_mode_action)

        script_menu = menubar.addMenu('Script')
        script_menu.addAction(self.create_action('Rename Script', self.rename_script))
        script_menu.addAction(self.create_action('Delete Script', self.delete_script))
        script_menu.addAction(self.create_action('Edit Script', self.edit_script))

        category_menu = menubar.addMenu('Category')
        category_menu.addAction(self.create_action('New Category', self.add_category))
        category_menu.addAction(self.create_action('Rename Category', self.rename_category))
        category_menu.addAction(self.create_action('Delete Category', self.delete_category))

        help_menu = menubar.addMenu('Help')
        help_menu.addAction(self.create_action('Documentation', self.show_documentation))
        help_menu.addAction(self.create_action('About', lambda: self.tabs.setCurrentIndex(2)))

    def create_action(self, name, callback):
        action = QAction(name, self)
        action.triggered.connect(callback)
        return action

    def init_main_tab(self):
        main_tab = QWidget()
        main_layout = QHBoxLayout()
        
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search scripts...")
        self.search_box.textChanged.connect(self.filter_scripts)
        left_layout.addWidget(self.search_box)
        
        self.script_tree = QTreeWidget()
        self.script_tree.setHeaderHidden(True)
        self.script_tree.itemClicked.connect(self.script_tree_selected)
        self.script_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.script_tree.customContextMenuRequested.connect(self.show_context_menu)
        left_layout.addWidget(self.script_tree)
        
        left_panel.setLayout(left_layout)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        self.script_desc = QLabel("Description will appear here")
        self.script_desc.setWordWrap(True)
        right_layout.addWidget(self.script_desc)
        
        self.vars_group = QGroupBox("Script Parameters")
        self.vars_widget = QWidget()
        self.vars_layout = QVBoxLayout(self.vars_widget)
        self.vars_layout.setSizeConstraint(QVBoxLayout.SetMinimumSize)
        
        vars_scroll = QScrollArea()
        vars_scroll.setWidgetResizable(True)
        vars_scroll.setWidget(self.vars_widget)
        vars_scroll.setMinimumHeight(200)
        vars_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        
        self.vars_group.setLayout(QVBoxLayout())
        self.vars_group.layout().addWidget(vars_scroll)
        right_layout.addWidget(self.vars_group)
        
        self.generate_btn = QPushButton("Generate and Open Script")
        self.generate_btn.clicked.connect(self.generate_and_open_script)
        right_layout.addWidget(self.generate_btn)
        
        right_panel.setLayout(right_layout)
        
        main_layout.addWidget(left_panel, stretch=1)
        main_layout.addWidget(right_panel, stretch=3)
        main_tab.setLayout(main_layout)
        self.tabs.addTab(main_tab, "Script Manager")

    def show_context_menu(self, position):
        item = self.script_tree.itemAt(position)
        if not item:
            return
            
        menu = QMenu()
        
        if item.parent():  # It's a script
            menu.addAction("Edit Script", self.edit_script)
            menu.addAction("Rename Script", self.rename_script)
            menu.addAction("Delete Script", self.delete_script)
            # menu.addAction("Export to GitHub", self.export_to_github)
        else:  # It's a category
            menu.addAction("Rename Category", self.rename_category)
            menu.addAction("Delete Category", self.delete_category)
            
        menu.exec_(self.script_tree.viewport().mapToGlobal(position))

    def init_help_tab(self):
        help_tab = QWidget()
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMarkdown("""
# 📚 MikroTik Script Manager Help

---

## 🚀 Getting Started

### 📥 Importing Scripts
- **File → Import Script** - Import .rsc or .txt files
- **File → Import from GitHub** - Paste raw GitHub URLs or Gist links
- **Organize scripts** into categories for better management

### 📁 Script Organization
- Create categories to group related scripts
- Use the **search box** to quickly find scripts
- **Right-click items** for context menu options

---

## ⚙️ Script Parameterization

Scripts can be made dynamic using variables. Format them like this:

```routeros
# serverip - Server IP address
:global serverip "192.168.1.100"

# username - Login username
:global username "admin"

### DO NOT EDIT FROM HERE ###
/system identity set name="$username-router"
```

### 🔧 Variable Types
- **`:global varname "value"`** - Global variables
- **`:set $varname "value"`** - Set variables  
- **`$varname`** - Direct substitution

### 💡 Best Practices
- Add descriptive comments above variables using **`# varname - description`**
- Use the **`### DO NOT EDIT FROM HERE ###`** marker to protect code
- Choose **meaningful variable names**
- Provide **sensible default values**

---

## 🛠️ Script Management

### ✏️ Editing
- **Right-click scripts** to edit, rename, or delete
- Modify script code, description, and category
- Scripts are **automatically saved**

### 🎯 Generation
1. **Select** a script from the tree
2. **Customize** variables in the parameters panel  
3. **Click** "Generate and Open Script"
4. Script **opens in your editor** and copies to clipboard

---

## 🌐 GitHub Integration

Import scripts directly from GitHub using raw URLs:
- `https://raw.githubusercontent.com/user/repo/branch/file.rsc`
- `https://gist.githubusercontent.com/user/gist-id/raw/file.rsc`

**Security Note:** Only HTTPS raw GitHub URLs are accepted for security.

---

## 🎨 Interface Features

### 🌙 Themes
Toggle between **dark and light modes** via **View → Dark Mode**

### 🔍 Search
Type in the search box to **filter scripts by name** in real-time

---

## 🆘 Troubleshooting

### ❌ Common Issues
- **Variables not showing:** Check comment format above variables
- **Script won't generate:** Ensure the cutoff marker is present
- **GitHub import fails:** Verify URL is a raw GitHub link

### 💾 Data Location
Scripts are stored in: **`data/mikrotik_data.json`**

To reset settings, delete the data folder and restart the application.

---

*💡 **Tip:** Great scripts start with great organization. Use categories and descriptive names to build a maintainable script library!*
""")
        layout = QVBoxLayout()
        layout.addWidget(help_text)
        help_tab.setLayout(layout)
        self.tabs.addTab(help_tab, "Help")

    def init_about_tab(self):
        about_tab = QWidget()
        about_text = QTextEdit()
        about_text.setReadOnly(True)
        about_text.setMarkdown("""
# 🚀 MikroTik Script Manager

## 📊 Application Information

| **Property** | **Details** |
|--------------|-------------|
| **Version** | 2.0.0 |
| **Author** | Daniel Jordaan |
| **License** | MIT Open Source |
| **Framework** | PyQt5 + Python |
| **Platform** | Windows, macOS, Linux |

---

## ✨ Key Features

### 🎯 Core Functionality
- **📁 Script Organization** - Categorize and manage RouterOS scripts
- **⚙️ Variable Parameterization** - Customize scripts with dynamic parameters  
- **🎨 Syntax Highlighting** - Beautiful RouterOS script highlighting
- **🚀 One-Click Deployment** - Generate and open customized scripts instantly

### 🌐 Integration
- **📥 GitHub Import** - Direct import from raw URLs and Gists
- **📤 Script Export** - Direct export to system editor
- **📋 Clipboard Copy** - Automatic clipboard copying
- **💾 Data Persistence** - JSON-based storage with backups

### 🎨 User Experience
- **🌙 Theme Support** - Dark and light modes
- **🔍 Real-time Search** - Filter scripts instantly
- **📱 Context Menus** - Quick right-click actions

---

## 🎯 Purpose

This tool helps **network administrators** and **system integrators** manage their MikroTik RouterOS scripts more effectively. Instead of maintaining dozens of similar scripts with hardcoded values, you can create **parameterized templates** that adapt to different environments.

### 💼 For Network Administrators
- **Centralize** script management in one application
- **Eliminate** duplicate scripts with different IP addresses
- **Deploy** consistent configurations across multiple sites
- **Maintain** documentation alongside your scripts

### 👨‍💻 For System Integrators
- **Build** reusable script templates for client deployments
- **Quickly customize** scripts for different network environments
- **Share** script libraries between team members
- **Reduce** configuration errors through parameterization

---

## 🏗️ Technical Design

The application follows a **modular architecture**:

- **🔧 Core Module:** Script management and variable extraction
- **🖥️ UI Module:** PyQt5-based interface with syntax highlighting
- **🌐 Integration Module:** GitHub import/export functionality
- **💾 Data Layer:** JSON-based storage with automatic backups

**Security features** include HTTPS-only GitHub integration, input validation, and local data storage with no external data transmission.

---

## 🎨 Development Philosophy

This project is built with the principle that **good tools should be simple, reliable, and focused**. Rather than trying to do everything, it excels at script organization and parameterization - the core problems that MikroTik administrators face daily.

---

## 🤝 Community

The MikroTik Script Manager is **open source** and welcomes contributions from the networking community. Whether you're reporting bugs, suggesting features, or contributing code, your involvement helps make this tool better for everyone.

---

## 📄 License

**MIT License** - You are free to use, modify, and distribute this software. The complete license terms are available in the LICENSE file.

---

## 🙏 Acknowledgments

Special thanks to **MikroTik** for creating RouterOS, the **Qt/PyQt team** for the excellent GUI framework, and the **open source community** for the tools and libraries that make projects like this possible.

---

**Made with ❤️ for the MikroTik community by network professionals**

*© 2025 Daniel Jordaan. All rights reserved.*
""")
        layout = QVBoxLayout()
        layout.addWidget(about_text)
        about_tab.setLayout(layout)
        self.tabs.addTab(about_tab, "About")

    def apply_style(self):
        if self.dark_mode:
            apply_dark_style(QApplication.instance())
        else:
            apply_light_style(QApplication.instance())
        self.styleChanged.emit(self.dark_mode)

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.script_manager.dark_mode = self.dark_mode
        self.apply_style()
        self.script_manager.save_data()

    def on_style_changed(self, dark_mode):
        pass

    def update_script_tree(self):
        self.script_tree.clear()
        current_script = self.get_selected_script_name()
        
        sorted_categories = sorted(self.script_manager.categories.keys())
        
        for category in sorted_categories:
            script_names = self.script_manager.categories[category]
            category_item = QTreeWidgetItem([category])
            self.script_tree.addTopLevelItem(category_item)
            
            for name in sorted(script_names):
                if name in self.script_manager.scripts:
                    script_item = QTreeWidgetItem([name])
                    category_item.addChild(script_item)
                    if current_script == name:
                        self.script_tree.setCurrentItem(script_item)
        
        self.script_tree.expandAll()

    def filter_scripts(self, text):
        search_text = text.lower()
        for i in range(self.script_tree.topLevelItemCount()):
            category_item = self.script_tree.topLevelItem(i)
            category_matches = search_text in category_item.text(0).lower()
            any_child_matches = False
            
            for j in range(category_item.childCount()):
                script_item = category_item.child(j)
                script_matches = search_text in script_item.text(0).lower()
                script_item.setHidden(not script_matches)
                if script_matches:
                    any_child_matches = True
            
            category_item.setHidden(not (category_matches or any_child_matches))

    def script_tree_selected(self, item, column):
        if item.parent():  # It's a script item
            script_name = item.text(0)
            if script_name in self.script_manager.scripts:
                self.script_selected(script_name)

    def add_category(self):
        name, ok = QInputDialog.getText(self, "New Category", "Category name:")
        if ok and name:
            if name not in self.script_manager.categories:
                self.script_manager.categories[name] = []
                self.update_script_tree()
                self.script_manager.save_data()
            else:
                QMessageBox.warning(self, "Duplicate", "Category already exists!")

    def rename_category(self):
        item = self.script_tree.currentItem()
        if not item or item.parent():
            return
            
        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(
            self, "Rename Category", 
            "New category name:",
            QLineEdit.Normal,
            old_name
        )
        
        if ok and new_name and new_name != old_name:
            if new_name in self.script_manager.categories:
                QMessageBox.warning(self, "Duplicate", "Category already exists!")
                return
                
            self.script_manager.categories[new_name] = self.script_manager.categories.pop(old_name)
            for script in self.script_manager.categories[new_name]:
                if script in self.script_manager.scripts:
                    self.script_manager.scripts[script]['category'] = new_name
            self.update_script_tree()
            self.script_manager.save_data()

    def delete_category(self):
        item = self.script_tree.currentItem()
        if not item or item.parent():
            return
            
        category_name = item.text(0)
        if self.script_manager.categories[category_name]:
            reply = QMessageBox.question(
                self, "Category Not Empty",
                "Move scripts to 'Uncategorized' before deleting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Yes:
                for script_name in self.script_manager.categories[category_name]:
                    if script_name in self.script_manager.scripts:
                        self.script_manager.scripts[script_name]['category'] = 'Uncategorized'
                        self.script_manager.categories['Uncategorized'].append(script_name)
                del self.script_manager.categories[category_name]
                self.update_script_tree()
                self.script_manager.save_data()
            elif reply == QMessageBox.No:
                del self.script_manager.categories[category_name]
                self.update_script_tree()
                self.script_manager.save_data()

    def import_script_with_options(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            suggested_name = os.path.splitext(os.path.basename(path))[0]
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Import Options")
            layout = QVBoxLayout()
            
            name_layout = QHBoxLayout()
            name_layout.addWidget(QLabel("Script Name:"))
            name_edit = QLineEdit(suggested_name)
            name_layout.addWidget(name_edit)
            layout.addLayout(name_layout)
            
            desc_layout = QHBoxLayout()
            desc_layout.addWidget(QLabel("Description:"))
            desc_edit = QLineEdit(f"Imported from {os.path.basename(path)}")
            desc_layout.addWidget(desc_edit)
            layout.addLayout(desc_layout)
            
            category_layout = QHBoxLayout()
            category_layout.addWidget(QLabel("Category:"))
            category_combo = QComboBox()
            category_combo.addItems(sorted(self.script_manager.categories.keys()))
            category_combo.setEditable(True)
            category_layout.addWidget(category_combo)
            layout.addLayout(category_layout)
            
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            dialog.setLayout(layout)
            
            if dialog.exec_() == QDialog.Accepted:
                name = name_edit.text().strip()
                description = desc_edit.text().strip()
                category = category_combo.currentText().strip()
                
                if not name:
                    raise ValueError("Script name cannot be empty")
                
                self.save_script(name, code, description, category)
                return True
            return False
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import script:\n{str(e)}")
            return False

    def import_script(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Script", "", 
            "Scripts (*.rsc *.txt);;All Files (*)"
        )
        if path:
            self.import_script_with_options(path)

    def import_from_github(self):
        url, ok = QInputDialog.getText(
            self, "GitHub Import", 
            "Enter raw GitHub URL:"
        )
        if ok and url:
            try:
                name, code, description = GitHubImporter.import_from_url(url)
                
                dialog = QDialog(self)
                dialog.setWindowTitle("GitHub Import Options")
                layout = QVBoxLayout()
                
                name_layout = QHBoxLayout()
                name_layout.addWidget(QLabel("Script Name:"))
                name_edit = QLineEdit(name)
                name_layout.addWidget(name_edit)
                layout.addLayout(name_layout)
                
                desc_layout = QHBoxLayout()
                desc_layout.addWidget(QLabel("Description:"))
                desc_edit = QLineEdit(description)
                desc_layout.addWidget(desc_edit)
                layout.addLayout(desc_layout)
                
                category_layout = QHBoxLayout()
                category_layout.addWidget(QLabel("Category:"))
                category_combo = QComboBox()
                category_combo.addItems(sorted(self.script_manager.categories.keys()))
                category_combo.setEditable(True)
                category_combo.setCurrentText("GitHub Imports")
                category_layout.addWidget(category_combo)
                layout.addLayout(category_layout)
                
                button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                button_box.accepted.connect(dialog.accept)
                button_box.rejected.connect(dialog.reject)
                layout.addWidget(button_box)
                
                dialog.setLayout(layout)
                
                if dialog.exec_() == QDialog.Accepted:
                    name = name_edit.text().strip()
                    description = desc_edit.text().strip()
                    category = category_combo.currentText().strip()
                    
                    if not name:
                        raise ValueError("Script name cannot be empty")
                    
                    self.save_script(name, code, description, category)
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import from GitHub:\n{str(e)}")

    def export_to_github(self):
        script_name = self.get_selected_script_name()
        if not script_name:
            QMessageBox.warning(self, "Warning", "No script selected")
            return
            
        if script_name not in self.script_manager.scripts:
            QMessageBox.warning(self, "Warning", "Script not found")
            return
            
        url, ok = QInputDialog.getText(
            self, "GitHub Export", 
            "Enter GitHub Gist URL (leave blank to create new):"
        )
        
        if not ok:
            return
            
        try:
            script = self.script_manager.scripts[script_name]
            code = script['code']
            
            if url:
                parsed = urlparse(url)
                if parsed.netloc != "gist.github.com":
                    raise ValueError("Invalid GitHub Gist URL")
                
                gist_id = parsed.path.split('/')[-1]
                api_url = f"https://api.github.com/gists/{gist_id}"
                
                response = requests.patch(
                    api_url,
                    json={
                        "files": {
                            f"{script_name}.rsc": {
                                "content": code
                            }
                        }
                    }
                )
                response.raise_for_status()
                QMessageBox.information(self, "Success", f"Script updated at:\n{response.json()['html_url']}")
            else:
                api_url = "https://api.github.com/gists"
                
                response = requests.post(
                    api_url,
                    json={
                        "description": f"MikroTik Script: {script_name}",
                        "public": True,
                        "files": {
                            f"{script_name}.rsc": {
                                "content": code
                            }
                        }
                    }
                )
                response.raise_for_status()
                QMessageBox.information(self, "Success", f"Script exported to:\n{response.json()['html_url']}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export to GitHub:\n{str(e)}")

    def save_script(self, name, code, description, category):
        if self.script_manager.EDIT_CUTOFF_MARKER not in code:
            reply = QMessageBox.question(
                self, "Warning",
                "Script is missing the required cutoff marker. Save anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        if category not in self.script_manager.categories:
            self.script_manager.categories[category] = []
        
        if name in self.script_manager.scripts:
            old_category = self.script_manager.scripts[name].get('category', 'Uncategorized')
            if old_category in self.script_manager.categories and name in self.script_manager.categories[old_category]:
                self.script_manager.categories[old_category].remove(name)
        
        if name not in self.script_manager.categories[category]:
            self.script_manager.categories[category].append(name)
        
        self.script_manager.scripts[name] = {
            'code': code,
            'description': description,
            'category': category
        }
        
        self.update_script_tree()
        self.select_script_in_tree(name)
        self.script_manager.save_data()

    def select_script_in_tree(self, script_name):
        for i in range(self.script_tree.topLevelItemCount()):
            category_item = self.script_tree.topLevelItem(i)
            for j in range(category_item.childCount()):
                if category_item.child(j).text(0) == script_name:
                    self.script_tree.setCurrentItem(category_item.child(j))
                    return

    def rename_script(self):
        current = self.get_selected_script_name()
        if not current:
            return
            
        new_name, ok = QInputDialog.getText(
            self, "Rename Script", 
            "New script name:",
            QLineEdit.Normal,
            current
        )
        
        if ok and new_name and new_name != current:
            if new_name in self.script_manager.scripts:
                QMessageBox.warning(self, "Duplicate", "Script name already exists!")
                return
            
            script_data = self.script_manager.scripts[current]
            category = script_data.get('category', 'Uncategorized')
            if category in self.script_manager.categories and current in self.script_manager.categories[category]:
                self.script_manager.categories[category].remove(current)
                self.script_manager.categories[category].append(new_name)
            
            self.script_manager.scripts[new_name] = script_data
            del self.script_manager.scripts[current]
            
            self.update_script_tree()
            self.select_script_in_tree(new_name)
            self.script_manager.save_data()

    def edit_script(self):
        script_name = self.get_selected_script_name()
        if not script_name or script_name not in self.script_manager.scripts:
            QMessageBox.warning(self, "Warning", "No script selected")
            return
            
        script = self.script_manager.scripts[script_name]
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Script: {script_name}")
        dialog.setMinimumSize(800, 600)
        layout = QVBoxLayout()
        
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("Description:"))
        desc_edit = QLineEdit(script['description'])
        desc_layout.addWidget(desc_edit)
        layout.addLayout(desc_layout)
        
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Category:"))
        category_combo = QComboBox()
        category_combo.addItems(sorted(self.script_manager.categories.keys()))
        category_combo.setEditable(True)
        category_combo.setCurrentText(script.get('category', 'Uncategorized'))
        category_layout.addWidget(category_combo)
        layout.addLayout(category_layout)
        
        code_edit = QTextEdit()
        code_edit.setPlainText(script['code'])
        code_edit.setFont(QFont("Courier New", 10))
        MikroTikHighlighter(code_edit.document())
        layout.addWidget(code_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            script['code'] = code_edit.toPlainText()
            script['description'] = desc_edit.text()
            category = category_combo.currentText()
            
            old_category = script.get('category', 'Uncategorized')
            if category != old_category:
                if old_category in self.script_manager.categories and script_name in self.script_manager.categories[old_category]:
                    self.script_manager.categories[old_category].remove(script_name)
                
                if category not in self.script_manager.categories:
                    self.script_manager.categories[category] = []
                
                self.script_manager.categories[category].append(script_name)
                script['category'] = category
            
            self.script_manager.save_data()
            self.update_script_tree()
            self.script_selected(script_name)

    def delete_script(self):
        current = self.get_selected_script_name()
        if not current:
            return
            
        confirm = QMessageBox.question(
            self, "Confirm Delete", 
            f"Delete script '{current}'?", 
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            script_data = self.script_manager.scripts.get(current, {})
            category = script_data.get('category', 'Uncategorized')
            if category in self.script_manager.categories and current in self.script_manager.categories[category]:
                self.script_manager.categories[category].remove(current)
            
            if current in self.script_manager.scripts:
                del self.script_manager.scripts[current]
            
            self.update_script_tree()
            self.clear_vars_layout()
            self.script_desc.clear()
            self.script_manager.save_data()

    def get_selected_script_name(self):
        item = self.script_tree.currentItem()
        if item and item.parent():
            return item.text(0)
        return None

    def script_selected(self, name):
        if name in self.script_manager.scripts:
            script = self.script_manager.scripts[name]
            self.script_desc.setText(script['description'])
            self.populate_vars(script['code'])

    def populate_vars(self, code):
        self.clear_vars_layout()
        self.current_vars = []
        vars = self.script_manager.extract_ordered_vars(code)
        defaults = self.script_manager.extract_var_defaults(code)
        descriptions = self.script_manager.extract_var_descriptions(code)

        needed_height = len(vars) * 60 + 50
        self.vars_group.setMinimumHeight(min(needed_height, 600))

        for var in vars:
            row = QHBoxLayout()
            
            desc = QLabel(descriptions.get(var, "No description available"))
            desc.setStyleSheet("color: gray; font-style: italic;")
            desc.setWordWrap(True)
            desc.setMinimumWidth(200)
            
            field = QLineEdit()
            field.setText(defaults.get(var, ""))
            field.setMinimumWidth(150)
            
            name = QLabel(f"${var}")
            name.setMinimumWidth(100)
            
            row.addWidget(desc, stretch=2)
            row.addWidget(field, stretch=1)
            row.addWidget(name, stretch=1)
            
            row_widget = QWidget()
            row_widget.setLayout(row)
            self.vars_layout.addWidget(row_widget)
            self.current_vars.append((var, field))
        
        self.vars_layout.addStretch()
        self.vars_widget.adjustSize()
        self.vars_group.adjustSize()

    def clear_vars_layout(self):
        while self.vars_layout.count():
            item = self.vars_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.vars_group.setMinimumHeight(200)

    def generate_and_open_script(self):
        name = self.get_selected_script_name()
        if not name or name not in self.script_manager.scripts:
            QMessageBox.warning(self, "Warning", "No script selected")
            return
            
        code = self.script_manager.scripts[name]['code']
        parts = code.split(self.script_manager.EDIT_CUTOFF_MARKER, 1)
        editable = parts[0]
        protected = parts[1] if len(parts) > 1 else ""

        for var, field in self.current_vars:
            val = field.text()
            editable = self.script_manager.SET_PATTERN.sub(
                lambda m: f':set ${m.group(1)} "{val}"' if m.group(1) == var else m.group(0),
                editable
            )
            editable = self.script_manager.DEFAULT_PATTERN.sub(
                lambda m: f':global {m.group(1)} "{val}"' if m.group(1) == var else m.group(0),
                editable
            )
            editable = editable.replace(f'${var}', val)

        self.final_script = editable + self.script_manager.EDIT_CUTOFF_MARKER + protected
        
        try:
            QApplication.clipboard().setText(self.final_script)
            
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.rsc',
                encoding='utf-8',
                delete=False
            ) as f:
                f.write(self.final_script)
                temp_path = f.name
                self.temp_files.append(temp_path)
            
            system = platform.system()
            if system == 'Windows':
                os.startfile(temp_path)
            elif system == 'Darwin':
                subprocess.run(['open', temp_path])
            else:
                subprocess.run(['xdg-open', temp_path])
                
            QMessageBox.information(
                self,
                "Success",
                "Script generated and copied to clipboard!\n"
                "It has also been opened in your default editor."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate script:\n{str(e)}")

    def cleanup_temp_files(self):
        for temp_path in self.temp_files:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                print(f"Error cleaning up temp file: {str(e)}")
        self.temp_files = []

    def closeEvent(self, event):
        self.cleanup_temp_files()
        self.script_manager.save_data()
        super().closeEvent(event)

    def show_documentation(self):
        self.tabs.setCurrentIndex(1)