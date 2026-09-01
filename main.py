import base64
import os
from datetime import datetime
from collections import deque

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

from jnius import autoclass, PythonJavaClass, java_method


# ============================================================
# AVA BLE UUID
# ============================================================

AVA_NAME = "AVA"

SERVICE_UUID = "7b7a0001-6a76-4156-9a76-415641000001"
COMMAND_UUID = "7b7a0002-6a76-4156-9a76-415641000001"
EVENT_UUID = "7b7a0003-6a76-4156-9a76-415641000001"
STATE_UUID = "7b7a0004-6a76-4156-9a76-415641000001"
DATA_UUID = "7b7a0005-6a76-4156-9a76-415641000001"

CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"


# ============================================================
# GATT CONSTANTS
# ============================================================

GATT_SUCCESS = 0

STATE_DISCONNECTED = 0
STATE_CONNECTED = 2

WRITE_TYPE_NO_RESPONSE = 1
WRITE_TYPE_DEFAULT = 2


# ============================================================
# CLOCK PROTOCOL
# ============================================================

TIME_REQUEST = "TIME_REQUEST"
TIME_RESPONSE = "TIME_RESPONSE"


# ============================================================
# FONT
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

FONT_PATH = os.path.join(
    BASE_DIR,
    "fonts",
    "Orbitron Bold.ttf"
)

if os.path.exists(FONT_PATH):

    LabelBase.register(
        name="Orbitron",
        fn_regular=FONT_PATH
    )

else:

    print(
        f"[FONT ERROR] Orbitron font not found: "
        f"{FONT_PATH}"
    )


FONT_NAME = "Orbitron"


# ============================================================
# ANDROID BLE
# ============================================================

