[app]

# AVA PET Android application
title = AVA PET
package.name = avapet
package.domain = org.ava

# Project source
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt
source.exclude_dirs = .git,.github,.buildozer,.kivy,bin,__pycache__

# Keep the Python runtime compatible with the pinned python-for-android
# release below.
requirements = python3==3.11.5,kivy==2.3.1,pyjnius==1.6.1

orientation = portrait
fullscreen = 0

# Android target/minimum API.
android.api = 30
android.minapi = 23
android.ndk_api = 23

# IMPORTANT: SDK/NDK paths are intentionally NOT specified here.
# The official Kivy Buildozer Docker image owns the Android toolchain.
# Buildozer will use the SDK/NDK installed inside that container.
android.accept_sdk_license = True

# Build only the architecture used by the current Android app.
android.archs = arm64-v8a

# BLE permissions used by the current AVA PET implementation.
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,ACCESS_FINE_LOCATION

# Produce an APK for debug/release targets.
android.release_artifact = apk
android.debug_artifact = apk

# Pin python-for-android to the known compatible release.
p4a.fork = kivy
p4a.branch = v2024.01.21
p4a.commit = 957a3e5f8c270f7aa648ba185e5a68c1077a798d

[buildozer]

log_level = 1
warn_on_root = 1
