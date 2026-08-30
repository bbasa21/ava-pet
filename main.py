from collections import deque

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView


# ============================================================
# AVA PET - Native Android BLE / GATT
# Android 10+ (API 29+)
#
# IMPORTANT:
# BluetoothGattCallback is a Java ABSTRACT CLASS, not an
# interface. PyJNIus cannot implement it through
# __javainterfaces__. A small Java bridge in src/ is therefore
# used to extend BluetoothGattCallback correctly and forward
# events to a Python listener interface.
# ============================================================

AVA_NAME = "AVA"

SERVICE_UUID = "7b7a0001-6a76-4156-9a76-415641000001"
COMMAND_UUID = "7b7a0002-6a76-4156-9a76-415641000001"
EVENT_UUID = "7b7a0003-6a76-4156-9a76-415641000001"

CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"

GATT_SUCCESS = 0
STATE_DISCONNECTED = 0
STATE_CONNECTED = 2
WRITE_TYPE_NO_RESPONSE = 1
WRITE_TYPE_DEFAULT = 2


class AndroidBLE:

    def __init__(self, logger):
        self.logger = logger

        self.autoclass = None
        self.PythonJavaClass = None
        self.java_method = None
        self.context = None
        self.adapter = None

        self.scan_callback = None
        self.scanning = False
        self.found_device = None
        self.found_address = None
        self.found_name = None

        self.gatt = None
        self.gatt_callback = None
        self.gatt_listener = None

        self.service = None
        self.command_characteristic = None
        self.event_characteristic = None
        self.event_descriptor = None

        self.connected = False
        self.connecting = False
        self.ready = False
        self.notifications_enabled = False

        self.command_queue = deque()
        self.command_write_busy = False
        self.descriptor_write_busy = False

        self.connection_generation = 0

        self._initialize_android()

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    def log(self, message):
        try:
            Clock.schedule_once(lambda *_: self.logger(str(message)))
        except Exception:
            pass

    # --------------------------------------------------------
    # Android initialization
    # --------------------------------------------------------

    def _initialize_android(self):
        try:
            from jnius import autoclass, PythonJavaClass, java_method

            self.autoclass = autoclass
            self.PythonJavaClass = PythonJavaClass
            self.java_method = java_method

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            self.context = PythonActivity.mActivity

            BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
            self.adapter = BluetoothAdapter.getDefaultAdapter()

            if self.adapter is None:
                self.log("ERROR: Bluetooth adapter unavailable.")
                return

            self.log("Android native BLE initialized.")
            self.log(f"Android API level: {self.android_sdk()}")

        except Exception as exc:
            self.log(f"ANDROID INIT ERROR: {exc}")

    def android_sdk(self):
        try:
            BuildVersion = self.autoclass("android.os.Build$VERSION")
            return int(BuildVersion.SDK_INT)
        except Exception:
            return 30

    # --------------------------------------------------------
    # BLE scan callback
    # --------------------------------------------------------

    def _create_scan_callback(self):
        outer = self
        PythonJavaClass = self.PythonJavaClass
        java_method = self.java_method

        class ScanCallback(PythonJavaClass):
            __javainterfaces__ = [
                "android/bluetooth/BluetoothAdapter$LeScanCallback"
            ]

            @java_method("(Landroid/bluetooth/BluetoothDevice;I[B)V")
            def onLeScan(self, device, rssi, scanRecord):
                try:
                    if device is None:
                        return

                    try:
                        name = device.getName()
                    except Exception:
                        name = None

                    try:
                        address = device.getAddress()
                    except Exception:
                        address = None

                    if name is None:
                        return

                    text = str(name)
                    if AVA_NAME not in text.upper():
                        return

                    outer.found_device = device
                    outer.found_name = text
                    outer.found_address = str(address or "UNKNOWN")
                    outer.scanning = False

                    outer.log(
                        f"AVA FOUND | name={outer.found_name} | "
                        f"address={outer.found_address} | rssi={rssi}"
                    )

                    try:
                        outer.adapter.stopLeScan(outer.scan_callback)
                    except Exception:
                        pass

                except Exception as exc:
                    outer.log(f"SCAN CALLBACK ERROR: {exc}")

        self.scan_callback = ScanCallback()

    # --------------------------------------------------------
    # Scan
    # --------------------------------------------------------

    def scan(self):
        if self.adapter is None:
            self.log("SCAN ERROR: Bluetooth unavailable.")
            return

        if self.scanning:
            self.log("SCAN: Already scanning.")
            return

        try:
            if not self.adapter.isEnabled():
                self.log("SCAN ERROR: Bluetooth is OFF.")
                return
        except Exception as exc:
            self.log(f"SCAN ERROR: Bluetooth state check failed: {exc}")
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
        self.command_write_busy = False
        self.descriptor_write_busy = False

        self._create_scan_callback()

        try:
            self.log("SCANNING FOR AVA...")
            started = self.adapter.startLeScan(self.scan_callback)
            if not started:
                self.log("SCAN ERROR: startLeScan() failed.")
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
            if self.adapter is not None:
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

    # --------------------------------------------------------
    # Correct GATT bridge
    # --------------------------------------------------------

    def _create_gatt_listener(self):
        outer = self
        PythonJavaClass = self.PythonJavaClass
        java_method = self.java_method

        class GattListener(PythonJavaClass):
            __javainterfaces__ = ["org/ava/avapet/AvaGattListener"]

            @java_method("(Landroid/bluetooth/BluetoothGatt;II)V")
            def onConnectionStateChange(self, gatt, status, newState):
                try:
                    outer.log(
                        f"GATT STATE CHANGE | status={status} | state={newState}"
                    )

                    if newState == STATE_CONNECTED:
                        outer.gatt = gatt
                        outer.connected = True
                        outer.connecting = False
                        outer.ready = False
                        outer.notifications_enabled = False

                        outer.log("GATT CONNECTED")

                        try:
                            started = gatt.discoverServices()
                            outer.log(
                                "SERVICE DISCOVERY STARTED."
                                if started
                                else "SERVICE DISCOVERY REQUEST FAILED."
                            )
                        except Exception as exc:
                            outer.log(f"SERVICE DISCOVERY ERROR: {exc}")

                    elif newState == STATE_DISCONNECTED:
                        outer.connected = False
                        outer.connecting = False
                        outer.ready = False
                        outer.notifications_enabled = False
                        outer.command_write_busy = False
                        outer.descriptor_write_busy = False
                        outer.service = None
                        outer.command_characteristic = None
                        outer.event_characteristic = None
                        outer.event_descriptor = None

                        outer.log(f"GATT DISCONNECTED | status={status}")

                        try:
                            gatt.close()
                        except Exception:
                            pass

                        if outer.gatt is gatt:
                            outer.gatt = None

                        if status != GATT_SUCCESS:
                            outer.log(f"GATT DISCONNECT ERROR CODE: {status}")

                except Exception as exc:
                    outer.log(f"GATT STATE CALLBACK ERROR: {exc}")

            @java_method("(Landroid/bluetooth/BluetoothGatt;I)V")
            def onServicesDiscovered(self, gatt, status):
                try:
                    outer.log(f"SERVICE DISCOVERY RESULT | status={status}")

                    if status != GATT_SUCCESS:
                        outer.log("SERVICE DISCOVERY FAILED.")
                        return

                    outer.log("SERVICES DISCOVERED.")

                    UUID = outer.autoclass("java.util.UUID")
                    service = gatt.getService(UUID.fromString(SERVICE_UUID))

                    if service is None:
                        outer.log("ERROR: AVA SERVICE NOT FOUND.")
                        return

                    outer.service = service
                    outer.log("AVA SERVICE FOUND.")

                    command = service.getCharacteristic(UUID.fromString(COMMAND_UUID))
                    event = service.getCharacteristic(UUID.fromString(EVENT_UUID))

                    if command is None:
                        outer.log("ERROR: COMMAND CHARACTERISTIC NOT FOUND.")
                        return

                    if event is None:
                        outer.log("ERROR: EVENT CHARACTERISTIC NOT FOUND.")
                        return

                    outer.command_characteristic = command
                    outer.event_characteristic = event

                    outer.log("COMMAND CHARACTERISTIC FOUND.")
                    outer.log("EVENT CHARACTERISTIC FOUND.")

                    outer.enable_notifications()

                except Exception as exc:
                    outer.log(f"SERVICE DISCOVERY CALLBACK ERROR: {exc}")

            @java_method(
                "(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;)V"
            )
            def onCharacteristicChanged(self, gatt, characteristic):
                try:
                    if characteristic is None:
                        return

                    uuid = str(characteristic.getUuid())
                    value = characteristic.getValue()
                    if value is None:
                        return

                    data = bytes(int(x) & 0xFF for x in value)
                    text = data.decode("utf-8", errors="replace")
                    outer.log(f"EVENT <- {uuid} | {text}")

                except Exception as exc:
                    outer.log(f"NOTIFICATION CALLBACK ERROR: {exc}")

            @java_method(
                "(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;I)V"
            )
            def onCharacteristicWrite(self, gatt, characteristic, status):
                try:
                    outer.command_write_busy = False
                    uuid = str(characteristic.getUuid()) if characteristic else "UNKNOWN"

                    if status == GATT_SUCCESS:
                        outer.log(f"WRITE OK | {uuid}")
                    else:
                        outer.log(f"WRITE FAILED | {uuid} | status={status}")

                    outer._process_command_queue()

                except Exception as exc:
                    outer.command_write_busy = False
                    outer.log(f"WRITE CALLBACK ERROR: {exc}")

            @java_method(
                "(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattDescriptor;I)V"
            )
            def onDescriptorWrite(self, gatt, descriptor, status):
                try:
                    outer.descriptor_write_busy = False

                    if status == GATT_SUCCESS:
                        outer.notifications_enabled = True
                        outer.ready = True
                        outer.log("EVENT NOTIFICATIONS ENABLED.")
                        outer.log("AVA READY.")
                        outer._process_command_queue()
                    else:
                        outer.notifications_enabled = False
                        outer.ready = False
                        outer.log(f"CCCD WRITE FAILED | status={status}")

                except Exception as exc:
                    outer.descriptor_write_busy = False
                    outer.log(f"DESCRIPTOR CALLBACK ERROR: {exc}")

        self.gatt_listener = GattListener()

        AvaGattCallback = self.autoclass("org.ava.avapet.AvaGattCallback")
        self.gatt_callback = AvaGattCallback(self.gatt_listener)

    # --------------------------------------------------------
    # Connect
    # --------------------------------------------------------

    def connect(self):
        if self.found_device is None:
            self.log("CONNECT ERROR: Scan for AVA first.")
            return False

        if self.connected:
            self.log("CONNECT: AVA is already connected.")
            return True

        if self.connecting:
            self.log("CONNECT: Connection already in progress.")
            return False

        if self.gatt is not None:
            self._close_gatt()

        try:
            self.connection_generation += 1
            self.connecting = True
            self.ready = False
            self.notifications_enabled = False
            self.command_write_busy = False
            self.descriptor_write_busy = False

            self._create_gatt_listener()

            self.log(
                f"GATT CONNECTION REQUESTED | "
                f"{self.found_name or 'AVA'} | {self.found_address}"
            )

            # Android 10+ has this overload. autoConnect=False gives
            # an immediate direct connection attempt.
            self.gatt = self.found_device.connectGatt(
                self.context,
                False,
                self.gatt_callback
            )

            if self.gatt is None:
                self.connecting = False
                self.log("CONNECT ERROR: connectGatt() returned NULL.")
                return False

            self.log("GATT CONNECT REQUEST ACCEPTED.")
            return True

        except Exception as exc:
            self.connecting = False
            self.log(f"CONNECT ERROR: {exc}")
            return False

    # --------------------------------------------------------
    # Enable EVENT notifications
    # --------------------------------------------------------

    def enable_notifications(self):
        if self.gatt is None or self.event_characteristic is None:
            self.log("NOTIFY ERROR: GATT/EVENT unavailable.")
            return False

        if self.descriptor_write_busy:
            self.log("NOTIFY: CCCD write already in progress.")
            return False

        try:
            self.log("ENABLING EVENT NOTIFICATIONS...")

            enabled = self.gatt.setCharacteristicNotification(
                self.event_characteristic,
                True
            )

            if not enabled:
                self.log("NOTIFY ERROR: setCharacteristicNotification() failed.")
                return False

            UUID = self.autoclass("java.util.UUID")
            descriptor = self.event_characteristic.getDescriptor(
                UUID.fromString(CCCD_UUID)
            )

            if descriptor is None:
                self.log("NOTIFY ERROR: CCCD descriptor NOT FOUND.")
                return False

            self.event_descriptor = descriptor

            BluetoothGattDescriptor = self.autoclass(
                "android.bluetooth.BluetoothGattDescriptor"
            )

            descriptor.setValue(
                BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            )

            self.descriptor_write_busy = True
            started = self.gatt.writeDescriptor(descriptor)

            if not started:
                self.descriptor_write_busy = False
                self.log("NOTIFY ERROR: writeDescriptor() failed.")
                return False

            self.log("CCCD WRITE REQUESTED.")
            return True

        except Exception as exc:
            self.descriptor_write_busy = False
            self.log(f"NOTIFICATION ERROR: {exc}")
            return False

    # --------------------------------------------------------
    # Command queue
    # --------------------------------------------------------

    def write_command(self, command):
        if not self.connected:
            self.log("COMMAND ERROR: AVA is not GATT connected.")
            return False

        if not self.ready:
            self.log("COMMAND ERROR: AVA GATT is not ready yet.")
            return False

        command = str(command).strip()
        if not command:
            return False

        self.command_queue.append(command)
        self._process_command_queue()
        return True

    def _process_command_queue(self):
        if self.command_write_busy:
            return

        if not self.connected or not self.ready:
            return

        if self.gatt is None or self.command_characteristic is None:
            return

        if not self.command_queue:
            return

        command = self.command_queue.popleft()

        try:
            data = command.encode("utf-8")
            self.command_characteristic.setValue(data)

            BluetoothGattCharacteristic = self.autoclass(
                "android.bluetooth.BluetoothGattCharacteristic"
            )

            # AVA COMMAND supports WRITE and WRITE_NR.
            # Prefer WRITE_WITHOUT_RESPONSE to avoid unnecessary
            # ACK traffic, while still falling back to normal write
            # if the characteristic does not advertise WRITE_NR.
            props = int(self.command_characteristic.getProperties())

            PROPERTY_WRITE_NO_RESPONSE = int(
                BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE
            )

            if props & PROPERTY_WRITE_NO_RESPONSE:
                self.command_characteristic.setWriteType(
                    WRITE_TYPE_NO_RESPONSE
                )
                write_type_name = "WRITE_NO_RESPONSE"
            else:
                self.command_characteristic.setWriteType(
                    WRITE_TYPE_DEFAULT
                )
                write_type_name = "WRITE"

            self.command_write_busy = True

            started = self.gatt.writeCharacteristic(
                self.command_characteristic
            )

            if not started:
                self.command_write_busy = False
                self.log(
                    f"COMMAND WRITE REQUEST FAILED | {command} | {write_type_name}"
                )
                Clock.schedule_once(
                    lambda *_: self._process_command_queue(),
                    0.05
                )
                return

            self.log(f"COMMAND -> {command} | {write_type_name}")

            # WRITE_NO_RESPONSE may not generate onCharacteristicWrite
            # on every Android/device combination. Release the queue
            # after a short delay if it is still busy.
            if write_type_name == "WRITE_NO_RESPONSE":
                Clock.schedule_once(self._release_no_response_write, 0.08)

        except Exception as exc:
            self.command_write_busy = False
            self.log(f"COMMAND WRITE ERROR: {exc}")
            Clock.schedule_once(lambda *_: self._process_command_queue(), 0.05)

    def _release_no_response_write(self, *_):
        if self.command_write_busy:
            self.command_write_busy = False
            self._process_command_queue()

    # --------------------------------------------------------
    # Close GATT
    # --------------------------------------------------------

    def _close_gatt(self):
        old_gatt = self.gatt

        self.connected = False
        self.connecting = False
        self.ready = False
        self.notifications_enabled = False
        self.command_write_busy = False
        self.descriptor_write_busy = False
        self.service = None
        self.command_characteristic = None
        self.event_characteristic = None
        self.event_descriptor = None
        self.command_queue.clear()

        if old_gatt is not None:
            try:
                old_gatt.disconnect()
            except Exception:
                pass
            try:
                old_gatt.close()
            except Exception:
                pass

        self.gatt = None

    def disconnect(self):
        if self.gatt is None:
            self.connected = False
            self.connecting = False
            self.ready = False
            self.log("DISCONNECT: No active GATT session.")
            return

        self.log("GATT DISCONNECT REQUESTED.")
        self._close_gatt()


