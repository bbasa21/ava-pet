[app]

# AVA PET Android application
title = AVA PET
package.name = avapet
package.domain = org.ava
version = 0.2

# Project source
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt
source.exclude_dirs = .git,.github,.buildozer,.kivy,bin,__pycache__

# Java BLE bridge. Buildozer passes this directory to
# python-for-android with --add-source.
android.add_src = src

# Python runtime
requirements = python3==3.11.5,kivy==2.3.1,pyjnius==1.6.1,filetype==1.2.0

orientation = portrait
fullscreen = 0

# Android 10+ = API 29+
android.api = 30
android.minapi = 29
android.ndk_api = 29

android.accept_sdk_license = True

# Current Android phone architecture
android.archs = arm64-v8a

# Android 10/11 permissions. The Python code requests the newer
# Bluetooth permissions on Android 12+ when the platform exposes them.
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,ACCESS_FINE_LOCATION,BLUETOOTH_SCAN,BLUETOOTH_CONNECT

android.release_artifact = apk
android.debug_artifact = apk

# Known compatible python-for-android release
p4a.fork = kivy
p4a.branch = v2024.01.21
p4a.commit = 957a3e5f8c270f7aa648ba185e5a68c1077a798d

[buildozer]

log_level = 1
warn_on_root = 1
