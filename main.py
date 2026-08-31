import base64
from collections import deque

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

AVA_NAME="AVA"
SERVICE_UUID="7b7a0001-6a76-4156-9a76-415641000001"
COMMAND_UUID="7b7a0002-6a76-4156-9a76-415641000001"
EVENT_UUID="7b7a0003-6a76-4156-9a76-415641000001"
CCCD_UUID="00002902-0000-1000-8000-00805f9b34fb"
GATT_SUCCESS=0
STATE_DISCONNECTED=0
STATE_CONNECTED=2
WRITE_TYPE_NO_RESPONSE=1
WRITE_TYPE_DEFAULT=2

class AndroidBLE:
    def __init__(self,logger):
        self.logger=logger; self.autoclass=None; self.context=None; self.adapter=None; self.sdk=30
        self.scan_callback=None; self.scanning=False; self.found_device=None; self.found_address=None; self.found_name=None
        self.gatt=None; self.gatt_callback=None; self.service=None; self.command_characteristic=None; self.event_characteristic=None; self.event_descriptor=None
        self.connected=False; self.connecting=False; self.ready=False; self.notifications_enabled=False
        self.command_queue=deque(); self.command_write_busy=False; self.descriptor_write_busy=False
        self._initialize_android(); Clock.schedule_interval(self._poll_java_events,0.05)

    def log(self,message):
        try: Clock.schedule_once(lambda *_: self.logger(str(message)))
        except Exception: pass

    def _initialize_android(self):
        try:
            from jnius import autoclass,PythonJavaClass,java_method
            self.autoclass=autoclass; self.PythonJavaClass=PythonJavaClass; self.java_method=java_method
            self.context=autoclass("org.kivy.android.PythonActivity").mActivity
            self.sdk=int(autoclass("android.os.Build$VERSION").SDK_INT)
            self.adapter=autoclass("android.bluetooth.BluetoothAdapter").getDefaultAdapter()
            if self.adapter is None: self.log("ERROR: BLUETOOTH ADAPTER UNAVAILABLE."); return
            self.log("ANDROID NATIVE BLE INITIALIZED."); self.log(f"ANDROID API LEVEL: {self.sdk}")
        except Exception as exc: self.log(f"ANDROID INIT ERROR: {exc}")

    def android_sdk(self): return self.sdk

    def _create_scan_callback(self):
        outer=self
        class ScanCallback(self.PythonJavaClass):
            __javainterfaces__=["android/bluetooth/BluetoothAdapter$LeScanCallback"]
            @self.java_method("(Landroid/bluetooth/BluetoothDevice;I[B)V")
            def onLeScan(self,device,rssi,scanRecord):
                try:
                    if device is None:return
                    try:name=device.getName()
                    except Exception:name=None
                    if name is None or AVA_NAME not in str(name).upper():return
                    try:address=str(device.getAddress())
                    except Exception:address="UNKNOWN"
                    outer.found_device=device; outer.found_name=str(name); outer.found_address=address; outer.scanning=False
                    outer.log(f"AVA FOUND | name={name} | address={address} | rssi={rssi}")
                    try:outer.adapter.stopLeScan(outer.scan_callback)
                    except Exception:pass
                except Exception as exc:outer.log(f"SCAN CALLBACK ERROR: {exc}")
        self.scan_callback=ScanCallback()

    def scan(self):
        if self.adapter is None:self.log("SCAN ERROR: BLUETOOTH UNAVAILABLE.");return
        if self.scanning:self.log("SCAN: ALREADY SCANNING.");return
        try:
            if not self.adapter.isEnabled():self.log("SCAN ERROR: BLUETOOTH IS OFF.");return
        except Exception as exc:self.log(f"SCAN ERROR: BLUETOOTH STATE CHECK FAILED: {exc}");return
        if self.gatt is not None:self._close_gatt()
        self.found_device=self.found_address=self.found_name=None; self.connected=self.connecting=self.ready=self.notifications_enabled=False
        self.command_queue.clear();self.command_write_busy=self.descriptor_write_busy=False;self._create_scan_callback()
        try:
            self.log("SCANNING FOR AVA...")
            if not self.adapter.startLeScan(self.scan_callback):self.log("SCAN ERROR: startLeScan() FAILED.");return
            self.scanning=True;Clock.schedule_once(self.stop_scan,10)
        except Exception as exc:self.scanning=False;self.log(f"SCAN ERROR: {exc}")

    def stop_scan(self,*_):
        if not self.scanning:return
        try:self.adapter.stopLeScan(self.scan_callback)
        except Exception:pass
        self.scanning=False;self.log("SCAN FINISHED: AVA NOT FOUND." if self.found_device is None else f"SCAN FINISHED: AVA FOUND | {self.found_address}")

    def has_ava(self):return self.found_device is not None

    def _create_java_gatt_callback(self):
        try:
            Callback=self.autoclass("org.ava.avapet.AvaGattCallback");self.gatt_callback=Callback();self.log("JAVA GATT CALLBACK BRIDGE INITIALIZED.");return True
        except Exception as exc:self.log(f"JAVA GATT CALLBACK INIT ERROR: {exc}");return False

    def connect(self):
        if self.found_device is None:self.log("CONNECT ERROR: SCAN FOR AVA FIRST.");return False
        if self.connected:self.log("CONNECT: AVA ALREADY CONNECTED.");return True
        if self.connecting:self.log("CONNECT: ALREADY IN PROGRESS.");return False
        if self.gatt is not None:self._close_gatt()
        if not self._create_java_gatt_callback():return False
        try:
            self.connecting=True;self.ready=False;self.notifications_enabled=False;self.command_write_busy=False;self.descriptor_write_busy=False
            self.log(f"GATT CONNECTION REQUESTED | {self.found_name or AVA_NAME} | {self.found_address}")
            self.gatt=self.found_device.connectGatt(self.context,False,self.gatt_callback)
            if self.gatt is None:self.connecting=False;self.log("CONNECT ERROR: connectGatt() RETURNED NULL.");return False
            self.log("GATT CONNECT REQUEST ACCEPTED.");return True
        except Exception as exc:self.connecting=False;self.log(f"CONNECT ERROR: {exc}");return False

    def _poll_java_events(self,*_):
        if self.gatt_callback is None:return
        try:
            for event in self.gatt_callback.drainEvents():self._handle_java_event(str(event))
        except Exception as exc:self.log(f"JAVA GATT EVENT POLL ERROR: {exc}")

    def _handle_java_event(self,event):
        parts=event.split("|",2);kind=parts[0] if parts else ""
        if kind=="STATE":
            status=int(parts[1]) if len(parts)>1 else -1;state=int(parts[2]) if len(parts)>2 else -1
            self.log(f"GATT STATE CHANGE | status={status} | state={state}")
            if state==STATE_CONNECTED:
                try:self.gatt=self.gatt_callback.getGatt()
                except Exception:pass
                self.connected=True;self.connecting=False;self.ready=False;self.notifications_enabled=False;self.log("GATT CONNECTED")
                try:self.log("SERVICE DISCOVERY STARTED." if self.gatt.discoverServices() else "SERVICE DISCOVERY REQUEST FAILED.")
                except Exception as exc:self.log(f"SERVICE DISCOVERY ERROR: {exc}")
            elif state==STATE_DISCONNECTED:
                self.connected=self.connecting=self.ready=self.notifications_enabled=False;self.command_write_busy=self.descriptor_write_busy=False
                self.service=self.command_characteristic=self.event_characteristic=self.event_descriptor=None;self.log(f"GATT DISCONNECTED | status={status}")
                if status!=GATT_SUCCESS:self.log(f"GATT DISCONNECT ERROR CODE: {status}")
                try:
                    if self.gatt is not None:self.gatt.close()
                except Exception:pass
                self.gatt=None
        elif kind=="SERVICES":
            status=int(parts[1]) if len(parts)>1 else -1;self.log(f"SERVICE DISCOVERY RESULT | status={status}")
            if status!=GATT_SUCCESS or self.gatt is None:self.log("SERVICE DISCOVERY FAILED.");return
            try:
                UUID=self.autoclass("java.util.UUID");self.service=self.gatt.getService(UUID.fromString(SERVICE_UUID))
                if self.service is None:self.log("ERROR: AVA SERVICE NOT FOUND.");return
                self.log("AVA SERVICE FOUND.");self.command_characteristic=self.service.getCharacteristic(UUID.fromString(COMMAND_UUID));self.event_characteristic=self.service.getCharacteristic(UUID.fromString(EVENT_UUID))
                if self.command_characteristic is None:self.log("ERROR: COMMAND CHARACTERISTIC NOT FOUND.");return
                if self.event_characteristic is None:self.log("ERROR: EVENT CHARACTERISTIC NOT FOUND.");return
                self.log("COMMAND CHARACTERISTIC FOUND.");self.log("EVENT CHARACTERISTIC FOUND.");self.enable_notifications()
            except Exception as exc:self.log(f"SERVICE DISCOVERY CALLBACK ERROR: {exc}")
        elif kind=="CHANGED":
            uuid=parts[1] if len(parts)>1 else "UNKNOWN";encoded=parts[2] if len(parts)>2 else ""
            try:text=base64.b64decode(encoded).decode("utf-8",errors="replace") if encoded else ""
            except Exception:text="<binary>"
            self.log(f"EVENT <- {uuid} | {text}")
        elif kind=="WRITE":
            uuid=parts[1] if len(parts)>1 else "UNKNOWN";status=int(parts[2]) if len(parts)>2 else -1;self.command_write_busy=False
            self.log(f"WRITE OK | {uuid}" if status==GATT_SUCCESS else f"WRITE FAILED | {uuid} | status={status}");self._process_command_queue()
        elif kind=="DESCRIPTOR":
            uuid=parts[1] if len(parts)>1 else "UNKNOWN";status=int(parts[2]) if len(parts)>2 else -1;self.descriptor_write_busy=False
            if status==GATT_SUCCESS:self.notifications_enabled=True;self.ready=True;self.log(f"CCCD WRITE OK | {uuid}");self.log("EVENT NOTIFICATIONS ENABLED.");self.log("AVA READY.");self._process_command_queue()
            else:self.notifications_enabled=self.ready=False;self.log(f"CCCD WRITE FAILED | {uuid} | status={status}")
        else:self.log(f"JAVA GATT EVENT UNKNOWN: {event}")

    def enable_notifications(self):
        if self.gatt is None or self.event_characteristic is None:self.log("NOTIFY ERROR: GATT/EVENT UNAVAILABLE.");return False
        try:
            if not self.gatt.setCharacteristicNotification(self.event_characteristic,True):self.log("NOTIFY ERROR: setCharacteristicNotification() FAILED.");return False
            UUID=self.autoclass("java.util.UUID");descriptor=self.event_characteristic.getDescriptor(UUID.fromString(CCCD_UUID))
            if descriptor is None:self.log("NOTIFY ERROR: CCCD NOT FOUND.");return False
            self.event_descriptor=descriptor;Descriptor=self.autoclass("android.bluetooth.BluetoothGattDescriptor");descriptor.setValue(Descriptor.ENABLE_NOTIFICATION_VALUE);self.descriptor_write_busy=True
            if not self.gatt.writeDescriptor(descriptor):self.descriptor_write_busy=False;self.log("NOTIFY ERROR: writeDescriptor() FAILED.");return False
            self.log("CCCD WRITE REQUESTED.");return True
        except Exception as exc:self.descriptor_write_busy=False;self.log(f"NOTIFICATION ERROR: {exc}");return False

    def write_command(self,command):
        if not self.connected:self.log("COMMAND ERROR: AVA NOT GATT CONNECTED.");return False
        if not self.ready:self.log("COMMAND ERROR: AVA GATT NOT READY.");return False
        command=str(command).strip()
        if not command:return False
        self.command_queue.append(command);self._process_command_queue();return True

    def _process_command_queue(self):
        if self.command_write_busy or not self.connected or not self.ready:return
        if self.gatt is None or self.command_characteristic is None or not self.command_queue:return
        command=self.command_queue.popleft()
        try:
            self.command_characteristic.setValue(command.encode("utf-8"));Characteristic=self.autoclass("android.bluetooth.BluetoothGattCharacteristic");props=int(self.command_characteristic.getProperties())
            if props & int(Characteristic.PROPERTY_WRITE_NO_RESPONSE):self.command_characteristic.setWriteType(WRITE_TYPE_NO_RESPONSE);name="WRITE_NO_RESPONSE"
            else:self.command_characteristic.setWriteType(WRITE_TYPE_DEFAULT);name="WRITE"
            self.command_write_busy=True
            if not self.gatt.writeCharacteristic(self.command_characteristic):self.command_write_busy=False;self.log(f"COMMAND WRITE REQUEST FAILED | {command} | {name}");Clock.schedule_once(lambda *_:self._process_command_queue(),.05);return
            self.log(f"COMMAND -> {command} | {name}")
            if name=="WRITE_NO_RESPONSE":Clock.schedule_once(self._release_no_response_write,.08)
        except Exception as exc:self.command_write_busy=False;self.log(f"COMMAND WRITE ERROR: {exc}");Clock.schedule_once(lambda *_:self._process_command_queue(),.05)

    def _release_no_response_write(self,*_):
        if self.command_write_busy:self.command_write_busy=False;self._process_command_queue()

    def _close_gatt(self):
        old=self.gatt;self.connected=self.connecting=self.ready=self.notifications_enabled=False;self.command_write_busy=self.descriptor_write_busy=False;self.service=self.command_characteristic=self.event_characteristic=self.event_descriptor=None;self.command_queue.clear();self.gatt=None
        try:
            if old is not None:old.disconnect()
        except Exception:pass
        try:
            if old is not None:old.close()
        except Exception:pass

    def disconnect(self):
        if self.gatt is None:self.log("DISCONNECT: NO ACTIVE GATT SESSION.");return
        self.log("GATT DISCONNECT REQUESTED.");self._close_gatt()

