import base64
import os
from datetime import datetime
from collections import deque

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from jnius import autoclass, PythonJavaClass, java_method

from ava_games import AVAILABLE_GAMES, game_load_command

AVA_NAME = "AVA"
SERVICE_UUID = "7b7a0001-6a76-4156-9a76-415641000001"
COMMAND_UUID = "7b7a0002-6a76-4156-9a76-415641000001"
EVENT_UUID = "7b7a0003-6a76-4156-9a76-415641000001"
STATE_UUID = "7b7a0004-6a76-4156-9a76-415641000001"
DATA_UUID = "7b7a0005-6a76-4156-9a76-415641000001"
CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"

GATT_SUCCESS = 0
STATE_DISCONNECTED = 0
STATE_CONNECTED = 2
WRITE_TYPE_NO_RESPONSE = 1
WRITE_TYPE_DEFAULT = 2
TIME_REQUEST = "TIME_REQUEST"
TIME_RESPONSE = "TIME_RESPONSE"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "fonts", "Orbitron Bold.ttf")
if os.path.exists(FONT_PATH):
    LabelBase.register(name="Orbitron", fn_regular=FONT_PATH)
FONT_NAME = "Orbitron" if os.path.exists(FONT_PATH) else "Roboto"
BACKGROUND_PATH = os.path.join(BASE_DIR, "IMG_20260902_023056_844.jpg")