# ============================================================
# AVA PET UI
# ============================================================

class AvaPetApp(App):

    def build(self):
        self.title = "AVA PET"

        root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(8)
        )

        root.add_widget(Label(
            text="[b]AVA PET[/b]",
            markup=True,
            font_size=dp(28),
            size_hint_y=None,
            height=dp(55)
        ))

        self.status_label = Label(
            text="DISCONNECTED",
            font_size=dp(18),
            size_hint_y=None,
            height=dp(42)
        )
        root.add_widget(self.status_label)

        row = BoxLayout(
            size_hint_y=None,
            height=dp(50),
            spacing=dp(8)
        )

        scan_button = Button(text="SCAN")
        scan_button.bind(on_release=lambda *_: self.ble.scan())
        row.add_widget(scan_button)

        connect_button = Button(text="CONNECT")
        connect_button.bind(on_release=lambda *_: self.connect_ava())
        row.add_widget(connect_button)

        disconnect_button = Button(text="DISCONNECT")
        disconnect_button.bind(on_release=lambda *_: self.disconnect_ava())
        row.add_widget(disconnect_button)

        root.add_widget(row)

        root.add_widget(self.command_row([
            ("EYES_CALM", "CALM"),
            ("EYES_HAPPY", "HAPPY"),
            ("EYES_SAD", "SAD"),
        ]))

        root.add_widget(self.command_row([
            ("EYES_SLEEPY", "SLEEPY"),
            ("EYES_THINKING", "THINKING"),
            ("EYES_LISTENING", "LISTENING"),
        ]))

        root.add_widget(self.command_row([
            ("EYES_SURPRISED", "SURPRISED"),
            ("BLINK", "BLINK"),
            ("HELLO_AVA", "HELLO"),
        ]))

        self.log_label = Label(
            text="AVA log:",
            size_hint_y=None,
            halign="left",
            valign="top"
        )
        self.log_label.bind(texture_size=self.update_log_height)

        scroll = ScrollView()
        scroll.add_widget(self.log_label)
        root.add_widget(scroll)

        self.ble = AndroidBLE(self.add_log)
        return root

    def command_row(self, commands):
        row = BoxLayout(
            size_hint_y=None,
            height=dp(48),
            spacing=dp(6)
        )

        for command, title in commands:
            button = Button(text=title)
            button.bind(
                on_release=lambda btn, cmd=command: self.test_command(cmd)
            )
            row.add_widget(button)

        return row

    def connect_ava(self):
        if not self.ble.has_ava():
            self.add_log("CONNECT: Scan for AVA first.")
            return

        self.add_log("AVA DISCOVERED. STARTING GATT CONNECTION...")
        self.status_label.text = "CONNECTING..."
        self.ble.connect()

    def disconnect_ava(self):
        self.ble.disconnect()
        self.status_label.text = "DISCONNECTED"

    def test_command(self, command):
        self.ble.write_command(command)

    def add_log(self, message):
        text = str(message)
        upper = text.upper()

        if "AVA FOUND" in upper:
            self.status_label.text = "AVA FOUND"

        if "GATT CONNECTION REQUESTED" in upper:
            self.status_label.text = "CONNECTING..."

        if "GATT CONNECTED" in upper:
            self.status_label.text = "GATT CONNECTED"

        if "AVA READY" in upper:
            self.status_label.text = "AVA READY"

        if "GATT DISCONNECTED" in upper or "DISCONNECTED" in upper:
            if "GATT CONNECTED" not in upper:
                self.status_label.text = "DISCONNECTED"

        if self.log_label.text == "AVA log:":
            self.log_label.text = ""

        self.log_label.text += "\n" + text

    def update_log_height(self, widget, texture_size):
        widget.height = max(texture_size[1], dp(120))

    # --------------------------------------------------------
    # Android 10+ permissions
    # --------------------------------------------------------

    def on_start(self):
        try:
            from android.permissions import request_permissions, Permission

            sdk = self.ble.android_sdk()

            if sdk >= 31:
                permissions = [
                    Permission.BLUETOOTH_SCAN,
                    Permission.BLUETOOTH_CONNECT,
                ]
                self.add_log("REQUESTING Android 12+ BLE permissions...")
            else:
                permissions = [
                    Permission.BLUETOOTH,
                    Permission.BLUETOOTH_ADMIN,
                    Permission.ACCESS_FINE_LOCATION,
                ]
                self.add_log("REQUESTING Android 10/11 BLE permissions...")

            request_permissions(permissions)

        except Exception as exc:
            self.add_log(f"PERMISSION ERROR: {exc}")


if __name__ == "__main__":
    AvaPetApp().run()
