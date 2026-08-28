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

# Python/Kivy runtime used by the current AVA PET app
requirements = python3,kivy,pyjnius

orientation = portrait
fullscreen = 0

# Android target
android.api = 30
android.minapi = 23

# GitHub Actions installs these into the writable runner SDK directory.
# Keep the paths explicit so Buildozer cannot fall back to /root/.buildozer.
android.sdk_path = /home/runner/android-sdk
android.ndk_path = /home/runner/android-sdk/ndk/28.2.13676358
android.accept_sdk_license = True

# Single architecture keeps the first debug APK smaller and simpler.
android.archs = arm64-v8a

# Bluetooth permissions for the Android 11 target.
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,ACCESS_FINE_LOCATION

# Build settings
android.release_artifact = apk
android.debug_artifact = apk

[buildozer]

log_level = 2
warn_on_root = 1
