import sys
import struct
import asyncio
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget,
                             QVBoxLayout, QHBoxLayout, QSlider, QCheckBox,
                             QLabel, QPushButton, QComboBox, QSpinBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import pyqtgraph as pg
import websockets

# ------------------------------------------------------------------
# Глобальные параметры (изменяемые через GUI)
# ------------------------------------------------------------------
BUF_SIZE = 1024
SAMPLING_RATE = 1 / 0.000313   # ~3194.88 Гц

PACKET_FORMAT = None
PACKET_STRUCT = None
PACKET_SIZE = None
FREQ_AXIS = None

def update_packet_format():
    global PACKET_FORMAT, PACKET_STRUCT, PACKET_SIZE, FREQ_AXIS
    PACKET_FORMAT = f'If{BUF_SIZE}f{BUF_SIZE // 2}f'
    PACKET_STRUCT = struct.Struct(PACKET_FORMAT)
    PACKET_SIZE = PACKET_STRUCT.size
    FREQ_AXIS = np.linspace(0, SAMPLING_RATE / 2, BUF_SIZE // 2)

update_packet_format()


# ------------------------------------------------------------------
# Поток для WebSocket-сервера (asyncio)
# ------------------------------------------------------------------
class WebSocketServerThread(QThread):
    data_received = pyqtSignal(int, float, np.ndarray, np.ndarray)
    status_updated = pyqtSignal(str)

    def __init__(self, host="0.0.0.0", port=8765):
        super().__init__()
        self.host = host
        self.port = port
        self.loop = None

    async def handler(self, websocket):
        self.status_updated.emit("Клиент подключился")
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    if len(message) != PACKET_SIZE:
                        print(f"Неверный размер пакета: {len(message)} ожидалось {PACKET_SIZE}")
                        continue
                    unpacked = PACKET_STRUCT.unpack(message)
                    sensor_id = unpacked[0]
                    if sensor_id not in (1, 2):
                        print(f"Неизвестный sensor_id: {sensor_id}")
                        continue
                    rms = unpacked[1]
                    accel = np.array(unpacked[2:2 + BUF_SIZE], dtype=np.float32)
                    spectrum = np.array(unpacked[2 + BUF_SIZE:], dtype=np.float32)
                    self.data_received.emit(sensor_id, rms, accel, spectrum)
                else:
                    print("Текстовое сообщение проигнорировано")
        except websockets.exceptions.ConnectionClosed:
            self.status_updated.emit("Клиент отключился")
        except Exception as e:
            self.status_updated.emit(f"Ошибка: {e}")

    async def start_server(self):
        self.status_updated.emit(f"Сервер запущен на ws://{self.host}:{self.port}")
        async with websockets.serve(self.handler, self.host, self.port):
            await asyncio.Future()

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.start_server())
        except Exception as e:
            self.status_updated.emit(f"Ошибка сервера: {e}")

    def stop(self):
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.quit()
        self.wait()


