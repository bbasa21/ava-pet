package org.ava.avapet;

import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.util.Base64;

import java.util.ArrayList;
import java.util.List;

/** Pure-Java BLE callback. Python polls drainEvents(); no custom interface. */
public final class AvaGattCallback extends BluetoothGattCallback {
    private final List<String> events = new ArrayList<>();

    private synchronized void push(String event) {
        events.add(event);
    }

    public synchronized String[] drainEvents() {
        String[] result = events.toArray(new String[0]);
        events.clear();
        return result;
    }

    @Override
    public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
        push("STATE|" + status + "|" + newState);
    }

    @Override
    public void onServicesDiscovered(BluetoothGatt gatt, int status) {
        push("SERVICES|" + status);
    }

    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic) {
        if (characteristic == null) {
            push("CHANGED||");
            return;
        }
        String uuid = String.valueOf(characteristic.getUuid());
        byte[] value = characteristic.getValue();
        String encoded = value == null ? "" : Base64.encodeToString(value, Base64.NO_WRAP);
        push("CHANGED|" + uuid + "|" + encoded);
    }

    @Override
    public void onCharacteristicWrite(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic, int status) {
        String uuid = characteristic == null ? "UNKNOWN" : String.valueOf(characteristic.getUuid());
        push("WRITE|" + uuid + "|" + status);
    }

    @Override
    public void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor descriptor, int status) {
        String uuid = descriptor == null ? "UNKNOWN" : String.valueOf(descriptor.getUuid());
        push("DESCRIPTOR|" + uuid + "|" + status);
    }
}
