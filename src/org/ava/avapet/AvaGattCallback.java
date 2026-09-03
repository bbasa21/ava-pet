package org.ava.avapet;

import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.util.Base64;

import org.kivy.android.PythonActivity;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** Pure-Java BLE callback. Python polls drainEvents(); no custom interface. */
public final class AvaGattCallback extends BluetoothGattCallback {
    private static final UUID SERVICE_UUID = UUID.fromString("7b7a0001-6a76-4156-9a76-415641000001");
    private static final UUID EVENT_UUID = UUID.fromString("7b7a0003-6a76-4156-9a76-415641000001");
    private static final UUID DATA_UUID = UUID.fromString("7b7a0005-6a76-4156-9a76-415641000001");
    private static final UUID CCCD_UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
    private static final int REQUESTED_MTU = 247;

    private final List<String> events = new ArrayList<>();
    private BluetoothGatt currentGatt;
    private int reconnectAttempts = 0;
    private boolean mtuRequested = false;

    private synchronized void push(String event) { events.add(event); }

    public synchronized String[] drainEvents() {
        String[] result = events.toArray(new String[0]);
        events.clear();
        return result;
    }

    public synchronized BluetoothGatt getGatt() { return currentGatt; }

    @Override
    public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
        currentGatt = gatt;

        if (newState == BluetoothGatt.STATE_CONNECTED) {
            reconnectAttempts = 0;
            mtuRequested = false;
            push("STATE|" + status + "|" + newState);

            // Android ATT defaults to a 23-byte MTU, which leaves only 20
            // bytes for an attribute value. AVA commands can exceed 20 bytes
            // (for example GAME_LOAD|MATH_BATTLE is 21 bytes), so negotiate a
            // larger MTU before service discovery and before Python can mark
            // the GATT connection ready for writes.
            try {
                if (gatt != null && gatt.requestMtu(REQUESTED_MTU)) {
                    mtuRequested = true;
                    push("MTU_REQUESTED|" + REQUESTED_MTU);
                    return;
                }
            } catch (Exception ignored) {
            }

            // If MTU negotiation cannot be requested, keep the connection
            // usable and continue with the existing discovery flow.
            discoverServices(gatt);
            return;
        }

        // Android BLE can occasionally report a transient GATT error (most
        // notably 133). Recreate the GATT connection explicitly over LE
        // instead of retrying the same failed transport session.
        if (newState == BluetoothGatt.STATE_DISCONNECTED
                && status != BluetoothGatt.GATT_SUCCESS
                && reconnectAttempts < 2) {
            reconnectAttempts++;

            final BluetoothGatt failedGatt = gatt;
            final BluetoothDevice device = gatt == null ? null : gatt.getDevice();
            final int attempt = reconnectAttempts;

            new Thread(() -> {
                try {
                    Thread.sleep(600L);

                    if (failedGatt != null) {
                        try {
                            failedGatt.close();
                        } catch (Exception ignored) {
                        }
                    }

                    if (device != null && PythonActivity.mActivity != null) {
                        BluetoothGatt retryGatt = device.connectGatt(
                                PythonActivity.mActivity,
                                false,
                                this,
                                BluetoothDevice.TRANSPORT_LE
                        );
                        synchronized (AvaGattCallback.this) {
                            currentGatt = retryGatt;
                        }
                    }
                } catch (Exception ignored) {
                }
            }).start();

            push("RETRY|" + status + "|" + attempt);
            return;
        }

        push("STATE|" + status + "|" + newState);
    }

    @Override
    public void onMtuChanged(BluetoothGatt gatt, int mtu, int status) {
        currentGatt = gatt;
        mtuRequested = false;
        push("MTU|" + mtu + "|" + status);

        // Service discovery happens only after the MTU exchange completes.
        // This guarantees that Python cannot become GATT-ready and send a
        // command while Android is still using the default 20-byte payload.
        discoverServices(gatt);
    }

    private void discoverServices(BluetoothGatt gatt) {
        try {
            if (gatt != null && gatt.discoverServices()) {
                push("SERVICES_REQUESTED");
            } else {
                push("SERVICES_REQUEST_FAILED");
            }
        } catch (Exception ignored) {
            push("SERVICES_REQUEST_FAILED");
        }
    }

    @Override
    public void onServicesDiscovered(BluetoothGatt gatt, int status) {
        currentGatt = gatt;
        push("SERVICES|" + status);
    }

    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic) {
        currentGatt = gatt;
        if (characteristic == null) { push("CHANGED||"); return; }
        String uuid = String.valueOf(characteristic.getUuid());
        byte[] value = characteristic.getValue();
        String encoded = value == null ? "" : Base64.encodeToString(value, Base64.NO_WRAP);
        push("CHANGED|" + uuid + "|" + encoded);
    }

    @Override
    public void onCharacteristicWrite(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic, int status) {
        currentGatt = gatt;
        String uuid = characteristic == null ? "UNKNOWN" : String.valueOf(characteristic.getUuid());
        push("WRITE|" + uuid + "|" + status);
    }

    @Override
    public void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor descriptor, int status) {
        currentGatt = gatt;

        String descriptorUuid = descriptor == null ? "UNKNOWN" : String.valueOf(descriptor.getUuid());
        BluetoothGattCharacteristic characteristic = descriptor == null ? null : descriptor.getCharacteristic();
        UUID characteristicUuid = characteristic == null ? null : characteristic.getUuid();

        // The Python side originally enabled only EVENT notifications. Keep
        // that public API intact, but once EVENT CCCD succeeds, automatically
        // enable DATA notifications as the second CCCD transaction. This is
        // required because AVA game messages arrive on DATA, not EVENT.
        if (status == BluetoothGatt.GATT_SUCCESS
                && characteristicUuid != null
                && characteristicUuid.equals(EVENT_UUID)) {
            if (enableDataNotifications(gatt)) {
                return;
            }
            // If DATA setup cannot even be requested, report the failure to
            // Python so AVA is not left apparently ready for games.
            push("DESCRIPTOR|" + EVENT_UUID + "|133");
            return;
        }

        if (characteristicUuid != null && characteristicUuid.equals(DATA_UUID)) {
            push("DESCRIPTOR|" + DATA_UUID + "|" + status);
            return;
        }

        push("DESCRIPTOR|" + descriptorUuid + "|" + status);
    }

    private boolean enableDataNotifications(BluetoothGatt gatt) {
        try {
            if (gatt == null) {
                return false;
            }

            BluetoothGattCharacteristic dataCharacteristic =
                    gatt.getService(SERVICE_UUID) == null
                            ? null
                            : gatt.getService(SERVICE_UUID).getCharacteristic(DATA_UUID);

            if (dataCharacteristic == null) {
                return false;
            }

            if (!gatt.setCharacteristicNotification(dataCharacteristic, true)) {
                return false;
            }

            BluetoothGattDescriptor dataDescriptor = dataCharacteristic.getDescriptor(CCCD_UUID);
            if (dataDescriptor == null) {
                return false;
            }

            dataDescriptor.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
            return gatt.writeDescriptor(dataDescriptor);
        } catch (Exception ignored) {
            return false;
        }
    }
}
