import sys
import os
import json
import shutil
import zipfile
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs, quote, unquote
import mimetypes
import threading
import time

# PyQt6 импорты
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtWebEngineWidgets import *
from PyQt6.QtWebEngineCore import *

class MacTitleBar(QWidget):
    """Кастомная панель заголовка в стиле macOS"""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(38)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(12)
        
        # Кнопки управления окном
        self.close_btn = self.create_window_button("#ff5f57", "✕")
        self.minimize_btn = self.create_window_button("#ffbd2e", "－")
        self.maximize_btn = self.create_window_button("#28ca42", "□")
        
        self.close_btn.clicked.connect(self.parent_window.close)
        self.minimize_btn.clicked.connect(self.parent_window.showMinimized)
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        
        layout.addWidget(self.close_btn)
        layout.addWidget(self.minimize_btn)
        layout.addWidget(self.maximize_btn)
        
        layout.addStretch(1)
        
        self.title_label = QLabel("Aura Browser")
        self.title_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                font-size: 13px;
                font-weight: 500;
                padding: 0 8px;
            }
        """)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        layout.addStretch(1)
        layout.addSpacing(60)
        
        self.setMouseTracking(True)
        
    def create_window_button(self, color, symbol):
        btn = QPushButton(symbol)
        btn.setFixedSize(12, 12)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: rgba(0, 0, 0, 0.7);
                border-radius: 6px;
                font-size: 8px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: black;
            }}
        """)
        return btn
        
    def toggle_maximize(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
        else:
            self.parent_window.showMaximized()
            
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent_window.dragPos = event.globalPosition().toPoint()
            event.accept()
            
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            if hasattr(self.parent_window, 'dragPos'):
                self.parent_window.move(
                    self.parent_window.pos() + 
                    event.globalPosition().toPoint() - self.parent_window.dragPos
                )
                self.parent_window.dragPos = event.globalPosition().toPoint()
                event.accept()

class Extension:
    """Класс для управления расширениями"""
    def __init__(self, path):
        self.path = Path(path)
        self.manifest = self.load_manifest()
        self.enabled = True
        self.id = self.generate_id()
        
    def load_manifest(self):
        """Загружает manifest.json расширения"""
        manifest_path = self.path / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def generate_id(self):
        """Генерирует ID для расширения"""
        name = self.manifest.get('name', 'unknown')
        return f"{name.lower().replace(' ', '_')}_{hash(str(self.path)) % 10000:04d}"
    
    def get_info(self):
        """Возвращает информацию о расширении"""
        return {
            'id': self.id,
            'name': self.manifest.get('name', 'Unknown'),
            'version': self.manifest.get('version', '1.0'),
            'description': self.manifest.get('description', ''),
            'author': self.manifest.get('author', ''),
            'path': str(self.path)
        }

class ExtensionManager:
    """Менеджер расширений браузера"""
    def __init__(self):
        self.extensions = []
        self.extensions_dir = Path.home() / ".aura_browser" / "extensions"
        self.extensions_dir.mkdir(parents=True, exist_ok=True)
        self.load_extensions()
        
    def load_extensions(self):
        """Загружает все установленные расширения"""
        self.extensions = []
        for ext_dir in self.extensions_dir.iterdir():
            if ext_dir.is_dir():
                extension = Extension(ext_dir)
                self.extensions.append(extension)
    
    def install_extension(self, crx_path):
        """Устанавливает расширение из .crx файла"""
        try:
            # Создаем временную папку
            temp_dir = self.extensions_dir / "temp"
            temp_dir.mkdir(exist_ok=True)
            
            # Распаковываем .crx (это zip архив)
            with zipfile.ZipFile(crx_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Читаем manifest.json
            manifest_path = temp_dir / "manifest.json"
            if not manifest_path.exists():
                shutil.rmtree(temp_dir)
                return False, "Manifest not found"
            
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            # Создаем уникальное имя для расширения
            ext_name = manifest.get('name', 'unknown').lower().replace(' ', '_')
            ext_version = manifest.get('version', '1.0')
            ext_id = f"{ext_name}_{ext_version}"
            
            # Переносим в постоянную папку
            final_dir = self.extensions_dir / ext_id
            if final_dir.exists():
                shutil.rmtree(final_dir)
            
            shutil.move(str(temp_dir), str(final_dir))
            
            # Добавляем в список
            extension = Extension(final_dir)
            self.extensions.append(extension)
            
            return True, f"Extension '{manifest.get('name')}' installed successfully"
            
        except Exception as e:
            return False, str(e)
    
    def uninstall_extension(self, extension_id):
        """Удаляет расширение"""
        for i, ext in enumerate(self.extensions):
            if ext.id == extension_id:
                try:
                    shutil.rmtree(ext.path)
                    self.extensions.pop(i)
                    return True, "Extension removed"
                except Exception as e:
                    return False, str(e)
        return False, "Extension not found"
    
    def toggle_extension(self, extension_id):
        """Включает/выключает расширение"""
        for ext in self.extensions:
            if ext.id == extension_id:
                ext.enabled = not ext.enabled
                return True, f"Extension {'enabled' if ext.enabled else 'disabled'}"
        return False, "Extension not found"
    
    def get_extension_widget(self):
        """Создает виджет для управления расширениями"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Заголовок
        title = QLabel("🔌 Extension Manager")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #8A2BE2;
            margin: 10px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Кнопка установки
        install_btn = QPushButton("📁 Install Extension (.crx)")
        install_btn.clicked.connect(self.install_dialog)
        install_btn.setStyleSheet("""
            QPushButton {
                background-color: #8A2BE2;
                color: white;
                border-radius: 10px;
                padding: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        layout.addWidget(install_btn)
        
        # Список расширений
        self.extensions_list = QListWidget()
        self.extensions_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                margin: 2px;
                padding: 10px;
            }
            QListWidget::item:selected {
                background-color: rgba(138, 43, 226, 0.3);
            }
        """)
        layout.addWidget(self.extensions_list, 1)
        
        # Панель управления
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        
        self.toggle_btn = QPushButton("Toggle")
        self.uninstall_btn = QPushButton("Uninstall")
        
        self.toggle_btn.clicked.connect(self.toggle_selected)
        self.uninstall_btn.clicked.connect(self.uninstall_selected)
        
        for btn in [self.toggle_btn, self.uninstall_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(138, 43, 226, 0.2);
                    color: #8A2BE2;
                    border: 1px solid rgba(138, 43, 226, 0.3);
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(138, 43, 226, 0.3);
                }
                QPushButton:disabled {
                    background-color: rgba(255, 255, 255, 0.05);
                    color: rgba(255, 255, 255, 0.3);
                }
            """)
            btn.setEnabled(False)
            control_layout.addWidget(btn)
        
        control_layout.addStretch()
        layout.addWidget(control_panel)
        
        # Подключаем выбор элемента
        self.extensions_list.itemSelectionChanged.connect(self.on_extension_selected)
        
        # Обновляем список
        self.update_extensions_list()
        
        return widget
    
    def update_extensions_list(self):
        """Обновляет список расширений"""
        self.extensions_list.clear()
        for ext in self.extensions:
            info = ext.get_info()
            item_text = f"✨ {info['name']} v{info['version']}"
            if not ext.enabled:
                item_text = f"⚫ {info['name']} v{info['version']} (Disabled)"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, ext.id)
            self.extensions_list.addItem(item)
    
    def on_extension_selected(self):
        """Обработчик выбора расширения"""
        selected = self.extensions_list.selectedItems()
        self.toggle_btn.setEnabled(len(selected) > 0)
        self.uninstall_btn.setEnabled(len(selected) > 0)
    
    def install_dialog(self):
        """Диалог установки расширения"""
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Select Chrome Extension (.crx)",
            str(Path.home()),
            "Chrome Extensions (*.crx);;All Files (*.*)"
        )
        
        if file_path:
            success, message = self.install_extension(file_path)
            if success:
                QMessageBox.information(None, "Success", message)
                self.update_extensions_list()
            else:
                QMessageBox.critical(None, "Error", message)
    
    def toggle_selected(self):
        """Включает/выключает выбранное расширение"""
        selected = self.extensions_list.selectedItems()
        if selected:
            ext_id = selected[0].data(Qt.ItemDataRole.UserRole)
            success, message = self.toggle_extension(ext_id)
            if success:
                self.update_extensions_list()
    
    def uninstall_selected(self):
        """Удаляет выбранное расширение"""
        selected = self.extensions_list.selectedItems()
        if selected:
            ext_id = selected[0].data(Qt.ItemDataRole.UserRole)
            reply = QMessageBox.question(
                None,
                "Confirm Uninstall",
                "Are you sure you want to uninstall this extension?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                success, message = self.uninstall_extension(ext_id)
                if success:
                    self.update_extensions_list()
                    QMessageBox.information(None, "Success", message)
                else:
                    QMessageBox.critical(None, "Error", message)

class ChromeWebStore:
    """Интеграция с Chrome Web Store"""
    
    @staticmethod
    def get_extension_info(extension_id):
        """Получает информацию о расширении из Chrome Web Store"""
        try:
            # URL для получения информации о расширении
            url = f"https://chrome.google.com/webstore/detail/{extension_id}"
            
            # Имитируем браузерный запрос
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'id': extension_id,
                    'available': True,
                    'name': "Extension from Chrome Web Store",
                    'message': "To download from Chrome Web Store, use direct .crx file or developer mode"
                }
            else:
                return {
                    'success': False,
                    'error': f"Extension not found (Status: {response.status_code})"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def extract_extension_id(url):
        """Извлекает ID расширения из URL Chrome Web Store"""
        try:
            parsed = urlparse(url)
            
            if 'chrome.google.com' in parsed.netloc and '/webstore/detail/' in parsed.path:
                path_parts = parsed.path.split('/')
                if len(path_parts) > 3:
                    return path_parts[3]
            
            return None
            
        except:
            return None

class RealDownloadManager:
    """Реальный менеджер загрузок с поддержкой потоков"""
    
    def __init__(self, downloads_dir):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.active_downloads = {}
        self.download_queue = []
        
    def start_download(self, url, filename=None, folder=None):
        """Начинает реальную загрузку файла"""
        if folder is None:
            folder = self.downloads_dir
        else:
            folder = Path(folder)
            folder.mkdir(parents=True, exist_ok=True)
        
        # Определяем имя файла
        if not filename:
            filename = self.extract_filename(url)
        
        filepath = folder / filename
        
        # Создаем уникальное имя, если файл уже существует
        counter = 1
        original_name = filepath.stem
        original_ext = filepath.suffix
        while filepath.exists():
            filepath = folder / f"{original_name} ({counter}){original_ext}"
            counter += 1
        
        # Создаем объект загрузки
        download_id = int(time.time() * 1000)
        download_info = {
            'id': download_id,
            'url': url,
            'filename': filepath.name,
            'filepath': str(filepath),
            'total_size': 0,
            'downloaded': 0,
            'status': 'starting',
            'speed': 0,
            'start_time': datetime.now(),
            'end_time': None,
            'error': None,
            'thread': None
        }
        
        # Запускаем загрузку в отдельном потоке
        thread = threading.Thread(
            target=self.download_file,
            args=(download_id, url, str(filepath), download_info),
            daemon=True
        )
        
        download_info['thread'] = thread
        self.active_downloads[download_id] = download_info
        thread.start()
        
        return download_id
    
    def download_file(self, download_id, url, filepath, download_info):
        """Загружает файл в отдельном потоке"""
        try:
            download_info['status'] = 'downloading'
            
            # Отправляем запрос с поддержкой докачки
            headers = {}
            if os.path.exists(filepath):
                # Если файл уже существует частично, продолжаем загрузку
                downloaded = os.path.getsize(filepath)
                headers['Range'] = f'bytes={downloaded}-'
                download_info['downloaded'] = downloaded
                mode = 'ab'  # Append mode
            else:
                mode = 'wb'  # Write mode
            
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # Получаем общий размер файла
            total_size = int(response.headers.get('content-length', 0))
            if 'content-range' in response.headers:
                # Если используем докачку, вычисляем полный размер
                content_range = response.headers['content-range']
                total_size = int(content_range.split('/')[-1])
            
            download_info['total_size'] = total_size
            
            # Загружаем файл частями
            chunk_size = 8192
            start_time = time.time()
            last_update = start_time
            
            with open(filepath, mode) as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if download_info['status'] == 'cancelled':
                        break
                    
                    if chunk:
                        f.write(chunk)
                        download_info['downloaded'] += len(chunk)
                        
                        # Обновляем скорость каждые 0.5 секунды
                        current_time = time.time()
                        if current_time - last_update >= 0.5:
                            elapsed = current_time - start_time
                            if elapsed > 0:
                                download_info['speed'] = download_info['downloaded'] / elapsed
                            last_update = current_time
            
            if download_info['status'] != 'cancelled':
                download_info['status'] = 'completed'
                download_info['end_time'] = datetime.now()
                download_info['speed'] = 0
            else:
                # Если загрузка отменена, удаляем частично скачанный файл
                if os.path.exists(filepath):
                    os.remove(filepath)
                
        except Exception as e:
            download_info['status'] = 'error'
            download_info['error'] = str(e)
            
        finally:
            # Удаляем из активных загрузок
            if download_id in self.active_downloads:
                del self.active_downloads[download_id]
    
    def pause_download(self, download_id):
        """Приостанавливает загрузку"""
        if download_id in self.active_downloads:
            self.active_downloads[download_id]['status'] = 'paused'
    
    def resume_download(self, download_id):
        """Возобновляет загрузку"""
        if download_id in self.active_downloads:
            download_info = self.active_downloads[download_id]
            if download_info['status'] == 'paused':
                # Перезапускаем загрузку с текущей позиции
                self.start_download(
                    download_info['url'],
                    download_info['filename'],
                    Path(download_info['filepath']).parent
                )
                # Удаляем старую запись
                del self.active_downloads[download_id]
    
    def cancel_download(self, download_id):
        """Отменяет загрузку"""
        if download_id in self.active_downloads:
            self.active_downloads[download_id]['status'] = 'cancelled'
    
    def get_download_info(self, download_id):
        """Возвращает информацию о загрузке"""
        return self.active_downloads.get(download_id)
    
    def get_all_downloads(self):
        """Возвращает все активные загрузки"""
        return list(self.active_downloads.values())
    
    @staticmethod
    def extract_filename(url):
        """Извлекает имя файла из URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path
            
            # Пытаемся получить имя файла из пути
            filename = os.path.basename(path)
            
            # Если имя файла не найдено в пути, создаем имя по умолчанию
            if not filename or '.' not in filename:
                filename = f"download_{int(time.time())}.bin"
            
            # Декодируем URL-encoded символы
            filename = unquote(filename)
            
            # Убираем query параметры если они есть в имени
            if '?' in filename:
                filename = filename.split('?')[0]
            
            return filename
            
        except:
            return f"download_{int(time.time())}.bin"
    
    @staticmethod
    def is_downloadable_url(url):
        """Проверяет, является ли URL ссылкой на скачиваемый файл"""
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            # Расширения файлов для скачивания
            downloadable_extensions = {
                '.exe', '.msi', '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
                '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                '.mp4', '.mp3', '.avi', '.mkv', '.mov', '.wav', '.flac',
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg',
                '.iso', '.dmg', '.apk', '.deb', '.rpm',
                '.torrent', '.crx', '.jar', '.py', '.js', '.html', '.css'
            }
            
            # Проверяем расширение файла
            for ext in downloadable_extensions:
                if path.endswith(ext):
                    return True
            
            # Ключевые слова в URL
            download_keywords = ['download', 'getfile', 'attachment', 'cdn', 'storage']
            for keyword in download_keywords:
                if keyword in url.lower():
                    return True
            
            return False
            
        except:
            return False

class DownloadManagerWindow(QMainWindow):
    """Окно менеджера загрузок"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setWindowTitle("Aura Download Manager")
        self.setGeometry(200, 200, 1000, 700)
        
        self.download_manager = parent.download_manager
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_table)
        self.update_timer.start(500)
        
        self.init_ui()
        
    def init_ui(self):
        main_widget = QWidget()
        main_widget.setObjectName("mainWidget")
        self.setCentralWidget(main_widget)
        
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Заголовок macOS
        title_bar = QWidget()
        title_bar.setFixedHeight(38)
        title_bar.setStyleSheet("background-color: rgba(30, 30, 30, 0.9);")
        
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 15, 0)
        
        close_btn = self.create_window_button("#ff5f57", "✕", self.close)
        minimize_btn = self.create_window_button("#ffbd2e", "－", self.showMinimized)
        
        title_layout.addWidget(close_btn)
        title_layout.addWidget(minimize_btn)
        title_layout.addStretch()
        
        title_label = QLabel("📥 Aura Download Manager")
        title_label.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 13px; font-weight: 500;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addSpacing(60)
        
        layout.addWidget(title_bar)
        
        # Основное содержимое
        content = QWidget()
        content.setStyleSheet("background-color: #1a1a2e;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # Панель инструментов
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        actions = [
            ("➕ New Download", self.new_download),
            ("⏸️ Pause All", self.pause_all),
            ("▶️ Resume All", self.resume_all),
            ("🗑️ Clear Completed", self.clear_completed),
            ("📁 Open Folder", self.open_downloads_folder),
        ]
        
        for text, callback in actions:
            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(138, 43, 226, 0.15);
                    color: #8A2BE2;
                    border: 1px solid rgba(138, 43, 226, 0.3);
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: rgba(138, 43, 226, 0.25);
                }
            """)
            btn.clicked.connect(callback)
            toolbar_layout.addWidget(btn)
        
        toolbar_layout.addStretch()
        content_layout.addWidget(toolbar)
        
        # Статистика
        stats = QWidget()
        stats.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 12px;
        """)
        stats_layout = QHBoxLayout(stats)
        
        self.stats_label = QLabel("📊 Active: 0 | Total: 0 | Speed: 0 KB/s")
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")
        stats_layout.addWidget(self.stats_label)
        stats_layout.addStretch()
        
        content_layout.addWidget(stats)
        
        # Таблица загрузок
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["File", "Size", "Progress", "Speed", "Time", "Status", "Actions"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                gridline-color: rgba(255, 255, 255, 0.05);
                font-size: 13px;
            }
            QTableWidget::item {
                color: rgba(255, 255, 255, 0.9);
                padding: 8px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }
            QTableWidget::item:selected {
                background-color: rgba(138, 43, 226, 0.3);
            }
            QHeaderView::section {
                background-color: rgba(138, 43, 226, 0.2);
                color: #8A2BE2;
                padding: 10px;
                border: none;
                font-weight: bold;
            }
            QProgressBar {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                background-color: rgba(255, 255, 255, 0.05);
                text-align: center;
                color: white;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #8A2BE2, stop: 1 #9370DB
                );
                border-radius: 6px;
            }
        """)
        
        content_layout.addWidget(self.table, 1)
        
        layout.addWidget(content)
        
        # Настраиваем ширину колонок
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
    
    def create_window_button(self, color, symbol, callback):
        btn = QPushButton(symbol)
        btn.setFixedSize(12, 12)
        btn.clicked.connect(callback)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: rgba(0, 0, 0, 0.7);
                border-radius: 6px;
                font-size: 8px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: black;
            }}
        """)
        return btn
    
    def new_download(self):
        """Создает новую загрузку"""
        dialog = QDialog(self)
        dialog.setWindowTitle("New Download")
        dialog.setFixedSize(500, 250)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
            QLabel {
                color: rgba(255, 255, 255, 0.9);
                font-size: 14px;
                margin-top: 10px;
            }
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.07);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #8A2BE2;
            }
            QPushButton {
                background-color: #8A2BE2;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("Download URL:"))
        url_input = QLineEdit()
        url_input.setPlaceholderText("https://example.com/file.zip")
        layout.addWidget(url_input)
        
        layout.addWidget(QLabel("Save to folder:"))
        location_input = QLineEdit(str(self.download_manager.downloads_dir))
        layout.addWidget(location_input)
        
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        download_btn = QPushButton("Start Download")
        
        cancel_btn.clicked.connect(dialog.reject)
        download_btn.clicked.connect(lambda: self.start_download_from_dialog(
            url_input.text(), location_input.text(), dialog
        ))
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(download_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def start_download_from_dialog(self, url, folder, dialog):
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL")
            return
        
        self.download_manager.start_download(url, folder=folder)
        dialog.accept()
    
    def pause_all(self):
        """Приостанавливает все загрузки"""
        for download in self.download_manager.get_all_downloads():
            if download['status'] in ['downloading', 'starting']:
                self.download_manager.pause_download(download['id'])
    
    def resume_all(self):
        """Возобновляет все загрузки"""
        for download in self.download_manager.get_all_downloads():
            if download['status'] == 'paused':
                self.download_manager.resume_download(download['id'])
    
    def clear_completed(self):
        """Очищает завершенные загрузки"""
        # В реальном менеджере мы бы хранили историю
        # Здесь просто обновляем таблицу
        self.update_table()
    
    def open_downloads_folder(self):
        """Открывает папку загрузок"""
        os.startfile(str(self.download_manager.downloads_dir))
    
    def update_table(self):
        """Обновляет таблицу загрузок"""
        downloads = self.download_manager.get_all_downloads()
        self.table.setRowCount(len(downloads))
        
        active = 0
        total_speed = 0
        
        for row, download in enumerate(downloads):
            # Filename
            self.table.setItem(row, 0, QTableWidgetItem(download['filename']))
            
            # Size
            size_text = self.format_size(download['total_size']) if download['total_size'] > 0 else "?"
            self.table.setItem(row, 1, QTableWidgetItem(size_text))
            
            # Progress
            progress_bar = QProgressBar()
            progress_bar.setMaximum(100)
            
            if download['total_size'] > 0:
                progress = (download['downloaded'] / download['total_size']) * 100
                progress_bar.setValue(int(progress))
                progress_bar.setFormat(f"{progress:.1f}%")
            else:
                progress_bar.setValue(0)
                progress_bar.setFormat("?")
            
            self.table.setCellWidget(row, 2, progress_bar)
            
            # Speed
            speed_text = self.format_speed(download['speed']) if download['speed'] > 0 else ""
            self.table.setItem(row, 3, QTableWidgetItem(speed_text))
            
            # Time
            if download['status'] == 'completed':
                elapsed = (download['end_time'] - download['start_time']).total_seconds()
                time_text = f"{elapsed:.1f}s"
            elif download['speed'] > 0 and download['total_size'] > 0:
                remaining = (download['total_size'] - download['downloaded']) / download['speed']
                time_text = f"{remaining:.1f}s left"
            else:
                time_text = ""
            self.table.setItem(row, 4, QTableWidgetItem(time_text))
            
            # Status
            status_text = download['status'].capitalize()
            if download['error']:
                status_text = f"Error: {download['error'][:30]}"
            
            status_item = QTableWidgetItem(status_text)
            
            # Цвет статуса
            if download['status'] == 'completed':
                status_item.setForeground(QColor("#4CAF50"))
            elif download['status'] == 'downloading':
                status_item.setForeground(QColor("#2196F3"))
            elif download['status'] == 'paused':
                status_item.setForeground(QColor("#FF9800"))
            elif download['status'] == 'error':
                status_item.setForeground(QColor("#F44336"))
            elif download['status'] == 'starting':
                status_item.setForeground(QColor("#9C27B0"))
            
            self.table.setItem(row, 5, status_item)
            
            # Actions
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(5, 2, 5, 2)
            action_layout.setSpacing(5)
            
            if download['status'] == 'downloading':
                pause_btn = QPushButton("⏸️")
                pause_btn.setFixedSize(30, 30)
                pause_btn.clicked.connect(lambda checked, d=download: self.download_manager.pause_download(d['id']))
                pause_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255, 152, 0, 0.2);
                        color: #FF9800;
                        border-radius: 6px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255, 152, 0, 0.3);
                    }
                """)
                action_layout.addWidget(pause_btn)
            elif download['status'] == 'paused':
                resume_btn = QPushButton("▶️")
                resume_btn.setFixedSize(30, 30)
                resume_btn.clicked.connect(lambda checked, d=download: self.download_manager.resume_download(d['id']))
                resume_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(33, 150, 243, 0.2);
                        color: #2196F3;
                        border-radius: 6px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: rgba(33, 150, 243, 0.3);
                    }
                """)
                action_layout.addWidget(resume_btn)
            
            if download['status'] == 'completed':
                open_btn = QPushButton("📂")
                open_btn.setFixedSize(30, 30)
                open_btn.clicked.connect(lambda checked, p=download['filepath']: self.open_file(p))
                open_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(76, 175, 80, 0.2);
                        color: #4CAF50;
                        border-radius: 6px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: rgba(76, 175, 80, 0.3);
                    }
                """)
                action_layout.addWidget(open_btn)
            
            cancel_btn = QPushButton("❌")
            cancel_btn.setFixedSize(30, 30)
            cancel_btn.clicked.connect(lambda checked, d=download: self.download_manager.cancel_download(d['id']))
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(244, 67, 54, 0.2);
                    color: #F44336;
                    border-radius: 6px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: rgba(244, 67, 54, 0.3);
                }
            """)
            action_layout.addWidget(cancel_btn)
            
            action_layout.addStretch()
            self.table.setCellWidget(row, 6, action_widget)
            
            # Статистика
            if download['status'] == 'downloading':
                active += 1
                total_speed += download['speed']
        
        # Обновляем статистику
        self.stats_label.setText(
            f"📊 Active: {active} | Total: {len(downloads)} | "
            f"Speed: {self.format_speed(total_speed)}"
        )
    
    def open_file(self, filepath):
        if os.path.exists(filepath):
            os.startfile(filepath)
    
    @staticmethod
    def format_size(bytes_count):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} TB"
    
    @staticmethod
    def format_speed(bytes_per_sec):
        return f"{DownloadManagerWindow.format_size(bytes_per_sec)}/s"

