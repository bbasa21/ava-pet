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

/** Pure-Java BLE callback. Python polls drainEvents(); no custom interface. */
public final class AvaGattCallback extends BluetoothGattCallback {
    private final List<String> events = new ArrayList<>();
    private BluetoothGatt currentGatt;
    private int reconnectAttempts = 0;

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
            push("STATE|" + status + "|" + newState);
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
        String uuid = descriptor == null ? "UNKNOWN" : String.valueOf(descriptor.getUuid());
        push("DESCRIPTOR|" + uuid + "|" + status);
    }
}