class AvaPetApp(App):
    def build(self):
        self.title="AVA PET";root=BoxLayout(orientation="vertical",padding=dp(12),spacing=dp(8));root.add_widget(Label(text="[b]AVA PET[/b]",markup=True,font_size=dp(28),size_hint_y=None,height=dp(55)));self.status_label=Label(text="DISCONNECTED",font_size=dp(18),size_hint_y=None,height=dp(42));root.add_widget(self.status_label)
        row=BoxLayout(size_hint_y=None,height=dp(50),spacing=dp(8))
        for title,cb in (("SCAN",self.ble_scan),("CONNECT",self.connect_ava),("DISCONNECT",self.disconnect_ava)):
            b=Button(text=title);b.bind(on_release=cb);row.add_widget(b)
        root.add_widget(row);root.add_widget(self.command_row((("EYES_CALM","CALM"),("EYES_HAPPY","HAPPY"),("EYES_SAD","SAD"))));root.add_widget(self.command_row((("EYES_SLEEPY","SLEEPY"),("EYES_THINKING","THINKING"),("EYES_LISTENING","LISTENING"))));root.add_widget(self.command_row((("EYES_SURPRISED","SURPRISED"),("BLINK","BLINK"),("HELLO_AVA","HELLO"))))
        self.log_label=Label(text="AVA log:",size_hint_y=None,halign="left",valign="top");self.log_label.bind(texture_size=self.update_log_height);scroll=ScrollView();scroll.add_widget(self.log_label);root.add_widget(scroll);self.ble=AndroidBLE(self.add_log);return root
    def ble_scan(self,*_):self.ble.scan()
    def command_row(self,commands):
        row=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(6))
        for command,title in commands:
            b=Button(text=title);b.bind(on_release=lambda _,cmd=command:self.test_command(cmd));row.add_widget(b)
        return row
    def connect_ava(self,*_):
        if not self.ble.has_ava():self.add_log("CONNECT: SCAN FOR AVA FIRST.");return
        self.add_log("AVA DISCOVERED. STARTING GATT CONNECTION...");self.status_label.text="CONNECTING...";self.ble.connect()
    def disconnect_ava(self,*_):self.ble.disconnect();self.status_label.text="DISCONNECTED"
    def test_command(self,command):self.ble.write_command(command)
    def add_log(self,message):
        text=str(message);upper=text.upper()
        if "AVA FOUND" in upper:self.status_label.text="AVA FOUND"
        if "GATT CONNECTION REQUESTED" in upper:self.status_label.text="CONNECTING..."
        if "GATT CONNECTED" in upper:self.status_label.text="GATT CONNECTED"
        if "AVA READY" in upper:self.status_label.text="AVA READY"
        if "GATT DISCONNECTED" in upper:self.status_label.text="DISCONNECTED"
        if self.log_label.text=="AVA log:":self.log_label.text=""
        self.log_label.text += "\n"+text
    def update_log_height(self,widget,texture_size):widget.height=max(texture_size[1],dp(120))
    def on_start(self):
        try:
            from android.permissions import request_permissions,Permission
            if self.ble.android_sdk()>=31:permissions=[Permission.BLUETOOTH_SCAN,Permission.BLUETOOTH_CONNECT];self.add_log("REQUESTING ANDROID 12+ BLE PERMISSIONS...")
            else:permissions=[Permission.BLUETOOTH,Permission.BLUETOOTH_ADMIN,Permission.ACCESS_FINE_LOCATION];self.add_log("REQUESTING ANDROID 10/11 BLE PERMISSIONS...")
            request_permissions(permissions)
        except Exception as exc:self.add_log(f"PERMISSION ERROR: {exc}")

if __name__=="__main__":AvaPetApp().run()