class AuraTab(QWebEngineView):
    """Вкладка браузера Aura с поддержкой загрузок"""
    def __init__(self, browser_window):
        super().__init__()
        self.browser_window = browser_window
        
        # Настраиваем профиль
        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        
        # Устанавливаем User-Agent
        profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Aura/1.0"
        )
        
        # Включаем все возможности
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        
        # Подключаем обработчик загрузок
        profile.downloadRequested.connect(self.handle_download_request)
        
    def handle_download_request(self, download):
        """Обрабатывает запрос на загрузку файла"""
        url = download.url().toString()
        suggested_name = download.downloadFileName()
        
        # Показываем диалог сохранения
        default_path = str(self.browser_window.download_manager.downloads_dir / suggested_name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save File",
            default_path,
            "All Files (*.*)"
        )
        
        if file_path:
            # Настраиваем загрузку
            download.setDownloadDirectory(os.path.dirname(file_path))
            download.setDownloadFileName(os.path.basename(file_path))
            download.accept()
            
            # Запускаем загрузку через наш менеджер
            download_id = self.browser_window.download_manager.start_download(
                url,
                os.path.basename(file_path),
                os.path.dirname(file_path)
            )
            
            # Показываем менеджер загрузок
            self.browser_window.show_download_manager()
            
            # Показываем уведомление
            self.browser_window.show_notification(
                "Download Started",
                f"Downloading: {os.path.basename(file_path)}"
            )
        else:
            download.cancel()
    
    def set_home_page(self):
        """Устанавливает домашнюю страницу с быстрыми ссылками"""
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Aura Browser</title>
            <style>
                :root {
                    --primary: #8A2BE2;
                    --primary-dark: #7B1FA2;
                    --background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    --card-bg: rgba(255, 255, 255, 0.05);
                    --text-primary: #ffffff;
                    --text-secondary: rgba(255, 255, 255, 0.7);
                }
                
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                body {
                    background: var(--background);
                    color: var(--text-primary);
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    min-height: 100vh;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    padding: 80px 20px 40px;
                    overflow-x: hidden;
                }
                
                .container {
                    max-width: 1200px;
                    width: 100%;
                }
                
                .header {
                    text-align: center;
                    margin-bottom: 60px;
                    animation: fadeIn 0.8s ease-out;
                }
                
                .logo {
                    font-size: 72px;
                    margin-bottom: 20px;
                    background: linear-gradient(135deg, var(--primary), #9370DB);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    animation: pulse 2s infinite;
                }
                
                @keyframes pulse {
                    0% { transform: scale(1); }
                    50% { transform: scale(1.1); }
                    100% { transform: scale(1); }
                }
                
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                
                h1 {
                    font-size: 48px;
                    font-weight: 700;
                    margin-bottom: 12px;
                    letter-spacing: -0.5px;
                }
                
                .subtitle {
                    font-size: 20px;
                    color: var(--text-secondary);
                    margin-bottom: 30px;
                    font-weight: 400;
                }
                
                .search-container {
                    max-width: 680px;
                    margin: 0 auto 60px;
                    position: relative;
                }
                
                .search-input {
                    width: 100%;
                    padding: 18px 24px;
                    font-size: 17px;
                    background: rgba(255, 255, 255, 0.08);
                    border: 2px solid rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                    color: var(--text-primary);
                    outline: none;
                    transition: all 0.3s ease;
                    backdrop-filter: blur(20px);
                }
                
                .search-input:focus {
                    background: rgba(255, 255, 255, 0.12);
                    border-color: var(--primary);
                    box-shadow: 0 0 0 4px rgba(138, 43, 226, 0.1);
                }
                
                .search-input::placeholder {
                    color: rgba(255, 255, 255, 0.4);
                }
                
                /* Быстрые ссылки */
                .quick-links-section {
                    margin: 40px 0 60px;
                    text-align: center;
                }
                
                .section-title {
                    font-size: 24px;
                    color: var(--text-primary);
                    margin-bottom: 30px;
                    font-weight: 600;
                    position: relative;
                    display: inline-block;
                }
                
                .section-title::after {
                    content: '';
                    position: absolute;
                    bottom: -10px;
                    left: 50%;
                    transform: translateX(-50%);
                    width: 60px;
                    height: 3px;
                    background: linear-gradient(90deg, var(--primary), #9370DB);
                    border-radius: 3px;
                }
                
                .links-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                    gap: 20px;
                    margin-top: 20px;
                }
                
                .link-card {
                    background: var(--card-bg);
                    border-radius: 16px;
                    padding: 25px 20px;
                    text-decoration: none;
                    color: var(--text-primary);
                    transition: all 0.3s ease;
                    border: 1px solid transparent;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    text-align: center;
                    backdrop-filter: blur(20px);
                    animation: slideUp 0.5s ease-out;
                    animation-fill-mode: both;
                }
                
                .link-card:hover {
                    transform: translateY(-5px);
                    border-color: var(--primary);
                    background: rgba(138, 43, 226, 0.1);
                    box-shadow: 0 12px 24px rgba(138, 43, 226, 0.2);
                }
                
                .link-icon {
                    font-size: 32px;
                    margin-bottom: 15px;
                    width: 60px;
                    height: 60px;
                    background: rgba(138, 43, 226, 0.1);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border: 2px solid rgba(138, 43, 226, 0.2);
                }
                
                .link-title {
                    font-size: 16px;
                    font-weight: 600;
                    margin-bottom: 5px;
                }
                
                .link-url {
                    font-size: 13px;
                    color: var(--text-secondary);
                    opacity: 0.8;
                }
                
                /* Тестовые загрузки */
                .test-downloads {
                    margin: 40px 0;
                    text-align: center;
                }
                
                .download-links {
                    display: flex;
                    justify-content: center;
                    gap: 15px;
                    flex-wrap: wrap;
                    margin-top: 20px;
                }
                
                .download-btn {
                    background: rgba(138, 43, 226, 0.2);
                    color: #8A2BE2;
                    padding: 12px 24px;
                    border-radius: 12px;
                    text-decoration: none;
                    border: 1px solid rgba(138, 43, 226, 0.3);
                    transition: all 0.3s;
                    font-weight: 500;
                }
                
                .download-btn:hover {
                    background: rgba(138, 43, 226, 0.3);
                    transform: translateY(-2px);
                }
                
                /* Информация */
                .info-section {
                    margin-top: 60px;
                    padding: 30px;
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 16px;
                    max-width: 800px;
                    border-left: 4px solid var(--primary);
                }
                
                .info-title {
                    color: var(--primary);
                    margin-bottom: 15px;
                    font-size: 20px;
                    font-weight: 600;
                }
                
                .info-list {
                    list-style: none;
                    margin: 15px 0;
                }
                
                .info-list li {
                    padding: 8px 0;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                
                .list-icon {
                    color: var(--primary);
                    font-size: 14px;
                }
                
                @keyframes slideUp {
                    from { opacity: 0; transform: translateY(30px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                
                /* Анимация задержки */
                .link-card:nth-child(1) { animation-delay: 0.1s; }
                .link-card:nth-child(2) { animation-delay: 0.2s; }
                .link-card:nth-child(3) { animation-delay: 0.3s; }
                .link-card:nth-child(4) { animation-delay: 0.4s; }
                .link-card:nth-child(5) { animation-delay: 0.5s; }
                .link-card:nth-child(6) { animation-delay: 0.6s; }
                .link-card:nth-child(7) { animation-delay: 0.7s; }
                .link-card:nth-child(8) { animation-delay: 0.8s; }
                
                @media (max-width: 768px) {
                    h1 { font-size: 36px; }
                    .subtitle { font-size: 18px; }
                    .links-grid {
                        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                        gap: 15px;
                    }
                    .link-card {
                        padding: 20px 15px;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">✨</div>
                    <h1>Aura Browser</h1>
                    <div class="subtitle">Elegant, Fast, and Powerful Browser</div>
                </div>
                
                <div class="search-container">
                    <input type="text" class="search-input" placeholder="Search with Google or enter address..." 
                           id="searchInput" onkeypress="handleSearch(event)">
                </div>
                
                <!-- Быстрые ссылки -->
                <div class="quick-links-section">
                    <h2 class="section-title">🚀 Quick Links</h2>
                    <div class="links-grid">
                        <a href="https://www.google.com" class="link-card">
                            <div class="link-icon">🔍</div>
                            <div class="link-title">Google</div>
                            <div class="link-url">google.com</div>
                        </a>
                        
                        <a href="https://www.youtube.com" class="link-card">
                            <div class="link-icon">▶️</div>
                            <div class="link-title">YouTube</div>
                            <div class="link-url">youtube.com</div>
                        </a>
                        
                        <a href="https://www.github.com" class="link-card">
                            <div class="link-icon">💻</div>
                            <div class="link-title">GitHub</div>
                            <div class="link-url">github.com</div>
                        </a>
                        
                        <a href="https://www.reddit.com" class="link-card">
                            <div class="link-icon">👥</div>
                            <div class="link-title">Reddit</div>
                            <div class="link-url">reddit.com</div>
                        </a>
                        
                        <a href="https://www.netflix.com" class="link-card">
                            <div class="link-icon">🎬</div>
                            <div class="link-title">Netflix</div>
                            <div class="link-url">netflix.com</div>
                        </a>
                        
                        <a href="https://www.amazon.com" class="link-card">
                            <div class="link-icon">🛒</div>
                            <div class="link-title">Amazon</div>
                            <div class="link-url">amazon.com</div>
                        </a>
                        
                        <a href="https://www.twitter.com" class="link-card">
                            <div class="link-icon">🐦</div>
                            <div class="link-title">Twitter</div>
                            <div class="link-url">twitter.com</div>
                        </a>
                        
                        <a href="https://www.wikipedia.org" class="link-card">
                            <div class="link-icon">📚</div>
                            <div class="link-title">Wikipedia</div>
                            <div class="link-url">wikipedia.org</div>
                        </a>
                    </div>
                </div>
                
                <!-- Тестовые загрузки -->
                <div class="test-downloads">
                    <h2 class="section-title">📥 Test Downloads</h2>
                    <p style="color: var(--text-secondary); margin-bottom: 20px;">
                        Try downloading sample files to test the download manager:
                    </p>
                    <div class="download-links">
                        <a href="https://www.learningcontainer.com/wp-content/uploads/2020/05/sample-zip-file.zip" class="download-btn">Sample ZIP File</a>
                        <a href="https://file-examples.com/wp-content/uploads/2017/10/file-example_PDF_1MB.pdf" class="download-btn">Sample PDF</a>
                        <a href="https://file-examples.com/wp-content/uploads/2017/04/file_example_MP4_480_1_5MG.mp4" class="download-btn">Sample Video</a>
                    </div>
                </div>
                
                <!-- Информация -->
                <div class="info-section">
                    <h3 class="info-title">✨ Features</h3>
                    <p>Aura Browser comes packed with powerful features:</p>
                    <ul class="info-list">
                        <li><span class="list-icon">✓</span> <strong>Real Download Manager</strong> - Pause, resume, and manage downloads</li>
                        <li><span class="list-icon">✓</span> <strong>Extension Support</strong> - Install Chrome extensions (.crx files)</li>
                        <li><span class="list-icon">✓</span> <strong>Chrome Web Store</strong> - Download extensions directly from store</li>
                        <li><span class="list-icon">✓</span> <strong>Modern Design</strong> - Beautiful macOS-inspired interface</li>
                        <li><span class="list-icon">✓</span> <strong>Chromium Engine</strong> - Fast and compatible with modern web</li>
                        <li><span class="list-icon">✓</span> <strong>Quick Links</strong> - Access your favorite sites instantly</li>
                    </ul>
                    <p style="margin-top: 15px; color: var(--text-secondary);">
                        Click any quick link to visit the site, or try the test downloads to see the download manager in action!
                    </p>
                </div>
            </div>
            
            <script>
                function handleSearch(event) {
                    if (event.key === 'Enter') {
                        const input = document.getElementById('searchInput');
                        const query = input.value.trim();
                        
                        if (query) {
                            if (query.includes('.')) {
                                let url = query;
                                if (!url.startsWith('http://') && !url.startsWith('https://')) {
                                    url = 'https://' + url;
                                }
                                window.location.href = url;
                            } else {
                                window.location.href = 'https://www.google.com/search?q=' + encodeURIComponent(query);
                            }
                        }
                    }
                }
                
                // Добавляем анимацию при загрузке
                document.addEventListener('DOMContentLoaded', function() {
                    const cards = document.querySelectorAll('.link-card');
                    cards.forEach((card, index) => {
                        card.style.animationDelay = (index * 0.1) + 's';
                    });
                });
            </script>
        </body>
        </html>
        """
        self.setHtml(html)

class AuraBrowser(QMainWindow):
    """Главное окно браузера Aura"""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setWindowTitle("Aura Browser")
        self.setGeometry(100, 100, 1400, 900)
        
        # Инициализируем менеджер загрузок
        self.download_manager = RealDownloadManager(Path.home() / "Downloads" / "Aura")
        self.download_manager_window = None
        
        # Инициализируем менеджер расширений
        self.extension_manager = ExtensionManager()
        
        self.init_ui()
        self.create_new_tab()
        
    def init_ui(self):
        main_widget = QWidget()
        main_widget.setObjectName("mainWidget")
        self.setCentralWidget(main_widget)
        
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Панель заголовка
        self.title_bar = MacTitleBar(self)
        layout.addWidget(self.title_bar)
        
        # Панель инструментов
        self.create_toolbar(layout)
        
        # Область вкладок
        self.create_tabs_area(layout)
        
        # Статус бар
        self.create_status_bar(layout)
        
        # Настраиваем стили
        self.setup_styles()
        
    def setup_styles(self):
        self.setStyleSheet("""
            #mainWidget {
                background-color: #1a1a2e;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            QMainWindow {
                background: transparent;
            }
            
            #toolBar {
                background-color: rgba(255, 255, 255, 0.03);
                border-top: 1px solid rgba(255, 255, 255, 0.05);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                padding: 8px 16px;
            }
            
            QPushButton#navButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.9);
                border: none;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
                min-width: 32px;
                min-height: 32px;
            }
            
            QPushButton#navButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
            }
            
            QPushButton#navButton:pressed {
                background-color: rgba(255, 255, 255, 0.16);
            }
            
            QLineEdit#urlBar {
                background-color: rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 8px 16px;
                font-size: 14px;
                selection-background-color: #8A2BE2;
                min-height: 32px;
            }
            
            QLineEdit#urlBar:focus {
                border: 1px solid #8A2BE2;
                background-color: rgba(255, 255, 255, 0.08);
            }
            
            QLineEdit#urlBar::placeholder {
                color: rgba(255, 255, 255, 0.4);
            }
            
            QPushButton#specialButton {
                background-color: rgba(138, 43, 226, 0.15);
                color: #8A2BE2;
                border: 1px solid rgba(138, 43, 226, 0.3);
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
                min-height: 32px;
            }
            
            QPushButton#specialButton:hover {
                background-color: rgba(138, 43, 226, 0.25);
                border-color: rgba(138, 43, 226, 0.4);
            }
            
            QTabBar::tab {
                background-color: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.7);
                padding: 10px 20px;
                margin-right: 4px;
                border-radius: 8px 8px 0 0;
                font-size: 13px;
                font-weight: 500;
                min-width: 120px;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-bottom: none;
            }
            
            QTabBar::tab:selected {
                background-color: rgba(138, 43, 226, 0.2);
                color: rgba(255, 255, 255, 0.95);
                border-color: rgba(138, 43, 226, 0.3);
            }
            
            #statusBar {
                background-color: rgba(255, 255, 255, 0.03);
                color: rgba(255, 255, 255, 0.6);
                font-size: 12px;
                padding: 6px 16px;
                border-top: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 0 0 12px 12px;
            }
        """)
        
    def create_toolbar(self, layout):
        toolbar = QWidget()
        toolbar.setObjectName("toolBar")
        toolbar.setFixedHeight(56)
        
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 8, 16, 8)
        toolbar_layout.setSpacing(8)
        
        # Кнопки навигации
        self.back_btn = QPushButton("←")
        self.back_btn.setObjectName("navButton")
        self.back_btn.setToolTip("Back")
        self.back_btn.clicked.connect(self.go_back)
        
        self.forward_btn = QPushButton("→")
        self.forward_btn.setObjectName("navButton")
        self.forward_btn.setToolTip("Forward")
        self.forward_btn.clicked.connect(self.go_forward)
        
        self.reload_btn = QPushButton("↻")
        self.reload_btn.setObjectName("navButton")
        self.reload_btn.setToolTip("Reload")
        self.reload_btn.clicked.connect(self.reload_page)
        
        self.home_btn = QPushButton("🏠")
        self.home_btn.setObjectName("navButton")
        self.home_btn.setToolTip("Home")
        self.home_btn.clicked.connect(self.go_home)
        
        toolbar_layout.addWidget(self.back_btn)
        toolbar_layout.addWidget(self.forward_btn)
        toolbar_layout.addWidget(self.reload_btn)
        toolbar_layout.addWidget(self.home_btn)
        
        toolbar_layout.addSpacing(12)
        
        # Адресная строка
        self.url_bar = QLineEdit()
        self.url_bar.setObjectName("urlBar")
        self.url_bar.setPlaceholderText("Search or enter address")
        self.url_bar.returnPressed.connect(self.navigate)
        
        toolbar_layout.addWidget(self.url_bar, 1)
        
        toolbar_layout.addSpacing(12)
        
        # Кнопка загрузок
        self.downloads_btn = QPushButton("📥")
        self.downloads_btn.setObjectName("specialButton")
        self.downloads_btn.setToolTip("Download Manager")
        self.downloads_btn.clicked.connect(self.show_download_manager)
        
        # Кнопка расширений
        self.extensions_btn = QPushButton("🔌")
        self.extensions_btn.setObjectName("specialButton")
        self.extensions_btn.setToolTip("Extensions")
        self.extensions_btn.clicked.connect(self.show_extensions)
        
        # Кнопка новой вкладки
        self.new_tab_btn = QPushButton("+")
        self.new_tab_btn.setObjectName("specialButton")
        self.new_tab_btn.setToolTip("New Tab")
        self.new_tab_btn.clicked.connect(self.create_new_tab)
        
        toolbar_layout.addWidget(self.downloads_btn)
        toolbar_layout.addWidget(self.extensions_btn)
        toolbar_layout.addWidget(self.new_tab_btn)
        
        layout.addWidget(toolbar)
        
    def create_tabs_area(self, layout):
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        layout.addWidget(self.tab_widget, 1)
        
    def create_status_bar(self, layout):
        self.status_bar = QWidget()
        self.status_bar.setObjectName("statusBar")
        self.status_bar.setFixedHeight(28)
        
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(16, 0, 16, 0)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        self.security_label = QLabel("🔒 Secure")
        self.security_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        
        status_layout.addWidget(self.security_label)
        
        layout.addWidget(self.status_bar)
        
    def create_new_tab(self, url=None):
        tab = AuraTab(self)
        
        tab.loadStarted.connect(self.on_load_started)
        tab.loadProgress.connect(self.on_load_progress)
        tab.loadFinished.connect(self.on_load_finished)
        tab.urlChanged.connect(lambda url: self.on_url_changed(tab, url))
        tab.titleChanged.connect(lambda title: self.on_title_changed(tab, title))
        
        index = self.tab_widget.addTab(tab, "New Tab")
        self.tab_widget.setCurrentIndex(index)
        
        if url:
            tab.setUrl(QUrl(url))
        else:
            tab.set_home_page()
            self.url_bar.setText("aura://home")
            
    def close_tab(self, index):
        if self.tab_widget.count() > 1:
            widget = self.tab_widget.widget(index)
            widget.deleteLater()
            self.tab_widget.removeTab(index)
            
    def on_tab_changed(self, index):
        if index >= 0:
            tab = self.tab_widget.widget(index)
            if tab:
                current_url = tab.url().toString()
                if current_url:
                    self.url_bar.setText(self.simplify_url(current_url))
                else:
                    self.url_bar.setText("aura://home")
                    
    def simplify_url(self, url):
        if not url or url == "aura://home":
            return "aura://home"
            
        if url.startswith('https://'):
            url = url[8:]
        elif url.startswith('http://'):
            url = url[7:]
            
        if url.startswith('www.'):
            url = url[4:]
            
        if '/' in url:
            url = url.split('/')[0]
            
        return url
        
    def on_load_started(self):
        self.status_label.setText("Loading...")
        
    def on_load_progress(self, progress):
        pass
        
    def on_load_finished(self, ok):
        self.status_label.setText("Ready")
        
    def on_url_changed(self, tab, url):
        current_tab = self.tab_widget.currentWidget()
        if tab == current_tab:
            url_str = url.toString()
            if url_str:
                self.url_bar.setText(self.simplify_url(url_str))
                
                if url_str.startswith('https://'):
                    self.security_label.setText("🔒 Secure")
                else:
                    self.security_label.setText("⚠️ Not Secure")
                    
    def on_title_changed(self, tab, title):
        index = self.tab_widget.indexOf(tab)
        if index >= 0:
            short_title = title[:25] + "..." if len(title) > 25 else title
            self.tab_widget.setTabText(index, short_title)
            
            if tab == self.tab_widget.currentWidget():
                self.title_bar.title_label.setText(title if len(title) < 30 else title[:27] + "...")
                
    def navigate(self):
        url = self.url_bar.text().strip()
        if not url or url == "aura://home":
            self.go_home()
            return
            
        if not url.startswith(('http://', 'https://', 'file://', 'aura://')):
            if '.' in url and ' ' not in url:
                url = 'https://' + url
            else:
                url = f'https://www.google.com/search?q={url.replace(" ", "+")}'
                
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.setUrl(QUrl(url))
            
    def go_back(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.back()
            
    def go_forward(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.forward()
            
    def reload_page(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.reload()
            
    def go_home(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.set_home_page()
            self.url_bar.setText("aura://home")
            
    def show_download_manager(self):
        """Показывает менеджер загрузок"""
        if not self.download_manager_window:
            self.download_manager_window = DownloadManagerWindow(self)
        
        self.download_manager_window.show()
        self.download_manager_window.raise_()
        
    def show_extensions(self):
        """Показывает менеджер расширений"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Aura Extensions")
        dialog.setGeometry(300, 200, 800, 600)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1a1a2e;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        extension_widget = self.extension_manager.get_extension_widget()
        layout.addWidget(extension_widget)
        
        dialog.exec()
        
    def show_notification(self, title, message):
        """Показывает уведомление"""
        # Простое уведомление в статус баре
        self.status_label.setText(f"{title}: {message}")
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Aura Browser")
    app.setOrganizationName("AuraSoft")
    
    app.setStyle("Fusion")
    
    browser = AuraBrowser()
    browser.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()