class AndroidBLE:
    def __init__(self, logger):
        self.logger = logger
        self.context = None
        self.adapter = None
        self.sdk = 30
        self.scan_callback = None
        self.scanning = False
        self.found_device = None
        self.found_address = None
        self.found_name = None
        self.gatt = None
        self.gatt_callback = None
        self.service = None
        self.command_characteristic = None
        self.event_characteristic = None
        self.state_characteristic = None
        self.data_characteristic = None
        self.event_descriptor = None
        self.connected = False
        self.connecting = False
        self.ready = False
        self.notifications_enabled = False
        self.command_queue = deque()
        self.data_queue = deque()
        self.command_write_busy = False
        self.data_write_busy = False
        self.descriptor_write_busy = False
        self._initialize_android()
        Clock.schedule_interval(self._poll_java_events, 0.05)

    def log(self, message):
        try:
            Clock.schedule_once(lambda *_: self.logger(str(message)))
        except Exception:
            pass

    def _initialize_android(self):
        try:
            Activity = autoclass("org.kivy.android.PythonActivity")
            Version = autoclass("android.os.Build$VERSION")
            BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
            self.context = Activity.mActivity
            self.sdk = int(Version.SDK_INT)
            self.adapter = BluetoothAdapter.getDefaultAdapter()
            if self.adapter is None:
                self.log("ERROR: BLUETOOTH ADAPTER UNAVAILABLE.")
                return
            self.log("ANDROID NATIVE BLE INITIALIZED.")
            self.log(f"ANDROID API LEVEL: {self.sdk}")
        except Exception as exc:
            self.log(f"ANDROID INIT ERROR: {exc}")

    def android_sdk(self):
        return self.sdk

    def _create_scan_callback(self):
        outer = self

        class ScanCallback(PythonJavaClass):
            __javainterfaces__ = ["android/bluetooth/BluetoothAdapter$LeScanCallback"]

            @java_method("(Landroid/bluetooth/BluetoothDevice;I[B)V")
            def onLeScan(self, device, rssi, scanRecord):
                try:
                    if device is None:
                        return
                    try:
                        name = device.getName()
                    except Exception:
                        name = None
                    if name is None or AVA_NAME not in str(name).upper():
                        return
                    try:
                        address = str(device.getAddress())
                    except Exception:
                        address = "UNKNOWN"
                    outer.found_device = device
                    outer.found_name = str(name)
                    outer.found_address = address
                    outer.scanning = False
                    outer.log(f"AVA FOUND | name={name} | address={address} | rssi={rssi}")
                    try:
                        outer.adapter.stopLeScan(outer.scan_callback)
                    except Exception:
                        pass
                except Exception as exc:
                    outer.log(f"SCAN CALLBACK ERROR: {exc}")

        self.scan_callback = ScanCallback()

    def scan(self):
        if self.adapter is None:
            self.log("SCAN ERROR: BLUETOOTH UNAVAILABLE.")
            return
        if self.scanning:
            self.log("SCAN: ALREADY SCANNING.")
            return
        try:
            if not self.adapter.isEnabled():
                self.log("SCAN ERROR: BLUETOOTH IS OFF.")
                return
        except Exception as exc:
            self.log(f"SCAN ERROR: BLUETOOTH STATE CHECK FAILED: {exc}")
            return
        if self.gatt is not None:
            self._close_gatt()
        self.found_device = None
        self.found_address = None
        self.found_name = None
        self.connected = False
        self.connecting = False
        self.ready = False
        self.notifications_enabled = False
        self.command_queue.clear()
        self.data_queue.clear()
        self.command_write_busy = False
        self.data_write_busy = False
        self.descriptor_write_busy = False
        self._create_scan_callback()
        try:
            self.log("SCANNING FOR AVA...")
            result = self.adapter.startLeScan(self.scan_callback)
            if not result:
                self.log("SCAN ERROR: startLeScan() FAILED.")
                return
            self.scanning = True
            Clock.schedule_once(self.stop_scan, 10)
        except Exception as exc:
            self.scanning = False
            self.log(f"SCAN ERROR: {exc}")

    def stop_scan(self, *_):
        if not self.scanning:
            return
        try:
            self.adapter.stopLeScan(self.scan_callback)
        except Exception:
            pass
        self.scanning = False
        if self.found_device is None:
            self.log("SCAN FINISHED: AVA NOT FOUND.")
        else:
            self.log(f"SCAN FINISHED: AVA FOUND | {self.found_address}")

    def has_ava(self):
        return self.found_device is not None

    def _create_java_gatt_callback(self):
        try:
            Callback = autoclass("org.ava.avapet.AvaGattCallback")
            self.gatt_callback = Callback()
            self.log("JAVA GATT CALLBACK BRIDGE INITIALIZED.")
            return True
        except Exception as exc:
            self.log(f"JAVA GATT CALLBACK INIT ERROR: {exc}")
            return False

    def connect(self):
        if self.found_device is None:
            self.log("CONNECT ERROR: SCAN FOR AVA FIRST.")
            return False
        if self.connected:
            self.log("CONNECT: AVA ALREADY CONNECTED.")
            return True
        if self.connecting:
            self.log("CONNECT: ALREADY IN PROGRESS.")
            return False
        if self.gatt is not None:
            self._close_gatt()
        if not self._create_java_gatt_callback():
            return False
        try:
            BluetoothDevice = autoclass("android.bluetooth.BluetoothDevice")
            self.connecting = True
            self.ready = False
            self.notifications_enabled = False
            self.command_write_busy = False
            self.data_write_busy = False
            self.descriptor_write_busy = False
            self.log(f"GATT CONNECTION REQUESTED | {self.found_name or AVA_NAME} | {self.found_address}")
            self.gatt = self.found_device.connectGatt(
                self.context,
                False,
                self.gatt_callback,
                BluetoothDevice.TRANSPORT_LE,
            )
            if self.gatt is None:
                self.connecting = False
                self.log("CONNECT ERROR: connectGatt() RETURNED NULL.")
                return False
            self.log("GATT CONNECT REQUEST ACCEPTED | TRANSPORT_LE.")
            return True
        except Exception as exc:
            self.connecting = False
            self.log(f"CONNECT ERROR: {exc}")
            return False

    def _poll_java_events(self, *_):
        if self.gatt_callback is None:
            return
        try:
            for event in self.gatt_callback.drainEvents():
                self._handle_java_event(str(event))
        except Exception as exc:
            self.log(f"JAVA GATT EVENT POLL ERROR: {exc}")

    def _handle_java_event(self, event):
        parts = event.split("|", 2)
        kind = parts[0] if parts else ""

        if kind == "RETRY":
            status = int(parts[1]) if len(parts) > 1 else -1
            attempt = int(parts[2]) if len(parts) > 2 else -1
            self.connecting = True
            self.connected = False
            self.ready = False
            self.notifications_enabled = False
            self.log(f"GATT RETRY REQUESTED | status={status} | attempt={attempt}")
            return

        if kind == "STATE":
            status = int(parts[1]) if len(parts) > 1 else -1
            state = int(parts[2]) if len(parts) > 2 else -1
            self.log(f"GATT STATE CHANGE | status={status} | state={state}")
            if state == STATE_CONNECTED:
                try:
                    self.gatt = self.gatt_callback.getGatt()
                except Exception:
                    pass
                self.connected = True
                self.connecting = False
                self.ready = False
                self.notifications_enabled = False
                self.log("GATT CONNECTED")
                try:
                    if self.gatt.discoverServices():
                        self.log("SERVICE DISCOVERY STARTED.")
                    else:
                        self.log("SERVICE DISCOVERY REQUEST FAILED.")
                except Exception as exc:
                    self.log(f"SERVICE DISCOVERY ERROR: {exc}")
            elif state == STATE_DISCONNECTED:
                self.connected = False
                self.connecting = False
                self.ready = False
                self.notifications_enabled = False
                self.command_write_busy = False
                self.data_write_busy = False
                self.descriptor_write_busy = False
                self.service = None
                self.command_characteristic = None
                self.event_characteristic = None
                self.state_characteristic = None
                self.data_characteristic = None
                self.event_descriptor = None
                self.command_queue.clear()
                self.data_queue.clear()
                self.log(f"GATT DISCONNECTED | status={status}")
                if status != GATT_SUCCESS:
                    self.log(f"GATT DISCONNECT ERROR CODE: {status}")
                try:
                    if self.gatt is not None:
                        self.gatt.close()
                except Exception:
                    pass
                self.gatt = None
            return

        if kind == "SERVICES":
            status = int(parts[1]) if len(parts) > 1 else -1
            self.log(f"SERVICE DISCOVERY RESULT | status={status}")
            if status != GATT_SUCCESS or self.gatt is None:
                self.log("SERVICE DISCOVERY FAILED.")
                return
            try:
                UUID = autoclass("java.util.UUID")
                self.service = self.gatt.getService(UUID.fromString(SERVICE_UUID))
                if self.service is None:
                    self.log("ERROR: AVA SERVICE NOT FOUND.")
                    return
                self.log("AVA SERVICE FOUND.")
                self.command_characteristic = self.service.getCharacteristic(UUID.fromString(COMMAND_UUID))
                self.event_characteristic = self.service.getCharacteristic(UUID.fromString(EVENT_UUID))
                self.state_characteristic = self.service.getCharacteristic(UUID.fromString(STATE_UUID))
                self.data_characteristic = self.service.getCharacteristic(UUID.fromString(DATA_UUID))
                if self.command_characteristic is None:
                    self.log("ERROR: COMMAND CHARACTERISTIC NOT FOUND.")
                    return
                if self.event_characteristic is None:
                    self.log("ERROR: EVENT CHARACTERISTIC NOT FOUND.")
                    return
                if self.data_characteristic is None:
                    self.log("ERROR: DATA CHARACTERISTIC NOT FOUND.")
                    return
                self.log("COMMAND CHARACTERISTIC FOUND.")
                self.log("EVENT CHARACTERISTIC FOUND.")
                if self.state_characteristic is not None:
                    self.log("STATE CHARACTERISTIC FOUND.")
                self.log("DATA CHARACTERISTIC FOUND.")
                self.enable_notifications()
            except Exception as exc:
                self.log(f"SERVICE DISCOVERY CALLBACK ERROR: {exc}")
            return

        if kind == "CHANGED":
            uuid = parts[1] if len(parts) > 1 else "UNKNOWN"
            encoded = parts[2] if len(parts) > 2 else ""
            try:
                text = base64.b64decode(encoded).decode("utf-8", errors="replace") if encoded else ""
            except Exception:
                text = "<binary>"
            self.log(f"EVENT <- {uuid} | {text}")
            if uuid.lower() == EVENT_UUID.lower() and text.strip().upper() == TIME_REQUEST:
                self.log("[CLOCK] AVA REQUESTED CURRENT TIME.")
                Clock.schedule_once(lambda *_: self.send_current_time_to_ava(), 0.05)
            return

        if kind == "WRITE":
            uuid = parts[1] if len(parts) > 1 else "UNKNOWN"
            status = int(parts[2]) if len(parts) > 2 else -1
            if uuid.lower() == COMMAND_UUID.lower():
                self.command_write_busy = False
                self.log(f"COMMAND WRITE OK | {uuid}" if status == GATT_SUCCESS else f"COMMAND WRITE FAILED | {uuid} | status={status}")
                self._process_command_queue()
            elif uuid.lower() == DATA_UUID.lower():
                self.data_write_busy = False
                self.log(f"DATA WRITE OK | {uuid}" if status == GATT_SUCCESS else f"DATA WRITE FAILED | {uuid} | status={status}")
                self._process_data_queue()
            else:
                self.log(f"WRITE EVENT UNKNOWN UUID | {uuid} | status={status}")
            return

        if kind == "DESCRIPTOR":
            uuid = parts[1] if len(parts) > 1 else "UNKNOWN"
            status = int(parts[2]) if len(parts) > 2 else -1
            self.descriptor_write_busy = False
            if status == GATT_SUCCESS:
                self.notifications_enabled = True
                self.ready = True
                self.log(f"CCCD WRITE OK | {uuid}")
                self.log("EVENT NOTIFICATIONS ENABLED.")
                self.log("AVA READY.")
                self._process_command_queue()
                self._process_data_queue()
            else:
                self.notifications_enabled = False
                self.ready = False
                self.log(f"CCCD WRITE FAILED | {uuid} | status={status}")
            return

        self.log(f"JAVA GATT EVENT UNKNOWN: {event}")

    def send_current_time_to_ava(self):
        if not self.connected:
            self.log("[CLOCK] CANNOT SEND TIME: AVA NOT CONNECTED.")
            return False
        if not self.ready:
            self.log("[CLOCK] CANNOT SEND TIME: AVA GATT NOT READY.")
            return False
        try:
            now = datetime.now()
            time_text = now.strftime("%H:%M:%S")
            date_text = now.strftime("%Y-%m-%d")
            command = f"{TIME_RESPONSE}|{time_text}|{date_text}"
            self.log(f"[CLOCK] PHONE TIME: {time_text}")
            self.log(f"[CLOCK] PHONE DATE: {date_text}")
            self.log(f"[CLOCK] DATA RESPONSE -> {command}")
            return self.write_data(command)
        except Exception as exc:
            self.log(f"[CLOCK] TIME RESPONSE ERROR: {exc}")
            return False

    def enable_notifications(self):
        if self.gatt is None or self.event_characteristic is None:
            self.log("NOTIFY ERROR: GATT/EVENT UNAVAILABLE.")
            return False
        try:
            if not self.gatt.setCharacteristicNotification(self.event_characteristic, True):
                self.log("NOTIFY ERROR: setCharacteristicNotification() FAILED.")
                return False
            UUID = autoclass("java.util.UUID")
            Descriptor = autoclass("android.bluetooth.BluetoothGattDescriptor")
            descriptor = self.event_characteristic.getDescriptor(UUID.fromString(CCCD_UUID))
            if descriptor is None:
                self.log("NOTIFY ERROR: CCCD NOT FOUND.")
                return False
            self.event_descriptor = descriptor
            descriptor.setValue(Descriptor.ENABLE_NOTIFICATION_VALUE)
            self.descriptor_write_busy = True
            if not self.gatt.writeDescriptor(descriptor):
                self.descriptor_write_busy = False
                self.log("NOTIFY ERROR: writeDescriptor() FAILED.")
                return False
            self.log("CCCD WRITE REQUESTED.")
            return True
        except Exception as exc:
            self.descriptor_write_busy = False
            self.log(f"NOTIFICATION ERROR: {exc}")
            return False

    def write_command(self, command):
        if not self.connected:
            self.log("COMMAND ERROR: AVA NOT GATT CONNECTED.")
            return False
        if not self.ready:
            self.log("COMMAND ERROR: AVA GATT NOT READY.")
            return False
        command = str(command).strip()
        if not command:
            return False
        self.command_queue.append(command)
        self._process_command_queue()
        return True

    def _process_command_queue(self):
        if self.command_write_busy or not self.connected or not self.ready:
            return
        if self.gatt is None or self.command_characteristic is None or not self.command_queue:
            return
        command = self.command_queue.popleft()
        try:
            self.command_characteristic.setValue(command.encode("utf-8"))
            Characteristic = autoclass("android.bluetooth.BluetoothGattCharacteristic")
            props = int(self.command_characteristic.getProperties())
            if props & int(Characteristic.PROPERTY_WRITE_NO_RESPONSE):
                self.command_characteristic.setWriteType(WRITE_TYPE_NO_RESPONSE)
                name = "WRITE_NO_RESPONSE"
            else:
                self.command_characteristic.setWriteType(WRITE_TYPE_DEFAULT)
                name = "WRITE"
            self.command_write_busy = True
            if not self.gatt.writeCharacteristic(self.command_characteristic):
                self.command_write_busy = False
                self.log(f"COMMAND WRITE REQUEST FAILED | {command} | {name}")
                Clock.schedule_once(lambda *_: self._process_command_queue(), 0.05)
                return
            self.log(f"COMMAND -> {command} | {name}")
            if name == "WRITE_NO_RESPONSE":
                Clock.schedule_once(self._release_no_response_command, 0.08)
        except Exception as exc:
            self.command_write_busy = False
            self.log(f"COMMAND WRITE ERROR: {exc}")
            Clock.schedule_once(lambda *_: self._process_command_queue(), 0.05)

    def _release_no_response_command(self, *_):
        if self.command_write_busy:
            self.command_write_busy = False
            self._process_command_queue()

    def write_data(self, data):
        if not self.connected:
            self.log("DATA ERROR: AVA NOT GATT CONNECTED.")
            return False
        if not self.ready:
            self.log("DATA ERROR: AVA GATT NOT READY.")
            return False
        data = str(data).strip()
        if not data:
            return False
        if self.data_characteristic is None:
            self.log("DATA ERROR: DATA CHARACTERISTIC UNAVAILABLE.")
            return False
        self.data_queue.append(data)
        self._process_data_queue()
        return True

    def _process_data_queue(self):
        if self.data_write_busy or not self.connected or not self.ready:
            return
        if self.gatt is None or self.data_characteristic is None or not self.data_queue:
            return
        data = self.data_queue.popleft()
        try:
            self.data_characteristic.setValue(data.encode("utf-8"))
            Characteristic = autoclass("android.bluetooth.BluetoothGattCharacteristic")
            props = int(self.data_characteristic.getProperties())
            if props & int(Characteristic.PROPERTY_WRITE_NO_RESPONSE):
                self.data_characteristic.setWriteType(WRITE_TYPE_NO_RESPONSE)
                name = "WRITE_NO_RESPONSE"
            else:
                self.data_characteristic.setWriteType(WRITE_TYPE_DEFAULT)
                name = "WRITE"
            self.data_write_busy = True
            if not self.gatt.writeCharacteristic(self.data_characteristic):
                self.data_write_busy = False
                self.log(f"DATA WRITE REQUEST FAILED | {data} | {name}")
                Clock.schedule_once(lambda *_: self._process_data_queue(), 0.05)
                return
            self.log(f"DATA -> {data} | {name}")
            if name == "WRITE_NO_RESPONSE":
                Clock.schedule_once(self._release_no_response_data, 0.08)
        except Exception as exc:
            self.data_write_busy = False
            self.log(f"DATA WRITE ERROR: {exc}")
            Clock.schedule_once(lambda *_: self._process_data_queue(), 0.05)

    def _release_no_response_data(self, *_):
        if self.data_write_busy:
            self.data_write_busy = False
            self._process_data_queue()

    def _close_gatt(self):
        old = self.gatt
        self.connected = False
        self.connecting = False
        self.ready = False
        self.notifications_enabled = False
        self.command_write_busy = False
        self.data_write_busy = False
        self.descriptor_write_busy = False
        self.service = None
        self.command_characteristic = None
        self.event_characteristic = None
        self.state_characteristic = None
        self.data_characteristic = None
        self.event_descriptor = None
        self.command_queue.clear()
        self.data_queue.clear()
        self.gatt = None
        try:
            if old is not None:
                old.disconnect()
        except Exception:
            pass
        try:
            if old is not None:
                old.close()
        except Exception:
            pass

    def disconnect(self):
        if self.gatt is None:
            self.log("DISCONNECT: NO ACTIVE GATT SESSION.")
            return
        self.log("GATT DISCONNECT REQUESTED.")
        self._close_gatt()