# ------------------------------------------------------------------
# Вкладка для одного датчика
# ------------------------------------------------------------------
class SensorTab(QWidget):
    def __init__(self, sensor_id, parent=None):
        super().__init__(parent)
        self.sensor_id = sensor_id
        self.accel_data = np.zeros(BUF_SIZE)
        self.spectrum_data = np.zeros(BUF_SIZE // 2)
        self.rms = 0.0

        pg.setConfigOptions(antialias=True)

        # График ускорения
        self.graph_accel = pg.PlotWidget(title=f'Датчик {sensor_id} – Ускорение')
        self.graph_accel.setLabel('left', 'мм/с²')
        self.graph_accel.setLabel('bottom', 'Отсчёт')
        self.graph_accel.showGrid(x=True, y=True, alpha=0.5)
        self.graph_accel.getAxis('left').enableAutoSIPrefix(False)
        self.curve_accel = self.graph_accel.plot(pen='c')

        # График спектра
        self.graph_spec = pg.PlotWidget(title=f'Датчик {sensor_id} – Спектр скорости')
        self.graph_spec.setLabel('left', 'мм/с')
        self.graph_spec.setLabel('bottom', 'Частота (Гц)')
        self.graph_spec.showGrid(x=True, y=True, alpha=0.5)
        self.graph_spec.setXRange(0, 1000)
        self.graph_spec.getAxis('left').enableAutoSIPrefix(False)
        self.curve_spec = self.graph_spec.plot(pen='lime')

        # Метки RMS и пика спектра
        self.rms_label = QLabel("RMS: -- мм/с")
        self.rms_label.setStyleSheet("font-weight: bold; color: white; background-color: black; padding: 4px;")
        self.peak_label = QLabel("Пик: -- мм/с @ -- Гц")
        self.peak_label.setStyleSheet("font-weight: bold; color: white; background-color: #333; padding: 4px;")

        # Ползунки масштаба
        self.accel_scale_slider = QSlider(Qt.Horizontal)
        self.accel_scale_slider.setRange(10, 500)
        self.accel_scale_slider.setValue(100)
        self.accel_scale_slider.valueChanged.connect(self.update_accel_scale)

        self.spec_scale_slider = QSlider(Qt.Horizontal)
        self.spec_scale_slider.setRange(10, 500)
        self.spec_scale_slider.setValue(100)
        self.spec_scale_slider.valueChanged.connect(self.update_spec_scale)

        # Чекбоксы скрытия
        self.hide_accel_cb = QCheckBox("Скрыть график ускорения")
        self.hide_accel_cb.toggled.connect(self.toggle_accel_visibility)
        self.hide_spec_cb = QCheckBox("Скрыть график спектра")
        self.hide_spec_cb.toggled.connect(self.toggle_spec_visibility)

        # Компоновка
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("Масштаб ускорения:"))
        control_layout.addWidget(self.accel_scale_slider)
        control_layout.addWidget(QLabel("Масштаб спектра:"))
        control_layout.addWidget(self.spec_scale_slider)
        control_layout.addWidget(self.hide_accel_cb)
        control_layout.addWidget(self.hide_spec_cb)
        control_layout.addStretch()
        control_layout.addWidget(self.rms_label)
        control_layout.addWidget(self.peak_label)

        layout = QVBoxLayout()
        layout.addWidget(self.graph_accel, stretch=2)
        layout.addWidget(self.graph_spec, stretch=1)
        layout.addLayout(control_layout)
        self.setLayout(layout)

        self.max_abs_accel = None
        self.max_spec = None

    def update_data(self, rms, accel, spectrum):
        # Проверка на корректность данных
        if not np.all(np.isfinite(accel)) or not np.all(np.isfinite(spectrum)):
            print(f"Warning: sensor {self.sensor_id} data contains NaN/Inf")
            return

        self.rms = rms
        self.accel_data = accel
        self.spectrum_data = spectrum

        # Максимумы для масштабирования
        current_max_accel = max(np.max(np.abs(accel)), 1e-9)
        current_max_spec = max(np.max(spectrum[1:]), 1e-9)

        if self.max_abs_accel is None:
            self.max_abs_accel = current_max_accel
            self.max_spec = current_max_spec
            self.update_accel_scale()
            self.update_spec_scale()
        else:
            self.max_abs_accel = current_max_accel
            self.max_spec = current_max_spec

        # Обновляем кривые
        self.curve_accel.setData(accel)
        self.curve_spec.setData(FREQ_AXIS[1:], spectrum[1:])

        # Поиск максимума в спектре (исключая DC)
        peak_idx = np.argmax(spectrum[1:]) + 1  # +1, т.к. начинали с 1
        peak_value = spectrum[peak_idx]
        peak_freq = FREQ_AXIS[peak_idx]

        self.rms_label.setText(f"RMS: {rms:.3f} мм/с")
        self.peak_label.setText(f"Пик: {peak_value:.2f} мм/с @ {peak_freq:.1f} Гц")

    def update_accel_scale(self):
        if self.max_abs_accel is None or not np.isfinite(self.max_abs_accel):
            return
        factor = self.accel_scale_slider.value() / 100.0
        limit = min(self.max_abs_accel * factor, 1e9)
        self.graph_accel.setYRange(-limit, limit)

    def update_spec_scale(self):
        if self.max_spec is None or not np.isfinite(self.max_spec):
            return
        factor = self.spec_scale_slider.value() / 100.0
        limit = min(self.max_spec * factor, 1e9)
        self.graph_spec.setYRange(0, limit)

    def toggle_accel_visibility(self, checked):
        self.graph_accel.setVisible(not checked)

    def toggle_spec_visibility(self, checked):
        self.graph_spec.setVisible(not checked)

    def resize_arrays(self):
        self.accel_data = np.zeros(BUF_SIZE)
        self.spectrum_data = np.zeros(BUF_SIZE // 2)
        self.max_abs_accel = None
        self.max_spec = None
        self.curve_accel.setData([])
        self.curve_spec.setData([])
        self.rms_label.setText("RMS: -- мм/с")
        self.peak_label.setText("Пик: -- мм/с @ -- Гц")

# ------------------------------------------------------------------
# Главное окно
# ------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Вибромонитор (сервер)")
        self.resize(1100, 700)

        self.tab_widget = QTabWidget()
        self.tab1 = SensorTab(1)
        self.tab2 = SensorTab(2)
        self.tab_widget.addTab(self.tab1, "Датчик 1")
        self.tab_widget.addTab(self.tab2, "Датчик 2")

        self.status_label = QLabel("Статус: Сервер остановлен")
        self.status_label.setStyleSheet("padding: 4px; background-color: #eee;")

        self.start_server_btn = QPushButton("Запустить сервер")
        self.start_server_btn.clicked.connect(self.start_server)
        self.stop_server_btn = QPushButton("Остановить сервер")
        self.stop_server_btn.clicked.connect(self.stop_server)
        self.stop_server_btn.setEnabled(False)

        # Элементы для ручного ввода параметров
        self.buf_size_combo = QComboBox()
        self.buf_size_combo.addItems(["512", "1024", "2048", "4096"])
        self.buf_size_combo.setCurrentText(str(BUF_SIZE))

        self.fs_spin = QSpinBox()
        self.fs_spin.setRange(100, 100000)
        self.fs_spin.setSingleStep(100)
        self.fs_spin.setValue(int(SAMPLING_RATE))
        self.fs_spin.setSuffix(" Гц")

        self.apply_params_btn = QPushButton("Применить параметры")
        self.apply_params_btn.clicked.connect(self.apply_parameters)

        # Верхняя панель
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("BUF_SIZE:"))
        top_layout.addWidget(self.buf_size_combo)
        top_layout.addWidget(QLabel("Частота дискр.:"))
        top_layout.addWidget(self.fs_spin)
        top_layout.addWidget(self.apply_params_btn)
        top_layout.addStretch()
        top_layout.addWidget(self.start_server_btn)
        top_layout.addWidget(self.stop_server_btn)

        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.tab_widget)
        main_layout.addWidget(self.status_label)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.server_thread = None

    def start_server(self):
        if self.server_thread is None or not self.server_thread.isRunning():
            self.server_thread = WebSocketServerThread("0.0.0.0", 8765)
            self.server_thread.data_received.connect(self.handle_data)
            self.server_thread.status_updated.connect(self.status_label.setText)
            self.server_thread.start()
            self.start_server_btn.setEnabled(False)
            self.stop_server_btn.setEnabled(True)

    def stop_server(self):
        if self.server_thread and self.server_thread.isRunning():
            self.server_thread.stop()
            self.server_thread = None
            self.start_server_btn.setEnabled(True)
            self.stop_server_btn.setEnabled(False)
            self.status_label.setText("Статус: Сервер остановлен")

    def handle_data(self, sensor_id, rms, accel, spectrum):
        if sensor_id == 1:
            self.tab1.update_data(rms, accel, spectrum)
        elif sensor_id == 2:
            self.tab2.update_data(rms, accel, spectrum)

    def apply_parameters(self):
        global BUF_SIZE, SAMPLING_RATE
        new_buf = int(self.buf_size_combo.currentText())
        new_fs = self.fs_spin.value()

        if new_buf != BUF_SIZE or new_fs != SAMPLING_RATE:
            BUF_SIZE = new_buf
            SAMPLING_RATE = new_fs
            update_packet_format()
            self.tab1.resize_arrays()
            self.tab2.resize_arrays()
            self.tab1.graph_spec.setXRange(0, SAMPLING_RATE / 2)
            self.tab2.graph_spec.setXRange(0, SAMPLING_RATE / 2)
            self.status_label.setText(f"Параметры обновлены: BUF_SIZE={BUF_SIZE}, Fs={SAMPLING_RATE}")
        else:
            self.status_label.setText("Параметры не изменились")

    def closeEvent(self, event):
        self.stop_server()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())