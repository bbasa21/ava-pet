from collections import deque

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView


# ============================================================
# AVA PET
# Native Android BLE / GATT
#
# Android 10+
#
# Android 10 / 11:
#   BLUETOOTH
#   BLUETOOTH_ADMIN
#   ACCESS_FINE_LOCATION
#
# Android 12+:
#   BLUETOOTH_SCAN
#   BLUETOOTH_CONNECT
#
# No Bleak.
# ============================================================


# ============================================================
# AVA BLE UUIDs
# ============================================================

AVA_NAME = "AVA"

SERVICE_UUID = "7b7a0001-6a76-4156-9a76-415641000001"
COMMAND_UUID = "7b7a0002-6a76-4156-9a76-415641000001"
EVENT_UUID = "7b7a0003-6a76-4156-9a76-415641000001"

CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"


# ============================================================
# Android constants
# ============================================================

GATT_SUCCESS = 0

STATE_DISCONNECTED = 0
STATE_CONNECTING = 1
STATE_CONNECTED = 2

WRITE_TYPE_DEFAULT = 2
WRITE_TYPE_NO_RESPONSE = 1


class AndroidBLE:

    # ========================================================
    # INIT
    # ========================================================

    def __init__(self, logger):

        self.logger = logger

        # Android
        self.autoclass = None
        self.PythonJavaClass = None
        self.java_method = None

        self.context = None
        self.adapter = None

        # Scanner
        self.scan_callback = None
        self.scanning = False
        self.scan_stop_event = None

        self.found_device = None
        self.found_address = None
        self.found_name = None

        # GATT
        self.gatt = None
        self.gatt_callback = None

        self.service = None
        self.command_characteristic = None
        self.event_characteristic = None
        self.event_descriptor = None

        # State
        self.connected = False
        self.ready = False
        self.notifications_enabled = False

        # Prevent duplicate connection attempts
        self.connecting = False

        # Command queue
        self.command_queue = deque()
        self.command_write_busy = False

        # Descriptor operation state
        self.descriptor_write_busy = False

        # Connection generation
        #
        # Every new connection receives a new generation number.
        # This prevents stale callbacks from old GATT sessions
        # from corrupting the current connection state.
        self.connection_generation = 0

        self._initialize_android()

    # ========================================================
    # LOGGER
    # ========================================================

    def log(self, message):

        try:
            Clock.schedule_once(
                lambda *_: self.logger(str(message))
            )
        except Exception:
            pass

    # ========================================================
    # ANDROID INITIALIZATION
    # ========================================================

    def _initialize_android(self):

        try:

            from jnius import (
                autoclass,
                PythonJavaClass,
                java_method
            )

            self.autoclass = autoclass
            self.PythonJavaClass = PythonJavaClass
            self.java_method = java_method

            PythonActivity = autoclass(
                "org.kivy.android.PythonActivity"
            )

            self.context = PythonActivity.mActivity

            BluetoothAdapter = autoclass(
                "android.bluetooth.BluetoothAdapter"
            )

            self.adapter = (
                BluetoothAdapter.getDefaultAdapter()
            )

            if self.adapter is None:

                self.log(
                    "ERROR: Bluetooth adapter unavailable."
                )

                return

            self.log(
                "Android native BLE initialized."
            )

            try:

                Build_VERSION = autoclass(
                    "android.os.Build$VERSION"
                )

                sdk = int(
                    Build_VERSION.SDK_INT
                )

                self.log(
                    f"Android API level: {sdk}"
                )

            except Exception:

                pass

        except Exception as exc:

            self.log(
                f"ANDROID INIT ERROR: {exc}"
            )

    # ========================================================
    # ANDROID SDK
    # ========================================================

    def android_sdk(self):

        try:

            Build_VERSION = self.autoclass(
                "android.os.Build$VERSION"
            )

            return int(
                Build_VERSION.SDK_INT
            )

        except Exception:

            return 30

    # ========================================================
    # SCAN CALLBACK
    # ========================================================

    def _create_scan_callback(self):

        PythonJavaClass = self.PythonJavaClass
        java_method = self.java_method

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
                scanRecord
            ):

                try:

                    if device is None:
                        return

                    name = None
                    address = None

                    try:
                        name = device.getName()
                    except Exception:
                        pass

                    try:
                        address = device.getAddress()
                    except Exception:
                        pass

                    if name is None:
                        return

                    name_text = str(name)

                    if (
                        name_text.upper() != AVA_NAME
                        and AVA_NAME not in name_text.upper()
                    ):
                        return

                    # Save device immediately.
                    outer.found_device = device
                    outer.found_name = name_text
                    outer.found_address = (
                        str(address)
                        if address is not None
                        else "UNKNOWN"
                    )

                    outer.scanning = False

                    outer.log(
                        f"FOUND: {outer.found_name} | "
                        f"{outer.found_address}"
                    )

                    try:

                        if outer.adapter is not None:

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
    # START SCAN
    # ========================================================

    def scan(self):

        if self.adapter is None:

            self.log(
                "SCAN ERROR: Bluetooth unavailable."
            )

            return

        if self.scanning:

            self.log(
                "SCAN: Already scanning."
            )

            return

        try:

            if not self.adapter.isEnabled():

                self.log(
                    "SCAN ERROR: Bluetooth is OFF."
                )

                return

        except Exception as exc:

            self.log(
                f"SCAN ERROR: Cannot check Bluetooth: {exc}"
            )

            return

        # If an old GATT session exists, clean it.
        if self.gatt is not None:

            self.log(
                "SCAN: Closing previous GATT session..."
            )

            self._close_gatt()

        self.found_device = None
        self.found_address = None
        self.found_name = None

        self.ready = False
        self.connected = False
        self.connecting = False
        self.notifications_enabled = False

        self._create_scan_callback()

        try:

            self.log(
                "SCANNING FOR AVA..."
            )

            started = self.adapter.startLeScan(
                self.scan_callback
            )

            if not started:

                self.log(
                    "SCAN ERROR: startLeScan() failed."
                )

                return

            self.scanning = True

            self.scan_stop_event = Clock.schedule_once(
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

            if self.adapter is not None:
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
                f"SCAN FINISHED: AVA FOUND "
                f"({self.found_address})"
            )

    # ========================================================
    # AVA FOUND?
    # ========================================================

    def has_ava(self):

        return self.found_device is not None

    # ========================================================
    # GATT CALLBACK
    #
    # IMPORTANT:
    #
    # BluetoothGattCallback is an ABSTRACT JAVA CLASS,
    # NOT an interface.
    #
    # Therefore it MUST NOT be placed in:
    #
    # __javainterfaces__
    #
    # The callback implementation below uses PyJNIus's
    # Java class inheritance mechanism.
    # ========================================================

    def _create_gatt_callback(self):

        PythonJavaClass = self.PythonJavaClass
        java_method = self.java_method

        outer = self

        # ----------------------------------------------------
        # Java class proxy
        # ----------------------------------------------------

        class GattCallback(PythonJavaClass):

            __javacontext__ = "system"

            @java_method(
                "(Landroid/bluetooth/BluetoothGatt;II)V"
            )
            def onConnectionStateChange(
                self,
                gatt,
                status,
                newState
            ):

                try:

                    outer.log(
                        f"GATT STATE CHANGE | "
                        f"status={status} | "
                        f"state={newState}"
                    )

                    if newState == STATE_CONNECTED:

                        outer.gatt = gatt
                        outer.connected = True
                        outer.connecting = False
                        outer.ready = False
                        outer.notifications_enabled = False

                        outer.log(
                            "🟢 GATT CONNECTED"
                        )

                        # Service discovery MUST happen after
                        # the connection is established.
                        try:

                            started = (
                                gatt.discoverServices()
                            )

                            if started:

                                outer.log(
                                    "SERVICE DISCOVERY STARTED."
                                )

                            else:

                                outer.log(
                                    "SERVICE DISCOVERY REQUEST FAILED."
                                )

                        except Exception as exc:

                            outer.log(
                                f"SERVICE DISCOVERY ERROR: {exc}"
                            )

                    elif newState == STATE_DISCONNECTED:

                        was_connected = (
                            outer.connected
                        )

                        outer.connected = False
                        outer.ready = False
                        outer.connecting = False
                        outer.notifications_enabled = False
                        outer.command_write_busy = False
                        outer.descriptor_write_busy = False

                        outer.command_characteristic = None
                        outer.event_characteristic = None
                        outer.event_descriptor = None
                        outer.service = None

                        outer.log(
                            f"🔴 GATT DISCONNECTED | "
                            f"status={status}"
                        )

                        if status != GATT_SUCCESS:

                            outer.log(
                                f"GATT DISCONNECT ERROR CODE: "
                                f"{status}"
                            )

                        try:

                            gatt.close()

                        except Exception:
                            pass

                        if outer.gatt is gatt:

                            outer.gatt = None

                        if was_connected:

                            outer.log(
                                "AVA session ended."
                            )

                except Exception as exc:

                    outer.log(
                        f"GATT STATE CALLBACK ERROR: {exc}"
                    )

            @java_method(
                "(Landroid/bluetooth/BluetoothGatt;I)V"
            )
            def onServicesDiscovered(
                self,
                gatt,
                status
            ):

                try:

                    outer.log(
                        f"SERVICE DISCOVERY RESULT | "
                        f"status={status}"
                    )

                    if status != GATT_SUCCESS:

                        outer.log(
                            "SERVICE DISCOVERY FAILED."
                        )

                        return

                    outer.log(
                        "SERVICES DISCOVERED."
                    )

                    UUID = outer.autoclass(
                        "java.util.UUID"
                    )

                    service_uuid = UUID.fromString(
                        SERVICE_UUID
                    )

                    command_uuid = UUID.fromString(
                        COMMAND_UUID
                    )

                    event_uuid = UUID.fromString(
                        EVENT_UUID
                    )

                    service = (
                        gatt.getService(
                            service_uuid
                        )
                    )

                    if service is None:

                        outer.log(
                            "ERROR: AVA SERVICE NOT FOUND."
                        )

                        return

                    outer.service = service

                    outer.log(
                        "AVA SERVICE FOUND."
                    )

                    command_characteristic = (
                        service.getCharacteristic(
                            command_uuid
                        )
                    )

                    if command_characteristic is None:

                        outer.log(
                            "ERROR: COMMAND CHARACTERISTIC NOT FOUND."
                        )

                        return

                    outer.command_characteristic = (
                        command_characteristic
                    )

                    outer.log(
                        "COMMAND CHARACTERISTIC FOUND."
                    )

                    event_characteristic = (
                        service.getCharacteristic(
                            event_uuid
                        )
                    )

                    if event_characteristic is None:

                        outer.log(
                            "ERROR: EVENT CHARACTERISTIC NOT FOUND."
                        )

                        return

                    outer.event_characteristic = (
                        event_characteristic
                    )

                    outer.log(
                        "EVENT CHARACTERISTIC FOUND."
                    )

                    # Enable notification.
                    outer.enable_notifications()

                except Exception as exc:

                    outer.log(
                        f"SERVICE DISCOVERY CALLBACK ERROR: {exc}"
                    )

            # ------------------------------------------------
            # Notification callback
            # ------------------------------------------------

            @java_method(
                "(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;)V"
            )
            def onCharacteristicChanged(
                self,
                gatt,
                characteristic
            ):

                try:

                    if characteristic is None:
                        return

                    uuid = str(
                        characteristic.getUuid()
                    )

                    value = characteristic.getValue()

                    if value is None:
                        return

                    data = bytes(
                        int(x) & 0xFF
                        for x in value
                    )

                    text = data.decode(
                        "utf-8",
                        errors="replace"
                    )

                    outer.log(
                        f"EVENT ← {uuid} | {text}"
                    )

                except Exception as exc:

                    outer.log(
                        f"NOTIFICATION CALLBACK ERROR: {exc}"
                    )

            # ------------------------------------------------
            # Characteristic write callback
            # ------------------------------------------------

            @java_method(
                "(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;I)V"
            )
            def onCharacteristicWrite(
                self,
                gatt,
                characteristic,
                status
            ):

                try:

                    uuid = str(
                        characteristic.getUuid()
                    )

                    outer.command_write_busy = False

                    if status == GATT_SUCCESS:

                        outer.log(
                            f"WRITE OK | {uuid}"
                        )

                    else:

                        outer.log(
                            f"WRITE FAILED | "
                            f"{uuid} | status={status}"
                        )

                    # Continue queued commands.
                    outer._process_command_queue()

                except Exception as exc:

                    outer.command_write_busy = False

                    outer.log(
                        f"WRITE CALLBACK ERROR: {exc}"
                    )

                    outer._process_command_queue()

            # ------------------------------------------------
            # Descriptor write callback
            # ------------------------------------------------

            @java_method(
                "(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattDescriptor;I)V"
            )
            def onDescriptorWrite(
                self,
                gatt,
                descriptor,
                status
            ):

                try:

                    outer.descriptor_write_busy = False

                    if status == GATT_SUCCESS:

                        outer.notifications_enabled = True
                        outer.ready = True

                        outer.log(
                            "CCCD WRITE OK."
                        )

                        outer.log(
                            "🟢 AVA READY."
                        )

                    else:

                        outer.notifications_enabled = False
                        outer.ready = False

                        outer.log(
                            f"CCCD WRITE FAILED | "
                            f"status={status}"
                        )

                except Exception as exc:

                    outer.descriptor_write_busy = False

                    outer.log(
                        f"DESCRIPTOR CALLBACK ERROR: {exc}"
                    )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Keep a strong Python reference alive.
        # Otherwise Java may lose the callback object.
        # ----------------------------------------------------

        self.gatt_callback = GattCallback()

    # ========================================================
    # CONNECT
    # ========================================================

    def connect(self):

        if self.found_device is None:

            self.log(
                "CONNECT ERROR: Scan for AVA first."
            )

            return False

        if self.connected:

            self.log(
                "CONNECT: AVA already connected."
            )

            return True

        if self.connecting:

            self.log(
                "CONNECT: Connection already in progress."
            )

            return False

        # Stop scan before GATT connection.
        if self.scanning:

            self.stop_scan()

        try:

            # Close stale GATT.
            if self.gatt is not None:

                self.log(
                    "CONNECT: Closing stale GATT..."
                )

                self._close_gatt()

            self._create_gatt_callback()

            self.connection_generation += 1

            self.connecting = True
            self.ready = False
            self.connected = False
            self.notifications_enabled = False

            self.log(
                f"CONNECTING TO AVA | "
                f"{self.found_name or AVA_NAME} | "
                f"{self.found_address or 'UNKNOWN'}"
            )

            # Android 10+
            #
            # connectGatt(Context, boolean, Callback)
            #
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
                    "CONNECT ERROR: connectGatt() returned NULL."
                )

                return False

            self.log(
                "GATT CONNECTION REQUESTED."
            )

            return True

        except Exception as exc:

            self.connecting = False

            self.log(
                f"CONNECT ERROR: {exc}"
            )

            return False

    # ========================================================
    # ENABLE EVENT NOTIFICATIONS
    # ========================================================

    def enable_notifications(self):

        if self.gatt is None:

            self.log(
                "NOTIFY ERROR: GATT unavailable."
            )

            return

        if self.event_characteristic is None:

            self.log(
                "NOTIFY ERROR: EVENT characteristic missing."
            )

            return

        if self.descriptor_write_busy:

            self.log(
                "NOTIFY: CCCD write already in progress."
            )

            return

        try:

            # Local notification registration.
            enabled = (
                self.gatt.setCharacteristicNotification(
                    self.event_characteristic,
                    True
                )
            )

            if not enabled:

                self.log(
                    "NOTIFY ERROR: "
                    "setCharacteristicNotification() failed."
                )

                return

            UUID = self.autoclass(
                "java.util.UUID"
            )

            descriptor_uuid = UUID.fromString(
                CCCD_UUID
            )

            descriptor = (
                self.event_characteristic.getDescriptor(
                    descriptor_uuid
                )
            )

            if descriptor is None:

                self.log(
                    "NOTIFY ERROR: CCCD NOT FOUND."
                )

                return

            self.event_descriptor = descriptor

            BluetoothGattDescriptor = self.autoclass(
                "android.bluetooth.BluetoothGattDescriptor"
            )

            descriptor_value = (
                BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            )

            descriptor.setValue(
                descriptor_value
            )

            self.descriptor_write_busy = True

            started = (
                self.gatt.writeDescriptor(
                    descriptor
                )
            )

            if not started:

                self.descriptor_write_busy = False

                self.log(
                    "NOTIFY ERROR: writeDescriptor() failed."
                )

                return

            self.log(
                "CCCD WRITE REQUESTED."
            )

        except Exception as exc:

            self.descriptor_write_busy = False

            self.log(
                f"NOTIFICATION SETUP ERROR: {exc}"
            )

    # ========================================================
    # COMMAND QUEUE
    # ========================================================

    def write_command(self, command):

        if not self.ready:

            self.log(
                "COMMAND BLOCKED: AVA is not READY."
            )

            return False

        if not command:

            return False

        command = str(command).strip()

        if not command:

            return False

        self.command_queue.append(
            command
        )

        self.log(
            f"COMMAND QUEUED → {command}"
        )

        self._process_command_queue()

        return True

    # ========================================================
    # PROCESS COMMAND QUEUE
    # ========================================================

    def _process_command_queue(self):

        if not self.ready:
            return

        if not self.connected:
            return

        if self.gatt is None:
            return

        if self.command_characteristic is None:
            return

        if self.command_write_busy:
            return

        if not self.command_queue:
            return

        command = (
            self.command_queue.popleft()
        )

        try:

            data = command.encode(
                "utf-8"
            )

            self.command_characteristic.setValue(
                data
            )

            BluetoothGattCharacteristic = (
                self.autoclass(
                    "android.bluetooth.BluetoothGattCharacteristic"
                )
            )

            self.command_characteristic.setWriteType(
                BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
            )

            self.command_write_busy = True

            started = (
                self.gatt.writeCharacteristic(
                    self.command_characteristic
                )
            )

            if not started:

                self.command_write_busy = False

                self.log(
                    f"COMMAND WRITE REQUEST FAILED → "
                    f"{command}"
                )

                # Try next queued command.
                Clock.schedule_once(
                    lambda *_:
                    self._process_command_queue(),
                    0
                )

                return

            self.log(
                f"COMMAND → {command}"
            )

        except Exception as exc:

            self.command_write_busy = False

            self.log(
                f"COMMAND WRITE ERROR: {exc}"
            )

            Clock.schedule_once(
                lambda *_:
                self._process_command_queue(),
                0
            )

    # ========================================================
    # DISCONNECT
    # ========================================================

    def disconnect(self):

        self.command_queue.clear()
        self.command_write_busy = False

        if self.gatt is None:

            self.connected = False
            self.ready = False
            self.connecting = False

            self.log(
                "DISCONNECT: No active GATT."
            )

            return

        try:

            self.log(
                "GATT DISCONNECT REQUESTED."
            )

            self.gatt.disconnect()

        except Exception as exc:

            self.log(
                f"DISCONNECT ERROR: {exc}"
            )

    # ========================================================
    # CLOSE GATT
    # ========================================================

    def _close_gatt(self):

        old_gatt = self.gatt

        self.gatt = None
        self.connected = False
        self.ready = False
        self.connecting = False
        self.notifications_enabled = False

        self.command_write_busy = False
        self.descriptor_write_busy = False

        self.command_characteristic = None
        self.event_characteristic = None
        self.event_descriptor = None
        self.service = None

        if old_gatt is None:
            return

        try:
            old_gatt.disconnect()
        except Exception:
            pass

        try:
            old_gatt.close()
        except Exception:
            pass

    # ========================================================
    # PUBLIC STATUS
    # ========================================================

    def is_connected(self):

        return (
            self.connected
            and self.gatt is not None
        )

    def is_ready(self):

        return (
            self.ready
            and self.notifications_enabled
            and self.connected
        )


