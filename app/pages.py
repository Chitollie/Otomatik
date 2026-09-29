from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .compteur import FISH_PRICES, format_money, setup_tesseract
from .config import APP_VERSION, DEFAULT_SETTINGS, save_settings
from .hotkey import vk_from_name
from .theme import LogBox, PageHeader, StatCard, button_row, card_row, format_duration, make_button

SETTINGS_TABS = [
    ("Touches", [
        ("cast_key", "Touche de lancer"),
        ("catch_key", "Touche de prise"),
        ("pause_key", "Touche pause / reprise (F8, F9…)"),
    ]),
    ("Minutage", [
        ("hold_duration", "Maintien de la touche de lancer (s)"),
        ("bite_timeout", "Attente maximale d'une touche (s)"),
        ("minigame_timeout", "Durée maximale du minijeu (s)"),
        ("minigame_end_delay", "Fin du minijeu après disparition (s)"),
        ("scan_interval", "Intervalle de scan (s)"),
        ("recast_min", "Pause avant relance, minimum (s)"),
        ("recast_max", "Pause avant relance, maximum (s)"),
    ]),
    ("Détection", [
        ("green_min", "Sensibilité du vert (plus bas = plus sensible)"),
        ("ref_w", "Largeur de référence"),
        ("ref_h", "Hauteur de référence"),
        ("roi_x", "Zone de la barre : X"),
        ("roi_y", "Zone de la barre : Y"),
        ("roi_w", "Zone de la barre : largeur"),
        ("roi_h", "Zone de la barre : hauteur"),
    ]),
]


class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.fields = {}
        self.setWindowTitle("Paramètres AutoFish")
        self.setMinimumWidth(520)

        tabs = QTabWidget()
        for title, entries in SETTINGS_TABS:
            page = QWidget()
            form = QFormLayout(page)
            form.setContentsMargins(16, 16, 16, 16)
            form.setVerticalSpacing(10)
            for key, label in entries:
                field = self.make_field(key)
                self.fields[key] = field
                form.addRow(label, field)
            tabs.addTab(page, title)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addLayout(button_row(
            make_button("Réinitialiser", self.reset, "secondary"),
            None,
            make_button("Annuler", self.reject, "secondary"),
            make_button("Enregistrer", self.accept),
        ))

    def make_field(self, key):
        default = DEFAULT_SETTINGS[key]
        value = self.cfg[key]
        if isinstance(default, str):
            field = QLineEdit(value)
        elif isinstance(default, int):
            field = QSpinBox()
            field.setButtonSymbols(QAbstractSpinBox.NoButtons)
            field.setRange(0, 100000)
            field.setValue(value)
        else:
            field = QDoubleSpinBox()
            field.setButtonSymbols(QAbstractSpinBox.NoButtons)
            field.setRange(0, 100000)
            field.setDecimals(4)
            field.setValue(value)
        return field

    def reset(self):
        for key, field in self.fields.items():
            default = DEFAULT_SETTINGS[key]
            field.setText(default) if isinstance(default, str) else field.setValue(default)

    def read(self):
        values = {}
        for key, field in self.fields.items():
            values[key] = field.text().strip().lower() if isinstance(field, QLineEdit) else field.value()
        return values

    def accept(self):
        values = self.read()

        if any(not values[key] for key in ("cast_key", "catch_key")):
            QMessageBox.warning(self, "Paramètres", "Les touches de lancer et de prise ne peuvent pas être vides.")
            return
        if vk_from_name(values["pause_key"]) is None:
            QMessageBox.warning(self, "Paramètres", "Touche de pause invalide (exemples : F8, F9, p).")
            return

        try:
            import pydirectinput

            known = getattr(pydirectinput, "KEYBOARD_MAPPING", None)
        except Exception:
            known = None
        if known:
            for key in ("cast_key", "catch_key"):
                if values[key] not in known:
                    QMessageBox.warning(self, "Paramètres", f"Touche inconnue : « {values[key]} » (exemples : e, space, enter).")
                    return

        if values["recast_min"] > values["recast_max"]:
            values["recast_min"], values["recast_max"] = values["recast_max"], values["recast_min"]

        self.cfg.update(values)
        save_settings(self.cfg)
        super().accept()


class Page(QWidget):
    def __init__(self):
        super().__init__()
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(28, 24, 28, 24)
        self.layout_.setSpacing(16)

    def refresh(self):
        pass


