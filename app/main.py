import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QListWidget,QStackedWidget,QPlainTextEdit,QDoubleSpinBox,QFormLayout,QDialog,QLineEdit,QMessageBox,QTableWidget,QTableWidgetItem,QHeaderView
from .config import *
from .autofish import AutoFish
from .antiafk import AntiAFK
from .compteur import Compteur,FISH_PRICES,format_money
from .updater import Updater

STYLE='''QWidget{background:#0b0f14;color:#e7edf5;font-family:Segoe UI} QListWidget,QPlainTextEdit,QTableWidget{background:#101722;border:1px solid #1c2a3a;border-radius:8px} QListWidget::item{padding:12px} QListWidget::item:selected{background:#0879d1} QPushButton{background:#0879d1;color:white;border:0;border-radius:7px;padding:10px 16px} QPushButton:hover{background:#0a8be9} QHeaderView::section{background:#0e151e;color:#e7edf5;border:0;padding:6px} QDoubleSpinBox,QLineEdit{background:#0e151e;border:1px solid #26384b;border-radius:6px;padding:7px}'''
DEFAULT={'ref_w':1920,'ref_h':1080,'roi_x':1082,'roi_y':245,'roi_w':40,'roi_h':592,'hold_duration':4.0,'bite_timeout':120.0,'minigame_timeout':60.0,'minigame_end_delay':.6,'scan_interval':.01,'recast_min':.5,'recast_max':2.0,'green_min':.005,'cast_key':'e','catch_key':'space'}
class Settings(QDialog):
 def __init__(self,cfg,parent=None):
  super().__init__(parent); self.cfg=cfg; self.setWindowTitle('Paramètres AutoFish'); f=QFormLayout(self); self.box={}
  for k,v in cfg.items():
   if isinstance(v,(int,float)):
    b=QDoubleSpinBox(); b.setRange(0,10000); b.setDecimals(4); b.setValue(v); self.box[k]=b; f.addRow(k,b)
  for k in ('cast_key','catch_key'):
   b=QLineEdit(cfg[k]); self.box[k]=b; f.addRow(k,b)
  ok=QPushButton('Enregistrer'); ok.clicked.connect(self.accept); f.addRow(ok)
 def accept(self):
  for k,b in self.box.items(): self.cfg[k]=b.value() if hasattr(b,'value') else b.text(); super().accept()
class Main(QMainWindow):
 def __init__(self):
  super().__init__(); self.setWindowTitle('Otomatik 1.0.0'); self.resize(950,600); self.setStyleSheet(STYLE); self.cfg=DEFAULT.copy(); self.af=AutoFish(self.cfg,self.log); self.aa=AntiAFK({},self.log); self.ct=Compteur(self.log)
  c=QWidget(); self.setCentralWidget(c); root=QHBoxLayout(c); left=QVBoxLayout(); title=QLabel('Otomatik'); title.setStyleSheet('font-size:22px;font-weight:700'); left.addWidget(title); self.nav=QListWidget(); self.nav.addItems(['AutoFish','Compteur','AntiAFK','Mise à jour']); self.nav.currentRowChanged.connect(self.stack_to); left.addWidget(self.nav); left.addStretch(); self.login=QPushButton('Connexion Discord'); left.addWidget(self.login); root.addLayout(left,1)
  self.stack=QStackedWidget(); self.stack.addWidget(self.auto_page()); self.stack.addWidget(self.counter_page()); self.stack.addWidget(self.afk_page()); self.stack.addWidget(self.update_page()); root.addWidget(self.stack,3); self.nav.setCurrentRow(0); self.timer=QTimer(self); self.timer.timeout.connect(self.refresh_counter); self.timer.start(300)
 def auto_page(self):
  p=QWidget(); l=QVBoxLayout(p); l.addWidget(QLabel('AutoFish')); r=QHBoxLayout();
  for txt,fn in [('Lancer',self.af.start),('Arrêter',self.af.stop),('Pause',self.af.pause),('Reprendre',self.af.resume),('Paramètres',self.settings)]: b=QPushButton(txt); b.clicked.connect(fn); r.addWidget(b)
  l.addLayout(r); self.console=QPlainTextEdit(); self.console.setReadOnly(True); l.addWidget(self.console); return p
 def counter_page(self):
  p=QWidget(); l=QVBoxLayout(p); l.addWidget(QLabel('Compteur de pêche')); r=QHBoxLayout()
  for txt,fn in [('Lancer',self.ct.start),('Arrêter',self.ct.stop),('Réinitialiser',self.ct.reset)]: b=QPushButton(txt); b.clicked.connect(fn); r.addWidget(b)
  l.addLayout(r); self.ct_total=QLabel(format_money(0)); self.ct_total.setStyleSheet('font-size:36px;font-weight:700;color:#0a8be9'); l.addWidget(self.ct_total)
  self.ct_rate=QLabel('0 $ / heure'); l.addWidget(self.ct_rate)
  self.ct_table=QTableWidget(len(FISH_PRICES),4); self.ct_table.setHorizontalHeaderLabels(['Poisson','Prix','Quantité','Total']); self.ct_table.verticalHeader().setVisible(False); self.ct_table.setEditTriggers(QTableWidget.NoEditTriggers); self.ct_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
  for i,(name,price) in enumerate(FISH_PRICES.items()):
   for j,v in enumerate((name,format_money(price),'0',format_money(0))): self.ct_table.setItem(i,j,QTableWidgetItem(v))
  l.addWidget(self.ct_table); return p
 def refresh_counter(self):
  s=self.ct.snapshot(); self.ct_total.setText(format_money(s['total'])); self.ct_rate.setText(f"{format_money(s['per_hour'])} / heure")
  for i,(name,price) in enumerate(FISH_PRICES.items()):
   n=s['counts'][name]; self.ct_table.item(i,2).setText(str(n)); self.ct_table.item(i,3).setText(format_money(n*price))
 def afk_page(self):
  p=QWidget(); l=QVBoxLayout(p); l.addWidget(QLabel('AntiAFK')); r=QHBoxLayout();
  for txt,fn in [('Lancer',self.aa.start),('Arrêter',self.aa.stop)]: b=QPushButton(txt); b.clicked.connect(fn); r.addWidget(b)
  l.addLayout(r); l.addWidget(QLabel('S → Z → attente 20 minutes → répétition')); return p
 def update_page(self):
  p=QWidget(); l=QVBoxLayout(p); l.addWidget(QLabel('Mise à jour')); b=QPushButton('Vérifier les mises à jour'); b.clicked.connect(self.update); l.addWidget(b); l.addStretch(); return p
 def stack_to(self,i): self.stack.setCurrentIndex(i)
 def settings(self):
  if Settings(self.cfg,self).exec(): self.log('Paramètres enregistrés.')
 def log(self,x):
  if hasattr(self,'console'): self.console.appendPlainText(x)
 def update(self):
  try:
   m=Updater().manifest(); QMessageBox.information(self,'Otomatik',f"Version disponible : {m['version']}\n\n{m.get('notes','')}")
  except Exception as e: QMessageBox.critical(self,'Mise à jour',str(e))
app=QApplication(sys.argv); w=Main(); w.show(); sys.exit(app.exec())