class AvaPetApp(App):
    def build(self):
        self.title = "AVA PET"
        self.root_layout = FloatLayout()
        self.background = Image(
            source=BACKGROUND_PATH,
            fit_mode="cover",
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )
        self.root_layout.add_widget(self.background)

        self.finding_page = FloatLayout(size_hint=(1, 1))
        self.finding_label = Label(
            text="Finding AVA",
            font_name=FONT_NAME,
            font_size=dp(27),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(60),
            pos_hint={"center_x": 0.5, "top": 0.88},
        )
        self.finding_page.add_widget(self.finding_label)

        self.ava_name_label = Label(
            text="",
            font_name=FONT_NAME,
            font_size=dp(20),
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(dp(145), dp(55)),
            pos_hint={"center_x": 0.38, "center_y": 0.52},
            halign="center",
            valign="middle",
        )
        self.finding_page.add_widget(self.ava_name_label)

        self.connect_button = Button(
            text="CONNECT",
            font_name=FONT_NAME,
            font_size=dp(15),
            size_hint=(None, None),
            size=(dp(125), dp(55)),
            pos_hint={"center_x": 0.67, "center_y": 0.52},
            background_normal="",
            background_down="",
            background_color=(0.45, 0.12, 0.75, 0.9),
            color=(1, 1, 1, 1),
        )
        self.connect_button.bind(on_press=self.connect_ava)

        self.ava_name_label.opacity = 0
        self.connect_button.opacity = 0
        self.connect_button.disabled = True
        self.root_layout.add_widget(self.finding_page)

        self.games_page = FloatLayout(size_hint=(1, 1))

        self.games_title = Label(
            text="MY GAMES",
            font_name=FONT_NAME,
            font_size=dp(28),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(60),
            pos_hint={"center_x": 0.5, "top": 0.93},
        )
        self.games_page.add_widget(self.games_title)

        self.games_status = Label(
            text="CHOOSE A GAME",
            font_name=FONT_NAME,
            font_size=dp(13),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(40),
            pos_hint={"center_x": 0.5, "top": 0.82},
        )
        self.games_page.add_widget(self.games_status)

        self.games_scroll = ScrollView(
            size_hint=(0.86, 0.68),
            pos_hint={"center_x": 0.5, "y": 0.07},
            do_scroll_x=False,
            bar_width=dp(4),
        )
        self.games_list = GridLayout(
            cols=1,
            spacing=dp(10),
            padding=[dp(8), dp(8), dp(8), dp(16)],
            size_hint_y=None,
        )
        self.games_list.bind(minimum_height=self.games_list.setter("height"))

        for game_id, title, subtitle in AVAILABLE_GAMES:
            game_button = Button(
                text=f"{title}\n{subtitle}",
                font_name=FONT_NAME,
                font_size=dp(14),
                size_hint_y=None,
                height=dp(62),
                background_normal="",
                background_down="",
                background_color=(0.45, 0.12, 0.75, 0.9),
                color=(1, 1, 1, 1),
            )
            game_button.bind(on_press=lambda _, gid=game_id: self.select_game(gid))
            self.games_list.add_widget(game_button)

        self.games_scroll.add_widget(self.games_list)
        self.games_page.add_widget(self.games_scroll)
        self.root_layout.add_widget(self.games_page)
        self.games_page.opacity = 0
        self.games_page.disabled = True

        # CONNECT is intentionally a direct child of the root layout.
        # This keeps the actual touch target above the page overlays and
        # prevents a full-screen FloatLayout from swallowing the tap.
        self.root_layout.add_widget(self.connect_button)

        self.ble = AndroidBLE(self.add_log)
        return self.root_layout

    def on_start(self):
        try:
            from android.permissions import request_permissions, check_permission, Permission
            sdk = self.ble.android_sdk()
            if sdk >= 31:
                permissions = [
                    Permission.BLUETOOTH_SCAN,
                    Permission.BLUETOOTH_CONNECT,
                    Permission.ACCESS_FINE_LOCATION,
                    Permission.ACCESS_COARSE_LOCATION,
                ]
                self.add_log("REQUESTING ANDROID 12+ BLE + LOCATION PERMISSIONS...")
            else:
                permissions = [
                    Permission.BLUETOOTH,
                    Permission.BLUETOOTH_ADMIN,
                    Permission.ACCESS_FINE_LOCATION,
                    Permission.ACCESS_COARSE_LOCATION,
                ]
                self.add_log("REQUESTING ANDROID 10/11 BLE + LOCATION PERMISSIONS...")
            if all(check_permission(p) for p in permissions):
                self.add_log("ANDROID PERMISSIONS ALREADY GRANTED.")
                Clock.schedule_once(self.start_automatic_scan, 0.2)
                return
            request_permissions(permissions, self._on_permissions_result)
        except Exception as exc:
            self.add_log(f"PERMISSION ERROR: {exc}")

    def _on_permissions_result(self, permissions, grants):
        try:
            if all(bool(v) for v in grants):
                self.add_log("ANDROID PERMISSIONS GRANTED.")
                Clock.schedule_once(self.start_automatic_scan, 0.2)
            else:
                self.add_log("ANDROID PERMISSIONS DENIED.")
        except Exception as exc:
            self.add_log(f"PERMISSION CALLBACK ERROR: {exc}")

    def start_automatic_scan(self, *_):
        self.finding_label.text = "Finding AVA"
        self.ava_name_label.text = ""
        self.ava_name_label.opacity = 0
        self.connect_button.opacity = 0
        self.connect_button.disabled = True
        self.games_page.opacity = 0
        self.games_page.disabled = True
        self.add_log("STARTING AUTOMATIC AVA SCAN...")
        self.ble.scan()

    def connect_ava(self, *_):
        self.finding_label.text = "Connecting to AVA"
        self.connect_button.disabled = True
        self.add_log("CONNECT BUTTON PRESSED.")
        if not self.ble.has_ava():
            self.finding_label.text = "AVA NOT FOUND"
            self.add_log("CONNECT: AVA NOT FOUND.")
            self.connect_button.disabled = False
            return
        self.add_log("AVA DISCOVERED. STARTING GATT CONNECTION...")
        if not self.ble.connect():
            self.finding_label.text = "CONNECTION FAILED"
            self.connect_button.disabled = False

    def show_my_games(self):
        self.connect_button.disabled = True
        self.connect_button.opacity = 0
        self.finding_page.opacity = 0
        self.finding_page.disabled = True
        self.games_page.opacity = 1
        self.games_page.disabled = False
        self.games_status.text = "CHOOSE A GAME"

    def select_game(self, game_id):
        command = game_load_command(game_id)
        self.games_status.text = f"LOADING {game_id}"
        self.add_log(f"GAME LOAD -> {game_id}")
        if self.ble.write_command(command):
            self.games_status.text = f"LOADED: {game_id}"
            self.add_log(f"GAME COMMAND SENT | {command}")
        else:
            self.games_status.text = "GAME LOAD FAILED"
            self.add_log(f"GAME COMMAND FAILED | {command}")

    def add_log(self, message):
        upper = str(message).upper()
        if "AVA FOUND" in upper:
            self.ava_name_label.text = str(self.ble.found_name or AVA_NAME)
            self.finding_label.text = "AVA FOUND"
            self.ava_name_label.opacity = 1
            self.connect_button.opacity = 1
            self.connect_button.disabled = False
        if "GATT CONNECTION REQUESTED" in upper:
            self.finding_label.text = "Connecting to AVA"
            self.connect_button.disabled = True
        if "GATT CONNECTED" in upper:
            self.finding_label.text = "AVA CONNECTED"
        if "GATT RETRY REQUESTED" in upper:
            self.finding_label.text = "Retrying AVA"
        if "AVA READY" in upper:
            self.show_my_games()
        if "GATT DISCONNECTED" in upper:
            self.finding_page.opacity = 1
            self.finding_page.disabled = False
            self.games_page.opacity = 0
            self.games_page.disabled = True
            self.finding_label.text = "Finding AVA"
            self.connect_button.disabled = False
            self.ava_name_label.opacity = 0
            self.connect_button.opacity = 0


if __name__ == "__main__":
    AvaPetApp().run()
