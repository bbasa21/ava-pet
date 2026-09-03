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
from kivy.core.window import Window
from jnius import autoclass, PythonJavaClass, java_method

from ava_games import AVAILABLE_GAMES, game_load_command


# ============================================================
# AVA PET
# COMPLETE MAIN.PY
# ============================================================

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


# ============================================================
# FILES / FONT
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FONT_PATH = os.path.join(
    BASE_DIR,
    "fonts",
    "Orbitron Bold.ttf",
)

if os.path.exists(FONT_PATH):
    LabelBase.register(
        name="Orbitron",
        fn_regular=FONT_PATH,
    )

FONT_NAME = (
    "Orbitron"
    if os.path.exists(FONT_PATH)
    else "Roboto"
)

BACKGROUND_PATH = os.path.join(
    BASE_DIR,
    "IMG_20260902_023056_844.jpg",
)


# ============================================================
# ANDROID BLE
# ============================================================

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

        Clock.schedule_interval(
            self._poll_java_events,
            0.05,
        )

    # --------------------------------------------------------
    # LOG
    # --------------------------------------------------------

    def log(self, message):

        try:
            Clock.schedule_once(
                lambda *_: self.logger(str(message))
            )
        except Exception:
            pass

    # --------------------------------------------------------
    # ANDROID INITIALIZATION
    # --------------------------------------------------------

    def _initialize_android(self):

        try:

            Activity = autoclass(
                "org.kivy.android.PythonActivity"
            )

            Version = autoclass(
                "android.os.Build$VERSION"
            )

            BluetoothAdapter = autoclass(
                "android.bluetooth.BluetoothAdapter"
            )

            self.context = Activity.mActivity

            self.sdk = int(
                Version.SDK_INT
            )

            self.adapter = (
                BluetoothAdapter.getDefaultAdapter()
            )

            if self.adapter is None:

                self.log(
                    "ERROR: BLUETOOTH ADAPTER UNAVAILABLE."
                )

                return

            self.log(
                "ANDROID NATIVE BLE INITIALIZED."
            )

            self.log(
                f"ANDROID API LEVEL: {self.sdk}"
            )

        except Exception as exc:

            self.log(
                f"ANDROID INIT ERROR: {exc}"
            )

    # --------------------------------------------------------
    # SDK
    # --------------------------------------------------------

    def android_sdk(self):

        return self.sdk

    # --------------------------------------------------------
    # SCAN CALLBACK
    # --------------------------------------------------------

    def _create_scan_callback(self):

        outer = self

        class ScanCallback(PythonJavaClass):

            __javainterfaces__ = [
                "android/bluetooth/BluetoothAdapter$LeScanCallback"
            ]

            @java_method(
                "(Landroid/bluetooth/BluetoothDevice;I[B)V"
            )
            def onLeScan(
                self,
                device,
                rssi,
                scanRecord,
            ):

                try:

                    if device is None:
                        return

                    try:
                        name = device.getName()
                    except Exception:
                        name = None

                    if (
                        name is None
                        or AVA_NAME not in str(name).upper()
                    ):
                        return

                    try:
                        address = str(
                            device.getAddress()
                        )
                    except Exception:
                        address = "UNKNOWN"

                    outer.found_device = device
                    outer.found_name = str(name)
                    outer.found_address = address

                    outer.scanning = False

                    outer.log(
                        f"AVA FOUND | name={name} | "
                        f"address={address} | rssi={rssi}"
                    )

                    try:

                        outer.adapter.stopLeScan(
                            outer.scan_callback
                        )

                    except Exception:
                        pass

                except Exception as exc:

                    outer.log(
                        f"SCAN CALLBACK ERROR: {exc}"
                    )

        self.scan_callback = ScanCallback()

    # --------------------------------------------------------
    # SCAN
    # --------------------------------------------------------

    def scan(self):

        if self.adapter is None:

            self.log(
                "SCAN ERROR: BLUETOOTH UNAVAILABLE."
            )

            return

        if self.scanning:

            self.log(
                "SCAN: ALREADY SCANNING."
            )

            return

        try:

            if not self.adapter.isEnabled():

                self.log(
                    "SCAN ERROR: BLUETOOTH IS OFF."
                )

                return

        except Exception as exc:

            self.log(
                f"SCAN ERROR: BLUETOOTH STATE CHECK FAILED: {exc}"
            )

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

            self.log(
                "SCANNING FOR AVA..."
            )

            result = (
                self.adapter.startLeScan(
                    self.scan_callback
                )
            )

            if not result:

                self.log(
                    "SCAN ERROR: startLeScan() FAILED."
                )

                return

            self.scanning = True

            Clock.schedule_once(
                self.stop_scan,
                10,
            )

        except Exception as exc:

            self.scanning = False

            self.log(
                f"SCAN ERROR: {exc}"
            )

    # --------------------------------------------------------
    # STOP SCAN
    # --------------------------------------------------------

    def stop_scan(self, *_):

        if not self.scanning:
            return

        try:

            self.adapter.stopLeScan(
                self.scan_callback
            )

        except Exception:
            pass

        self.scanning = False

        if self.found_device is None:

            self.log(
                "SCAN FINISHED: AVA NOT FOUND."
            )

        else:

            self.log(
                f"SCAN FINISHED: AVA FOUND | "
                f"{self.found_address}"
            )

    # --------------------------------------------------------
    # HAS AVA
    # --------------------------------------------------------

    def has_ava(self):

        return self.found_device is not None

    # --------------------------------------------------------
    # JAVA GATT CALLBACK
    # --------------------------------------------------------

    def _create_java_gatt_callback(self):

        try:

            Callback = autoclass(
                "org.ava.avapet.AvaGattCallback"
            )

            self.gatt_callback = Callback()

            self.log(
                "JAVA GATT CALLBACK BRIDGE INITIALIZED."
            )

            return True

        except Exception as exc:

            self.log(
                f"JAVA GATT CALLBACK INIT ERROR: {exc}"
            )

            return False

    # --------------------------------------------------------
    # CONNECT
    # --------------------------------------------------------

    def connect(self):

        if self.found_device is None:

            self.log(
                "CONNECT ERROR: SCAN FOR AVA FIRST."
            )

            return False

        if self.connected:

            self.log(
                "CONNECT: AVA ALREADY CONNECTED."
            )

            return True

        if self.connecting:

            self.log(
                "CONNECT: ALREADY IN PROGRESS."
            )

            return False

        if self.gatt is not None:
            self._close_gatt()

        if not self._create_java_gatt_callback():
            return False

        try:

            BluetoothDevice = autoclass(
                "android.bluetooth.BluetoothDevice"
            )

            self.connecting = True
            self.ready = False
            self.notifications_enabled = False

            self.command_write_busy = False
            self.data_write_busy = False
            self.descriptor_write_busy = False

            self.log(
                f"GATT CONNECTION REQUESTED | "
                f"{self.found_name or AVA_NAME} | "
                f"{self.found_address}"
            )

            self.gatt = (
                self.found_device.connectGatt(
                    self.context,
                    False,
                    self.gatt_callback,
                    BluetoothDevice.TRANSPORT_LE,
                )
            )

            if self.gatt is None:

                self.connecting = False

                self.log(
                    "CONNECT ERROR: "
                    "connectGatt() RETURNED NULL."
                )

                return False

            self.log(
                "GATT CONNECT REQUEST ACCEPTED | TRANSPORT_LE."
            )

            return True

        except Exception as exc:

            self.connecting = False

            self.log(
                f"CONNECT ERROR: {exc}"
            )

            return False

    # --------------------------------------------------------
    # JAVA EVENT POLLER
    # --------------------------------------------------------

    def _poll_java_events(self, *_):

        if self.gatt_callback is None:
            return

        try:

            for event in (
                self.gatt_callback.drainEvents()
            ):

                self._handle_java_event(
                    str(event)
                )

        except Exception as exc:

            self.log(
                f"JAVA GATT EVENT POLL ERROR: {exc}"
            )

    # --------------------------------------------------------
    # HANDLE JAVA EVENT
    # --------------------------------------------------------

    def _handle_java_event(self, event):

        parts = event.split("|", 2)

        kind = (
            parts[0]
            if parts
            else ""
        )

        # ----------------------------------------------------
        # RETRY
        # ----------------------------------------------------

        if kind == "RETRY":

            status = (
                int(parts[1])
                if len(parts) > 1
                else -1
            )

            attempt = (
                int(parts[2])
                if len(parts) > 2
                else -1
            )

            self.connecting = True
            self.connected = False
            self.ready = False
            self.notifications_enabled = False

            self.log(
                f"GATT RETRY REQUESTED | "
                f"status={status} | "
                f"attempt={attempt}"
            )

            return

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        if kind == "STATE":

            status = (
                int(parts[1])
                if len(parts) > 1
                else -1
            )

            state = (
                int(parts[2])
                if len(parts) > 2
                else -1
            )

            self.log(
                f"GATT STATE CHANGE | "
                f"status={status} | "
                f"state={state}"
            )

            if state == STATE_CONNECTED:

                try:

                    self.gatt = (
                        self.gatt_callback.getGatt()
                    )

                except Exception:
                    pass

                self.connected = True
                self.connecting = False
                self.ready = False
                self.notifications_enabled = False

                self.log(
                    "GATT CONNECTED"
                )

                try:

                    if self.gatt.discoverServices():

                        self.log(
                            "SERVICE DISCOVERY STARTED."
                        )

                    else:

                        self.log(
                            "SERVICE DISCOVERY REQUEST FAILED."
                        )

                except Exception as exc:

                    self.log(
                        f"SERVICE DISCOVERY ERROR: {exc}"
                    )

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

                self.log(
                    f"GATT DISCONNECTED | status={status}"
                )

                if status != GATT_SUCCESS:

                    self.log(
                        f"GATT DISCONNECT ERROR CODE: {status}"
                    )

                try:

                    if self.gatt is not None:
                        self.gatt.close()

                except Exception:
                    pass

                self.gatt = None

            return

        # ----------------------------------------------------
        # SERVICES
        # ----------------------------------------------------

        if kind == "SERVICES":

            status = (
                int(parts[1])
                if len(parts) > 1
                else -1
            )

            self.log(
                f"SERVICE DISCOVERY RESULT | status={status}"
            )

            if (
                status != GATT_SUCCESS
                or self.gatt is None
            ):

                self.log(
                    "SERVICE DISCOVERY FAILED."
                )

                return

            try:

                UUID = autoclass(
                    "java.util.UUID"
                )

                self.service = (
                    self.gatt.getService(
                        UUID.fromString(
                            SERVICE_UUID
                        )
                    )
                )

                if self.service is None:

                    self.log(
                        "ERROR: AVA SERVICE NOT FOUND."
                    )

                    return

                self.log(
                    "AVA SERVICE FOUND."
                )

                self.command_characteristic = (
                    self.service.getCharacteristic(
                        UUID.fromString(
                            COMMAND_UUID
                        )
                    )
                )

                self.event_characteristic = (
                    self.service.getCharacteristic(
                        UUID.fromString(
                            EVENT_UUID
                        )
                    )
                )

                self.state_characteristic = (
                    self.service.getCharacteristic(
                        UUID.fromString(
                            STATE_UUID
                        )
                    )
                )

                self.data_characteristic = (
                    self.service.getCharacteristic(
                        UUID.fromString(
                            DATA_UUID
                        )
                    )
                )

                if self.command_characteristic is None:

                    self.log(
                        "ERROR: COMMAND CHARACTERISTIC NOT FOUND."
                    )

                    return

                if self.event_characteristic is None:

                    self.log(
                        "ERROR: EVENT CHARACTERISTIC NOT FOUND."
                    )

                    return

                if self.data_characteristic is None:

                    self.log(
                        "ERROR: DATA CHARACTERISTIC NOT FOUND."
                    )

                    return

                self.log(
                    "COMMAND CHARACTERISTIC FOUND."
                )

                self.log(
                    "EVENT CHARACTERISTIC FOUND."
                )

                if self.state_characteristic is not None:

                    self.log(
                        "STATE CHARACTERISTIC FOUND."
                    )

                self.log(
                    "DATA CHARACTERISTIC FOUND."
                )

                self.enable_notifications()

            except Exception as exc:

                self.log(
                    f"SERVICE DISCOVERY CALLBACK ERROR: {exc}"
                )

            return

        # ----------------------------------------------------
        # CHANGED
        # ----------------------------------------------------

        if kind == "CHANGED":

            uuid = (
                parts[1]
                if len(parts) > 1
                else "UNKNOWN"
            )

            encoded = (
                parts[2]
                if len(parts) > 2
                else ""
            )

            try:

                text = (
                    base64.b64decode(
                        encoded
                    ).decode(
                        "utf-8",
                        errors="replace",
                    )
                    if encoded
                    else ""
                )

            except Exception:

                text = "<binary>"

            self.log(
                f"EVENT <- {uuid} | {text}"
            )

            if (
                uuid.lower()
                == EVENT_UUID.lower()
                and
                text.strip().upper()
                == TIME_REQUEST
            ):

                self.log(
                    "[CLOCK] AVA REQUESTED CURRENT TIME."
                )

                Clock.schedule_once(
                    lambda *_:
                    self.send_current_time_to_ava(),
                    0.05,
                )

            elif (
                uuid.lower()
                == DATA_UUID.lower()
            ):

                Clock.schedule_once(
                    lambda *_:
                    self.handle_game_data(text),
                    0,
                )

            return

        # ----------------------------------------------------
        # WRITE
        # ----------------------------------------------------

        if kind == "WRITE":

            uuid = (
                parts[1]
                if len(parts) > 1
                else "UNKNOWN"
            )

            status = (
                int(parts[2])
                if len(parts) > 2
                else -1
            )

            if (
                uuid.lower()
                == COMMAND_UUID.lower()
            ):

                self.command_write_busy = False

                if status == GATT_SUCCESS:

                    self.log(
                        f"COMMAND WRITE OK | {uuid}"
                    )

                else:

                    self.log(
                        f"COMMAND WRITE FAILED | "
                        f"{uuid} | status={status}"
                    )

                self._process_command_queue()

            elif (
                uuid.lower()
                == DATA_UUID.lower()
            ):

                self.data_write_busy = False

                if status == GATT_SUCCESS:

                    self.log(
                        f"DATA WRITE OK | {uuid}"
                    )

                else:

                    self.log(
                        f"DATA WRITE FAILED | "
                        f"{uuid} | status={status}"
                    )

                self._process_data_queue()

            else:

                self.log(
                    f"WRITE EVENT UNKNOWN UUID | "
                    f"{uuid} | status={status}"
                )

            return

        # ----------------------------------------------------
        # DESCRIPTOR
        # ----------------------------------------------------

        if kind == "DESCRIPTOR":

            uuid = (
                parts[1]
                if len(parts) > 1
                else "UNKNOWN"
            )

            status = (
                int(parts[2])
                if len(parts) > 2
                else -1
            )

            self.descriptor_write_busy = False

            if status == GATT_SUCCESS:

                self.notifications_enabled = True
                self.ready = True

                self.log(
                    f"CCCD WRITE OK | {uuid}"
                )

                self.log(
                    "EVENT NOTIFICATIONS ENABLED."
                )

                self.log(
                    "AVA READY."
                )

                self._process_command_queue()
                self._process_data_queue()

            else:

                self.notifications_enabled = False
                self.ready = False

                self.log(
                    f"CCCD WRITE FAILED | "
                    f"{uuid} | status={status}"
                )

            return

        self.log(
            f"JAVA GATT EVENT UNKNOWN: {event}"
        )

    # --------------------------------------------------------
    # SEND TIME
    # --------------------------------------------------------

    def send_current_time_to_ava(self):

        if not self.connected:

            self.log(
                "[CLOCK] CANNOT SEND TIME: AVA NOT CONNECTED."
            )

            return False

        if not self.ready:

            self.log(
                "[CLOCK] CANNOT SEND TIME: "
                "AVA GATT NOT READY."
            )

            return False

        try:

            now = datetime.now()

            time_text = now.strftime(
                "%H:%M:%S"
            )

            date_text = now.strftime(
                "%Y-%m-%d"
            )

            command = (
                f"{TIME_RESPONSE}|"
                f"{time_text}|"
                f"{date_text}"
            )

            self.log(
                f"[CLOCK] PHONE TIME: {time_text}"
            )

            self.log(
                f"[CLOCK] PHONE DATE: {date_text}"
            )

            self.log(
                f"[CLOCK] DATA RESPONSE -> {command}"
            )

            return self.write_data(command)

        except Exception as exc:

            self.log(
                f"[CLOCK] TIME RESPONSE ERROR: {exc}"
            )

            return False

    # --------------------------------------------------------
    # ENABLE NOTIFICATIONS
    # --------------------------------------------------------

    def enable_notifications(self):

        if (
            self.gatt is None
            or self.event_characteristic is None
        ):

            self.log(
                "NOTIFY ERROR: GATT/EVENT UNAVAILABLE."
            )

            return False

        try:

            if not self.gatt.setCharacteristicNotification(
                self.event_characteristic,
                True,
            ):

                self.log(
                    "NOTIFY ERROR: "
                    "setCharacteristicNotification() FAILED."
                )

                return False

            UUID = autoclass(
                "java.util.UUID"
            )

            Descriptor = autoclass(
                "android.bluetooth.BluetoothGattDescriptor"
            )

            descriptor = (
                self.event_characteristic.getDescriptor(
                    UUID.fromString(
                        CCCD_UUID
                    )
                )
            )

            if descriptor is None:

                self.log(
                    "NOTIFY ERROR: CCCD NOT FOUND."
                )

                return False

            self.event_descriptor = descriptor

            descriptor.setValue(
                Descriptor.ENABLE_NOTIFICATION_VALUE
            )

            self.descriptor_write_busy = True

            if not self.gatt.writeDescriptor(
                descriptor
            ):

                self.descriptor_write_busy = False

                self.log(
                    "NOTIFY ERROR: "
                    "writeDescriptor() FAILED."
                )

                return False

            self.log(
                "CCCD WRITE REQUESTED."
            )

            return True

        except Exception as exc:

            self.descriptor_write_busy = False

            self.log(
                f"NOTIFICATION ERROR: {exc}"
            )

            return False

    # --------------------------------------------------------
    # WRITE COMMAND
    # --------------------------------------------------------

    def write_command(self, command):

        if not self.connected:

            self.log(
                "COMMAND ERROR: "
                "AVA NOT GATT CONNECTED."
            )

            return False

        if not self.ready:

            self.log(
                "COMMAND ERROR: "
                "AVA GATT NOT READY."
            )

            return False

        command = str(command).strip()

        if not command:
            return False

        self.command_queue.append(
            command
        )

        self._process_command_queue()

        return True

    # --------------------------------------------------------
    # PROCESS COMMAND QUEUE
    # --------------------------------------------------------

    def _process_command_queue(self):

        if (
            self.command_write_busy
            or not self.connected
            or not self.ready
        ):

            return

        if (
            self.gatt is None
            or self.command_characteristic is None
            or not self.command_queue
        ):

            return

        command = (
            self.command_queue.popleft()
        )

        try:

            self.command_characteristic.setValue(
                command.encode("utf-8")
            )

            Characteristic = autoclass(
                "android.bluetooth.BluetoothGattCharacteristic"
            )

            props = int(
                self.command_characteristic.getProperties()
            )

            if (
                props
                & int(
                    Characteristic.PROPERTY_WRITE_NO_RESPONSE
                )
            ):

                self.command_characteristic.setWriteType(
                    WRITE_TYPE_NO_RESPONSE
                )

                name = "WRITE_NO_RESPONSE"

            else:

                self.command_characteristic.setWriteType(
                    WRITE_TYPE_DEFAULT
                )

                name = "WRITE"

            self.command_write_busy = True

            if not self.gatt.writeCharacteristic(
                self.command_characteristic
            ):

                self.command_write_busy = False

                self.log(
                    f"COMMAND WRITE REQUEST FAILED | "
                    f"{command} | {name}"
                )

                Clock.schedule_once(
                    lambda *_:
                    self._process_command_queue(),
                    0.05,
                )

                return

            self.log(
                f"COMMAND -> {command} | {name}"
            )

            if name == "WRITE_NO_RESPONSE":

                Clock.schedule_once(
                    self._release_no_response_command,
                    0.08,
                )

        except Exception as exc:

            self.command_write_busy = False

            self.log(
                f"COMMAND WRITE ERROR: {exc}"
            )

            Clock.schedule_once(
                lambda *_:
                self._process_command_queue(),
                0.05,
            )

    # --------------------------------------------------------
    # RELEASE COMMAND
    # --------------------------------------------------------

    def _release_no_response_command(self, *_):

        if self.command_write_busy:

            self.command_write_busy = False

            self._process_command_queue()

    # --------------------------------------------------------
    # WRITE DATA
    # --------------------------------------------------------

    def write_data(self, data):

        if not self.connected:

            self.log(
                "DATA ERROR: AVA NOT GATT CONNECTED."
            )

            return False

        if not self.ready:

            self.log(
                "DATA ERROR: AVA GATT NOT READY."
            )

            return False

        data = str(data).strip()

        if not data:
            return False

        if self.data_characteristic is None:

            self.log(
                "DATA ERROR: "
                "DATA CHARACTERISTIC UNAVAILABLE."
            )

            return False

        self.data_queue.append(
            data
        )

        self._process_data_queue()

        return True

    # --------------------------------------------------------
    # PROCESS DATA QUEUE
    # --------------------------------------------------------

    def _process_data_queue(self):

        if (
            self.data_write_busy
            or not self.connected
            or not self.ready
        ):

            return

        if (
            self.gatt is None
            or self.data_characteristic is None
            or not self.data_queue
        ):

            return

        data = (
            self.data_queue.popleft()
        )

        try:

            self.data_characteristic.setValue(
                data.encode("utf-8")
            )

            Characteristic = autoclass(
                "android.bluetooth.BluetoothGattCharacteristic"
            )

            props = int(
                self.data_characteristic.getProperties()
            )

            if (
                props
                & int(
                    Characteristic.PROPERTY_WRITE_NO_RESPONSE
                )
            ):

                self.data_characteristic.setWriteType(
                    WRITE_TYPE_NO_RESPONSE
                )

                name = "WRITE_NO_RESPONSE"

            else:

                self.data_characteristic.setWriteType(
                    WRITE_TYPE_DEFAULT
                )

                name = "WRITE"

            self.data_write_busy = True

            if not self.gatt.writeCharacteristic(
                self.data_characteristic
            ):

                self.data_write_busy = False

                self.log(
                    f"DATA WRITE REQUEST FAILED | "
                    f"{data} | {name}"
                )

                Clock.schedule_once(
                    lambda *_:
                    self._process_data_queue(),
                    0.05,
                )

                return

            self.log(
                f"DATA -> {data} | {name}"
            )

            if name == "WRITE_NO_RESPONSE":

                Clock.schedule_once(
                    self._release_no_response_data,
                    0.08,
                )

        except Exception as exc:

            self.data_write_busy = False

            self.log(
                f"DATA WRITE ERROR: {exc}"
            )

            Clock.schedule_once(
                lambda *_:
                self._process_data_queue(),
                0.05,
            )

    # --------------------------------------------------------
    # RELEASE DATA
    # --------------------------------------------------------

    def _release_no_response_data(self, *_):

        if self.data_write_busy:

            self.data_write_busy = False

            self._process_data_queue()

    # --------------------------------------------------------
    # CLOSE GATT
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # DISCONNECT
    # --------------------------------------------------------

    def disconnect(self):

        if self.gatt is None:

            self.log(
                "DISCONNECT: NO ACTIVE GATT SESSION."
            )

            return

        self.log(
            "GATT DISCONNECT REQUESTED."
        )

        self._close_gatt()


