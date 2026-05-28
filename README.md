# EzEdit - Lightweight IDE + Text Editor

EzEdit is a lightweight, classic-style integrated development environment (IDE) built with Python and Qt5. It is designed to be fast, responsive, and provide a distraction-free environment for coding with modern IDE features while keeping the interface clean and efficient.

## The Problem

Modern IDEs (like VS Code or IntelliJ) are powerful but often feel bloated. They consume significant system resources, require lengthy startup times, and can be distracting. For many developers, a simple, fast tool that handles editing, compiling, and running code is all that is needed.

## The Solution

EzEdit bridges the gap between a basic text editor and a heavy IDE. It provides an integrated workflow—edit, compile, run, and clean—without the overhead of background language servers or heavy plugin ecosystems. It runs entirely locally on your machine, respects your privacy, and has no cost.

## Features

* **Classic UI:** A clean, native-style interface using the Windows classic aesthetic.
* **Integrated Workflow:** Built-in terminal (cmd) that syncs with your current workspace directory.
* **Project Management:** A sidebar for managing your workspace with drag-and-drop, and right-click operations (New File/Folder, Rename, Delete).
* **Multi-Language Support:** Syntax highlighting for Python, C/C++, Java, C#, Rust, HTML, CSS, JavaScript, PHP, Ruby, SQL, Bash, and Perl.
* **Build Tools:** Execute code (F5) with automatic compilation for C, C++, Java, and Rust.
* **Auto-Cleanup:** Optional toggle to delete compiled `.exe` files after execution to keep your workspace clean.
* **Find & Replace:** Non-modal search tool that stays open while you work.

## Technical Details

EzEdit is built using established open-source libraries:
- **PyQt5:** For the graphical user interface.
- **QScintilla:** For the source code editing engine and syntax highlighting.
- **Python Standard Library:** For file system operations and terminal integration.

## Installation

### For End Users
Download the `EzEdit_Setup.exe` from the Releases page. Run the installer to add the application to your system with a desktop shortcut.

### For Developers

1. **Requirements:** Python 3.8 or higher.
2. **Install dependencies:**
```
pip install -r requirements.txt
```
