package org.ava.avapet;

import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;

public final class AvaGattCallback extends BluetoothGattCallback {

    private final AvaGattListener listener;

    public AvaGattCallback(AvaGattListener listener) {
        this.listener = listener;
    }

    @Override
    public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
        if (listener != null) {
            listener.onConnectionStateChange(gatt, status, newState);
        }
    }

    @Override
    public void onServicesDiscovered(BluetoothGatt gatt, int status) {
        if (listener != null) {
            listener.onServicesDiscovered(gatt, status);
        }
    }

    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic) {
        if (listener != null) {
            listener.onCharacteristicChanged(gatt, characteristic);
        }
    }

    @Override
    public void onCharacteristicWrite(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic, int status) {
        if (listener != null) {
            listener.onCharacteristicWrite(gatt, characteristic, status);
        }
    }

    @Override
    public void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor descriptor, int status) {
        if (listener != null) {
            listener.onDescriptorWrite(gatt, descriptor, status);
        }
    }
}
