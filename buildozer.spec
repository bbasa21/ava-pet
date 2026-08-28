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

# Android Python/Kivy runtime.
# python-for-android v2026.05.09 uses Python 3.14.x.
requirements = python3,kivy,pyjnius

orientation = portrait
fullscreen = 0

# Android target.
# Python 3.14 requires an NDK/API target of at least 24 because
# CPython's Android build uses preadv()/pwritev(), which are available
# from Android API 24 onward.
android.api = 30
android.minapi = 24
android.ndk_api = 24

# GitHub Actions installs the SDK/NDK into this writable runner directory.
android.sdk_path = /home/runner/android-sdk
android.ndk_path = /home/runner/android-sdk/ndk/28.2.13676358
android.accept_sdk_license = True
android.skip_update = True

# Build only the architecture we currently need.
android.archs = arm64-v8a

# Bluetooth permissions for the current AVA PET BLE implementation.
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,ACCESS_FINE_LOCATION

# APK output.
android.release_artifact = apk
android.debug_artifact = apk

# Pin python-for-android to the latest released version instead of a moving
# branch. This makes CI reproducible and avoids silently changing Python/p4a
# recipes between workflow runs.
p4a.fork = kivy
p4a.branch = master
p4a.commit = 58d2114

[buildozer]

# Keep Buildozer itself concise; p4a debug output is enabled by Buildozer
# automatically at log_level >= 2, so use level 1 for CI unless debugging.
log_level = 1
warn_on_root = 1
