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

# Keep the Python runtime compatible with the pinned python-for-android
# release below. Pin the application-side packages as well so a new
# upstream release cannot silently change the CI build.
requirements = python3==3.11.5,kivy==2.3.1,pyjnius==1.6.1

orientation = portrait
fullscreen = 0

# Android target/minimum API.
android.api = 30
android.minapi = 23
android.ndk_api = 23

# GitHub Actions installs the Android SDK/NDK in this writable runner path.
android.sdk_path = /home/runner/android-sdk
android.ndk_path = /home/runner/android-sdk/ndk/25.1.8937393
android.accept_sdk_license = True
android.skip_update = True

# Build only the architecture used by the current Android app.
android.archs = arm64-v8a

# BLE permissions used by the current AVA PET implementation.
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,ACCESS_FINE_LOCATION

# Produce an APK for both debug and release targets.
android.release_artifact = apk
android.debug_artifact = apk

# Pin python-for-android to the verified 2024.01.21 release.
# This avoids the newer CPython 3.14 build that previously failed in the
# Android API-23 toolchain on preadv/pwritev.
p4a.fork = kivy
p4a.branch = v2024.01.21
p4a.commit = 957a3e5f8c270f7aa648ba185e5a68c1077a798d

[buildozer]

# Keep normal CI output readable; the workflow captures the full compiler
# log as an artifact if the build fails.
log_level = 1
warn_on_root = 1