# ============================================================
# AVA PET APP
# ============================================================

class AvaPetApp(App):

    def _window_game_touch_down(self, window, touch):
        if self.games_page.disabled or self.games_page.opacity <= 0:
            return False

        if self._game_touch_lock:
            return False

        for game_id, button in self.game_buttons.items():
            if button.disabled:
                continue

            # تبدیل مختصات لمس پنجره به مختصات خود Button
            local_pos = button.to_widget(*touch.pos)

            if button.collide_point(*local_pos):
                self._game_touch_lock = True

                self.add_log(f"GAME TOUCH WINDOW | {game_id}")
                self.game_button_pressed(game_id)

                Clock.schedule_once(
                    self._release_game_touch_lock,
                    0.25,
                )

                return True

        return False
    # ========================================================
    # BUILD
    # ========================================================

    def build(self):

        self.title = "AVA PET"

        self.root_layout = FloatLayout()

        # ----------------------------------------------------
        # BACKGROUND
        # ----------------------------------------------------

        self.background = Image(
            source=BACKGROUND_PATH,
            fit_mode="cover",
            size_hint=(1, 1),
            pos_hint={
                "x": 0,
                "y": 0,
            },
        )

        self.root_layout.add_widget(
            self.background
        )

        # ====================================================
        # FINDING / CONNECTION PAGE
        # ====================================================

        self.finding_page = FloatLayout(
            size_hint=(1, 1)
        )

        self.finding_label = Label(
            text="Finding AVA",
            font_name=FONT_NAME,
            font_size=dp(27),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(60),
            pos_hint={
                "center_x": 0.5,
                "top": 0.88,
            },
        )

        self.finding_page.add_widget(
            self.finding_label
        )

        self.ava_name_label = Label(
            text="",
            font_name=FONT_NAME,
            font_size=dp(20),
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(dp(145), dp(55)),
            pos_hint={
                "center_x": 0.38,
                "center_y": 0.52,
            },
            halign="center",
            valign="middle",
        )

        self.finding_page.add_widget(
            self.ava_name_label
        )

        self.connect_button = Button(
            text="CONNECT",
            font_name=FONT_NAME,
            font_size=dp(15),
            size_hint=(None, None),
            size=(dp(125), dp(55)),
            pos_hint={
                "center_x": 0.67,
                "center_y": 0.52,
            },
            background_normal="",
            background_down="",
            background_color=(
                0.45,
                0.12,
                0.75,
                0.9,
            ),
            color=(1, 1, 1, 1),
        )

        self.connect_button.bind(
            on_press=self.connect_ava
        )

        self.ava_name_label.opacity = 0
        self.connect_button.opacity = 0
        self.connect_button.disabled = True

        self.root_layout.add_widget(
            self.finding_page
        )

        # ====================================================
        # MY GAMES PAGE
        # ====================================================

        self.games_page = FloatLayout(
            size_hint=(1, 1)
        )

        self.games_title = Label(
            text="MY GAMES",
            font_name=FONT_NAME,
            font_size=dp(28),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(60),
            pos_hint={
                "center_x": 0.5,
                "top": 0.93,
            },
        )

        self.games_page.add_widget(
            self.games_title
        )

        self.games_status = Label(
            text="CHOOSE A GAME",
            font_name=FONT_NAME,
            font_size=dp(13),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(40),
            pos_hint={
                "center_x": 0.5,
                "top": 0.82,
            },
        )

        self.games_page.add_widget(
            self.games_status
        )

        # ----------------------------------------------------
        # SCROLL VIEW
        # ----------------------------------------------------

        self.games_scroll = ScrollView(
            size_hint=(0.86, 0.68),
            pos_hint={
                "center_x": 0.5,
                "y": 0.07,
            },
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(4),
        )

        self.games_list = GridLayout(
            cols=1,
            spacing=dp(10),
            padding=[
                dp(8),
                dp(8),
                dp(8),
                dp(16),
            ],
            size_hint_y=None,
        )

        self.games_list.bind(
            minimum_height=
            self.games_list.setter("height")
        )

        # ----------------------------------------------------
        # GAME BUTTONS
        # ----------------------------------------------------

        self.game_buttons = {}

        for game_id, title, subtitle in AVAILABLE_GAMES:

            game_button = Button(
                text=(
                    f"{title}\n"
                    f"{subtitle}"
                ),
                font_name=FONT_NAME,
                font_size=dp(14),
                size_hint_y=None,
                height=dp(62),
                background_normal="",
                background_down="",
                background_color=(
                    0.45,
                    0.12,
                    0.75,
                    0.9,
                ),
                color=(1, 1, 1, 1),
            )

            # Store exact button reference.
            self.game_buttons[
                str(game_id).strip().upper()
            ] = game_button

            # NORMAL KIVY PATH:
            # Use on_release rather than only on_press.
            game_button.bind(
                on_release=
                lambda button,
                gid=game_id:
                self.game_button_pressed(gid)
            )

            self.games_list.add_widget(
                game_button
            )

        self.games_scroll.add_widget(
            self.games_list
        )

        self.games_page.add_widget(
            self.games_scroll
        )

        self.root_layout.add_widget(
            self.games_page
        )

        self.games_page.opacity = 0
        self.games_page.disabled = True

        # ====================================================
        # MATH BATTLE PAGE
        # ====================================================

        self.math_page = FloatLayout(
            size_hint=(1, 1)
        )

        self.math_title = Label(
            text="MATH BATTLE",
            font_name=FONT_NAME,
            font_size=dp(25),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(55),
            pos_hint={
                "center_x": 0.5,
                "top": 0.94,
            },
        )

        self.math_page.add_widget(
            self.math_title
        )

        self.math_round_label = Label(
            text="ROUND 1 / 5",
            font_name=FONT_NAME,
            font_size=dp(13),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(35),
            pos_hint={
                "center_x": 0.5,
                "top": 0.84,
            },
        )

        self.math_page.add_widget(
            self.math_round_label
        )

        self.math_score_label = Label(
            text="ALI: 0     AVA: 0",
            font_name=FONT_NAME,
            font_size=dp(15),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(40),
            pos_hint={
                "center_x": 0.5,
                "top": 0.78,
            },
        )

        self.math_page.add_widget(
            self.math_score_label
        )

        self.math_question_label = Label(
            text="WAITING FOR QUESTION...",
            font_name=FONT_NAME,
            font_size=dp(25),
            color=(1, 1, 1, 1),
            size_hint=(0.92, None),
            height=dp(80),
            pos_hint={
                "center_x": 0.5,
                "top": 0.69,
            },
            halign="center",
            valign="middle",
        )

        self.math_question_label.bind(
            size=lambda inst, val:
            setattr(
                inst,
                "text_size",
                val,
            )
        )

        self.math_page.add_widget(
            self.math_question_label
        )

        # ----------------------------------------------------
        # MATH OPTIONS
        # ----------------------------------------------------

        self.math_options_grid = GridLayout(
            cols=2,
            rows=2,
            spacing=dp(12),
            padding=[
                dp(12),
                dp(8),
            ],
            size_hint=(0.88, None),
            height=dp(150),
            pos_hint={
                "center_x": 0.5,
                "center_y": 0.39,
            },
        )

        self.math_option_buttons = []

        for index in range(4):

            button = Button(
                text="-",
                font_name=FONT_NAME,
                font_size=dp(19),
                background_normal="",
                background_down="",
                background_color=(
                    0.45,
                    0.12,
                    0.75,
                    0.9,
                ),
                color=(1, 1, 1, 1),
            )

            button.bind(
                on_press=
                lambda _,
                idx=index:
                self.select_math_answer(idx)
            )

            self.math_option_buttons.append(
                button
            )

            self.math_options_grid.add_widget(
                button
            )

        self.math_page.add_widget(
            self.math_options_grid
        )

        # ----------------------------------------------------
        # MATH ANSWER STATUS
        # ----------------------------------------------------

        self.math_answer_label = Label(
            text="",
            font_name=FONT_NAME,
            font_size=dp(13),
            color=(1, 1, 1, 1),
            size_hint=(0.94, None),
            height=dp(55),
            pos_hint={
                "center_x": 0.5,
                "y": 0.16,
            },
            halign="center",
            valign="middle",
        )

        self.math_answer_label.bind(
            size=lambda inst, val:
            setattr(
                inst,
                "text_size",
                val,
            )
        )

        self.math_page.add_widget(
            self.math_answer_label
        )

        # ----------------------------------------------------
        # BACK
        # ----------------------------------------------------

        self.math_back_button = Button(
            text="BACK TO GAMES",
            font_name=FONT_NAME,
            font_size=dp(12),
            size_hint=(None, None),
            size=(dp(170), dp(42)),
            pos_hint={
                "center_x": 0.5,
                "y": 0.05,
            },
            background_normal="",
            background_down="",
            background_color=(
                0.25,
                0.08,
                0.42,
                0.9,
            ),
            color=(1, 1, 1, 1),
        )

        self.math_back_button.bind(
            on_press=self.back_to_games
        )

        self.math_page.add_widget(
            self.math_back_button
        )

        self.root_layout.add_widget(
            self.math_page
        )

        self.math_page.opacity = 0
        self.math_page.disabled = True

        # ====================================================
        # GAME STATE
        # ====================================================

        self.game_id = None

        self.game_round = 0
        self.game_total_rounds = 5

        self.game_options = []

        self.game_ali_score = 0
        self.game_ava_score = 0

        self.game_ali_answer = None
        self.game_ava_answer = None

        self.game_ali_answered = False
        self.game_ava_answered = False

        self.game_last_result_round = 0

        # Prevent duplicate fallback touch activation.
        self._game_touch_lock = False
        Window.bind(on_touch_down=self._window_game_touch_down)

        # ====================================================
        # CONNECT BUTTON ABOVE FINDING PAGE
        # ====================================================

        self.root_layout.add_widget(
            self.connect_button
        )

        # ====================================================
        # BLE
        # ====================================================

        self.ble = AndroidBLE(
            self.add_log
        )

        return self.root_layout

    # ========================================================
    # START
    # ========================================================

    def on_start(self):

        try:

            from android.permissions import (
                request_permissions,
                check_permission,
                Permission,
            )

            sdk = self.ble.android_sdk()

            if sdk >= 31:

                permissions = [
                    Permission.BLUETOOTH_SCAN,
                    Permission.BLUETOOTH_CONNECT,
                    Permission.ACCESS_FINE_LOCATION,
                    Permission.ACCESS_COARSE_LOCATION,
                ]

                self.add_log(
                    "REQUESTING ANDROID 12+ "
                    "BLE + LOCATION PERMISSIONS..."
                )

            else:

                permissions = [
                    Permission.BLUETOOTH,
                    Permission.BLUETOOTH_ADMIN,
                    Permission.ACCESS_FINE_LOCATION,
                    Permission.ACCESS_COARSE_LOCATION,
                ]

                self.add_log(
                    "REQUESTING ANDROID 10/11 "
                    "BLE + LOCATION PERMISSIONS..."
                )

            if all(
                check_permission(p)
                for p in permissions
            ):

                self.add_log(
                    "ANDROID PERMISSIONS ALREADY GRANTED."
                )

                Clock.schedule_once(
                    self.start_automatic_scan,
                    0.2,
                )

                return

            request_permissions(
                permissions,
                self._on_permissions_result,
            )

        except Exception as exc:

            self.add_log(
                f"PERMISSION ERROR: {exc}"
            )

    # ========================================================
    # PERMISSION RESULT
    # ========================================================

    def _on_permissions_result(
        self,
        permissions,
        grants,
    ):

        try:

            if all(bool(v) for v in grants):

                self.add_log(
                    "ANDROID PERMISSIONS GRANTED."
                )

                Clock.schedule_once(
                    self.start_automatic_scan,
                    0.2,
                )

            else:

                self.add_log(
                    "ANDROID PERMISSIONS DENIED."
                )

        except Exception as exc:

            self.add_log(
                f"PERMISSION CALLBACK ERROR: {exc}"
            )

    # ========================================================
    # AUTOMATIC SCAN
    # ========================================================

    def start_automatic_scan(self, *_):

        self.finding_label.text = "Finding AVA"

        self.ava_name_label.text = ""
        self.ava_name_label.opacity = 0

        self.connect_button.opacity = 0
        self.connect_button.disabled = True

        self.games_page.opacity = 0
        self.games_page.disabled = True

        self.math_page.opacity = 0
        self.math_page.disabled = True

        self.add_log(
            "STARTING AUTOMATIC AVA SCAN..."
        )

        self.ble.scan()

    # ========================================================
    # CONNECT AVA
    # ========================================================

    def connect_ava(self, *_):

        self.finding_label.text = (
            "Connecting to AVA"
        )

        self.connect_button.disabled = True

        self.add_log(
            "CONNECT BUTTON PRESSED."
        )

        if not self.ble.has_ava():

            self.finding_label.text = (
                "AVA NOT FOUND"
            )

            self.add_log(
                "CONNECT: AVA NOT FOUND."
            )

            self.connect_button.disabled = False

            return

        self.add_log(
            "AVA DISCOVERED. "
            "STARTING GATT CONNECTION..."
        )

        if not self.ble.connect():

            self.finding_label.text = (
                "CONNECTION FAILED"
            )

            self.connect_button.disabled = False

    # ========================================================
    # SHOW MY GAMES
    # ========================================================

    def show_my_games(self):

        self.connect_button.disabled = True
        self.connect_button.opacity = 0

        self.finding_page.opacity = 0
        self.finding_page.disabled = True

        self.math_page.opacity = 0
        self.math_page.disabled = True

        self.games_page.opacity = 1
        self.games_page.disabled = False

        self.games_status.text = (
            "CHOOSE A GAME"
        )

        # Important diagnostic.
        self.add_log(
            "MY GAMES PAGE READY. BUTTONS ENABLED."
        )

        # Reset fallback touch lock.
        self._game_touch_lock = False

    # ========================================================
    # GAME BUTTON HANDLER
    # ========================================================

    def game_button_pressed(self, game_id):

        game_id = str(
            game_id
        ).strip().upper()

        # Immediate visible confirmation.
        self.games_status.text = (
            f"BUTTON: {game_id}"
        )

        # Diagnostic confirmation.
        self.add_log(
            f"!!! GAME BUTTON PRESSED: {game_id} !!!"
        )

        # Continue into actual game logic.
        self.select_game(
            game_id,
            _button_event=True,
        )

    # ========================================================
    # FALLBACK GAME TOUCH HANDLER
    #
    # If Android/Kivy ever fails to dispatch the Button
    # callback inside ScrollView, games_page catches the
    # touch and resolves the button manually.
    # ========================================================

    def _game_page_touch_fallback(
        self,
        touch,
    ):

        if (
            self.games_page.disabled
            or self.games_page.opacity <= 0
        ):

            return False

        if self._game_touch_lock:

            return False

        # The actual ScrollView occupies this area.
        if not self.games_scroll.collide_point(
            *touch.pos
        ):

            return False

        # Check exact game button positions.
        for game_id, button in self.game_buttons.items():

            if button.disabled:
                continue

            if button.collide_point(
                *touch.pos
            ):

                self._game_touch_lock = True

                self.add_log(
                    f"GAME TOUCH FALLBACK | {game_id}"
                )

                Clock.schedule_once(
                    lambda *_,
                    gid=game_id:
                    self.game_button_pressed(gid),
                    0,
                )

                Clock.schedule_once(
                    self._release_game_touch_lock,
                    0.20,
                )

                return True

        return False

    def _release_game_touch_lock(self, *_):

        self._game_touch_lock = False

    # ========================================================
    # OVERRIDE TOUCH DISPATCH FOR GAMES PAGE
    # ========================================================

    def on_touch_down(self, touch):

        # First let the normal Kivy widget tree process
        # the touch.
        handled = super().on_touch_down(touch)

        if handled:
            return True

        # If nothing handled it, perform our fallback.
        if self._game_page_touch_fallback(touch):

            return True

        return False

    # ========================================================
    # SELECT GAME
    # ========================================================

    def select_game(
        self,
        game_id,
        _button_event=False,
    ):

        game_id = str(
            game_id
        ).strip().upper()

        # Don't duplicate the diagnostic when called
        # through game_button_pressed().
        if not _button_event:

            self.add_log(
                f"!!! GAME BUTTON PRESSED: {game_id} !!!"
            )

        command = game_load_command(
            game_id
        )

        self.games_status.text = (
            f"LOADING {game_id}"
        )

        self.add_log(
            f"GAME LOAD -> {game_id}"
        )

        # ----------------------------------------------------
        # SEND GAME_LOAD
        # ----------------------------------------------------

        if self.ble.write_command(
            command
        ):

            self.games_status.text = (
                f"LOADED: {game_id}"
            )

            self.add_log(
                f"GAME COMMAND SENT | {command}"
            )

            # ------------------------------------------------
            # MATH BATTLE
            # ------------------------------------------------

            if game_id == "MATH_BATTLE":

                self.reset_math_state()

                self.game_id = (
                    "MATH_BATTLE"
                )

                self.games_status.text = (
                    "MATH BATTLE STARTING"
                )

                self.math_page.opacity = 1
                self.math_page.disabled = False

                self.games_page.opacity = 0
                self.games_page.disabled = True

                self.math_answer_label.text = (
                    "STARTING GAME..."
                )

                # GAME_LOAD loads the game.
                # GAME_START generates round 1.
                if self.ble.write_command(
                    "GAME_START"
                ):

                    self.add_log(
                        "GAME START -> MATH_BATTLE"
                    )

                else:

                    self.add_log(
                        "GAME START QUEUE FAILED"
                    )

                    self.games_status.text = (
                        "GAME START FAILED"
                    )

                    self.math_answer_label.text = (
                        "GAME START FAILED"
                    )

        else:

            self.games_status.text = (
                "GAME LOAD FAILED"
            )

            self.add_log(
                f"GAME COMMAND FAILED | {command}"
            )

    # ========================================================
    # RESET MATH
    # ========================================================

    def reset_math_state(self):

        self.game_round = 0

        self.game_options = []

        self.game_ali_score = 0
        self.game_ava_score = 0

        self.game_ali_answer = None
        self.game_ava_answer = None

        self.game_ali_answered = False
        self.game_ava_answered = False

        self.game_last_result_round = 0

        self.math_round_label.text = (
            "ROUND 1 / 5"
        )

        self.math_score_label.text = (
            "ALI: 0     AVA: 0"
        )

        self.math_question_label.text = (
            "WAITING FOR QUESTION..."
        )

        self.math_answer_label.text = ""

        for button in (
            self.math_option_buttons
        ):

            button.text = "-"
            button.disabled = True

    # ========================================================
    # SHOW MATH QUESTION
    # ========================================================

    def show_math_question(
        self,
        round_number,
        a,
        b,
        operator,
        options,
    ):

        try:

            self.game_round = int(
                round_number
            )

            self.game_options = [
                int(value)
                for value in options[:4]
            ]

        except Exception as exc:

            self.add_log(
                f"GAME QUESTION PARSE ERROR: {exc}"
            )

            return

        if len(
            self.game_options
        ) != 4:

            self.add_log(
                "GAME QUESTION ERROR: "
                "EXPECTED 4 OPTIONS."
            )

            return

        self.game_ali_answer = None
        self.game_ava_answer = None

        self.game_ali_answered = False
        self.game_ava_answered = False

        self.math_round_label.text = (
            f"ROUND {self.game_round} / "
            f"{self.game_total_rounds}"
        )

        self.math_question_label.text = (
            f"{a} {operator} {b} = ?"
        )

        self.math_answer_label.text = (
            "CHOOSE YOUR ANSWER"
        )

        for idx, button in enumerate(
            self.math_option_buttons
        ):

            button.text = str(
                self.game_options[idx]
            )

            button.disabled = False

        self.add_log(
            f"MATH QUESTION | "
            f"ROUND={self.game_round} | "
            f"{a} {operator} {b} | "
            f"OPTIONS={self.game_options}"
        )

    # ========================================================
    # MATH ANSWER
    # ========================================================

    def select_math_answer(
        self,
        index,
    ):

        if self.game_ali_answered:
            return

        if (
            index < 0
            or index >= len(
                self.game_options
            )
        ):

            return

        answer = (
            self.game_options[index]
        )

        self.game_ali_answer = answer
        self.game_ali_answered = True

        for button in (
            self.math_option_buttons
        ):

            button.disabled = True

        self.math_answer_label.text = (
            f"ALI ANSWER: {answer} | "
            f"WAITING FOR AVA..."
        )

        command = (
            f"GAME_ANSWER|ALI|{answer}"
        )

        self.add_log(
            f"MATH ANSWER -> {command}"
        )

        if not self.ble.write_data(
            command
        ):

            self.game_ali_answered = False

            self.math_answer_label.text = (
                "ANSWER SEND FAILED"
            )

            for button in (
                self.math_option_buttons
            ):

                button.disabled = False

    # ========================================================
    # GAME DATA
    # ========================================================

    def handle_game_data(
        self,
        text,
    ):

        text = str(
            text
        ).strip()

        if (
            not text
            or text == "<binary>"
        ):

            return

        self.add_log(
            f"GAME DATA <- {text}"
        )

        parts = text.split("|")

        message = (
            parts[0].strip().upper()
            if parts
            else ""
        )

        try:

            # ------------------------------------------------
            # QUESTION
            # ------------------------------------------------

            if message == "GAME_QUESTION":

                if len(parts) < 9:

                    self.add_log(
                        "GAME QUESTION ERROR: "
                        "INVALID FIELD COUNT."
                    )

                    return

                self.show_math_question(
                    parts[1],
                    parts[2],
                    parts[3],
                    parts[4],
                    parts[5:9],
                )

                return

            # ------------------------------------------------
            # ANSWER
            # ------------------------------------------------

            if message == "GAME_ANSWER":

                if len(parts) < 3:
                    return

                player = (
                    parts[1]
                    .strip()
                    .upper()
                )

                answer = int(
                    parts[2]
                )

                if player == "AVA":

                    self.game_ava_answer = answer
                    self.game_ava_answered = True

                    if self.game_ali_answered:

                        self.math_answer_label.text = (
                            f"ALI: "
                            f"{self.game_ali_answer} | "
                            f"AVA: {answer} | "
                            f"CHECKING..."
                        )

                    else:

                        self.math_answer_label.text = (
                            f"AVA ANSWERED: {answer}"
                        )

                elif player == "ALI":

                    self.game_ali_answer = answer
                    self.game_ali_answered = True

                return

            # ------------------------------------------------
            # RESULT
            # ------------------------------------------------

            if message == "GAME_RESULT":

                if len(parts) < 6:

                    self.add_log(
                        "GAME RESULT ERROR: "
                        "INVALID FIELD COUNT."
                    )

                    return

                round_number = int(
                    parts[1]
                )

                ali_answer = int(
                    parts[2]
                )

                ava_answer = int(
                    parts[3]
                )

                ali_correct = bool(
                    int(parts[4])
                )

                ava_correct = bool(
                    int(parts[5])
                )

                self.apply_math_result(
                    round_number,
                    ali_answer,
                    ava_answer,
                    ali_correct,
                    ava_correct,
                )

                return

            # ------------------------------------------------
            # SCORE DEBUG
            # ------------------------------------------------

            if message == "GAME_SCORE":

                if len(parts) >= 3:

                    self.add_log(
                        f"GAME SCORE DEBUG <- "
                        f"ALI={parts[1]} "
                        f"AVA={parts[2]}"
                    )

                return

            # ------------------------------------------------
            # FINISHED
            # ------------------------------------------------

            if message == "GAME_FINISHED":

                winner = (
                    parts[1]
                    if len(parts) > 1
                    else "DRAW"
                )

                self.show_math_finished(
                    winner
                )

                return

        except Exception as exc:

            self.add_log(
                f"GAME DATA PARSE ERROR: "
                f"{exc} | {text}"
            )

    # ========================================================
    # APPLY RESULT
    # ========================================================

    def apply_math_result(
        self,
        round_number,
        ali_answer,
        ava_answer,
        ali_correct,
        ava_correct,
    ):

        if (
            round_number
            == self.game_last_result_round
        ):

            return

        self.game_last_result_round = (
            round_number
        )

        self.game_ali_answer = (
            ali_answer
        )

        self.game_ava_answer = (
            ava_answer
        )

        self.game_ali_answered = True
        self.game_ava_answered = True

        # APP IS SCORE AUTHORITY.
        if (
            ali_correct
            and not ava_correct
        ):

            self.game_ali_score += 1

            result = (
                "ALI WINS ROUND"
            )

        elif (
            ava_correct
            and not ali_correct
        ):

            self.game_ava_score += 1

            result = (
                "AVA WINS ROUND"
            )

        elif (
            ali_correct
            and ava_correct
        ):

            result = (
                "ROUND DRAW"
            )

        else:

            result = (
                "NOBODY GETS A POINT"
            )

        self.math_score_label.text = (
            f"ALI: {self.game_ali_score}"
            f"     "
            f"AVA: {self.game_ava_score}"
        )

        self.math_answer_label.text = (
            f"ALI: {ali_answer} "
            f"{'✓' if ali_correct else '✗'}    "
            f"AVA: {ava_answer} "
            f"{'✓' if ava_correct else '✗'}\n"
            f"{result}"
        )

        self.add_log(
            f"MATH RESULT | "
            f"ROUND={round_number} | "
            f"ALI={ali_answer}/"
            f"{int(ali_correct)} | "
            f"AVA={ava_answer}/"
            f"{int(ava_correct)} | "
            f"SCORE="
            f"{self.game_ali_score}:"
            f"{self.game_ava_score}"
        )

    # ========================================================
    # FINISHED
    # ========================================================

    def show_math_finished(
        self,
        winner,
    ):

        winner_text = (
            str(winner)
            .strip()
            .upper()
        )

        if winner_text in (
            "ALI",
            "ALI_WINS",
        ):

            final = "ALI WINS!"

        elif winner_text in (
            "AVA",
            "AVA_WINS",
        ):

            final = "AVA WINS!"

        else:

            final = "DRAW!"

        self.math_answer_label.text = (
            f"{final}\n"
            f"FINAL SCORE  "
            f"ALI: {self.game_ali_score}  "
            f"AVA: {self.game_ava_score}"
        )

        for button in (
            self.math_option_buttons
        ):

            button.disabled = True

        self.add_log(
            f"MATH FINISHED | "
            f"WINNER={winner_text} | "
            f"APP SCORE="
            f"{self.game_ali_score}:"
            f"{self.game_ava_score}"
        )

    # ========================================================
    # BACK TO GAMES
    # ========================================================

    def back_to_games(self, *_):

        self.math_page.opacity = 0
        self.math_page.disabled = True

        self.games_page.opacity = 1
        self.games_page.disabled = False

        self.games_status.text = (
            "CHOOSE A GAME"
        )

        self._game_touch_lock = False

        self.ble.write_command(
            "GAME_END"
        )

    # ========================================================
    # LOG / UI STATE
    # ========================================================

    def add_log(self, message):

        upper = str(
            message
        ).upper()

        # ----------------------------------------------------
        # AVA FOUND
        # ----------------------------------------------------

        if "AVA FOUND" in upper:

            self.ava_name_label.text = str(
                self.ble.found_name
                or AVA_NAME
            )

            self.finding_label.text = (
                "AVA FOUND"
            )

            self.ava_name_label.opacity = 1

            self.connect_button.opacity = 1
            self.connect_button.disabled = False

        # ----------------------------------------------------
        # CONNECTION REQUEST
        # ----------------------------------------------------

        if "GATT CONNECTION REQUESTED" in upper:

            self.finding_label.text = (
                "Connecting to AVA"
            )

            self.connect_button.disabled = True

        # ----------------------------------------------------
        # CONNECTED
        # ----------------------------------------------------

        if "GATT CONNECTED" in upper:

            self.finding_label.text = (
                "AVA CONNECTED"
            )

        # ----------------------------------------------------
        # RETRY
        # ----------------------------------------------------

        if "GATT RETRY REQUESTED" in upper:

            self.finding_label.text = (
                "Retrying AVA"
            )

        # ----------------------------------------------------
        # READY
        # ----------------------------------------------------

        if "AVA READY" in upper:

            self.show_my_games()

        # ----------------------------------------------------
        # DISCONNECTED
        # ----------------------------------------------------

        if "GATT DISCONNECTED" in upper:

            self.finding_page.opacity = 1
            self.finding_page.disabled = False

            self.games_page.opacity = 0
            self.games_page.disabled = True

            self.math_page.opacity = 0
            self.math_page.disabled = True

            self.finding_label.text = (
                "Finding AVA"
            )

            self.connect_button.disabled = False

            self.ava_name_label.opacity = 0
            self.connect_button.opacity = 0


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    AvaPetApp().run()

