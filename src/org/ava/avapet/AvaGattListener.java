package org.ava.avapet;

import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;

public interface AvaGattListener {
    void onConnectionStateChange(BluetoothGatt gatt, int status, int newState);
    void onServicesDiscovered(BluetoothGatt gatt, int status);
    void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic);
    void onCharacteristicWrite(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic, int status);
    void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor descriptor, int status);
}
