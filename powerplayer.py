#!/usr/bin/env python3
"""PowerPlayer Linux 1.0 — original PyQt6 multimedia application."""
import sys
import json
import hashlib
import subprocess
import shutil
from PyQt6.QtCore import QTimer, QSize, QEvent, QPoint, QProcess
from PyQt6.QtGui import QIcon, QPixmap, QFont, QFontDatabase, QCursor, QPainter, QColor
from pathlib import Path
from PyQt6.QtCore import Qt, QUrl, QSettings
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFileDialog, QListWidget, QSplitter, QMessageBox,
    QFrame, QStackedWidget, QComboBox, QMenu, QStyle, QAbstractItemView, QListView, QSizePolicy, QLineEdit, QDialog, QDialogButtonBox, QWidgetAction, QTextEdit, QTreeWidget, QTreeWidgetItem, QListWidgetItem)
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget

MEDIA_EXT = {'.mp4','.mkv','.avi','.mov','.webm','.m4v','.mpg','.mpeg','.ts',
             '.mp3','.flac','.ogg','.wav','.m4a','.aac','.opus'}

class SkyPage(QWidget):
    """Sfondo locale disegnato soltanto sulle pagine, mai sopra il video."""
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.sky_image = QPixmap(str(image_path))
        self.sky_enabled = True

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.sky_enabled and not self.sky_image.isNull():
            painter.drawPixmap(self.rect(), self.sky_image, self.sky_image.rect())
            painter.fillRect(self.rect(), QColor(0, 5, 15, 65))
        else:
            painter.fillRect(self.rect(), QColor('#111214'))
        painter.end()


class PowerPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PowerPlayer Linux 1.0')
        self.resize(1250, 760)
        self.setMinimumSize(850, 530)
        self.setAcceptDrops(True)
        self.settings = QSettings('PowerPlayerLinux', 'PowerPlayer')
        self.sky_enabled = str(self.settings.value('sky_background', 'true')).lower() not in ('false', '0', 'no')
        self.sky_path = Path(__file__).resolve().parent / 'cielo_stellato.png'
        self.sky_pages = []
        self.paths = []
        self.metadata_cache = {}
        self.current_index = -1
        self.dragging = False
        self.resume_pending = None
        self.resume_attempts = 0
        self.resume_store = self.load_resume()
        self.cover_cache = Path.home() / '.cache' / 'powerplayer-linux' / 'covers'
        self.cover_cache.mkdir(parents=True, exist_ok=True)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(float(self.settings.value('volume', 70)) / 100)
        self.disc_process = None  # Lettore mpv esterno, separato da Qt Multimedia.
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.video = QVideoWidget(self)
        self.fullscreen_host = None
        self.controls_visible = True
        self.controls_last_motion = 0
        self.player.setVideoOutput(self.video)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)

        header = QFrame(objectName='header')
        h = QHBoxLayout(header)
        h.setContentsMargins(18,8,18,8)
        logo = QLabel('PowerPlayer  ▸')
        logo.setObjectName('logo')
        h.addWidget(logo)
        collapse = QPushButton('☰')
        collapse.setToolTip('Mostra / nascondi menu laterale')
        collapse.setFixedWidth(44)
        collapse.clicked.connect(self.toggle_sidebar)
        h.addWidget(collapse)
        h.addWidget(QLabel('LINUX  /  1.0'))
        h.addStretch()
        open_btn = QPushButton('＋  Apri file')
        open_btn.setObjectName('primary')
        open_btn.clicked.connect(self.open_files)
        h.addWidget(open_btn)
        folder_btn = QPushButton('Apri cartella')
        folder_btn.clicked.connect(self.open_folder)
        h.addWidget(folder_btn)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(0)
        root.addLayout(body,1)
        sidebar = QFrame(objectName='sidebar')
        sidebar.setFixedWidth(208)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(10,18,10,14)
        side.setSpacing(5)
        side.addWidget(QLabel('MEDIENBIBLIOTHEK  /  LIBRERIA'))
        self.nav = []
        for label, page in [('⌂  In riproduzione',0),('▣  Film e video',1)]:
            b = QPushButton(label)
            b.setProperty('nav',True)
            b.setCheckable(True)
            b.clicked.connect(lambda _, n=page: self.show_page(n))
            self.nav.append(b)
            side.addWidget(b)
        side.addSpacing(10)
        side.addWidget(QLabel('IL MIO COMPUTER'))
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setIndentation(15)
        self.folder_tree.setMinimumHeight(180)
        self.folder_tree.itemExpanded.connect(self.expand_folder)
        self.folder_tree.itemClicked.connect(self.select_folder)
        side.addWidget(self.folder_tree, 1)
        self.populate_roots()
        side.addSpacing(8)
        side.addWidget(QLabel('SORGENTI'))
        dvd = QPushButton('▤  DVD / Blu-ray')
        dvd.setProperty('nav',True)
        dvd.clicked.connect(self.disc_info)
        side.addWidget(dvd)
        note = QLabel('Trascina qui video o musica\nper aggiungerli alla coda.')
        note.setWordWrap(True)
        note.setObjectName('hint')
        side.addWidget(note)
        self.sidebar = sidebar
        body.addWidget(sidebar)

        self.pages = QStackedWidget()
        body.addWidget(self.pages,1)
        player_page = SkyPage(self.sky_path)
        self.sky_pages.append(player_page)
        p = QVBoxLayout(player_page)
        p.setContentsMargins(24,18,24,18)
        p.setSpacing(10)
        title_row = QHBoxLayout()
        self.now_title = QLabel('Nessun contenuto selezionato')
        self.now_title.setObjectName('nowtitle')
        title_row.addWidget(self.now_title,1)
        self.audio_tracks = QComboBox()
        self.audio_tracks.setMinimumWidth(155)
        self.audio_tracks.addItem('Traccia audio')
        self.audio_tracks.setToolTip('Traccia audio')
        self.audio_tracks.currentIndexChanged.connect(self.select_audio)
        title_row.addWidget(self.audio_tracks)
        self.subtitle_tracks = QComboBox()
        self.subtitle_tracks.setMinimumWidth(175)
        self.subtitle_tracks.addItem('Sottotitoli: off')
        self.subtitle_tracks.setToolTip('Sottotitoli incorporati')
        self.subtitle_tracks.currentIndexChanged.connect(self.select_subtitle)
        title_row.addWidget(self.subtitle_tracks)
        p.addLayout(title_row)
        self.video.setStyleSheet('background:#05080d;')
        stage = QFrame(objectName='videoStage')
        self.video_stage = stage
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(0,0,0,0)
        stage_layout.setSpacing(0)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        stage_layout.addWidget(self.video, 1)
        p.addWidget(stage,1)
        self.welcome = QLabel('POWERPLAYER\n\nIl tuo cinema, sotto le stelle\n\nApri un film o scegli una cartella dalla barra laterale')
        self.welcome.setObjectName('skyWelcome')
        self.welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome.setWordWrap(True)
        p.addWidget(self.welcome, 1)
        stage.hide()
        self.pages.addWidget(player_page)

        library_page = SkyPage(self.sky_path)
        self.sky_pages.append(library_page)
        lib = QVBoxLayout(library_page)
        lib.setContentsMargins(26,22,26,20)
        lib.addWidget(QLabel('LA TUA LIBRERIA MULTIMEDIALE'))
        desc = QLabel('Doppio clic su un elemento per riprodurlo. Puoi aggiungere più file o un’intera cartella.')
        desc.setObjectName('hint')
        lib.addWidget(desc)
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText('Cerca per titolo, formato o risoluzione…')
        self.library_search.setClearButtonEnabled(True)
        self.library_search.textChanged.connect(self.filter_library)
        lib.addWidget(self.library_search)
        self.playlist = QListWidget()
        self.playlist.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.playlist.setViewMode(QListView.ViewMode.IconMode)
        self.playlist.setIconSize(QSize(154, 92))
        self.playlist.setGridSize(QSize(195, 145))
        self.playlist.setResizeMode(QListView.ResizeMode.Adjust)
        self.playlist.setMovement(QListView.Movement.Static)
        self.playlist.setWordWrap(True)
        self.playlist.setSpacing(8)
        self.playlist.itemDoubleClicked.connect(lambda _: self.play_index(self.playlist.currentRow()))
        self.playlist.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist.customContextMenuRequested.connect(self.queue_menu)
        lib.addWidget(self.playlist,1)
        self.library_count = QLabel('0 elementi')
        lib.addWidget(self.library_count)
        lib_buttons = QHBoxLayout()
        add_btn = QPushButton('＋ Aggiungi file')
        add_btn.clicked.connect(self.open_files)
        clear_btn = QPushButton('Svuota coda')
        clear_btn.clicked.connect(self.clear_queue)
        info_btn = QPushButton('ⓘ Informazioni')
        info_btn.clicked.connect(self.show_selected_info)
        lib_buttons.addWidget(info_btn)
        lib_buttons.addWidget(add_btn)
        lib_buttons.addWidget(clear_btn)
        lib_buttons.addStretch()
        lib.addLayout(lib_buttons)
        self.pages.addWidget(library_page)

        # File browser: folder tree at left, folder contents in the central panel.
        browser_page = SkyPage(self.sky_path)
        self.sky_pages.append(browser_page)
        browser_layout = QVBoxLayout(browser_page)
        browser_layout.setContentsMargins(24,18,24,18)
        top = QHBoxLayout()
        self.folder_heading = QLabel('Il mio computer')
        self.folder_heading.setObjectName('nowtitle')
        top.addWidget(self.folder_heading, 1)
        up_btn = QPushButton('↑ Cartella superiore')
        up_btn.clicked.connect(self.folder_up)
        top.addWidget(up_btn)
        browser_layout.addLayout(top)
        self.folder_hint = QLabel('Doppio clic su una cartella per aprirla, su un video o audio per riprodurlo.')
        self.folder_hint.setObjectName('hint')
        browser_layout.addWidget(self.folder_hint)
        self.folder_contents = QListWidget()
        self.folder_contents.setViewMode(QListView.ViewMode.ListMode)
        self.folder_contents.itemDoubleClicked.connect(self.activate_folder_item)
        browser_layout.addWidget(self.folder_contents, 1)
        self.pages.addWidget(browser_page)
        for sky_page in self.sky_pages:
            sky_page.sky_enabled = self.sky_enabled
        self.current_folder = Path.home()


        bottom = QFrame(objectName='bottom')
        b = QVBoxLayout(bottom)
        b.setContentsMargins(16, 5, 16, 7)
        b.setSpacing(2)
        self.position = QSlider(Qt.Orientation.Horizontal)
        self.position.setObjectName('timeline')
        self.position.setRange(0, 0)
        self.position.sliderPressed.connect(self.on_slider_pressed)
        self.position.sliderReleased.connect(self.on_slider_released)
        self.position.sliderMoved.connect(self.preview_position)
        b.addWidget(self.position)
        controls = QHBoxLayout()
        controls.setSpacing(4)
        self.time_label = QLabel('00:00 / 00:00')
        self.time_label.setObjectName('timeLabel')
        controls.addWidget(self.time_label)
        controls.addStretch(1)
        self.repeat_btn = QPushButton('⟳')
        self.repeat_btn.setObjectName('transport')
        self.repeat_btn.setToolTip('Ripeti il film corrente')
        self.repeat_btn.setCheckable(True)
        self.repeat_btn.toggled.connect(self.change_repeat)
        controls.addWidget(self.repeat_btn)
        self.open_transport_btn = QPushButton('▱')
        self.open_transport_btn.setObjectName('transport')
        self.open_transport_btn.setToolTip('Apri file multimediale')
        self.open_transport_btn.clicked.connect(self.open_files)
        controls.addWidget(self.open_transport_btn)
        self.prev_btn = QPushButton('⏮')
        self.prev_btn.setObjectName('transport')
        self.prev_btn.setToolTip('File precedente')
        self.prev_btn.clicked.connect(self.previous)
        controls.addWidget(self.prev_btn)
        self.play_btn = QPushButton('▶')
        self.play_btn.setObjectName('transportPlay')
        self.play_btn.setToolTip('Riproduci / Pausa')
        self.play_btn.clicked.connect(self.toggle_play)
        controls.addWidget(self.play_btn)
        self.next_btn = QPushButton('⏭')
        self.next_btn.setObjectName('transport')
        self.next_btn.setToolTip('File successivo')
        self.next_btn.clicked.connect(self.next)
        controls.addWidget(self.next_btn)
        self.stop_btn = QPushButton('■')
        self.stop_btn.setObjectName('transport')
        self.stop_btn.setToolTip('Interrompi')
        self.stop_btn.clicked.connect(self.player.stop)
        controls.addWidget(self.stop_btn)
        self.volume_btn = QPushButton('◖))')
        self.volume_btn.setObjectName('transport')
        self.volume_btn.setToolTip('Mostra / nascondi volume')
        self.volume_btn.clicked.connect(self.toggle_volume_control)
        controls.addWidget(self.volume_btn)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(self.settings.value('volume', 70)))
        self.volume.setFixedWidth(88)
        self.volume.setVisible(False)
        self.volume.valueChanged.connect(self.change_volume)
        controls.addWidget(self.volume)
        self.speed = QComboBox()
        for label, rate in [('0.5×',0.5),('0.75×',0.75),('1×',1.0),('1.25×',1.25),('1.5×',1.5),('2×',2.0)]:
            self.speed.addItem(label, rate)
        self.speed.setCurrentIndex(2)
        self.speed.currentIndexChanged.connect(self.change_speed)
        self.aspect = QComboBox()
        self.aspect.addItem('Adatta', Qt.AspectRatioMode.KeepAspectRatio)
        self.aspect.addItem('Riempi', Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        self.aspect.addItem('Allunga', Qt.AspectRatioMode.IgnoreAspectRatio)
        self.aspect.currentIndexChanged.connect(self.change_aspect)
        self.more_btn = QPushButton('•••')
        self.more_btn.setObjectName('transport')
        self.more_btn.setToolTip('Altre opzioni di riproduzione')
        self.more_menu = QMenu(self)
        self.more_menu.addAction('Schermo intero (F11)', self.toggle_fullscreen)
        self.more_menu.addAction('Sottotitoli e audio', self.show_track_options)
        speed_action = QWidgetAction(self.more_menu)
        speed_widget = QWidget()
        speed_layout = QHBoxLayout(speed_widget)
        speed_layout.setContentsMargins(8, 2, 8, 2)
        speed_layout.addWidget(QLabel('Velocità'))
        speed_layout.addWidget(self.speed)
        speed_action.setDefaultWidget(speed_widget)
        self.more_menu.addAction(speed_action)
        aspect_action = QWidgetAction(self.more_menu)
        aspect_widget = QWidget()
        aspect_layout = QHBoxLayout(aspect_widget)
        aspect_layout.setContentsMargins(8, 2, 8, 2)
        aspect_layout.addWidget(QLabel('Formato'))
        aspect_layout.addWidget(self.aspect)
        aspect_action.setDefaultWidget(aspect_widget)
        self.more_menu.addAction(aspect_action)
        self.more_btn.setMenu(self.more_menu)
        controls.addWidget(self.more_btn)
        controls.addStretch(1)
        self.full_btn = QPushButton('⛶')
        self.full_btn.setObjectName('transport')
        self.full_btn.setToolTip('Schermo intero (F11)')
        self.full_btn.clicked.connect(self.toggle_fullscreen)
        controls.addWidget(self.full_btn)
        b.addLayout(controls)
        root.addWidget(bottom)
        self.bottom_bar = bottom
        self.main_root = root
        self.normal_stage_layout = stage_layout
        self.autohide_timer = QTimer(self)
        self.autohide_timer.setInterval(250)
        self.autohide_timer.timeout.connect(self.check_autohide)
        self.autohide_timer.start()
        self.idle_ticks = 0
        QApplication.instance().installEventFilter(self)
        self.statusBar().showMessage('Pronto — apri un file o trascinalo nella finestra')

        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.seekableChanged.connect(self.try_restore_position)
        self.player.playbackStateChanged.connect(self.update_play_button)
        self.player.mediaStatusChanged.connect(self.on_media_status)
        self.player.errorOccurred.connect(self.on_error)
        self.player.tracksChanged.connect(self.refresh_tracks)
        self.player.seekableChanged.connect(self.on_seekable)
        self.resume_timer = QTimer(self)
        self.resume_timer.setInterval(10000)
        self.resume_timer.timeout.connect(self.save_current_position)
        self.resume_timer.start()
        self.build_menus()
        self.apply_style()
        families = set(QFontDatabase.families())
        for family in ('Segoe UI', 'Inter', 'Noto Sans', 'Liberation Sans'):
            if family in families:
                self.setFont(QFont(family, 10))
                break
        self.show_page(0)
        self.restore_library()
        saved = self.settings.value('geometry')
        if saved is not None:
            self.restoreGeometry(saved)

    def apply_style(self):
        # Stile ispirato al layout scuro di PowerDVD; nessun elemento grafico proprietario.
        self.setStyleSheet('''
            QMainWindow, QWidget {background:#111214; color:#e7e7e7; font-size:13px; font-weight:400;}
            SkyPage {background:transparent;}
            QLabel#skyWelcome {background:transparent; color:#e5efff; font-size:23px; font-weight:500;}
            QLabel#nowtitle, QLabel#hint {background:transparent;}
            QFrame#header {background:#17181a; border-bottom:1px solid #292b2e;}
            QFrame#sidebar {background:#252628; border-right:1px solid #303134;}
            QTreeWidget {background:#252628; border:0; border-radius:7px; color:#e5e5e5;}
            QTreeWidget::item {padding:5px 3px; border-radius:5px;}
            QTreeWidget::item:selected {background:#2769a8; color:white;}
            QFrame#bottom {background:#191a1c; border-top:1px solid #303134; border-radius:6px;}
            QPushButton#transport {background:transparent; border:0; border-radius:5px; padding:3px 7px; min-width:24px; min-height:25px; color:#c5c8ce; font-size:17px;}
            QPushButton#transport:hover {background:#34383d; color:white;}
            QPushButton#transport:checked {background:#254e6c; color:#7bc6ff;}
            QPushButton#transportPlay {background:transparent; border:1px solid #555b64; border-radius:17px; padding:1px; min-width:32px; min-height:32px; color:white; font-size:20px;}
            QPushButton#transportPlay:hover {background:#2585c4; border-color:#2585c4;}
            QLabel#timeLabel {font-size:11px; color:#989ca3;}
            QSlider#timeline::groove:horizontal {height:3px; background:#43464b; border-radius:1px;}
            QSlider#timeline::handle:horizontal {background:#b4b8bf; width:9px; margin:-4px 0; border-radius:4px;}
            QFrame#videoStage {background:#070809; border:1px solid #202124; border-radius:8px;}
            QLabel#logo {color:#f3f3f3; font-size:21px; font-weight:600;}
            QLabel#nowtitle {color:#f0f0f0; font-size:16px; font-weight:600;}
            QLabel#hint {color:#96999d; font-size:12px;}
            QPushButton {background:#2d2e31; border:1px solid #393b3f; border-radius:7px;
                         padding:8px 12px; color:#e9e9e9;}
            QPushButton:hover {background:#3a3c40; border-color:#51545a;}
            QPushButton:pressed {background:#222326;}
            QPushButton#primary {background:#1999ec; border:1px solid #1999ec; color:white; font-weight:600;}
            QPushButton#primary:hover {background:#36a9f3;}
            QPushButton[nav="true"] {text-align:left; background:transparent; border:0;
                                     border-radius:6px; padding:10px 11px; color:#d4d5d7;}
            QPushButton[nav="true"]:hover {background:#35373a;}
            QPushButton[nav="true"]:checked {background:#45474b; color:white; font-weight:600;}
            QLineEdit {background:rgba(22,30,44,230); color:#eeeeee; border:1px solid #404247;
                       border-radius:7px; padding:9px; selection-background-color:#168edb;}
            QListWidget {background:rgba(9,16,29,205); border:1px solid #2e3034; border-radius:8px;}
            QListWidget::item {padding:7px; border-radius:7px;}
            QListWidget::item:hover {background:#292b2f;}
            QListWidget::item:selected {background:#333f4c;}
            QComboBox {background:#292b2e; border:1px solid #3c3e42; border-radius:7px; padding:7px;}
            QComboBox QAbstractItemView {background:#292b2e; color:white;}
            QMenuBar, QMenu, QStatusBar {background:#191a1c; color:#e4e4e4;}
            QMenuBar::item:selected, QMenu::item:selected {background:#35383d; border-radius:4px;}
            QSlider::groove:horizontal {height:5px; background:#484a4e; border-radius:2px;}
            QSlider::sub-page:horizontal {background:#159ceb; border-radius:2px;}
            QSlider::handle:horizontal {background:#d9e4ec; width:13px; margin:-5px 0; border-radius:6px;}
        ''')

    def build_menus(self):
        file_menu = self.menuBar().addMenu('File')
        self.action(file_menu,'Apri file…','Ctrl+O',self.open_files)
        self.action(file_menu,'Apri cartella…','Ctrl+Shift+O',self.open_folder)
        self.action(file_menu,'Informazioni elemento selezionato',None,self.show_selected_info)
        self.action(file_menu,'Mostra libreria','Ctrl+L',lambda:self.show_page(1))
        file_menu.addSeparator()
        self.action(file_menu,'Esci','Ctrl+Q',self.close)
        playback = self.menuBar().addMenu('Riproduzione')
        self.action(playback,'Play / Pausa','Space',self.toggle_play)
        self.action(playback,'Avanti 10 secondi','Right',lambda:self.seek(10000))
        self.action(playback,'Indietro 10 secondi','Left',lambda:self.seek(-10000))
        self.action(playback,'File successivo','Ctrl+Right',self.next)
        self.action(playback,'File precedente','Ctrl+Left',self.previous)
        view = self.menuBar().addMenu('Visualizza')
        self.sky_action = QAction('Cielo stellato', self)
        self.sky_action.setCheckable(True)
        self.sky_action.setChecked(self.sky_enabled)
        self.sky_action.toggled.connect(self.toggle_sky_background)
        view.addAction(self.sky_action)
        view.addSeparator()
        self.action(view,'Schermo intero','F11',self.toggle_fullscreen)
        self.action(view,'Mostra / nascondi barra laterale','Ctrl+B',self.toggle_sidebar)
        self.action(view,'Cerca nella libreria','Ctrl+F',self.focus_library_search)
        self.action(view,'Lettore','Esc',lambda:self.show_page(0))
        help_menu = self.menuBar().addMenu('Aiuto')
        self.action(help_menu,'Informazioni',None,self.about)

    def action(self, menu, label, shortcut, callback):
        a = QAction(label,self)
        if shortcut: a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(callback)
        menu.addAction(a)

    def toggle_sky_background(self, enabled):
        self.sky_enabled = bool(enabled)
        self.settings.setValue('sky_background', self.sky_enabled)
        for page in self.sky_pages:
            page.sky_enabled = self.sky_enabled and (page is not self.pages.widget(0) or not self.video_stage.isVisible())
            page.update()

    def focus_library_search(self):
        self.show_page(1)
        self.library_search.setFocus()

    def show_page(self, page):
        self.pages.setCurrentIndex(page)
        for i,b in enumerate(self.nav): b.setChecked(i == page)
        self.show_controls()

    def populate_roots(self):
        self.folder_tree.clear()
        home = Path.home()
        roots = [('⌂  Home', home), ('▣  Scaricati', home / 'Scaricati'),
                 ('▣  Video', home / 'Video'), ('♫  Musica', home / 'Musica'),
                 ('▣  Immagini', home / 'Immagini')]
        for label, path in roots:
            if path.is_dir():
                self.add_folder_node(None, label, path)
        # Mounted removable drives and other local volumes (when accessible).
        for base in (Path('/run/media') / home.name, Path('/media') / home.name):
            if base.is_dir():
                try:
                    for path in sorted(base.iterdir()):
                        if path.is_dir():
                            self.add_folder_node(None, '▣  ' + path.name, path)
                except OSError:
                    pass

    def add_folder_node(self, parent, label, path):
        node = QTreeWidgetItem([label]) if parent is None else QTreeWidgetItem(parent, [label])
        node.setData(0, Qt.ItemDataRole.UserRole, str(path))
        if parent is None:
            self.folder_tree.addTopLevelItem(node)
        node.addChild(QTreeWidgetItem(['…']))  # Lazy-load subfolders.
        return node

    def expand_folder(self, node):
        path = Path(node.data(0, Qt.ItemDataRole.UserRole) or '')
        node.takeChildren()
        try:
            folders = sorted((p for p in path.iterdir() if p.is_dir() and not p.is_symlink()),
                             key=lambda p: p.name.casefold())
            for child in folders[:300]:
                self.add_folder_node(node, '▣  ' + child.name, child)
        except (OSError, PermissionError):
            pass

    def select_folder(self, node, column=0):
        path = node.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.browse_folder(Path(path))

    def browse_folder(self, path):
        path = Path(path)
        if not path.is_dir():
            return
        self.current_folder = path
        self.folder_heading.setText(str(path))
        self.folder_contents.clear()
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))
            for entry in entries[:1500]:
                if entry.name.startswith('.'):
                    continue
                if not entry.is_dir() and entry.suffix.lower() not in MEDIA_EXT:
                    continue
                item = QListWidgetItem(('▣  ' if entry.is_dir() else '▶  ') + entry.name)
                item.setData(Qt.ItemDataRole.UserRole, str(entry))
                self.folder_contents.addItem(item)
            self.folder_hint.setText(f'{self.folder_contents.count()} elementi · doppio clic per aprire')
        except (OSError, PermissionError) as exc:
            self.folder_hint.setText(f'Impossibile leggere la cartella: {exc}')
        self.show_page(2)

    def folder_up(self):
        self.browse_folder(self.current_folder.parent)

    def activate_folder_item(self, item):
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        if path.is_dir():
            self.browse_folder(path)
        elif path.is_file() and path.suffix.lower() in MEDIA_EXT:
            self.add_paths([str(path)], autoplay=False)
            index = self.paths.index(str(path.resolve()))
            self.play_index(index)

    def restore_library(self):
        """Restore saved library without automatically starting playback."""
        raw = self.settings.value('library_paths', '[]')
        try:
            paths = json.loads(raw) if isinstance(raw, str) else []
        except (TypeError, ValueError):
            paths = []
        if isinstance(paths, list):
            self.add_paths([p for p in paths if isinstance(p, str)], autoplay=False)

    def persist_library(self):
        self.settings.setValue('library_paths', json.dumps(self.paths, ensure_ascii=False))

    def media_info(self, path):
        """Read technical metadata locally with ffprobe, when installed."""
        if path in self.metadata_cache:
            return self.metadata_cache[path]
        info = {'format': Path(path).suffix.lstrip('.').upper(), 'duration': '',
                'resolution': '', 'video': '', 'audio': '', 'size': ''}
        try:
            info['size'] = f'{Path(path).stat().st_size / (1024**3):.2f} GiB'
        except OSError:
            pass
        ffprobe = shutil.which('ffprobe')
        if ffprobe:
            try:
                result = subprocess.run([ffprobe, '-v', 'quiet', '-show_format',
                    '-show_streams', '-of', 'json', path], capture_output=True,
                    text=True, timeout=6, check=False)
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    seconds = float(data.get('format', {}).get('duration', 0))
                    if seconds > 0:
                        info['duration'] = self.fmt(round(seconds * 1000))
                    for stream in data.get('streams', []):
                        kind = stream.get('codec_type')
                        if kind == 'video' and not info['video']:
                            info['video'] = stream.get('codec_name', '').upper()
                            w, h = stream.get('width'), stream.get('height')
                            if w and h:
                                info['resolution'] = f'{w} × {h}'
                        elif kind == 'audio' and not info['audio']:
                            info['audio'] = stream.get('codec_name', '').upper()
            except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
                pass
        self.metadata_cache[path] = info
        return info

    def add_paths(self, files, autoplay=True):
        files = [str(Path(f).resolve()) for f in files
                 if Path(f).is_file() and Path(f).suffix.lower() in MEDIA_EXT]
        new_files = [f for f in files if f not in self.paths]
        if not new_files:
            # Existing library entries must still open when selected via Apri file.
            if autoplay and files:
                self.play_index(self.paths.index(files[0]))
            return
        first = len(self.paths)
        from PyQt6.QtWidgets import QListWidgetItem
        for f in new_files:
            self.paths.append(f)
            item = QListWidgetItem(Path(f).name)
            info = {'format': Path(f).suffix.lstrip('.').upper(), 'resolution': '', 'duration': ''}
            detail = ' · '.join(x for x in (info['format'], info['resolution'], info['duration']) if x)
            item.setText(f'{Path(f).stem}\n{detail}')
            item.setToolTip(f'{f}\n{detail}')
            icon = None  # Preview generation is expensive; keep file opening responsive.
            if icon is not None:
                item.setIcon(icon)
            self.playlist.addItem(item)
        self.persist_library()
        self.filter_library(self.library_search.text())
        if autoplay and self.current_index < 0:
            self.play_index(first)
        self.statusBar().showMessage(f'{len(new_files)} file aggiunti — {len(self.paths)} nella libreria', 5000)

    def show_selected_info(self):
        row = self.playlist.currentRow()
        if not 0 <= row < len(self.paths):
            QMessageBox.information(self, 'Informazioni', 'Seleziona prima un elemento della libreria.')
            return
        path = self.paths[row]
        info = self.media_info(path)
        labels = [('Titolo', Path(path).name), ('Formato', info['format']),
                  ('Durata', info['duration']), ('Risoluzione', info['resolution']),
                  ('Codec video', info['video']), ('Codec audio', info['audio']),
                  ('Dimensione', info['size']), ('Percorso', path)]
        details = '\n'.join(f'{label}: {value or "Non disponibile"}' for label, value in labels)
        QMessageBox.information(self, 'Informazioni multimediali', details)

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def filter_library(self, text):
        needle = text.casefold().strip()
        for i, path in enumerate(self.paths):
            item = self.playlist.item(i)
            if item is not None:
                info = self.metadata_cache.get(path, {})
                searchable = ' '.join([Path(path).name, info.get('format', ''), info.get('resolution', '')]).casefold()
                item.setHidden(needle not in searchable)
        visible = sum(not self.playlist.item(i).isHidden() for i in range(self.playlist.count()))
        self.library_count.setText(f'{visible} elementi visibili su {len(self.paths)}')

    def change_speed(self, index):
        rate = self.speed.itemData(index)
        if rate is not None:
            self.player.setPlaybackRate(float(rate))

    def change_aspect(self, index):
        mode = self.aspect.itemData(index)
        if mode is not None:
            self.video.setAspectRatioMode(mode)

    def open_files(self):
        files,_ = QFileDialog.getOpenFileNames(self,'Apri file multimediali',str(Path.home()),
            'Multimedia (*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.mpg *.mpeg *.ts *.mp3 *.flac *.ogg *.wav *.m4a *.aac *.opus);;Tutti i file (*)')
        self.add_paths(files)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self,'Scegli una cartella',str(Path.home()))
        if folder:
            files = sorted(str(p) for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in MEDIA_EXT)
            self.add_paths(files)

    def play_index(self,index):
        if not 0 <= index < len(self.paths): return
        self.save_current_position()
        self.current_index = index
        self.playlist.setCurrentRow(index)
        path = self.paths[index]
        if not Path(path).is_file():
            QMessageBox.warning(self,'File non trovato',path)
            return
        # Set the pending seek BEFORE changing the source: Qt may emit signals immediately.
        self.resume_pending = (path, int(self.resume_store.get(path, 0)))
        self.resume_attempts = 0
        # Reveal video before loading; the sky is for the welcome screen only.
        self.welcome.hide()
        self.video_stage.show()
        self.pages.widget(0).sky_enabled = False
        self.pages.widget(0).update()
        self.player.setSource(QUrl.fromLocalFile(path))
        self.now_title.setText(Path(path).name)
        self.show_page(0)
        self.player.play()

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self.current_index >= 0:
            self.player.play()
        else:
            self.open_files()

    def previous(self):
        if self.paths: self.play_index(max(0,self.current_index-1))

    def next(self):
        if self.current_index + 1 < len(self.paths): self.play_index(self.current_index+1)

    def seek(self,delta):
        if self.current_index >= 0:
            self.player.setPosition(max(0,min(self.player.duration(),self.player.position()+delta)))

    def clear_queue(self):
        self.save_current_position()
        self.resume_pending = None
        self.player.stop()
        self.player.setSource(QUrl())
        self.pages.widget(0).sky_enabled = self.sky_enabled
        self.pages.widget(0).update()
        self.paths.clear()
        self.playlist.clear()
        self.library_search.clear()
        self.persist_library()
        self.current_index = -1
        self.now_title.setText('Nessun contenuto selezionato')
        self.video_stage.hide()
        self.welcome.show()
        self.show_page(1)

    def queue_menu(self,point):
        row = self.playlist.indexAt(point).row()
        if row < 0:return
        menu = QMenu(self)
        play = menu.addAction('Riproduci')
        details = menu.addAction('Informazioni sul file')
        remove = menu.addAction('Rimuovi dalla libreria')
        selected = menu.exec(self.playlist.mapToGlobal(point))
        if selected == play:self.play_index(row)
        elif selected == details:
            self.playlist.setCurrentRow(row)
            self.show_selected_info()
        elif selected == remove:
            self.paths.pop(row)
            self.playlist.takeItem(row)
            if row == self.current_index:
                self.save_current_position()
                self.player.stop()
                self.player.setSource(QUrl())
                self.current_index = -1
                self.now_title.setText('Nessun contenuto selezionato')
                self.video_stage.hide()
                self.welcome.show()
            elif row < self.current_index:
                self.current_index -= 1
            self.persist_library()
            self.filter_library(self.library_search.text())

    def refresh_tracks(self):
        self.audio_tracks.blockSignals(True)
        self.subtitle_tracks.blockSignals(True)
        self.audio_tracks.clear()
        for i,track in enumerate(self.player.audioTracks()):
            name = track.stringValue(track.Key.Title) or track.stringValue(track.Key.Language) or f'Audio {i+1}'
            self.audio_tracks.addItem(name,i)
        self.audio_tracks.setCurrentIndex(self.player.activeAudioTrack())
        self.subtitle_tracks.clear()
        self.subtitle_tracks.addItem('Sottotitoli: off',-1)
        for i,track in enumerate(self.player.subtitleTracks()):
            name = track.stringValue(track.Key.Title) or track.stringValue(track.Key.Language) or f'Traccia {i+1}'
            self.subtitle_tracks.addItem(name,i)
        active = self.player.activeSubtitleTrack()
        self.subtitle_tracks.setCurrentIndex(active+1)
        self.audio_tracks.blockSignals(False)
        self.subtitle_tracks.blockSignals(False)

    def select_audio(self,index):
        if index >= 0:self.player.setActiveAudioTrack(self.audio_tracks.itemData(index))

    def select_subtitle(self,index):
        if index >= 0:self.player.setActiveSubtitleTrack(self.subtitle_tracks.itemData(index))

    def try_restore_position(self, *args):
        if self.resume_pending is None:
            return
        path, position = self.resume_pending
        if not (0 <= self.current_index < len(self.paths)) or self.paths[self.current_index] != path:
            self.resume_pending = None
            return
        if position <= 15000:
            self.resume_pending = None
            return
        duration = self.player.duration()
        if duration <= 0 or not self.player.isSeekable():
            return  # Wait for metadata and a seekable stream.
        if position >= duration - 10000:
            self.resume_pending = None
            return
        self.player.setPosition(position)
        self.resume_attempts += 1
        # Some backends initially accept a seek but reset it when playback starts.
        QTimer.singleShot(350, lambda p=path, target=position: self.verify_resume(p, target))

    def verify_resume(self, path, target):
        if self.resume_pending != (path, target):
            return
        if abs(self.player.position() - target) <= 2500:
            self.resume_pending = None
            self.statusBar().showMessage('Ripresa dal punto salvato', 5000)
        elif self.resume_attempts < 8:
            QTimer.singleShot(350, self.try_restore_position)
        else:
            self.resume_pending = None
            self.statusBar().showMessage('Ripresa automatica non riuscita', 5000)

    def on_media_status(self,status):
        if status in (QMediaPlayer.MediaStatus.LoadedMedia,
                      QMediaPlayer.MediaStatus.BufferedMedia,
                      QMediaPlayer.MediaStatus.BufferingMedia):
            self.try_restore_position()
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.resume_pending = None
            if 0 <= self.current_index < len(self.paths):
                self.resume_store.pop(self.paths[self.current_index], None)
                self.persist_resume()
            if self.repeat_btn.isChecked() and self.current_index >= 0:
                self.play_index(self.current_index)
            else:
                self.next()

    def on_error(self,error,message):
        if error != QMediaPlayer.Error.NoError:
            self.statusBar().showMessage('Errore riproduzione: '+(message or str(error)),12000)

    def update_play_button(self,state):
        self.play_btn.setText('Ⅱ' if state == QMediaPlayer.PlaybackState.PlayingState else '▶')
        if state != QMediaPlayer.PlaybackState.PlayingState:
            self.show_controls()

    @staticmethod
    def fmt(ms):
        seconds = max(0,ms//1000)
        hours,rem = divmod(seconds,3600)
        minutes,secs = divmod(rem,60)
        return f'{hours:02}:{minutes:02}:{secs:02}' if hours else f'{minutes:02}:{secs:02}'

    def update_duration(self,duration):
        self.position.setMaximum(max(0,duration))
        self.update_position(self.player.position())
        self.try_restore_position()

    def update_position(self,ms):
        if not self.dragging:self.position.setValue(ms)
        self.time_label.setText(f'{self.fmt(ms)} / {self.fmt(self.player.duration())}')

    def on_slider_pressed(self):self.dragging = True
    def on_slider_released(self):
        self.player.setPosition(self.position.value())
        self.dragging = False
        self.save_current_position()
    def preview_position(self,value):
        self.time_label.setText(f'{self.fmt(value)} / {self.fmt(self.player.duration())}')

    def change_repeat(self, enabled):
        self.repeat_btn.setToolTip('Ripetizione attiva' if enabled else 'Ripeti il film corrente')

    def toggle_volume_control(self):
        self.volume.setVisible(not self.volume.isVisible())
        self.show_controls()

    def show_track_options(self):
        self.show_page(0)
        self.statusBar().showMessage('Seleziona audio e sottotitoli nei menu sopra il video', 6000)
        self.show_controls()

    def change_volume(self,value):
        self.audio.setVolume(value/100)
        self.settings.setValue('volume',value)

    def toggle_fullscreen(self):
        # Move the existing video widget and toolbar into a dedicated full-screen
        # window, so the same playback controls work in both modes.
        if self.fullscreen_host is not None:
            self.exit_fullscreen()
            return
        self.show_controls()
        self.normal_stage_layout.removeWidget(self.video)
        self.main_root.removeWidget(self.bottom_bar)
        host = QWidget(None)
        host.setWindowTitle('PowerPlayer — Schermo intero')
        host.setStyleSheet('background:#050607;')
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.video.setParent(host)
        self.bottom_bar.setParent(host)
        layout.addWidget(self.video, 1)
        layout.addWidget(self.bottom_bar)
        self.fullscreen_host = host
        host.installEventFilter(self)
        host.showFullScreen()
        self.show_controls()

    def exit_fullscreen(self):
        host = self.fullscreen_host
        if host is None:
            return
        self.fullscreen_host = None
        layout = host.layout()
        layout.removeWidget(self.video)
        layout.removeWidget(self.bottom_bar)
        self.video.setParent(self.pages.widget(0))
        self.normal_stage_layout.addWidget(self.video, 1)
        self.bottom_bar.setParent(self.centralWidget())
        self.main_root.addWidget(self.bottom_bar)
        host.hide()
        host.deleteLater()
        self.show_controls()

    def show_controls(self):
        if not hasattr(self, 'bottom_bar'):
            return
        self.idle_ticks = 0
        if not self.bottom_bar.isVisible():
            self.bottom_bar.show()
        self.controls_visible = True

    def check_autohide(self):
        if not hasattr(self, 'bottom_bar'):
            return
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        active_video = self.fullscreen_host is not None or self.pages.currentIndex() == 0
        if not playing or not active_video or self.dragging:
            self.show_controls()
            return
        target = self.fullscreen_host if self.fullscreen_host is not None else self
        cursor = target.mapFromGlobal(QCursor.pos())
        near_bottom = 0 <= cursor.x() < target.width() and target.height() - 85 <= cursor.y() <= target.height()
        # Keep controls visible when the mouse is over a button or a popup.
        over_bar = self.bottom_bar.isVisible() and self.bottom_bar.rect().contains(self.bottom_bar.mapFromGlobal(QCursor.pos()))
        if near_bottom or over_bar:
            self.show_controls()
            return
        self.idle_ticks += 1
        if self.idle_ticks >= 12 and self.bottom_bar.isVisible():
            self.bottom_bar.hide()
            self.controls_visible = False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and self.fullscreen_host is not None:
            if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_F11):
                self.exit_fullscreen()
                return True
            if event.key() == Qt.Key.Key_Space:
                self.toggle_play()
                return True
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
            if self.fullscreen_host is not None:
                target = self.fullscreen_host
            else:
                target = self
            pos = target.mapFromGlobal(QCursor.pos())
            if 0 <= pos.x() < target.width() and target.height() - 100 <= pos.y() <= target.height():
                self.show_controls()
        return super().eventFilter(obj, event)

    def disc_info(self):
        """Gestione supporti non protetti tramite mpv in finestra separata."""
        dialog = QDialog(self)
        dialog.setWindowTitle('DVD / Blu-ray — PowerPlayer Linux 1.0')
        dialog.setMinimumWidth(530)
        layout = QVBoxLayout(dialog)
        title = QLabel('DVD / BLU-RAY')
        title.setStyleSheet('font-size: 18px; font-weight: 600;')
        layout.addWidget(title)
        info = QLabel('Riproduzione tramite mpv in una finestra separata.\n'
                      'DVD e Blu-ray non protetti; menu e dischi cifrati non garantiti.')
        info.setWordWrap(True)
        layout.addWidget(info)
        if not shutil.which('mpv'):
            warning = QLabel('mpv non è installato. Su Garuda Linux: sudo pacman -S mpv')
            warning.setStyleSheet('color:#ffbd75;')
            layout.addWidget(warning)
        layout.addWidget(QLabel('Lettore ottico rilevato:'))
        devices = QComboBox()
        found = sorted(Path('/dev').glob('sr[0-9]*'))
        for device in found:
            if device.is_block_device():
                devices.addItem(str(device))
        if not devices.count():
            devices.addItem('Nessun lettore collegato', '')
        layout.addWidget(devices)
        actions = [
            ('Riproduci DVD nel lettore', 'dvd', 'device'),
            ('Riproduci Blu-ray nel lettore', 'bd', 'device'),
            ('Apri cartella VIDEO_TS / DVD', 'dvd', 'folder'),
            ('Apri cartella BDMV / Blu-ray', 'bd', 'folder'),
            ('Apri immagine ISO DVD', 'dvd', 'iso'),
            ('Apri immagine ISO Blu-ray', 'bd', 'iso'),
        ]
        for label, kind, source_type in actions:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, k=kind, t=source_type:
                                   self.launch_disc(k, t, devices.currentData(), dialog))
            layout.addWidget(button)
        close_button = QPushButton('Chiudi')
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec()

    def launch_disc(self, kind, source_type, device, dialog):
        """Avvia mpv con argomenti separati; nessuna shell o comando non fidato."""
        if not shutil.which('mpv'):
            QMessageBox.warning(self, 'mpv mancante',
                                'Installa il lettore con: sudo pacman -S mpv')
            return
        if self.disc_process is not None and self.disc_process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, 'Disco in riproduzione',
                                    'Chiudi prima la finestra mpv già aperta.')
            return
        if source_type == 'device':
            if not device or not Path(device).is_block_device():
                QMessageBox.warning(self, 'Lettore assente',
                                    'Collega il lettore USB e inserisci un disco.')
                return
            source = device
        elif source_type == 'folder':
            selected = QFileDialog.getExistingDirectory(self, 'Scegli la cartella del disco', str(Path.home()))
            if not selected:
                return
            path = Path(selected)
            # mpv/libdvdnav e libbluray vogliono la radice del disco, non VIDEO_TS/BDMV.
            if path.name.upper() in ('VIDEO_TS', 'BDMV'):
                path = path.parent
            expected = 'VIDEO_TS' if kind == 'dvd' else 'BDMV'
            if not (path / expected).is_dir():
                QMessageBox.warning(self, 'Cartella non valida',
                                    f'La cartella selezionata non contiene {expected}.')
                return
            source = str(path)
        else:
            selected, _ = QFileDialog.getOpenFileName(self, 'Scegli immagine ISO', str(Path.home()),
                                                       'Immagini ISO (*.iso *.ISO)')
            if not selected:
                return
            source = selected
        args = ['--force-window=yes', '--keep-open=no']
        if kind == 'dvd':
            args.extend(['--dvd-device=' + source, 'dvd://'])
        else:
            args.extend(['--bluray-device=' + source, 'bd://'])
        process = QProcess(self)
        process.setProgram(shutil.which('mpv'))
        process.setArguments(args)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.errorOccurred.connect(lambda error: self.statusBar().showMessage(
            'Impossibile avviare mpv: ' + process.errorString(), 12000))
        process.finished.connect(lambda code, status: self.on_disc_finished(process, code))
        self.disc_process = process
        process.start()
        dialog.accept()
        self.statusBar().showMessage('Avvio ' + ('DVD' if kind == 'dvd' else 'Blu-ray') + ' tramite mpv…', 6000)

    def on_disc_finished(self, process, code):
        output = bytes(process.readAllStandardOutput()).decode('utf-8', errors='replace')
        if code != 0:
            detail = output[-1800:] or 'Verifica il disco, il lettore e le librerie disponibili.'
            QMessageBox.warning(self, 'Riproduzione disco non riuscita', detail)
        else:
            self.statusBar().showMessage('Riproduzione disco terminata', 5000)
        if self.disc_process is process:
            self.disc_process = None
        process.deleteLater()

    def load_resume(self):
        raw = self.settings.value('resume_positions', '{}')
        try:
            obj = json.loads(raw) if isinstance(raw, str) else {}
            return {str(k): int(v) for k, v in obj.items() if isinstance(v, (int, float)) and int(v) >= 0}
        except (ValueError, TypeError, AttributeError):
            return {}

    def persist_resume(self):
        self.settings.setValue('resume_positions', json.dumps(self.resume_store))

    def save_current_position(self):
        if not 0 <= self.current_index < len(self.paths):
            return
        path = self.paths[self.current_index]
        if self.resume_pending is not None and self.resume_pending[0] == path:
            return  # Do not overwrite a saved position before the seek completes.
        position = self.player.position()
        duration = self.player.duration()
        if duration > 0 and position > 10000:
            if position >= duration - 10000:
                self.resume_store.pop(path, None)
            else:
                self.resume_store[path] = position
            self.persist_resume()

    def on_seekable(self, seekable):
        self.position.setEnabled(bool(seekable))

    def cover_for(self, path):
        # Extract one preview frame with system ffmpeg, if available.
        # Files are never executed; ffmpeg is invoked with an argument list.
        if Path(path).suffix.lower() in {'.mp3', '.flac', '.ogg', '.wav', '.m4a', '.aac', '.opus'}:
            return None
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            return None
        try:
            stat = Path(path).stat()
            key = hashlib.sha256(f'{path}|{stat.st_size}|{stat.st_mtime_ns}'.encode()).hexdigest()
            out = self.cover_cache / f'{key}.jpg'
            if not out.exists():
                subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-ss', '00:00:08',
                    '-i', path, '-frames:v', '1', '-vf', 'scale=320:-2', '-y', str(out)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=8, check=False)
            if out.is_file() and out.stat().st_size:
                pix = QPixmap(str(out))
                if not pix.isNull():
                    return QIcon(pix)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return None

    def about(self):
        QMessageBox.information(self,'PowerPlayer Linux 1.0',
            'PowerPlayer Linux 1.0\nLettore multimediale originale con PyQt6 e Qt Multimedia.\n'
            'Libreria persistente e metadati tramite ffprobe (facoltativo).\n'
            'Progetto indipendente, non affiliato a CyberLink.')

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()
    def dropEvent(self,event):
        paths = []
        for url in event.mimeData().urls():
            if not url.isLocalFile():continue
            p = Path(url.toLocalFile())
            if p.is_dir():
                paths.extend(str(x) for x in sorted(p.iterdir()) if x.is_file() and x.suffix.lower() in MEDIA_EXT)
            elif p.is_file():paths.append(str(p))
        self.add_paths(paths)
        event.acceptProposedAction()

    def closeEvent(self,event):
        if self.fullscreen_host is not None:
            self.exit_fullscreen()
        self.save_current_position()
        self.settings.setValue('geometry',self.saveGeometry())
        self.player.stop()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PowerPlayer()
    window.show()
    sys.exit(app.exec())
