import threading
from typing import Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView


# ============================================================
# AVA BLE
# Android 11 native BLE + GATT
# ============================================================

AVA_NAME = "AVA"

SERVICE_UUID = (
    "7b7a0001-6a76-4156-9a76-415641000001"
)

COMMAND_UUID = (
    "7b7a0002-6a76-4156-9a76-415641000001"
)

EVENT_UUID = (
    "7b7a0003-6a76-4156-9a76-415641000001"
)


class AndroidBLE:

    def __init__(self, logger):
        self.logger = logger

        self.adapter = None
        self.scanning = False

        self.found_device = None
        self.found_address = None

        self.context = None
        self.scan_callback = None

        # GATT
        self.gatt = None
        self.service = None
        self.command_characteristic = None
        self.event_characteristic = None

        self.connected = False
        self.notifications_enabled = False

        self._initialize_android()

    # --------------------------------------------------------
    # Logger
    # --------------------------------------------------------

    def log(self, message):
        Clock.schedule_once(
            lambda *_: self.logger(message)
        )

    # --------------------------------------------------------
    # Android initialization
    # --------------------------------------------------------

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
                    "Bluetooth is not available."
                )

                return

            self.log(
                "Android Bluetooth API initialized."
            )

        except Exception as exc:

            self.log(
                f"Android Bluetooth initialization error: {exc}"
            )

    # --------------------------------------------------------
    # Scan callback
    # --------------------------------------------------------

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

                    name = device.getName()
                    address = device.getAddress()

                    if name is None:
                        return

                    name_upper = str(
                        name
                    ).upper()

                    if (
                        name_upper == AVA_NAME
                        or AVA_NAME in name_upper
                    ):

                        outer.found_device = device

                        outer.found_address = str(
                            address
                        )

                        outer.scanning = False

                        outer.log(
                            f"FOUND: {name} | {address}"
                        )

                        try:

                            outer.adapter.stopLeScan(
                                self
                            )

                        except Exception:
                            pass

                except Exception as exc:

                    outer.log(
                        f"SCAN CALLBACK ERROR: {exc}"
                    )

        self.scan_callback = ScanCallback()

    # --------------------------------------------------------
    # Scan
    # --------------------------------------------------------

    def scan(self):

        if self.adapter is None:

            self.log(
                "Bluetooth adapter unavailable."
            )

            return

        if self.scanning:

            self.log(
                "Already scanning..."
            )

            return

        if not self.adapter.isEnabled():

            self.log(
                "Please turn Bluetooth ON."
            )

            return

        self.found_device = None
        self.found_address = None

        self._create_scan_callback()

        try:

            self.log(
                "Scanning for AVA..."
            )

            started = self.adapter.startLeScan(
                self.scan_callback
            )

            if not started:

                self.log(
                    "Android BLE scan failed to start."
                )

                return

            self.scanning = True

            Clock.schedule_once(
                self.stop_scan,
                8
            )

        except Exception as exc:

            self.scanning = False

            self.log(
                f"SCAN ERROR: {exc}"
            )

    # --------------------------------------------------------
    # Stop scan
    # --------------------------------------------------------

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
                "AVA not found."
            )

        else:

            self.log(
                "Scan finished."
            )

    # --------------------------------------------------------
    # Current discovered device
    # --------------------------------------------------------

    def has_ava(self):

        return (
            self.found_device is not None
        )

    # --------------------------------------------------------
    # GATT callback
    # --------------------------------------------------------

    def _create_gatt_callback(self):

        PythonJavaClass = self.PythonJavaClass
        java_method = self.java_method

        outer = self

        class GattCallback(PythonJavaClass):

            __javainterfaces__ = [
                "android/bluetooth/BluetoothGattCallback"
            ]

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

                    BluetoothProfile = outer.autoclass(
                        "android.bluetooth.BluetoothProfile"
                    )

                    connected_state = (
                        BluetoothProfile.STATE_CONNECTED
                    )

                    disconnected_state = (
                        BluetoothProfile.STATE_DISCONNECTED
                    )

                    if (
                        newState ==
                        connected_state
                    ):

                        outer.gatt = gatt
                        outer.connected = True

                        outer.log(
                            f"CONNECTED | GATT status={status}"
                        )

                        try:

                            gatt.discoverServices()

                            outer.log(
                                "Service discovery started."
                            )

                        except Exception as exc:

                            outer.log(
                                f"Service discovery error: {exc}"
                            )

                    elif (
                        newState ==
                        disconnected_state
                    ):

                        outer.connected = False
                        outer.notifications_enabled = False

                        outer.command_characteristic = None
                        outer.event_characteristic = None
                        outer.service = None

                        outer.log(
                            f"Disconnected | GATT status={status}"
                        )

                        try:

                            gatt.close()

                        except Exception:
                            pass

                        outer.gatt = None

                except Exception as exc:

                    outer.log(
                        f"GATT STATE ERROR: {exc}"
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

                    if status != 0:

                        outer.log(
                            f"Service discovery failed | status={status}"
                        )

                        return

                    outer.log(
                        "Services discovered."
                    )

                    service_uuid = (
                        outer.autoclass(
                            "java.util.UUID"
                        ).fromString(
                            SERVICE_UUID
                        )
                    )

                    command_uuid = (
                        outer.autoclass(
                            "java.util.UUID"
                        ).fromString(
                            COMMAND_UUID
                        )
                    )

                    event_uuid = (
                        outer.autoclass(
                            "java.util.UUID"
                        ).fromString(
                            EVENT_UUID
                        )
                    )

                    service = (
                        gatt.getService(
                            service_uuid
                        )
                    )

                    if service is None:

                        outer.log(
                            "AVA service NOT found."
                        )

                        return

                    outer.service = service

                    outer.log(
                        "AVA service found."
                    )

                    command_characteristic = (
                        service.getCharacteristic(
                            command_uuid
                        )
                    )

                    event_characteristic = (
                        service.getCharacteristic(
                            event_uuid
                        )
                    )

                    if command_characteristic is None:

                        outer.log(
                            "COMMAND characteristic NOT found."
                        )

                        return

                    if event_characteristic is None:

                        outer.log(
                            "EVENT characteristic NOT found."
                        )

                        return

                    outer.command_characteristic = (
                        command_characteristic
                    )

                    outer.event_characteristic = (
                        event_characteristic
                    )

                    outer.log(
                        "COMMAND characteristic found."
                    )

                    outer.log(
                        "EVENT characteristic found."
                    )

                    outer.enable_notifications()

                except Exception as exc:

                    outer.log(
                        f"SERVICE DISCOVERY ERROR: {exc}"
                    )

            @java_method(
                "(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;)V"
            )
            def onCharacteristicChanged(
                self,
                gatt,
                characteristic
            ):

                try:

                    uuid = str(
                        characteristic.getUuid()
                    )

                    value = (
                        characteristic.getValue()
                    )

                    if value is None:
                        return

                    data = bytes(
                        [
                            int(x)
                            for x in value
                        ]
                    )

                    try:

                        text = data.decode(
                            "utf-8",
                            errors="replace"
                        )

                    except Exception:

                        text = str(
                            data
                        )

                    outer.log(
                        f"EVENT ← {uuid} | {text}"
                    )

                except Exception as exc:

                    outer.log(
                        f"NOTIFY ERROR: {exc}"
                    )

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

                    if status == 0:

                        outer.log(
                            f"WRITE OK | {uuid}"
                        )

                    else:

                        outer.log(
                            f"WRITE FAILED | {uuid} | status={status}"
                        )

                except Exception as exc:

                    outer.log(
                        f"WRITE CALLBACK ERROR: {exc}"
                    )

        self.gatt_callback = GattCallback()

    # --------------------------------------------------------
    # Connect
    # --------------------------------------------------------

    def connect(self):

        if self.found_device is None:

            self.log(
                "No AVA device discovered."
            )

            return False

        try:

            self._create_gatt_callback()

            BluetoothDevice = self.autoclass(
                "android.bluetooth.BluetoothDevice"
            )

            self.log(
                f"Connecting to {self.found_address}..."
            )

            # Android 11 / API 30:
            # connectGatt(Context, autoConnect, callback)

            self.gatt = (
                self.found_device.connectGatt(
                    self.context,
                    False,
                    self.gatt_callback
                )
            )

            if self.gatt is None:

                self.log(
                    "connectGatt() returned NULL."
                )

                return False

            self.log(
                "GATT connection requested."
            )

            return True

        except Exception as exc:

            self.log(
                f"CONNECT ERROR: {exc}"
            )

            return False

    # --------------------------------------------------------
    # Enable notifications
    # --------------------------------------------------------

    def enable_notifications(self):

        if self.gatt is None:

            self.log(
                "Cannot enable notifications: no GATT."
            )

            return

        if self.event_characteristic is None:

            self.log(
                "Cannot enable notifications: EVENT missing."
            )

            return

        try:

            descriptor_uuid = (
                self.autoclass(
                    "java.util.UUID"
                ).fromString(
                    "00002902-0000-1000-8000-00805f9b34fb"
                )
            )

            descriptor = (
                self.event_characteristic.getDescriptor(
                    descriptor_uuid
                )
            )

            if descriptor is None:

                self.log(
                    "CCCD descriptor NOT found."
                )

                return

            enabled = self.gatt.setCharacteristicNotification(
                self.event_characteristic,
                True
            )

            if not enabled:

                self.log(
                    "setCharacteristicNotification() failed."
                )

                return

            BluetoothGattDescriptor = self.autoclass(
                "android.bluetooth.BluetoothGattDescriptor"
            )

            value = (
                BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            )

            descriptor.setValue(
                value
            )

            started = self.gatt.writeDescriptor(
                descriptor
            )

            if started:

                self.notifications_enabled = True

                self.log(
                    "EVENT notifications enabled."
                )

            else:

                self.log(
                    "Failed to write CCCD."
                )

        except Exception as exc:

            self.log(
                f"NOTIFICATION ERROR: {exc}"
            )

    # --------------------------------------------------------
    # Write command
    # --------------------------------------------------------

    def write_command(self, command):

        if not self.connected:

            self.log(
                "Cannot send command: AVA not connected."
            )

            return False

        if self.gatt is None:

            self.log(
                "Cannot send command: GATT unavailable."
            )

            return False

        if self.command_characteristic is None:

            self.log(
                "Cannot send command: COMMAND characteristic unavailable."
            )

            return False

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

            write_type = (
                BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
            )

            self.command_characteristic.setWriteType(
                write_type
            )

            started = self.gatt.writeCharacteristic(
                self.command_characteristic
            )

            if started:

                self.log(
                    f"COMMAND → {command}"
                )

                return True

            self.log(
                f"COMMAND WRITE FAILED → {command}"
            )

            return False

        except Exception as exc:

            self.log(
                f"COMMAND WRITE ERROR: {exc}"
            )

            return False

    # --------------------------------------------------------
    # Disconnect
    # --------------------------------------------------------

    def disconnect(self):

        if self.gatt is None:

            self.connected = False

            self.log(
                "No active GATT connection."
            )

            return

        try:

            self.gatt.disconnect()

            self.log(
                "GATT disconnect requested."
            )

        except Exception as exc:

            self.log(
                f"DISCONNECT ERROR: {exc}"
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
        # Title
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
        # Status
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
        # Scan / Connect row
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
        # Eye controls
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
        # Log
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

    # --------------------------------------------------------
    # Command row
    # --------------------------------------------------------

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

            # Commandها عمداً بدون هیچ تغییری نگه داشته شده‌اند.

            button.bind(
                on_release=lambda btn,
                cmd=command:
                self.test_command(cmd)
            )

            row.add_widget(
                button
            )

        return row

    # --------------------------------------------------------
    # Connect
    # --------------------------------------------------------

    def connect_ava(self):

        if not self.ble.has_ava():

            self.add_log(
                "Scan first."
            )

            return

        self.add_log(
            "AVA discovered."
        )

        self.ble.connect()

    # --------------------------------------------------------
    # Disconnect
    # --------------------------------------------------------

    def disconnect_ava(self):

        self.ble.disconnect()

        self.status_label.text = (
            "🔴 Disconnected"
        )

    # --------------------------------------------------------
    # Command test
    # --------------------------------------------------------

    def test_command(
        self,
        command
    ):

        self.ble.write_command(
            command
        )

    # --------------------------------------------------------
    # Log
    # --------------------------------------------------------

    def add_log(
        self,
        message
    ):

        if message.startswith(
            "FOUND:"
        ):

            self.status_label.text = (
                "🟡 AVA FOUND"
            )

        if (
            "CONNECTED" in message
        ):

            self.status_label.text = (
                "🟢 AVA CONNECTED"
            )

        if (
            "Disconnected" in message
        ):

            self.status_label.text = (
                "🔴 Disconnected"
            )

        if self.log_label.text == "AVA log:":

            self.log_label.text = ""

        self.log_label.text += (
            "\n" + message
        )

    def update_log_height(
        self,
        widget,
        texture_size
    ):

        widget.height = max(
            texture_size[1],
            dp(120)
        )

    # --------------------------------------------------------
    # Permissions
    # --------------------------------------------------------

    def on_start(self):

        try:

            from android.permissions import (
                request_permissions,
                Permission
            )

            request_permissions(
                [
                    Permission.BLUETOOTH,
                    Permission.BLUETOOTH_ADMIN,
                    Permission.ACCESS_FINE_LOCATION
                ]
            )

            self.add_log(
                "Android 11 BLE permissions requested."
            )

        except Exception as exc:

            self.add_log(
                f"Permission error: {exc}"
            )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    AvaPetApp().run()