class AutoFishPage(Page):
    def __init__(self, cfg, worker, open_settings):
        super().__init__()
        self.cfg = cfg
        self.worker = worker

        self.header = PageHeader("AutoFish", "Maintient la touche de lancer, puis appuie sur la touche de prise dès que la barre est verte.")
        self.start_button = make_button("Lancer", worker.start)
        self.pause_button = make_button("Pause", worker.toggle_pause, "secondary")
        self.stop_button = make_button("Arrêter", worker.stop, "danger")
        self.hint = QLabel()
        self.hint.setObjectName("muted")

        self.casts = StatCard("Lancers")
        self.minigames = StatCard("Minijeux")
        self.presses = StatCard("Appuis")
        self.duration = StatCard("Durée")
        self.log = LogBox(180)

        self.layout_.addWidget(self.header)
        self.layout_.addLayout(button_row(
            self.start_button, self.pause_button, self.stop_button, None,
            make_button("Paramètres", open_settings, "secondary"),
        ))
        self.layout_.addWidget(self.hint)
        self.layout_.addLayout(card_row(self.casts, self.minigames, self.presses, self.duration))
        self.layout_.addWidget(self.log, 1)
        self.refresh()

    def refresh(self):
        state = self.worker.snapshot()
        if not state["running"]:
            self.header.badge.set_state("Arrêté", "idle")
        elif state["paused"]:
            self.header.badge.set_state("En pause", "paused")
        else:
            self.header.badge.set_state(state["phase"], "running")

        self.start_button.setEnabled(not state["running"])
        self.pause_button.setEnabled(state["running"])
        self.pause_button.setText("Reprendre" if state["paused"] else "Pause")
        self.stop_button.setEnabled(state["running"])
        self.hint.setText(f"{self.cfg['pause_key'].upper()} : pause / reprise depuis le jeu.")

        self.casts.set_value(str(state["casts"]))
        self.minigames.set_value(str(state["minigames"]))
        self.presses.set_value(str(state["presses"]))
        self.duration.set_value(format_duration(state["elapsed"]))