class AndroidBLE:

    def __init__(self, logger):

        self.logger = logger

        # ----------------------------------------------------
        # Android
        # ----------------------------------------------------

        self.autoclass = None
        self.PythonJavaClass = None
        self.java_method = None

        self.context = None
        self.adapter = None

        self.sdk = 30

        # ----------------------------------------------------
        # Scan
        # ----------------------------------------------------

        self.scan_callback = None
        self.scanning = False

        self.found_device = None
        self.found_address = None
        self.found_name = None

        # ----------------------------------------------------
        # GATT
        # ----------------------------------------------------

        self.gatt = None
        self.gatt_callback = None

        self.service = None

        self.command_characteristic = None
        self.event_characteristic = None
        self.state_characteristic = None
        self.data_characteristic = None

        self.event_descriptor = None

        # ----------------------------------------------------
        # State
        # ----------------------------------------------------

        self.connected = False
        self.connecting = False
        self.ready = False

        self.notifications_enabled = False

        # ----------------------------------------------------
        # COMMAND queue
        # ----------------------------------------------------

        self.command_queue = deque()
        self.command_write_busy = False

        # ----------------------------------------------------
        # DATA queue
        # ----------------------------------------------------

        self.data_queue = deque()
        self.data_write_busy = False

        # ----------------------------------------------------
        # Descriptor
        # ----------------------------------------------------

        self.descriptor_write_busy = False

        # ----------------------------------------------------
        # Android initialization
        # ----------------------------------------------------

        self._initialize_android()

        Clock.schedule_interval(
            self._poll_java_events,
            0.05
        )

    # ========================================================
    # LOG
    # ========================================================

    def log(self, message):

        try:

            Clock.schedule_once(
                lambda *_:
                self.logger(str(message))
            )

        except Exception:
            pass

    # ========================================================
    # ANDROID INITIALIZATION
    # ========================================================

    def _initialize_android(self):

        try:

            self.autoclass = autoclass
            self.PythonJavaClass = PythonJavaClass
            self.java_method = java_method

            Activity = autoclass(
                "org.kivy.android.PythonActivity"
            )

            self.context = Activity.mActivity

            Version = autoclass(
                "android.os.Build$VERSION"
            )

            self.sdk = int(
                Version.SDK_INT
            )

            BluetoothAdapter = autoclass(
                "android.bluetooth.BluetoothAdapter"
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

    # ========================================================
    # SDK
    # ========================================================

    def android_sdk(self):

        return self.sdk

    # ========================================================
    # SCAN CALLBACK
    # ========================================================

    def _create_scan_callback(self):

        outer = self

        class ScanCallback(
            self.PythonJavaClass
        ):

            __javainterfaces__ = [
                "android/bluetooth/"
                "BluetoothAdapter$LeScanCallback"
            ]

            @self.java_method(
                "(Landroid/bluetooth/"
                "BluetoothDevice;I[B)V"
            )
            def onLeScan(
                self,
                device,
                rssi,
                scanRecord
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
                        or AVA_NAME not in
                        str(name).upper()
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
                        f"AVA FOUND | "
                        f"name={name} | "
                        f"address={address} | "
                        f"rssi={rssi}"
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

    # ========================================================
    # SCAN
    # ========================================================

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
                f"SCAN ERROR: BLUETOOTH STATE CHECK FAILED: "
                f"{exc}"
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

            result = self.adapter.startLeScan(
                self.scan_callback
            )

            if not result:

                self.log(
                    "SCAN ERROR: startLeScan() FAILED."
                )

                return

            self.scanning = True

            Clock.schedule_once(
                self.stop_scan,
                10
            )

        except Exception as exc:

            self.scanning = False

            self.log(
                f"SCAN ERROR: {exc}"
            )

    # ========================================================
    # STOP SCAN
    # ========================================================

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

    # ========================================================
    # HAS AVA
    # ========================================================

    def has_ava(self):

        return self.found_device is not None

    # ========================================================
    # JAVA GATT CALLBACK
    # ========================================================

    def _create_java_gatt_callback(self):

        try:

            Callback = self.autoclass(
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

    # ========================================================
    # CONNECT
    # ========================================================

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
                    self.gatt_callback
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
                "GATT CONNECT REQUEST ACCEPTED."
            )

            return True

        except Exception as exc:

            self.connecting = False

            self.log(
                f"CONNECT ERROR: {exc}"
            )

            return False

    # ========================================================
    # POLL JAVA EVENTS
    # ========================================================

    def _poll_java_events(self, *_):

        if self.gatt_callback is None:
            return

        try:

            events = (
                self.gatt_callback.drainEvents()
            )

            for event in events:

                self._handle_java_event(
                    str(event)
                )

        except Exception as exc:

            self.log(
                f"JAVA GATT EVENT POLL ERROR: {exc}"
            )

    # ========================================================
    # JAVA EVENT HANDLER
    # ========================================================

    def _handle_java_event(self, event):

        parts = event.split("|", 2)

        kind = (
            parts[0]
            if parts
            else ""
        )

        # ====================================================
        # STATE
        # ====================================================

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

                    result = (
                        self.gatt.discoverServices()
                    )

                    self.log(
                        "SERVICE DISCOVERY STARTED."
                        if result
                        else
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
                    f"GATT DISCONNECTED | "
                    f"status={status}"
                )

                if status != GATT_SUCCESS:

                    self.log(
                        f"GATT DISCONNECT ERROR CODE: "
                        f"{status}"
                    )

                try:

                    if self.gatt is not None:
                        self.gatt.close()

                except Exception:
                    pass

                self.gatt = None

        # ====================================================
        # SERVICES
        # ====================================================

        elif kind == "SERVICES":

            status = (
                int(parts[1])
                if len(parts) > 1
                else -1
            )

            self.log(
                f"SERVICE DISCOVERY RESULT | "
                f"status={status}"
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

                UUID = self.autoclass(
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

                # --------------------------------------------
                # COMMAND
                # --------------------------------------------

                self.command_characteristic = (
                    self.service.getCharacteristic(
                        UUID.fromString(
                            COMMAND_UUID
                        )
                    )
                )

                # --------------------------------------------
                # EVENT
                # --------------------------------------------

                self.event_characteristic = (
                    self.service.getCharacteristic(
                        UUID.fromString(
                            EVENT_UUID
                        )
                    )
                )

                # --------------------------------------------
                # STATE
                # --------------------------------------------

                self.state_characteristic = (
                    self.service.getCharacteristic(
                        UUID.fromString(
                            STATE_UUID
                        )
                    )
                )

                # --------------------------------------------
                # DATA
                # --------------------------------------------

                self.data_characteristic = (
                    self.service.getCharacteristic(
                        UUID.fromString(
                            DATA_UUID
                        )
                    )
                )

                if self.command_characteristic is None:

                    self.log(
                        "ERROR: COMMAND CHARACTERISTIC "
                        "NOT FOUND."
                    )

                    return

                if self.event_characteristic is None:

                    self.log(
                        "ERROR: EVENT CHARACTERISTIC "
                        "NOT FOUND."
                    )

                    return

                if self.data_characteristic is None:

                    self.log(
                        "ERROR: DATA CHARACTERISTIC "
                        "NOT FOUND."
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

                # --------------------------------------------
                # Notifications
                # --------------------------------------------

                self.enable_notifications()

            except Exception as exc:

                self.log(
                    f"SERVICE DISCOVERY CALLBACK ERROR: "
                    f"{exc}"
                )

        # ====================================================
        # CHANGED / NOTIFICATION
        # ====================================================

        elif kind == "CHANGED":

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
                        errors="replace"
                    )
                    if encoded
                    else ""
                )

            except Exception:

                text = "<binary>"

            self.log(
                f"EVENT <- {uuid} | {text}"
            )

            # ------------------------------------------------
            # TIME REQUEST
            #
            # فقط EVENT_UUID معتبر است.
            # ------------------------------------------------

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
                    0.05
                )

        # ====================================================
        # WRITE
        # ====================================================

        elif kind == "WRITE":

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

            # ------------------------------------------------
            # COMMAND WRITE
            # ------------------------------------------------

            if uuid.lower() == COMMAND_UUID.lower():

                self.command_write_busy = False

                if status == GATT_SUCCESS:

                    self.log(
                        f"COMMAND WRITE OK | {uuid}"
                    )

                else:

                    self.log(
                        f"COMMAND WRITE FAILED | "
                        f"{uuid} | "
                        f"status={status}"
                    )

                self._process_command_queue()

            # ------------------------------------------------
            # DATA WRITE
            # ------------------------------------------------

            elif uuid.lower() == DATA_UUID.lower():

                self.data_write_busy = False

                if status == GATT_SUCCESS:

                    self.log(
                        f"DATA WRITE OK | {uuid}"
                    )

                else:

                    self.log(
                        f"DATA WRITE FAILED | "
                        f"{uuid} | "
                        f"status={status}"
                    )

                self._process_data_queue()

            # ------------------------------------------------
            # UNKNOWN WRITE
            # ------------------------------------------------

            else:

                self.log(
                    f"WRITE EVENT UNKNOWN UUID | "
                    f"{uuid} | "
                    f"status={status}"
                )

        # ====================================================
        # DESCRIPTOR
        # ====================================================

        elif kind == "DESCRIPTOR":

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
                    f"{uuid} | "
                    f"status={status}"
                )

        # ====================================================
        # UNKNOWN EVENT
        # ====================================================

        else:

            self.log(
                f"JAVA GATT EVENT UNKNOWN: {event}"
            )

    # ========================================================
    # CLOCK
    # ========================================================

    def send_current_time_to_ava(self):

        if not self.connected:

            self.log(
                "[CLOCK] CANNOT SEND TIME: "
                "AVA NOT CONNECTED."
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
                f"[CLOCK] PHONE TIME: "
                f"{time_text}"
            )

            self.log(
                f"[CLOCK] PHONE DATE: "
                f"{date_text}"
            )

            self.log(
                f"[CLOCK] DATA RESPONSE -> "
                f"{command}"
            )

            # IMPORTANT:
            # Clock response goes through DATA,
            # NOT COMMAND.

            return self.write_data(
                command
            )

        except Exception as exc:

            self.log(
                f"[CLOCK] TIME RESPONSE ERROR: "
                f"{exc}"
            )

            return False

    # ========================================================
    # ENABLE EVENT NOTIFICATIONS
    # ========================================================

    def enable_notifications(self):

        if (
            self.gatt is None
            or self.event_characteristic is None
        ):

            self.log(
                "NOTIFY ERROR: "
                "GATT/EVENT UNAVAILABLE."
            )

            return False

        try:

            if not self.gatt.setCharacteristicNotification(
                self.event_characteristic,
                True
            ):

                self.log(
                    "NOTIFY ERROR: "
                    "setCharacteristicNotification() "
                    "FAILED."
                )

                return False

            UUID = self.autoclass(
                "java.util.UUID"
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

            Descriptor = self.autoclass(
                "android.bluetooth."
                "BluetoothGattDescriptor"
            )

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

    # ========================================================
    # WRITE COMMAND
    #
    # Phone -> AVA COMMAND characteristic
    # ========================================================

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

    # ========================================================
    # COMMAND QUEUE
    # ========================================================

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

            Characteristic = self.autoclass(
                "android.bluetooth."
                "BluetoothGattCharacteristic"
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
                    f"{command} | "
                    f"{name}"
                )

                Clock.schedule_once(
                    lambda *_:
                    self._process_command_queue(),
                    0.05
                )

                return

            self.log(
                f"COMMAND -> {command} | {name}"
            )

            if name == "WRITE_NO_RESPONSE":

                Clock.schedule_once(
                    self._release_no_response_command,
                    0.08
                )

        except Exception as exc:

            self.command_write_busy = False

            self.log(
                f"COMMAND WRITE ERROR: {exc}"
            )

            Clock.schedule_once(
                lambda *_:
                self._process_command_queue(),
                0.05
            )

    # ========================================================
    # RELEASE COMMAND NO RESPONSE
    # ========================================================

    def _release_no_response_command(self, *_):

        if self.command_write_busy:

            self.command_write_busy = False

            self._process_command_queue()

    # ========================================================
    # WRITE DATA
    #
    # Phone -> AVA DATA characteristic
    #
    # Example:
    # TIME_RESPONSE|22:41:30|2026-09-01
    # ========================================================

    def write_data(self, data):

        if not self.connected:

            self.log(
                "DATA ERROR: "
                "AVA NOT GATT CONNECTED."
            )

            return False

        if not self.ready:

            self.log(
                "DATA ERROR: "
                "AVA GATT NOT READY."
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

    # ========================================================
    # DATA QUEUE
    # ========================================================

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

            Characteristic = self.autoclass(
                "android.bluetooth."
                "BluetoothGattCharacteristic"
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
                    f"{data} | "
                    f"{name}"
                )

                Clock.schedule_once(
                    lambda *_:
                    self._process_data_queue(),
                    0.05
                )

                return

            self.log(
                f"DATA -> {data} | {name}"
            )

            if name == "WRITE_NO_RESPONSE":

                Clock.schedule_once(
                    self._release_no_response_data,
                    0.08
                )

        except Exception as exc:

            self.data_write_busy = False

            self.log(
                f"DATA WRITE ERROR: {exc}"
            )

            Clock.schedule_once(
                lambda *_:
                self._process_data_queue(),
                0.05
            )

    # ========================================================
    # RELEASE DATA NO RESPONSE
    # ========================================================

    def _release_no_response_data(self, *_):

        if self.data_write_busy:

            self.data_write_busy = False

            self._process_data_queue()

    # ========================================================
    # CLOSE GATT
    # ========================================================

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

    # ========================================================
    # DISCONNECT
    # ========================================================

    def disconnect(self):

        if self.gatt is None:

            self.log(
                "DISCONNECT: "
                "NO ACTIVE GATT SESSION."
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

    # ========================================================
    # BUILD
    # ========================================================

    def build(self):

        self.title = "AVA PET"

        root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(8)
        )

        # ====================================================
        # TITLE
        # ====================================================

        root.add_widget(
            Label(
                text="[b]AVA PET[/b]",
                markup=True,
                font_name=FONT_NAME,
                font_size=dp(28),
                size_hint_y=None,
                height=dp(55)
            )
        )

        # ====================================================
        # STATUS
        # ====================================================

        self.status_label = Label(
            text="DISCONNECTED",
            font_name=FONT_NAME,
            font_size=dp(18),
            size_hint_y=None,
            height=dp(42)
        )

        root.add_widget(
            self.status_label
        )

        # ====================================================
        # CONNECTION BUTTONS
        # ====================================================

        row = BoxLayout(
            size_hint_y=None,
            height=dp(50),
            spacing=dp(8)
        )

        for title, callback in (
            ("SCAN", self.ble_scan),
            ("CONNECT", self.connect_ava),
            ("DISCONNECT", self.disconnect_ava)
        ):

            button = Button(
                text=title,
                font_name=FONT_NAME
            )

            button.bind(
                on_release=callback
            )

            row.add_widget(
                button
            )

        root.add_widget(
            row
        )

        # ====================================================
        # EYES
        # ====================================================

        root.add_widget(
            self.command_row(
                (
                    ("EYES_CALM", "CALM"),
                    ("EYES_HAPPY", "HAPPY"),
                    ("EYES_SAD", "SAD")
                )
            )
        )

        root.add_widget(
            self.command_row(
                (
                    ("EYES_SLEEPY", "SLEEPY"),
                    ("EYES_THINKING", "THINKING"),
                    ("EYES_LISTENING", "LISTENING")
                )
            )
        )

        root.add_widget(
            self.command_row(
                (
                    ("EYES_SURPRISED", "SURPRISED"),
                    ("BLINK", "BLINK"),
                    ("HELLO_AVA", "HELLO")
                )
            )
        )

        # ====================================================
        # LOG
        # ====================================================

        self.log_label = Label(
            text="AVA log:",
            font_name=FONT_NAME,
            size_hint_y=None,
            halign="left",
            valign="top"
        )

        self.log_label.bind(
            texture_size=self.update_log_height
        )

        scroll = ScrollView()

        scroll.add_widget(
            self.log_label
        )

        root.add_widget(
            scroll
        )

        # ====================================================
        # BLE
        # ====================================================

        self.ble = AndroidBLE(
            self.add_log
        )

        return root

    # ========================================================
    # SCAN
    # ========================================================

    def ble_scan(self, *_):

        self.ble.scan()

    # ========================================================
    # COMMAND ROW
    # ========================================================

    def command_row(self, commands):

        row = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            spacing=dp(6)
        )

        for command, title in commands:

            button = Button(
                text=title,
                font_name=FONT_NAME
            )

            button.bind(
                on_release=lambda _, cmd=command:
                self.test_command(cmd)
            )

            row.add_widget(
                button
            )

        return row

    # ========================================================
    # CONNECT
    # ========================================================

    def connect_ava(self, *_):

        if not self.ble.has_ava():

            self.add_log(
                "CONNECT: SCAN FOR AVA FIRST."
            )

            return

        self.add_log(
            "AVA DISCOVERED. "
            "STARTING GATT CONNECTION..."
        )

        self.status_label.text = (
            "CONNECTING..."
        )

        self.ble.connect()

    # ========================================================
    # DISCONNECT
    # ========================================================

    def disconnect_ava(self, *_):

        self.ble.disconnect()

        self.status_label.text = (
            "DISCONNECTED"
        )

    # ========================================================
    # TEST COMMAND
    # ========================================================

    def test_command(self, command):

        self.ble.write_command(
            command
        )

    # ========================================================
    # LOG
    # ========================================================

    def add_log(self, message):

        text = str(message)
        upper = text.upper()

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        if "AVA FOUND" in upper:

            self.status_label.text = (
                "AVA FOUND"
            )

        if "GATT CONNECTION REQUESTED" in upper:

            self.status_label.text = (
                "CONNECTING..."
            )

        if "GATT CONNECTED" in upper:

            self.status_label.text = (
                "GATT CONNECTED"
            )

        if "AVA READY" in upper:

            self.status_label.text = (
                "AVA READY"
            )

        if "GATT DISCONNECTED" in upper:

            self.status_label.text = (
                "DISCONNECTED"
            )

        # ----------------------------------------------------
        # Log text
        # ----------------------------------------------------

        if self.log_label.text == "AVA log:":

            self.log_label.text = ""

        self.log_label.text += (
            "\n" + text
        )

    # ========================================================
    # LOG HEIGHT
    # ========================================================

    def update_log_height(
        self,
        widget,
        texture_size
    ):

        widget.height = max(
            texture_size[1],
            dp(120)
        )

    # ========================================================
    # ANDROID PERMISSIONS
    # ========================================================

    def on_start(self):

        try:

            from android.permissions import (
                request_permissions,
                Permission
            )

            if self.ble.android_sdk() >= 31:

                permissions = [
                    Permission.BLUETOOTH_SCAN,
                    Permission.BLUETOOTH_CONNECT
                ]

                self.add_log(
                    "REQUESTING ANDROID 12+ "
                    "BLE PERMISSIONS..."
                )

            else:

                permissions = [
                    Permission.BLUETOOTH,
                    Permission.BLUETOOTH_ADMIN,
                    Permission.ACCESS_FINE_LOCATION
                ]

                self.add_log(
                    "REQUESTING ANDROID 10/11 "
                    "BLE PERMISSIONS..."
                )

            request_permissions(
                permissions
            )

        except Exception as exc:

            self.add_log(
                f"PERMISSION ERROR: {exc}"
            )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    AvaPetApp().run()
