[app]

# AVA PET Android application
title = AVA PET
package.name = avapet
package.domain = org.ava

# Project source
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt
source.exclude_dirs = .git,.github,.buildozer,.kivy,bin,__pycache__

version = 0.1

# Keep the Android Python runtime on Python 3.11 for this CI build.
# The newer p4a 2026.05.09 recipe builds CPython 3.14, whose Android
# sources require APIs newer than our previous API-23 configuration.
requirements = python3==3.11.5,kivy,pyjnius

orientation = portrait
fullscreen = 0

# Android target/minimum API.
android.api = 30
android.minapi = 23
android.ndk_api = 23

# GitHub Actions installs the SDK/NDK into this writable runner directory.
android.sdk_path = /home/runner/android-sdk
android.ndk_path = /home/runner/android-sdk/ndk/28.2.13676358
android.accept_sdk_license = True
android.skip_update = True

# Build only the architecture we need.
android.archs = arm64-v8a

# Bluetooth permissions for the current AVA PET BLE implementation.
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,ACCESS_FINE_LOCATION

# APK output.
android.release_artifact = apk
android.debug_artifact = apk

# Pin python-for-android to a known release whose Python recipe is 3.11.5.
# This avoids the Python 3.14 / Android API-23 preadv/pwritev failure.
p4a.fork = kivy
p4a.branch = v2024.01.21
p4a.commit = 957a3e5f8c270f7aa648ba185e5a68c1077a798d

[buildozer]

# Keep CI logs useful without dumping every compiler command.
log_level = 1
warn_on_root = 1
