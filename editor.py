import sys
import os
import webbrowser
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QAction, 
                             QFileDialog, QMessageBox, QLineEdit, QDockWidget, 
                             QTreeView, QFileSystemModel, QLabel, QStatusBar,
                             QPlainTextEdit, QWidget, QVBoxLayout, QHBoxLayout, 
                             QMenu, QInputDialog, QDialog, QCheckBox, QPushButton, 
                             QShortcut, QSplitter, QFrame, QSizePolicy)
from PyQt5.Qsci import (QsciScintilla, QsciLexerPython, QsciLexerCPP, QsciLexerHTML, 
                        QsciLexerCSS, QsciLexerJavaScript, QsciLexerRuby, QsciLexerPerl,
                        QsciLexerBash, QsciLexerBatch, QsciLexerSQL, QsciLexerProperties)
from PyQt5.QtGui import QFont, QIcon, QColor, QKeySequence
from PyQt5.QtCore import Qt, QProcess, QDir, QSettings, QTimer

class FindReplaceDialog(QDialog):
    """Non-modal Find & Replace window. Stays open while editing."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Find / Replace")
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Find:"))
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Search text...")
        row1.addWidget(self.find_input)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Replace:"))
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replacement text...")
        row2.addWidget(self.replace_input)
        layout.addLayout(row2)

        opt_row = QHBoxLayout()
        self.case_cb  = QCheckBox("Match case")
        self.whole_cb = QCheckBox("Whole word")
        self.regex_cb = QCheckBox("Regex")
        opt_row.addWidget(self.case_cb)
        opt_row.addWidget(self.whole_cb)
        opt_row.addWidget(self.regex_cb)
        layout.addLayout(opt_row)

        btn_row = QHBoxLayout()
        self.find_next_btn   = QPushButton("Find Next")
        self.find_prev_btn   = QPushButton("Find Prev")
        self.replace_btn     = QPushButton("Replace")
        self.replace_all_btn = QPushButton("Replace All")
        self.close_btn       = QPushButton("Close")
        for btn in (self.find_next_btn, self.find_prev_btn, 
                    self.replace_btn, self.replace_all_btn, self.close_btn):
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self.status_lbl = QLabel("")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_lbl)

        self.close_btn.clicked.connect(self.hide)
        self.find_input.returnPressed.connect(self._emit_find_next)
        self.find_next_btn.clicked.connect(self._emit_find_next)
        self.find_prev_btn.clicked.connect(self._emit_find_prev)
        self.replace_btn.clicked.connect(self._emit_replace)
        self.replace_all_btn.clicked.connect(self._emit_replace_all)

    def _emit_find_next(self):
        if self.parent(): self.parent().do_find(forward=True)

    def _emit_find_prev(self):
        if self.parent(): self.parent().do_find(forward=False)

    def _emit_replace(self):
        if self.parent(): self.parent().do_replace()

    def _emit_replace_all(self):
        if self.parent(): self.parent().do_replace_all()

    def set_status(self, msg):
        self.status_lbl.setText(msg)

class GotoLineDialog(QDialog):
    def __init__(self, parent=None, max_line=1):
        super().__init__(parent)
        self.setWindowTitle("Go to Line")
        self.setFixedSize(260, 90)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(f"Line (1-{max_line}):"))
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("line number")
        row.addWidget(self.line_edit)
        layout.addLayout(row)
        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Go")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)
        self.line_edit.returnPressed.connect(self.accept)

    def value(self):
        try:
            return int(self.line_edit.text())
        except ValueError:
            return -1

class EzEdit(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EzEdit")
        self.resize(1200, 800)

        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))

        self.settings = QSettings("ColinGarbutt", "EzEdit")

        self.status_label   = QLabel("  Ready")
        self.encoding_label = QLabel("UTF-8 ")
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.encoding_label)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(False)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_tab_titles)
        self.tabs.tabBarDoubleClicked.connect(self.edit_tab_title)
        self.tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self.show_tab_context_menu)
        
        self.rename_edit = None 
        self.setCentralWidget(self.tabs)

        self.find_dialog = FindReplaceDialog(self)

        self._word_wrap = False
        self._show_ws = False

        self.setup_terminal()   
        self.setup_tree_view()  
        self.setup_menu()       

        geom = self.settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

        last_files = self.settings.value("lastFiles", [])
        if last_files:
            for p in last_files:
                if isinstance(p, str) and os.path.isfile(p):
                    self.open_file_from_path(p)
        if self.tabs.count() == 0:
            self.new_file()

    def show_tab_context_menu(self, position):
        index = self.tabs.tabBar().tabAt(position)
        if index < 0:
            return
        
        editor    = self.tabs.widget(index)
        file_path = getattr(editor, 'file_path', None)
        
        menu = QMenu()
        
        if file_path and os.path.exists(file_path):
            reveal_action    = menu.addAction("Reveal in Project Explorer")
            open_win_action  = menu.addAction("Open in Windows Explorer")
            copy_path_action = menu.addAction("Copy File Path")
            menu.addSeparator()
        else:
            reveal_action = open_win_action = copy_path_action = None
            
        close_action        = menu.addAction("Close Tab")
        close_others_action = menu.addAction("Close Other Tabs")
        close_right_action  = menu.addAction("Close Tabs to the Right")
        
        action = menu.exec_(self.tabs.mapToGlobal(position))
        if action is None:
            return
        
        if file_path and os.path.exists(file_path):
            if action == reveal_action:
                self.open_workspace(os.path.dirname(file_path))
                self.tree_view.setCurrentIndex(self.file_model.index(file_path))
            elif action == open_win_action:
                subprocess.Popen(f'explorer /select,"{os.path.normpath(file_path)}"')
            elif action == copy_path_action:
                QApplication.clipboard().setText(file_path)
                self.statusBar().showMessage(" Path copied to clipboard.", 2000)
                
        if action == close_action:
            self.close_tab(index)
        elif action == close_others_action:
            for i in range(self.tabs.count() - 1, -1, -1):
                if i != index:
                    self.close_tab(i)
        elif action == close_right_action:
            for i in range(self.tabs.count() - 1, index, -1):
                self.close_tab(i)

    def setup_terminal(self):
        self.terminal_dock = QDockWidget("Terminal", self)
        self.terminal_dock.setObjectName("terminal_dock")
        self.terminal_dock.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable
        )
        
        term_widget = QWidget()
        term_layout = QVBoxLayout()
        term_layout.setContentsMargins(0, 0, 0, 0)
        term_layout.setSpacing(0)
        
        self.term_output = QPlainTextEdit()
        self.term_output.setReadOnly(True)
        self.term_output.setFont(QFont("Courier New", 10))
        self.term_output.setStyleSheet("background-color: #0C0C0C; color: #00FF00;")
        self.term_output.setMaximumBlockCount(2000) 
        
        prompt_row = QHBoxLayout()
        prompt_row.setContentsMargins(2, 2, 2, 2)
        prompt_row.setSpacing(4)

        self.prompt_label = QLabel("C:\\>")
        self.prompt_label.setFont(QFont("Courier New", 10))
        self.prompt_label.setStyleSheet("background-color: #0C0C0C; color: #00FF00;")

        self.term_input = QLineEdit()
        self.term_input.setFont(QFont("Courier New", 10))
        self.term_input.setStyleSheet(
            "background-color: #0C0C0C; color: #00FF00; border: none;"
        )
        self.term_input.returnPressed.connect(self.run_terminal_command)
        
        prompt_row.addWidget(self.prompt_label)
        prompt_row.addWidget(self.term_input)

        self._cmd_history  = []
        self._cmd_hist_idx = -1
        self.term_input.installEventFilter(self)

        term_layout.addWidget(self.term_output)
        term_layout.addLayout(prompt_row)
        term_widget.setLayout(term_layout)
        
        self.terminal_dock.setWidget(term_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.terminal_dock)
        
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self._on_process_finished)
        self.process.start("cmd.exe", ["/K"])

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if obj is self.term_input and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Up:
                if self._cmd_history and self._cmd_hist_idx < len(self._cmd_history) - 1:
                    self._cmd_hist_idx += 1
                    self.term_input.setText(self._cmd_history[-(self._cmd_hist_idx + 1)])
                return True
            if key == Qt.Key_Down:
                if self._cmd_hist_idx > 0:
                    self._cmd_hist_idx -= 1
                    self.term_input.setText(self._cmd_history[-(self._cmd_hist_idx + 1)])
                elif self._cmd_hist_idx == 0:
                    self._cmd_hist_idx = -1
                    self.term_input.clear()
                return True
        return super().eventFilter(obj, event)

    def run_terminal_command(self):
        command = self.term_input.text().strip()
        if not command:
            return
        if self.process.state() != QProcess.Running:
            self.process.start("cmd.exe", ["/K"])
            self.process.waitForStarted(2000)
        self.process.write((command + '\r\n').encode())
        self._cmd_history.append(command)
        self._cmd_hist_idx = -1
        self.term_input.clear()

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        self.term_output.moveCursor(self.term_output.textCursor().End)
        self.term_output.insertPlainText(data)
        self.term_output.ensureCursorVisible()

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode('utf-8', errors='replace')
        self.term_output.moveCursor(self.term_output.textCursor().End)
        self.term_output.insertPlainText(data)
        self.term_output.ensureCursorVisible()

    def _on_process_finished(self):
        self.term_output.appendPlainText("\n[Shell process ended. Press Enter to restart.]")

    def setup_tree_view(self):
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath("")
        self.file_model.setReadOnly(False) 
        
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_model)
        self.tree_view.setHeaderHidden(True)
        for i in range(1, 4):
            self.tree_view.hideColumn(i)
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(16)
            
        self.tree_view.setDragEnabled(True)
        self.tree_view.setAcceptDrops(False)
        self.tree_view.setDragDropMode(QTreeView.DragOnly)
            
        self.tree_view.doubleClicked.connect(self.tree_file_clicked)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_explorer_menu)
        
        self.dock = QDockWidget("Project Explorer", self)
        self.dock.setObjectName("explorer_dock")
        self.dock.setWidget(self.tree_view)
        self.dock.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable
        )
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)
        
        self.default_workspace = os.getcwd()
        self.open_workspace(self.default_workspace)

    def show_explorer_menu(self, position):
        index  = self.tree_view.indexAt(position)
        
        if not index.isValid():
            path   = self.file_model.rootPath()
            is_dir = True
        else:
            path   = self.file_model.filePath(index)
            is_dir = os.path.isdir(path)
        
        menu = QMenu()
        
        new_file_action = new_dir_action = None
        if is_dir:
            new_file_action = menu.addAction("New File...")
            new_dir_action  = menu.addAction("New Folder...")
            menu.addSeparator()
            
        rename_action = menu.addAction("Rename...") if index.isValid() else None
        delete_action = menu.addAction("Delete")    if index.isValid() else None
        
        if index.isValid():
            menu.addSeparator()
            menu.addAction("Copy Path").triggered.connect(
                lambda: QApplication.clipboard().setText(path)
            )
            menu.addAction("Open in Windows Explorer").triggered.connect(
                lambda: subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
            )
            
        action = menu.exec_(self.tree_view.viewport().mapToGlobal(position))
        if action is None:
            return
        
        if is_dir and action == new_file_action:
            name, ok = QInputDialog.getText(self, "New File", "File name:")
            if ok and name.strip():
                new_path = os.path.join(path, name.strip())
                try:
                    open(new_path, 'w').close()
                    self.open_file_from_path(new_path) 
                except Exception as e:
                    QMessageBox.warning(self, "Error", str(e))

        elif is_dir and action == new_dir_action:
            name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
            if ok and name.strip():
                try:
                    os.makedirs(os.path.join(path, name.strip()), exist_ok=True)
                except Exception as e:
                    QMessageBox.warning(self, "Error", str(e))

        elif rename_action and action == rename_action:
            old_name = os.path.basename(path)
            new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=old_name)
            if ok and new_name.strip() and new_name.strip() != old_name:
                new_path = os.path.join(os.path.dirname(path), new_name.strip())
                try:
                    os.rename(path, new_path)
                    self.sync_tabs_after_rename(path, new_path)
                except Exception as e:
                    QMessageBox.warning(self, "Rename Error", str(e))

        elif delete_action and action == delete_action:
            label = os.path.basename(path)
            reply = QMessageBox.question(
                self, "Delete", 
                f"Permanently delete '{label}'?\nThis cannot be undone.", 
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    if is_dir:
                        self.file_model.rmdir(index)
                    else:
                        self.file_model.remove(index)
                        for i in range(self.tabs.count() - 1, -1, -1):
                            ed = self.tabs.widget(i)
                            if getattr(ed, 'file_path', '') == path:
                                self.tabs.removeTab(i)
                        if self.tabs.count() == 0:
                            self.new_file()
                except Exception as e:
                    QMessageBox.warning(self, "Delete Error", str(e))

    def sync_tabs_after_rename(self, old_path, new_path):
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if getattr(editor, 'file_path', '') == old_path:
                editor.file_path = new_path
                editor.filename  = os.path.basename(new_path)
                self.apply_syntax_highlighting(editor, new_path)
        self.update_tab_titles()

    def open_folder_dialog(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Open Workspace Folder")
        if folder_path:
            self.open_workspace(folder_path)

    def open_workspace(self, path):
        self.file_model.setRootPath(path)
        self.tree_view.setRootIndex(self.file_model.index(path))
        self.dock.setWindowTitle(f"Explorer - {os.path.basename(path)}")
        self.dock.show()
        if hasattr(self, 'process') and self.process.state() == QProcess.Running:
            self.process.write((f'cd /d "{path}"\r\n').encode())
        if hasattr(self, 'prompt_label'):
            short = path[:30] + "..." if len(path) > 30 else path
            self.prompt_label.setText(f"{short}>")
            
    def close_workspace(self):
        self.open_workspace(self.default_workspace)

    def setup_menu(self):
        menu = self.menuBar()
        
        file_menu = menu.addMenu("&File")
        self.add_action(file_menu, "&New File",         "Ctrl+N",       self.new_file)
        self.add_action(file_menu, "&Open File...",     "Ctrl+O",       self.open_file)
        self.add_action(file_menu, "&Save",             "Ctrl+S",       self.save_file)
        self.add_action(file_menu, "Save &As...",       "Ctrl+Shift+S", self.save_file_as)
        self.add_action(file_menu, "Save A&ll",         "Ctrl+Alt+S",   self.save_all)
        file_menu.addSeparator()
        self.add_action(file_menu, "Open &Folder...",   "Ctrl+K",       self.open_folder_dialog)
        self.add_action(file_menu, "Close Folder",      None,           self.close_workspace)
        file_menu.addSeparator()
        self.add_action(file_menu, "E&xit",             "Alt+F4",       self.close)

        edit_menu = menu.addMenu("&Edit")
        self.add_action(edit_menu, "&Undo",                "Ctrl+Z",     lambda: self.current_editor_action("undo"))
        self.add_action(edit_menu, "&Redo",                "Ctrl+Y",     lambda: self.current_editor_action("redo"))
        edit_menu.addSeparator()
        self.add_action(edit_menu, "Cu&t",                 "Ctrl+X",     lambda: self.current_editor_action("cut"))
        self.add_action(edit_menu, "&Copy",                "Ctrl+C",     lambda: self.current_editor_action("copy"))
        self.add_action(edit_menu, "&Paste",               "Ctrl+V",     lambda: self.current_editor_action("paste"))
        self.add_action(edit_menu, "Select &All",          "Ctrl+A",     lambda: self.current_editor_action("selectAll"))
        edit_menu.addSeparator()
        self.add_action(edit_menu, "&Find / Replace...",   "Ctrl+F",     self.show_find_replace)
        self.add_action(edit_menu, "&Go to Line...",       "Ctrl+G",     self.goto_line)
        edit_menu.addSeparator()
        self.add_action(edit_menu, "Toggle Line &Comment", "Ctrl+/",     self.toggle_comment)
        self.add_action(edit_menu, "D&uplicate Line",      "Ctrl+D",     self.duplicate_line)

        view_menu = menu.addMenu("&View")
        self.add_action(view_menu, "Zoom &In",           "Ctrl+=",   lambda: self.current_editor_action("zoomIn"))
        self.add_action(view_menu, "Zoom &Out",          "Ctrl+-",   lambda: self.current_editor_action("zoomOut"))
        self.add_action(view_menu, "Reset Zoom",         "Ctrl+0",   self.reset_zoom)
        view_menu.addSeparator()
        
        self.wrap_act = QAction("Word Wrap", self, checkable=True)
        self.wrap_act.setShortcut("Alt+Z")
        self.wrap_act.setChecked(self._word_wrap)
        self.wrap_act.toggled.connect(self.set_word_wrap)
        view_menu.addAction(self.wrap_act)

        self.ws_act = QAction("Show Whitespace", self, checkable=True)
        self.ws_act.setShortcut("Alt+W")
        self.ws_act.setChecked(self._show_ws)
        self.ws_act.toggled.connect(self.set_whitespace)
        view_menu.addAction(self.ws_act)
        
        view_menu.addSeparator()
        term_act = self.terminal_dock.toggleViewAction()
        term_act.setText("Terminal Panel")
        term_act.setShortcut("Ctrl+`")
        view_menu.addAction(term_act)
        
        exp_act = self.dock.toggleViewAction()
        exp_act.setText("Explorer Panel")
        exp_act.setShortcut("Ctrl+B")
        view_menu.addAction(exp_act)

        run_menu = menu.addMenu("&Run")
        self.add_action(run_menu, "Run Current File",    "F5",       self.run_current_file)
        run_menu.addSeparator()
        self.cleanup_act = QAction("Auto-Cleanup Compiled Files", self, checkable=True)
        self.cleanup_act.setChecked(self.settings.value("auto_cleanup", True, type=bool))
        self.cleanup_act.toggled.connect(lambda checked: self.settings.setValue("auto_cleanup", checked))
        run_menu.addAction(self.cleanup_act)

        help_menu = menu.addMenu("&Help")
        docs_menu = help_menu.addMenu("&Documentation")
        self.add_action(docs_menu, "Python",             None, lambda: webbrowser.open("https://docs.python.org/3/"))
        self.add_action(docs_menu, "C/C++ Reference",    None, lambda: webbrowser.open("https://en.cppreference.com/w/"))
        self.add_action(docs_menu, "HTML / CSS / JS",    None, lambda: webbrowser.open("https://developer.mozilla.org/"))
        self.add_action(docs_menu, "Java",               None, lambda: webbrowser.open("https://docs.oracle.com/en/java/"))
        self.add_action(docs_menu, "Ruby",               None, lambda: webbrowser.open("https://www.ruby-lang.org/en/documentation/"))
        self.add_action(docs_menu, "PHP",                None, lambda: webbrowser.open("https://www.php.net/docs.php"))
        self.add_action(docs_menu, "Rust",               None, lambda: webbrowser.open("https://doc.rust-lang.org/book/"))
        self.add_action(docs_menu, "SQL (W3Schools)",    None, lambda: webbrowser.open("https://www.w3schools.com/sql/"))
        self.add_action(docs_menu, "Bash (GNU)",         None, lambda: webbrowser.open("https://www.gnu.org/software/bash/manual/"))
        self.add_action(docs_menu, "Perl",               None, lambda: webbrowser.open("https://perldoc.perl.org/"))
        help_menu.addSeparator()
        self.add_action(help_menu, "View &License",      None, self.open_license_file)

    def add_action(self, menu, name, shortcut, callback):
        action = QAction(name, self)
        if shortcut: 
            action.setShortcut(shortcut)
        action.triggered.connect(callback)
        menu.addAction(action)

    def create_editor(self):
        editor = QsciScintilla()
        editor.setUtf8(True)
        
        font = QFont("Courier New", 10)
        editor.setFont(font)
        editor.setMarginsFont(font)
        
        editor.setMarginType(0, QsciScintilla.NumberMargin)
        editor.setMarginWidth(0, "000000") 
        
        editor.setMarginType(2, QsciScintilla.SymbolMargin)
        editor.setMarginWidth(2, 14)
        editor.setFolding(QsciScintilla.BoxedTreeFoldStyle)
        editor.setFoldMarginColors(QColor("#f0f0f0"), QColor("#d0d0d0"))
        
        editor.setIndentationGuides(True)
        editor.setEdgeMode(QsciScintilla.EdgeNone)
        editor.setEdgeColumn(80)
        editor.setEdgeColor(QColor("#E0E0E0"))
        editor.setCaretLineVisible(True)
        editor.setCaretLineBackgroundColor(QColor("#EFF5FB")) 
        editor.setBraceMatching(QsciScintilla.SloppyBraceMatch)
        editor.setAutoIndent(True)
        editor.setIndentationsUseTabs(False)
        editor.setTabWidth(4)

        editor.setWrapMode(QsciScintilla.WrapWord if self._word_wrap else QsciScintilla.WrapNone)
        editor.setWhitespaceVisibility(QsciScintilla.WsVisible if self._show_ws else QsciScintilla.WsInvisible)
        
        editor.cursorPositionChanged.connect(self.update_status_bar)
        editor.modificationChanged.connect(self.update_tab_titles)
        
        return editor

    def current_editor_action(self, action_name):
        editor = self.tabs.currentWidget()
        if editor: 
            getattr(editor, action_name)()

    def set_word_wrap(self, checked):
        self._word_wrap = checked
        mode = QsciScintilla.WrapWord if checked else QsciScintilla.WrapNone
        for i in range(self.tabs.count()):
            self.tabs.widget(i).setWrapMode(mode)
        self.statusBar().showMessage(f" Word Wrap: {'ON' if checked else 'OFF'}", 2000)

    def set_whitespace(self, checked):
        self._show_ws = checked
        mode = QsciScintilla.WsVisible if checked else QsciScintilla.WsInvisible
        for i in range(self.tabs.count()):
            self.tabs.widget(i).setWhitespaceVisibility(mode)
        self.statusBar().showMessage(f" Show Whitespace: {'ON' if checked else 'OFF'}", 2000)

    def reset_zoom(self):
        editor = self.tabs.currentWidget()
        if editor:
            editor.zoomTo(0)

    def duplicate_line(self):
        editor = self.tabs.currentWidget()
        if editor:
            editor.SendScintilla(QsciScintilla.SCI_LINEDUPLICATE)

    def toggle_comment(self):
        editor = self.tabs.currentWidget()
        if not editor: return
        path = getattr(editor, 'file_path', '')
        ext  = os.path.splitext(path)[1].lower() if path else ''

        if ext in ('.lua',):
            token = '--'
        elif ext in ('.bat', '.cmd'):
            token = 'REM '
        elif ext in ('.py', '.pyw', '.rb', '.sh', '.bash', '.zsh', '.pl'):
            token = '#'
        elif ext in ('.html', '.htm', '.xml', '.css'):
            self.statusBar().showMessage(" Toggle comment not supported for this file type.", 2000)
            return
        else:
            token = '//'

        line_from, _, line_to, _ = editor.getSelection()
        if line_from == -1:
            line_from = line_to = editor.getCursorPosition()[0]

        for ln in range(line_from, line_to + 1):
            text     = editor.text(ln)
            stripped = text.lstrip()
            indent   = text[: len(text) - len(stripped)]
            if stripped.startswith(token):
                editor.setSelection(ln, len(indent), ln, len(indent) + len(token))
                editor.replaceSelectedText("")
            else:
                editor.insertAt(token, ln, len(indent))

    def show_find_replace(self):
        editor = self.tabs.currentWidget()
        if editor:
            sel = editor.selectedText()
            if sel:
                self.find_dialog.find_input.setText(sel)
        self.find_dialog.show()
        self.find_dialog.find_input.setFocus()
        self.find_dialog.find_input.selectAll()

    def do_find(self, forward=True):
        editor = self.tabs.currentWidget()
        if not editor: return
        text  = self.find_dialog.find_input.text()
        if not text: return
        case  = self.find_dialog.case_cb.isChecked()
        whole = self.find_dialog.whole_cb.isChecked()
        regex = self.find_dialog.regex_cb.isChecked()
        found = editor.findFirst(text, regex, case, whole, True, forward)
        self.find_dialog.set_status("" if found else f"'{text}' not found.")

    def do_replace(self):
        editor = self.tabs.currentWidget()
        if not editor: return
        if editor.hasSelectedText():
            editor.replaceSelectedText(self.find_dialog.replace_input.text())
        self.do_find(forward=True)

    def do_replace_all(self):
        editor = self.tabs.currentWidget()
        if not editor: return
        find_text    = self.find_dialog.find_input.text()
        replace_text = self.find_dialog.replace_input.text()
        case  = self.find_dialog.case_cb.isChecked()
        whole = self.find_dialog.whole_cb.isChecked()
        regex = self.find_dialog.regex_cb.isChecked()
        count = 0
        editor.setCursorPosition(0, 0)
        while editor.findFirst(find_text, regex, case, whole, False):
            editor.replaceSelectedText(replace_text)
            count += 1
        self.find_dialog.set_status(f"Replaced {count} occurrence(s).")

    def goto_line(self):
        editor = self.tabs.currentWidget()
        if not editor: return
        max_line = editor.lines()
        dlg = GotoLineDialog(self, max_line)
        if dlg.exec_() == QDialog.Accepted:
            ln = dlg.value()
            if 1 <= ln <= max_line:
                editor.setCursorPosition(ln - 1, 0)
                editor.ensureLineVisible(ln - 1)
            else:
                self.statusBar().showMessage(f" Line {ln} is out of range (1-{max_line}).", 3000)

    def new_file(self):
        editor = self.create_editor()
        editor.filename = "Untitled"
        self.tabs.addTab(editor, editor.filename)
        self.tabs.setCurrentWidget(editor)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*)")
        if path:
            self.open_file_from_path(path)

    def open_file_from_path(self, path):
        for i in range(self.tabs.count()):
            if getattr(self.tabs.widget(i), 'file_path', '') == path:
                self.tabs.setCurrentIndex(i)
                return

        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Cannot Open File", str(e))
            return

        editor = self.create_editor()
        editor.setText(content)
        self.apply_syntax_highlighting(editor, path)
        editor.file_path = path
        editor.filename  = os.path.basename(path)
        editor.setModified(False)
        self.tabs.addTab(editor, editor.filename)
        self.tabs.setCurrentWidget(editor)

    def save_file(self, index=None, proposed_name=None):
        if not isinstance(index, int):
            index = self.tabs.currentIndex()
        editor = self.tabs.widget(index)
        if not editor: return False

        if hasattr(editor, 'file_path') and os.path.exists(editor.file_path) and not proposed_name:
            path = editor.file_path
        else:
            default = proposed_name or getattr(editor, 'filename', 'Untitled')
            path, _ = QFileDialog.getSaveFileName(self, "Save File", default, "All Files (*)")
            if not path: return False
            editor.file_path = path
            editor.filename  = os.path.basename(path)

        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(editor.text())
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
            return False
            
        editor.setModified(False)
        self.apply_syntax_highlighting(editor, path)
        self.update_tab_titles()
        self.statusBar().showMessage(f" Saved: {os.path.basename(path)}", 3000)
        return True

    def save_file_as(self):
        index  = self.tabs.currentIndex()
        editor = self.tabs.widget(index)
        if not editor: return
        default = getattr(editor, 'file_path', '') or getattr(editor, 'filename', 'Untitled')
        path, _ = QFileDialog.getSaveFileName(self, "Save As", default, "All Files (*)")
        if not path: return
        editor.file_path = path
        editor.filename  = os.path.basename(path)
        self.save_file(index)

    def save_all(self):
        saved = 0
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if editor.isModified():
                if self.save_file(i):
                    saved += 1
        self.statusBar().showMessage(f" Saved {saved} file(s).", 3000)

    def close_tab(self, index):
        editor = self.tabs.widget(index)
        if editor and editor.isModified():
            name  = getattr(editor, 'filename', 'Untitled')
            reply = QMessageBox.question(
                self, "Unsaved Changes", 
                f"Save changes to '{name}' before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                if not self.save_file(index):
                    return 
            elif reply == QMessageBox.Cancel:
                return 

        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.new_file()

    def closeEvent(self, event):
        self.settings.setValue("geometry",    self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        
        open_paths = []
        for i in range(self.tabs.count()):
            p = getattr(self.tabs.widget(i), 'file_path', '')
            if p and os.path.exists(p):
                open_paths.append(p)
        self.settings.setValue("lastFiles", open_paths)

        modified_editors = [self.tabs.widget(i) for i in range(self.tabs.count()) if self.tabs.widget(i).isModified()]
        
        if modified_editors:
            self.tabs.setCurrentWidget(modified_editors[0])
            msg = QMessageBox(self)
            msg.setWindowTitle("Unsaved Changes")
            msg.setText("You have unsaved files. Do you want to save all currently made changes before exiting?")
            msg.setStandardButtons(QMessageBox.SaveAll | QMessageBox.Discard | QMessageBox.Cancel)
            reply = msg.exec_()
            
            if reply == QMessageBox.SaveAll:
                self.save_all()
                if any(ed.isModified() for ed in modified_editors):
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        
        if hasattr(self, 'process') and self.process.state() == QProcess.Running:
            self.process.kill()
            self.process.waitForFinished(1000)
            
        event.accept()

    def apply_syntax_highlighting(self, editor, path):
        ext = os.path.splitext(path)[1].lower()
        lexer = None
        
        if   ext in ('.py', '.pyw'):                                    lexer = QsciLexerPython(editor)
        elif ext in ('.c', '.cpp', '.cc', '.h', '.hpp', 
                     '.cs', '.java', '.swift', '.kt', '.rs'):           lexer = QsciLexerCPP(editor)
        elif ext in ('.html', '.htm', '.xml', '.php'):                  lexer = QsciLexerHTML(editor)
        elif ext in ('.js', '.jsx', '.ts', '.tsx'):                     lexer = QsciLexerJavaScript(editor)
        elif ext in ('.css', '.scss', '.less'):                         lexer = QsciLexerCSS(editor)
        elif ext in ('.rb',):                                           lexer = QsciLexerRuby(editor)
        elif ext in ('.pl',):                                           lexer = QsciLexerPerl(editor)
        elif ext in ('.sh', '.bash', '.zsh'):                           lexer = QsciLexerBash(editor)
        elif ext in ('.bat', '.cmd'):                                   lexer = QsciLexerBatch(editor)
        elif ext in ('.sql',):                                          lexer = QsciLexerSQL(editor)
        elif ext in ('.ini', '.properties', '.cfg', '.conf', '.env'):   lexer = QsciLexerProperties(editor)
        
        if lexer:
            font = QFont("Courier New", 10)
            lexer.setDefaultFont(font)
            for style in range(128):
                try:
                    lexer.setFont(font, style)
                except Exception:
                    pass
            editor.setLexer(lexer)
        else:
            editor.setLexer(None)

    def edit_tab_title(self, index):
        if index < 0: return
        if self.rename_edit:
            self.rename_edit.deleteLater()
            self.rename_edit = None
            
        rect = self.tabs.tabBar().tabRect(index)
        rect.moveTopLeft(self.tabs.tabBar().mapToParent(rect.topLeft()))
        
        self.rename_edit = QLineEdit(self.tabs)
        editor = self.tabs.widget(index)
        self.rename_edit.setText(getattr(editor, 'filename', 'Untitled'))
        self.rename_edit.setGeometry(rect)
        self.rename_edit.setFocus()
        self.rename_edit.selectAll()
        self.rename_edit.show()
        
        self.rename_edit.returnPressed.connect(lambda: self.finish_rename(index))
        self.rename_edit.editingFinished.connect(lambda: self.finish_rename(index))

    def finish_rename(self, index):
        if not self.rename_edit: return
        
        widget           = self.rename_edit
        self.rename_edit = None 
        new_name         = widget.text().strip()
        widget.hide()
        widget.deleteLater()
        
        if not new_name: return
        
        editor   = self.tabs.widget(index)
        if not editor: return
        old_path = getattr(editor, 'file_path', None)
        
        if old_path and os.path.exists(old_path):
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            if new_path != old_path:
                try:
                    os.rename(old_path, new_path)
                    editor.file_path = new_path
                except Exception as e:
                    QMessageBox.warning(self, "Rename Error", f"Could not rename file:\n{e}")
                    return
            editor.filename = new_name
            self.apply_syntax_highlighting(editor, getattr(editor, 'file_path', new_name))
        else:
            self.save_file(index, proposed_name=new_name)

        self.update_tab_titles()

    def update_tab_titles(self, index=None):
        for i in range(self.tabs.count()):
            editor    = self.tabs.widget(i)
            full_name = getattr(editor, 'filename', 'Untitled')
            modified  = editor.isModified()
            display   = full_name + (" *" if modified else "")
            
            if i == self.tabs.currentIndex():
                self.tabs.setTabText(i, display)
                self.tabs.setTabToolTip(i, getattr(editor, 'file_path', full_name))
                ln, col = editor.getCursorPosition()
                self.update_status_bar(ln, col)
                if hasattr(editor, 'file_path') and os.path.exists(editor.file_path):
                    dir_path = os.path.dirname(editor.file_path)
                    if hasattr(self, 'process') and self.process.state() == QProcess.Running:
                        self.process.write((f'cd /d "{dir_path}"\r\n').encode())
                    if hasattr(self, 'prompt_label'):
                        short = dir_path[:30] + "..." if len(dir_path) > 30 else dir_path
                        self.prompt_label.setText(f"{short}>")
            else:
                if len(display) > 16:
                    ext_idx = display.rfind('.')
                    if ext_idx != -1 and (len(display) - ext_idx) <= 7:
                        ext  = display[ext_idx:]
                        base = display[:ext_idx]
                        display = base[:6] + "..." + ext
                    else:
                        display = display[:12] + "..."
                self.tabs.setTabText(i, display)

    def tree_file_clicked(self, index):
        path = self.file_model.filePath(index)
        if os.path.isfile(path):
            self.open_file_from_path(path)

    def update_status_bar(self, line, col):
        self.status_label.setText(f"  Ln {line + 1},  Col {col + 1}")

    def run_current_file(self):
        editor = self.tabs.currentWidget()
        if not editor: return

        if not hasattr(editor, 'file_path') or not os.path.exists(editor.file_path):
            reply = QMessageBox.question(
                self, "Save Required", 
                "The file must be saved before it can be run.\nSave now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                if not self.save_file(): return
            else: return
                
        if editor.isModified():
            self.save_file()

        path = os.path.normpath(editor.file_path)
        base_path = os.path.splitext(path)[0]
        exe_path = f"{base_path}.exe"
        class_path = f"{base_path}.class"

        cleanup = f' & del /f /q "{exe_path}"' if self.cleanup_act.isChecked() else ""
        cleanup_java = f' & del /f /q "{class_path}"' if self.cleanup_act.isChecked() else ""
        
        ext = os.path.splitext(path)[1].lower()
        cmd = ""
        
        if   ext in ('.py', '.pyw'): cmd = f'python "{path}"'
        elif ext == '.js':           cmd = f'node "{path}"'
        elif ext == '.rb':           cmd = f'ruby "{path}"'
        elif ext == '.php':          cmd = f'php "{path}"'
        elif ext in ('.bat', '.cmd'):cmd = f'"{path}"'
        
        elif ext in ('.cpp', '.cc'):
            self.term_output.appendPlainText("\n[Compiling C++...]")
            cmd = f'g++ -o "{exe_path}" "{path}" && "{exe_path}"{cleanup}'
        elif ext == '.c':
            self.term_output.appendPlainText("\n[Compiling C...]")
            cmd = f'gcc -o "{exe_path}" "{path}" && "{exe_path}"{cleanup}'
        elif ext == '.java':
            self.term_output.appendPlainText("\n[Compiling Java...]")
            class_name = os.path.splitext(os.path.basename(path))[0]
            cmd = f'javac "{path}" && java -cp "{os.path.dirname(path)}" {class_name}{cleanup_java}'
        elif ext == '.cs':
            self.term_output.appendPlainText("\n[Compiling C#...]")
            cmd = f'csc /nologo /out:"{exe_path}" "{path}" && "{exe_path}"{cleanup}'
        elif ext == '.rs':
            self.term_output.appendPlainText("\n[Compiling Rust...]")
            cmd = f'rustc "{path}" -o "{exe_path}" && "{exe_path}"{cleanup}'
        else:
            self.terminal_dock.show()
            self.term_output.appendPlainText(f"\n[INFO] EzEdit cannot auto-run '{ext}' files.")
            return

        self.terminal_dock.show()
        self.term_input.setFocus()
        self.term_output.appendPlainText(f"\n--- Running: {editor.filename} ---")
        self.process.write((cmd + '\r\n').encode())

    def open_license_file(self):
        license_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LICENSE.txt")
        if os.path.exists(license_path):
            self.open_file_from_path(license_path)
            editor = self.tabs.currentWidget()
            if editor:
                editor.setReadOnly(True)
        else:
            QMessageBox.information(self, "Not Found", "LICENSE.txt was not found next to editor.py.")

if __name__ == "__main__":
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("colingarbutt.ezedit.1.0")
    except AttributeError:
        pass

    app = QApplication(sys.argv)
    app.setFont(QFont("Tahoma", 8))
    app.setStyle("Windows")

    window = EzEdit()

    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            window.open_file_from_path(arg)

    window.show()
    sys.exit(app.exec_())