# ============================================================
# AVA PET APP
# ============================================================

class AvaPetApp(App):

    def build(self):

        self.title = "AVA PET"

        root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(8)
        )

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        root.add_widget(
            Label(
                text="[b]AVA PET[/b]",
                markup=True,
                font_size=dp(28),
                size_hint_y=None,
                height=dp(55)
            )
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status_label = Label(
            text="🔴 Disconnected",
            font_size=dp(18),
            size_hint_y=None,
            height=dp(42)
        )

        root.add_widget(
            self.status_label
        )

        # ----------------------------------------------------
        # CONNECTION CONTROLS
        # ----------------------------------------------------

        row = BoxLayout(
            size_hint_y=None,
            height=dp(50),
            spacing=dp(8)
        )

        scan_button = Button(
            text="SCAN"
        )

        scan_button.bind(
            on_release=lambda *_:
            self.ble.scan()
        )

        row.add_widget(
            scan_button
        )

        connect_button = Button(
            text="CONNECT"
        )

        connect_button.bind(
            on_release=lambda *_:
            self.connect_ava()
        )

        row.add_widget(
            connect_button
        )

        disconnect_button = Button(
            text="DISCONNECT"
        )

        disconnect_button.bind(
            on_release=lambda *_:
            self.disconnect_ava()
        )

        row.add_widget(
            disconnect_button
        )

        root.add_widget(
            row
        )

        # ----------------------------------------------------
        # EYES
        # ----------------------------------------------------

        root.add_widget(
            self.command_row(
                [
                    ("EYES_CALM", "CALM"),
                    ("EYES_HAPPY", "HAPPY"),
                    ("EYES_SAD", "SAD"),
                ]
            )
        )

        root.add_widget(
            self.command_row(
                [
                    ("EYES_SLEEPY", "SLEEPY"),
                    ("EYES_THINKING", "THINKING"),
                    ("EYES_LISTENING", "LISTENING"),
                ]
            )
        )

        root.add_widget(
            self.command_row(
                [
                    ("EYES_SURPRISED", "SURPRISED"),
                    ("BLINK", "BLINK"),
                    ("HELLO_AVA", "HELLO"),
                ]
            )
        )

        # ----------------------------------------------------
        # LOG
        # ----------------------------------------------------

        self.log_label = Label(
            text="AVA log:",
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

        # ----------------------------------------------------
        # BLE
        # ----------------------------------------------------

        self.ble = AndroidBLE(
            self.add_log
        )

        return root

    # ========================================================
    # COMMAND ROW
    # ========================================================

    def command_row(
        self,
        commands
    ):

        row = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            spacing=dp(6)
        )

        for command, title in commands:

            button = Button(
                text=title
            )

            button.bind(
                on_release=lambda btn,
                cmd=command:
                self.test_command(cmd)
            )

            row.add_widget(
                button
            )

        return row

    # ========================================================
    # CONNECT AVA
    # ========================================================

    def connect_ava(self):

        if not self.ble.has_ava():

            self.add_log(
                "CONNECT: Scan first."
            )

            return

        self.add_log(
            "AVA discovered."
        )

        self.status_label.text = (
            "🟡 Connecting..."
        )

        self.ble.connect()

    # ========================================================
    # DISCONNECT AVA
    # ========================================================

    def disconnect_ava(self):

        self.ble.disconnect()

        self.status_label.text = (
            "🔴 Disconnected"
        )

    # ========================================================
    # TEST COMMAND
    # ========================================================

    def test_command(
        self,
        command
    ):

        self.ble.write_command(
            command
        )

    # ========================================================
    # LOG
    # ========================================================

    def add_log(
        self,
        message
    ):

        message = str(message)

        # -----------------------------
        # Status
        # -----------------------------

        if message.startswith(
            "FOUND:"
        ):

            self.status_label.text = (
                "🟡 AVA FOUND"
            )

        elif (
            "GATT CONNECTED" in message
        ):

            self.status_label.text = (
                "🟢 AVA CONNECTED"
            )

        elif (
            "AVA READY" in message
        ):

            self.status_label.text = (
                "🟢 AVA READY"
            )

        elif (
            "GATT DISCONNECTED" in message
        ):

            self.status_label.text = (
                "🔴 Disconnected"
            )

        # -----------------------------
        # Log
        # -----------------------------

        if self.log_label.text == "AVA log:":

            self.log_label.text = ""

        self.log_label.text += (
            "\n" + message
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
    # PERMISSIONS
    # ========================================================

    def on_start(self):

        try:

            from android.permissions import (
                request_permissions,
                Permission
            )

            sdk = self.ble.android_sdk()

            permissions = []

            # ---------------------------------------------
            # Android 12+
            # ---------------------------------------------

            if sdk >= 31:

                permissions.extend(
                    [
                        Permission.BLUETOOTH_SCAN,
                        Permission.BLUETOOTH_CONNECT,
                    ]
                )

                self.add_log(
                    "Requesting Android 12+ BLE permissions..."
                )

            # ---------------------------------------------
            # Android 10 / 11
            # ---------------------------------------------

            else:

                permissions.extend(
                    [
                        Permission.BLUETOOTH,
                        Permission.BLUETOOTH_ADMIN,
                        Permission.ACCESS_FINE_LOCATION,
                    ]
                )

                self.add_log(
                    "Requesting Android 10/11 BLE permissions..."
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
