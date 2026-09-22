#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, COMM, ID3NoHeaderError
from PyQt6.QtCore import Qt, QMimeData, QSize, QByteArray
from PyQt6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
    QPixmap,
    QAction,
    QKeySequence,
    QIcon,
    QFontDatabase,
    QFont
)
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QListWidget,
    QLabel,
    QFrame,
    QFileDialog,
    QMessageBox,
    QStyle
)


# ----------------- RESOURCE PATH HELPER -----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_name: str) -> str:
    """
    Kaynak dosyasını (ikon, font vb.) önce betiğin kendi dizininde,
    bulamazsa /usr/share/PyTag sistem dizininde arar.
    """
    local_path = os.path.join(BASE_DIR, relative_name)
    if os.path.exists(local_path):
        return local_path
    system_path = os.path.join("/usr/share/PyTag", relative_name)
    if os.path.exists(system_path):
        return system_path
    return local_path


class ImageDropLabel(QLabel):
    """Square area for Drag & Drop cover art."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Drag & Drop\nCover Image Here\n(or Click)")
        self.setFixedSize(200, 200)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #3584e4;
                border-radius: 8px;
                background-color: rgba(53, 132, 228, 0.04);
                color: #3584e4;
                font-size: 12px;
                font-weight: 500;
            }
            QLabel:hover {
                border-color: #1c71d8;
                color: #1c71d8;
                background-color: rgba(53, 132, 228, 0.10);
            }
        """)
        self.image_path = None

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = os.path.splitext(url.toLocalFile())[1].lower()
                if ext in ['.jpg', '.jpeg', '.png']:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png']:
                self.set_image(file_path)
                main_win = self.window()
                if hasattr(main_win, 'set_cover_for_selected'):
                    with open(file_path, "rb") as f:
                        main_win.set_cover_for_selected(f.read(), ext)
                event.acceptProposedAction()
                break

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            home_dir = os.path.expanduser("~")
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Cover Image", home_dir, "Images (*.png *.jpg *.jpeg)"
            )
            if file_path:
                self.set_image(file_path)
                ext = os.path.splitext(file_path)[1].lower()
                main_win = self.window()
                if hasattr(main_win, 'set_cover_for_selected'):
                    with open(file_path, "rb") as f:
                        main_win.set_cover_for_selected(f.read(), ext)

    def set_image(self, file_path: str):
        self.image_path = file_path
        pixmap = QPixmap(file_path)
        scaled_pixmap = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled_pixmap)

    def clear_image(self):
        self.image_path = None
        self.clear()
        self.setText("Drag & Drop\nCover Image Here\n(or Click)")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyTag - Mp3 Tag Editor")
        self.setMinimumSize(680, 520)
        self.resize(760, 580)
        self.setAcceptDrops(True)

        # Uygulama resmi ikonu (PyTag.png)
        app_icon_path = get_resource_path("PyTag.png")
        if os.path.exists(app_icon_path):
            self.setWindowIcon(QIcon(app_icon_path))

        self.mp3_files = []
        self.file_tags = {}  # Holds {file_path: {'tags': {...}, 'image': bytes/None, 'dirty': bool}}
        self.is_modified = False
        self.current_file = None
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main Layout: Left side (Files + Image) & Right side (Tags + Buttons)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ----------------- LEFT SIDE -----------------
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)

        # 1. List Header Label
        lbl_file_list = QLabel("Track List")
        lbl_file_list.setStyleSheet("font-weight: bold; font-size: 13px;")
        left_layout.addWidget(lbl_file_list)

        # 2. File List Widget with proper styling and scrollbars
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.file_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.file_list.setAlternatingRowColors(True)  # Visual enhancement
        self.file_list.itemSelectionChanged.connect(self.on_file_selection_changed)
        left_layout.addWidget(self.file_list)

        # 3. List Action Buttons (Add, Remove, Clear)
        list_btn_layout = QHBoxLayout()
        list_btn_layout.setSpacing(6)

        self.btn_list_add = QPushButton("Add")
        self.btn_list_remove = QPushButton("Remove")
        self.btn_list_clear = QPushButton("Clear")

        list_btn_layout.addWidget(self.btn_list_add)
        list_btn_layout.addWidget(self.btn_list_remove)
        list_btn_layout.addWidget(self.btn_list_clear)

        left_layout.addLayout(list_btn_layout)

        # 4. Cover Image Drop Box & Control Buttons
        cover_container_layout = QHBoxLayout()
        cover_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_container_layout.setSpacing(6)

        self.cover_label = ImageDropLabel()

        # Sistem ikonlarını kullanan dikey buton çubuğu
        cover_btn_layout = QVBoxLayout()
        cover_btn_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        cover_btn_layout.setSpacing(6)

        self.btn_cover_change = QPushButton()
        self.btn_cover_change.setFixedSize(34, 34)
        self.btn_cover_change.setToolTip("Change / Add Cover Image")
        icon_change = QIcon.fromTheme(
            "document-open",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        self.btn_cover_change.setIcon(icon_change)
        self.btn_cover_change.clicked.connect(self.action_change_cover)

        self.btn_cover_remove = QPushButton()
        self.btn_cover_remove.setFixedSize(34, 34)
        self.btn_cover_remove.setToolTip("Remove Embedded Cover Art")
        # Sistem temasından 'edit-delete' veya Qt'nin standart çöp kutusu simgesini çek
        icon_remove = QIcon.fromTheme(
            "edit-delete",
            self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        )
        self.btn_cover_remove.setIcon(icon_remove)
        self.btn_cover_remove.clicked.connect(self.action_remove_cover)

        cover_btn_layout.addWidget(self.btn_cover_change)
        cover_btn_layout.addWidget(self.btn_cover_remove)

        cover_container_layout.addWidget(self.cover_label)
        cover_container_layout.addLayout(cover_btn_layout)

        left_layout.addLayout(cover_container_layout)

        main_layout.addLayout(left_layout, stretch=4)

        # ----------------- RIGHT SIDE -----------------
        right_layout = QVBoxLayout()

        # Tag Input Fields (QLineEdits & QTextEdit)
        form_layout = QFormLayout()
        form_layout.setSpacing(6)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.input_title = QLineEdit()
        self.input_artist = QLineEdit()
        self.input_album_artist = QLineEdit()
        self.input_album = QLineEdit()
        self.input_composer = QLineEdit()
        self.input_year = QLineEdit()
        self.input_track = QLineEdit()
        self.input_disc = QLineEdit()
        self.input_genre = QLineEdit()

        form_layout.addRow("Title:", self.input_title)
        form_layout.addRow("Artist:", self.input_artist)
        form_layout.addRow("Album Artist:", self.input_album_artist)
        form_layout.addRow("Album:", self.input_album)
        form_layout.addRow("Composer:", self.input_composer)
        form_layout.addRow("Year:", self.input_year)
        form_layout.addRow("Track #:", self.input_track)
        form_layout.addRow("Disc #:", self.input_disc)
        form_layout.addRow("Genre:", self.input_genre)

        right_layout.addLayout(form_layout)

        # Multi-line Comment Field (Fills the remaining vertical space)
        lbl_comment = QLabel("Comment:")
        right_layout.addWidget(lbl_comment)

        self.input_comment = QTextEdit()
        self.input_comment.setAcceptRichText(False)
        self.input_comment.setPlaceholderText("Add comments, notes, or lyrics...")
        right_layout.addWidget(self.input_comment)

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()

        self.btn_clear_sel = QPushButton("Clear Selected")
        self.btn_clear_all = QPushButton("Clear All")
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setDefault(True)

        btn_layout.addWidget(self.btn_clear_sel)
        btn_layout.addWidget(self.btn_clear_all)
        btn_layout.addWidget(self.btn_apply)

        right_layout.addLayout(btn_layout)

        main_layout.addLayout(right_layout, stretch=5)

        # Signal connections
        self.btn_list_add.clicked.connect(self.action_add_files)
        self.btn_list_remove.clicked.connect(self.action_remove_files)
        self.btn_list_clear.clicked.connect(self.action_clear_list)

        self.btn_clear_sel.clicked.connect(self.clear_selected_files)
        self.btn_clear_all.clicked.connect(self.clear_all_fields)
        self.btn_apply.clicked.connect(self.apply_tags)

        # Track changes in inputs to warn on exit
        for line_edit in [self.input_title, self.input_artist, self.input_album_artist,
                          self.input_album, self.input_composer, self.input_year,
                          self.input_track, self.input_disc, self.input_genre]:
            line_edit.textEdited.connect(self.mark_as_modified)

        self.input_comment.textChanged.connect(self.mark_as_modified)

        # Create menu bar after UI widgets (like file_list) are initialized
        self.create_menu_bar()

# ----------------- MENU BAR CREATION -----------------
    def create_menu_bar(self):
        menubar = self.menuBar()

        # 1. FILE MENU
        file_menu = menubar.addMenu("&File")

        act_add_files = QAction("&Add Files...", self)
        act_add_files.setShortcut(QKeySequence.StandardKey.Open)  # Ctrl+O
        act_add_files.triggered.connect(self.action_add_files)
        file_menu.addAction(act_add_files)

        act_add_folder = QAction("Add &Folder...", self)
        act_add_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_add_folder.triggered.connect(self.action_add_folder)
        file_menu.addAction(act_add_folder)

        file_menu.addSeparator()

        act_apply = QAction("&Apply Changes", self)
        act_apply.setShortcut(QKeySequence.StandardKey.Save)  # Ctrl+S
        act_apply.triggered.connect(self.apply_tags)
        file_menu.addAction(act_apply)

        file_menu.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)  # Ctrl+Q
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # 2. EDIT MENU
        edit_menu = menubar.addMenu("&Edit")

        act_select_all = QAction("&Select All Files", self)
        act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)  # Ctrl+A
        act_select_all.triggered.connect(self.file_list.selectAll)
        edit_menu.addAction(act_select_all)

        edit_menu.addSeparator()

        act_clear_sel_tags = QAction("Clear &Selected Tags", self)
        act_clear_sel_tags.triggered.connect(self.clear_selected_files)
        edit_menu.addAction(act_clear_sel_tags)

        act_clear_all_tags = QAction("Clear &All Tags", self)
        act_clear_all_tags.triggered.connect(self.clear_all_fields)
        edit_menu.addAction(act_clear_all_tags)

        edit_menu.addSeparator()

        act_remove_files = QAction("&Remove Selected from List", self)
        act_remove_files.setShortcut(QKeySequence.StandardKey.Delete)
        act_remove_files.triggered.connect(self.action_remove_files)
        edit_menu.addAction(act_remove_files)

        act_clear_list = QAction("Clear &File List", self)
        act_clear_list.triggered.connect(self.action_clear_list)
        edit_menu.addAction(act_clear_list)

        # 3. HELP MENU
        help_menu = menubar.addMenu("&Help")

        act_about = QAction("&About PyTag", self)
        act_about.triggered.connect(self.action_show_about)
        help_menu.addAction(act_about)

    def action_add_folder(self):
        """Allows user to pick a folder from the File menu."""
        home_dir = os.path.expanduser("~")
        dir_path = QFileDialog.getExistingDirectory(self, "Select Folder Containing MP3s", home_dir)
        if dir_path:
            self.load_directory(dir_path)

    def action_show_about(self):
        """Displays About Dialog with App Icon, metadata and GitHub link."""
        about_box = QMessageBox(self)
        about_box.setWindowTitle("About PyTag")
        about_box.setTextFormat(Qt.TextFormat.RichText)
        about_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)

        icon_path = get_resource_path("PyTag.png")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(
                64, 64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            about_box.setIconPixmap(pix)

        about_text = (
            "<h2 style='margin-bottom: 2px;'>PyTag</h2>"
            "<b>Version:</b> 0.0.1 (beta)<br>"
            "<b>License:</b> GNU GPLv3<br>"
            "<b>GUI / UX:</b> Qt-6<br>"
            "<b>Language:</b> Python 3<br>"
            "<b>Developer:</b> A. Serhat KILIÇOĞLU (shampuan)<br>"
            "<b>GitHub:</b> <a href='https://github.com/shampuan'>github.com/shampuan</a>"
            "<hr style='margin: 8px 0;'>"
            "<p>PyTag is a very simple and lightweight Python application that allows "
            "you to edit the tags of your music files.</p>"
            "<p><i>This program comes with absolutely no warranty.</i></p>"
            "<p style='color: #666;'>Copyright &copy; 2026 - A. Serhat KILIÇOĞLU</p>"
        )

        about_box.setText(about_text)
        about_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        about_box.exec()

    # ----------------- COVER ACTIONS -----------------
    def action_change_cover(self):
        """Opens dialog to select a cover image and applies it to selection."""
        home_dir = os.path.expanduser("~")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Cover Image", home_dir, "Images (*.png *.jpg *.jpeg)"
        )
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            with open(file_path, "rb") as f:
                self.set_cover_for_selected(f.read(), ext)
            self.cover_label.set_image(file_path)

    def action_remove_cover(self):
        """Removes cover art from selected files (or ALL if none selected)."""
        selected_rows = [idx.row() for idx in self.file_list.selectedIndexes()]
        target_indices = selected_rows if selected_rows else range(len(self.mp3_files))

        if not target_indices:
            return

        for r in target_indices:
            f = self.mp3_files[r]
            self.file_tags[f]['image'] = None
            self.file_tags[f]['dirty'] = True

        self.cover_label.clear_image()
        self.is_modified = True

    # ----------------- LIST ACTION BUTTONS -----------------
    def action_add_files(self):
        """Opens file dialog to select and append MP3 files to the list."""
        home_dir = os.path.expanduser("~")
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Audio Files",
            home_dir,
            "Audio Files (*.mp3)"
        )
        if files:
            for f in sorted(files):
                self.add_file(f)

    def action_remove_files(self):
        """Removes selected files from the list and internal memory."""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return

        for item in reversed(selected_items):
            row = self.file_list.row(item)
            self.file_list.takeItem(row)
            if row < len(self.mp3_files):
                file_path = self.mp3_files.pop(row)
                self.file_tags.pop(file_path, None)

        # Clear UI fields if the list becomes empty
        if not self.mp3_files:
            self.action_clear_list()

    def action_clear_list(self):
        """Clears the whole list, memory cache, and tag input fields."""
        self.file_list.clear()
        self.mp3_files.clear()
        self.file_tags.clear()
        self.current_file = None

        self.input_title.clear()
        self.input_artist.clear()
        self.input_album_artist.clear()
        self.input_album.clear()
        self.input_composer.clear()
        self.input_year.clear()
        self.input_track.clear()
        self.input_disc.clear()
        self.input_genre.clear()
        self.input_comment.clear()
        self.cover_label.clear_image()
        self.is_modified = False
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                self.load_directory(path)
            elif os.path.isfile(path) and path.lower().endswith(".mp3"):
                self.add_file(path)
        event.acceptProposedAction()

    def load_directory(self, dir_path: str):
        for root, _, files in os.walk(dir_path):
            for file in sorted(files):
                if file.lower().endswith(".mp3"):
                    self.add_file(os.path.join(root, file))

    def add_file(self, file_path: str):
        if file_path not in self.mp3_files:
            self.mp3_files.append(file_path)
            self.file_list.addItem(os.path.basename(file_path))
            self.read_tags_to_memory(file_path)

    def read_tags_to_memory(self, file_path: str):
        """Reads tags and image from physical file into application memory."""
        tags = {
            'title': '', 'artist': '', 'albumartist': '', 'album': '',
            'composer': '', 'date': '', 'tracknumber': '', 'discnumber': '',
            'genre': '', 'comment': ''
        }
        image_data = None

        try:
            audio = EasyID3(file_path)
            for k in ['title', 'artist', 'albumartist', 'album', 'composer', 'date', 'tracknumber', 'discnumber', 'genre']:
                tags[k] = audio.get(k, [''])[0]
        except (ID3NoHeaderError, KeyError):
            pass

        try:
            full_id3 = ID3(file_path)
            # Read Comment (COMM frame)
            comments = full_id3.getall("COMM")
            if comments:
                tags['comment'] = comments[0].text[0]

            # Read Cover Art
            for tag in full_id3.values():
                if isinstance(tag, APIC):
                    image_data = tag.data
                    break
        except ID3NoHeaderError:
            pass

        self.file_tags[file_path] = {'tags': tags, 'image': image_data, 'dirty': False}

    # ----------------- ACTIONS & SLOTS -----------------
    def on_file_selection_changed(self):
        """Updates right fields based on the selected item."""
        selected_items = self.file_list.selectedIndexes()
        count = len(selected_items)

        # Tüm metin kutularının listesi
        text_inputs = [
            self.input_title, self.input_artist, self.input_album_artist,
            self.input_album, self.input_composer, self.input_year,
            self.input_track, self.input_disc, self.input_genre, self.input_comment
        ]

        if count == 0:
            self.current_file = None
            for w in text_inputs:
                w.clear()
                w.setEnabled(False)
            self.cover_label.clear_image()
            return

        elif count > 1:
            # MULTI-SELECTION PROTECTION:
            # Lock text fields to prevent accidental overwriting of titles and track numbers
            self.current_file = None
            for w in text_inputs:
                w.blockSignals(True)
                w.clear()
                w.setEnabled(False)
                w.blockSignals(False)

            self.input_title.setPlaceholderText(f"<{count} tracks selected - Select tracks individually to edit text>")
            self.cover_label.setText("Drop Cover Image Here\nto apply to all\nselected tracks")
            return

        # TEKLİ SEÇİM (count == 1): Tüm alanlar serbest ve düzenlenebilir
        for w in text_inputs:
            w.setEnabled(True)
        self.input_title.setPlaceholderText("")

        self.current_file = self.mp3_files[selected_items[0].row()]
        data = self.file_tags.get(self.current_file, {})
        tags = data.get('tags', {})

        # Formu doldururken yanlışlıkla 'modified' tetiklenmesin
        for w in text_inputs:
            w.blockSignals(True)

        self.input_title.setText(tags.get('title', ''))
        self.input_artist.setText(tags.get('artist', ''))
        self.input_album_artist.setText(tags.get('albumartist', ''))
        self.input_album.setText(tags.get('album', ''))
        self.input_composer.setText(tags.get('composer', ''))
        self.input_year.setText(tags.get('date', ''))
        self.input_track.setText(tags.get('tracknumber', ''))
        self.input_disc.setText(tags.get('discnumber', ''))
        self.input_genre.setText(tags.get('genre', ''))
        self.input_comment.setPlainText(tags.get('comment', ''))

        for w in text_inputs:
            w.blockSignals(False)

        image_data = data.get('image')
        if image_data:
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            scaled = pixmap.scaled(
                self.cover_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.cover_label.setPixmap(scaled)
        else:
            self.cover_label.clear_image()

    def mark_as_modified(self):
        """Updates the memory state when user types in inputs."""
        # Yalnızca tek bir dosya aktif olarak düzenleniyorsa hafızayı güncelle
        if not self.current_file or self.current_file not in self.file_tags:
            return

        self.is_modified = True
        self.file_tags[self.current_file]['tags'] = {
            'title': self.input_title.text().strip(),
            'artist': self.input_artist.text().strip(),
            'albumartist': self.input_album_artist.text().strip(),
            'album': self.input_album.text().strip(),
            'composer': self.input_composer.text().strip(),
            'date': self.input_year.text().strip(),
            'tracknumber': self.input_track.text().strip(),
            'discnumber': self.input_disc.text().strip(),
            'genre': self.input_genre.text().strip(),
            'comment': self.input_comment.toPlainText().strip()
        }
        self.file_tags[self.current_file]['dirty'] = True

    def clear_selected_files(self):
        """Clears the tag information and cover ONLY for the selected music file(s)."""
        selected_rows = [idx.row() for idx in self.file_list.selectedIndexes()]
        if not selected_rows:
            QMessageBox.information(self, "Info", "Please select file(s) from the list first.")
            return

        empty_tags = {
            'title': '', 'artist': '', 'albumartist': '', 'album': '',
            'composer': '', 'date': '', 'tracknumber': '', 'discnumber': '',
            'genre': '', 'comment': ''
        }

        for r in selected_rows:
            f = self.mp3_files[r]
            self.file_tags[f]['tags'] = empty_tags.copy()
            self.file_tags[f]['image'] = None
            self.file_tags[f]['dirty'] = True

        self.input_title.clear()
        self.input_artist.clear()
        self.input_album_artist.clear()
        self.input_album.clear()
        self.input_composer.clear()
        self.input_year.clear()
        self.input_track.clear()
        self.input_disc.clear()
        self.input_genre.clear()
        self.input_comment.clear()
        self.cover_label.clear_image()
        self.is_modified = True

    def clear_all_fields(self):
        """Clears the tag information and cover for ALL music files in the list."""
        if not self.mp3_files:
            return

        empty_tags = {
            'title': '', 'artist': '', 'albumartist': '', 'album': '',
            'composer': '', 'date': '', 'tracknumber': '', 'discnumber': '',
            'genre': '', 'comment': ''
        }

        for f in self.mp3_files:
            self.file_tags[f]['tags'] = empty_tags.copy()
            self.file_tags[f]['image'] = None
            self.file_tags[f]['dirty'] = True

        self.input_title.clear()
        self.input_artist.clear()
        self.input_album_artist.clear()
        self.input_album.clear()
        self.input_composer.clear()
        self.input_year.clear()
        self.input_track.clear()
        self.input_disc.clear()
        self.input_genre.clear()
        self.input_comment.clear()
        self.cover_label.clear_image()
        self.is_modified = True

    def set_cover_for_selected(self, image_data: bytes, ext: str = ".jpg"):
        """Assigns dropped/selected cover image to selected files (or ALL if none selected)."""
        selected_rows = [idx.row() for idx in self.file_list.selectedIndexes()]
        
        # Seçili dosya yoksa listedeki TÜM dosyalara kapağı ata
        target_indices = selected_rows if selected_rows else range(len(self.mp3_files))

        for r in target_indices:
            f = self.mp3_files[r]
            self.file_tags[f]['image'] = image_data
            self.file_tags[f]['image_mime'] = "image/png" if ext.lower() == ".png" else "image/jpeg"
            self.file_tags[f]['dirty'] = True

        self.is_modified = True

    def closeEvent(self, event):
        """Warns the user on exit if unapplied changes exist."""
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unapplied changes. If you exit now, they will not be saved.\n\nDo you really want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def apply_tags(self):
        """Writes memory tags directly to physical files on disk."""
        # Collect all files modified in memory (dirty == True)
        target_files = [f for f, data in self.file_tags.items() if data.get('dirty', False)]

        if not target_files:
            QMessageBox.information(self, "Info", "No modified tags or cover art to save.")
            return
        updated_count = 0

        for file_path in target_files:
            try:
                data = self.file_tags.get(file_path)
                if not data:
                    continue

                # ID3 başlığını oluştur veya yükle
                try:
                    full_id3 = ID3(file_path)
                except ID3NoHeaderError:
                    full_id3 = ID3()

                # 1. Metin etiketlerini yaz (EasyID3 üzerinden ID3v2.3 olarak)
                tags = data['tags']
                audio = EasyID3(file_path)
                easy_keys = ['title', 'artist', 'albumartist', 'album', 'composer', 'date', 'tracknumber', 'discnumber', 'genre']
                
                for k in easy_keys:
                    val = tags.get(k, '').strip()
                    if val:
                        audio[k] = val
                    else:
                        audio.pop(k, None)
                audio.save(v2_version=3)

                # 2. Yorum ve Kapak Resmini yaz
                full_id3 = ID3(file_path)

                # Yorum
                comment_text = tags.get('comment', '').strip()
                full_id3.delall("COMM")
                if comment_text:
                    full_id3.add(COMM(encoding=3, lang='eng', desc='', text=comment_text))

                # Kapak Resmi
                image_data = data.get('image')
                full_id3.delall("APIC")
                if image_data:
                    mime = data.get('image_mime', 'image/jpeg')
                    full_id3.add(
                        APIC(
                            encoding=3,
                            mime=mime,
                            type=3,  # Front cover
                            desc="Front Cover",
                            data=image_data
                        )
                    )

                # Linux & Windows dosya yöneticileriyle en uyumlu format ID3v2.3
                full_id3.save(file_path, v2_version=3)

                data['dirty'] = False
                updated_count += 1
            except Exception as e:
                print(f"Error writing to {file_path}: {e}")

        # Eğer hedefteki tüm dosyalar işlendiyse kaydedilmemiş durumunu sıfırla
        self.is_modified = any(d.get('dirty', False) for d in self.file_tags.values())

        QMessageBox.information(
            self,
            "Success",
            f"Successfully updated tags and cover for {updated_count} file(s)!"
        )


def main():
    # Oturum türüne duyarlı başlatma:
    # Kullanıcı elle bir platform belirtmediyse ortama göre en stabil olanı seç
    if "QT_QPA_PLATFORM" not in os.environ:
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session_type == "wayland":
            # Wayland oturumundaysa native wayland dene, sorun olursa xcb (X11) fallback yap
            os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
        elif session_type == "x11":
            # XFCE ve geleneksel masaüstleri için doğrudan xcb kullan
            os.environ["QT_QPA_PLATFORM"] = "xcb"

    app = QApplication(sys.argv)

    # 1. Özel Yazı Tipini (LiberationSans-Regular.ttf) Programa Bağla
    font_path = get_resource_path("LiberationSans-Regular.ttf")
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0], 10))

    # 2. Görev çubuğu ve pencere için genel uygulama ikonu
    app_icon_path = get_resource_path("PyTag.png")
    if os.path.exists(app_icon_path):
        app.setWindowIcon(QIcon(app_icon_path))

    # 3. Qt6 sistem simgeleri desteği
    if not QIcon.themeName():
        for theme in ["Adwaita", "breeze", "Papirus", "elementary"]:
            if QIcon.hasThemeIcon("document-open"):
                break
            QIcon.setThemeName(theme)

    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()