class CompteurPage(Page):
    def __init__(self, worker):
        super().__init__()
        self.worker = worker

        self.header = PageHeader("Compteur de pêche", "Lit la notification en haut à droite et calcule ce que rapportent tes poissons.")
        self.start_button = make_button("Lancer", self.start)
        self.stop_button = make_button("Arrêter", worker.stop, "danger")
        self.reset_button = make_button("Réinitialiser", worker.reset, "secondary")

        self.warning = QLabel("Tesseract OCR est introuvable. Installe-le (voir le README) puis clique sur Lancer.")
        self.warning.setObjectName("warning")
        self.warning.setWordWrap(True)
        self.warning.setVisible(setup_tesseract() is None)

        self.total = StatCard("Total gagné", format_money(0))
        self.total.value.setObjectName("bigValue")
        self.rate = StatCard("Rythme", "0 $ / h")
        self.duration = StatCard("Durée")
        self.fish_count = StatCard("Poissons")

        self.table = QTableWidget(len(FISH_PRICES), 4)
        self.table.setHorizontalHeaderLabels(["Poisson", "Prix", "Quantité", "Total"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setShowGrid(False)
        for row, (name, price) in enumerate(FISH_PRICES.items()):
            for column, text in enumerate((name, format_money(price), "0", format_money(0))):
                item = QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, column, item)
        for column in range(4):
            align = Qt.AlignRight if column else Qt.AlignLeft
            self.table.horizontalHeaderItem(column).setTextAlignment(align | Qt.AlignVCenter)
        self.table.setMinimumHeight(34 * len(FISH_PRICES) + 40)

        self.log = LogBox(80)

        self.layout_.addWidget(self.header)
        self.layout_.addLayout(button_row(self.start_button, self.stop_button, self.reset_button, None))
        self.layout_.addWidget(self.warning)
        self.layout_.addLayout(card_row(self.total, self.rate, self.duration, self.fish_count))
        self.layout_.addWidget(self.table, 1)
        self.layout_.addWidget(self.log)
        self.refresh()

    def start(self):
        self.worker.start()
        self.warning.setVisible(setup_tesseract() is None)

    def refresh(self):
        state = self.worker.snapshot()
        self.header.badge.set_state("En marche" if state["running"] else "Arrêté", "running" if state["running"] else "idle")
        self.start_button.setEnabled(not state["running"])
        self.stop_button.setEnabled(state["running"])

        self.total.set_value(format_money(state["total"]))
        self.rate.set_value(f"{format_money(state['per_hour'])} / h")
        self.duration.set_value(format_duration(state["elapsed"]))
        self.fish_count.set_value(str(sum(state["counts"].values())))

        for row, (name, price) in enumerate(FISH_PRICES.items()):
            count = state["counts"][name]
            self.table.item(row, 2).setText(str(count))
            self.table.item(row, 3).setText(format_money(count * price))


class AntiAFKPage(Page):
    def __init__(self, cfg, worker):
        super().__init__()
        self.cfg = cfg
        self.worker = worker

        self.header = PageHeader("AntiAFK", "Envoie S puis Z à intervalle régulier pour éviter d'être déconnecté.")
        self.start_button = make_button("Lancer", worker.start)
        self.stop_button = make_button("Arrêter", worker.stop, "danger")

        self.interval = QSpinBox()
        self.interval.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.interval.setFixedWidth(90)
        self.interval.setRange(1, 240)
        self.interval.setSuffix(" min")
        self.interval.setValue(cfg["afk_minutes"])
        self.interval.valueChanged.connect(self.set_interval)

        self.cycles = StatCard("Cycles envoyés")
        self.countdown = StatCard("Prochaine action dans")
        self.every = StatCard("Intervalle")
        self.log = LogBox(180)

        interval_row = QFrame()
        interval_row.setObjectName("card")
        row = button_row(QLabel("Intervalle entre deux actions"), None, self.interval)
        row.setContentsMargins(16, 10, 16, 10)
        interval_row.setLayout(row)

        self.layout_.addWidget(self.header)
        self.layout_.addLayout(button_row(self.start_button, self.stop_button, None))
        self.layout_.addWidget(interval_row)
        self.layout_.addLayout(card_row(self.cycles, self.countdown, self.every))
        self.layout_.addWidget(self.log, 1)
        self.refresh()

    def set_interval(self, value):
        self.cfg["afk_minutes"] = value
        save_settings(self.cfg)

    def refresh(self):
        state = self.worker.snapshot()
        self.header.badge.set_state("En marche" if state["running"] else "Arrêté", "running" if state["running"] else "idle")
        self.start_button.setEnabled(not state["running"])
        self.stop_button.setEnabled(state["running"])

        self.cycles.set_value(str(state["cycles"]))
        left = state["seconds_left"]
        self.countdown.set_value("—" if left is None else format_duration(left)[3:])
        self.every.set_value(f"{state['interval_minutes']} min")


class UpdatePage(Page):
    def __init__(self, on_check, on_download):
        super().__init__()
        self.info = None

        self.header = PageHeader("Mises à jour", "Compare ta version avec celle publiée sur GitHub.")
        self.check_button = make_button("Vérifier les mises à jour", on_check)
        self.download_button = make_button("Télécharger", on_download, "secondary")
        self.download_button.setEnabled(False)

        self.installed = StatCard("Version installée", APP_VERSION)
        self.latest = StatCard("Dernière version")
        self.status = QLabel("Aucune vérification effectuée.")
        self.status.setWordWrap(True)

        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setPlaceholderText("Les notes de version apparaîtront ici.")

        self.layout_.addWidget(self.header)
        self.layout_.addLayout(button_row(self.check_button, self.download_button, None))
        self.layout_.addLayout(card_row(self.installed, self.latest))
        self.layout_.addWidget(self.status)
        self.layout_.addWidget(self.notes, 1)

    def show_checking(self):
        self.check_button.setEnabled(False)
        self.header.badge.set_state("Vérification…", "info")
        self.status.setText("Vérification en cours…")

    def show_result(self, info):
        self.info = info
        self.check_button.setEnabled(True)
        self.latest.set_value(info.version)
        self.notes.setPlainText(info.notes)
        self.download_button.setEnabled(info.is_newer and bool(info.url or info.files))
        if info.is_newer:
            self.header.badge.set_state("Mise à jour disponible", "paused")
            self.status.setText(f"La version {info.version} est disponible.")
        else:
            self.header.badge.set_state("À jour", "running")
            self.status.setText("Tu utilises la dernière version.")

    def show_error(self, message):
        self.check_button.setEnabled(True)
        self.download_button.setEnabled(False)
        self.header.badge.set_state("Erreur", "error")
        self.status.setText(message)

    def show_downloaded(self, folder):
        self.status.setText(f"Fichiers téléchargés et vérifiés (SHA-256) dans : {folder}")
