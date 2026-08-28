[app]

title = AVA PET
package.name = avapet
package.domain = org.ava

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt

version = 0.1

requirements = python3,kivy,pyjnius

orientation = portrait
fullscreen = 0

# Android 11 / API 30 target for the first prototype
android.api = 30
android.minapi = 23
android.ndk_path = /root/.buildozer/android/platform/android-ndk-r25b
# BLE permissions needed by this first Android-11 target.
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,ACCESS_FINE_LOCATION

android.archs = arm64-v8a

[buildozer]

log_level = 2
warn_on_root = 1
