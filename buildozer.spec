[app]

# AVA PET Android application
title = AVA PET
package.name = avapet
package.domain = org.ava

# IMPORTANT:
# Keep the version number higher than every previously installed release.
# Current installed release: 0.3
# Next release should be: 0.4
version = 0.3

# Project source
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt,ttf
source.exclude_dirs = .git,.github,.buildozer,.kivy,bin,__pycache__

# Java BLE bridge. Buildozer passes this directory to
# python-for-android with --add-source.
android.add_src = src

# Python runtime
requirements = python3==3.11.5,kivy==2.3.1,pyjnius==1.6.1,filetype==1.2.0

# AVA PET is a landscape application.
orientation = landscape
fullscreen = 1

# Android 10+ = API 29+
# Target API 31 so Android 12+ Nearby Devices permissions are handled
# using BLUETOOTH_SCAN / BLUETOOTH_CONNECT.
android.api = 31
android.minapi = 29
android.ndk_api = 29

android.accept_sdk_license = True

# Current Android phone architecture
android.archs = arm64-v8a

# BLE + location permissions.
# Runtime permission handling is performed by main.py.
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,BLUETOOTH_SCAN,BLUETOOTH_CONNECT

# APK is intentionally kept as the release artifact for direct installation/update.
android.release_artifact = apk
android.debug_artifact = apk

# ---------------------------------------------------------------------------
# RELEASE SIGNING - DO NOT PUT SECRETS IN THIS FILE
# ---------------------------------------------------------------------------
# All future release APKs MUST use the SAME signing keystore and alias.
# The keystore must be stored OUTSIDE the Git repository and backed up safely.
#
# python-for-android reads these release-signing environment variables:
#
#   P4A_RELEASE_KEYSTORE
#   P4A_RELEASE_KEYSTORE_PASSWD
#   P4A_RELEASE_KEYALIAS
#   P4A_RELEASE_KEYALIAS_PASSWD
#
# Never commit the .keystore/.jks file or its passwords to GitHub.
# On Windows PowerShell, these can be supplied as:
#
#   $env:P4A_RELEASE_KEYSTORE = "C:\AVA-PET-Keys\ava-pet-release.keystore"
#   $env:P4A_RELEASE_KEYSTORE_PASSWD = "<keystore-password>"
#   $env:P4A_RELEASE_KEYALIAS = "ava-pet"
#   $env:P4A_RELEASE_KEYALIAS_PASSWD = "<key-password>"
#
# Once configured, build release APKs with:
#
#   buildozer android release
#
# The signing key must never change between releases. Losing it means future
# APKs cannot update installations signed with the lost key.

# Known compatible python-for-android release
p4a.fork = kivy
p4a.branch = v2024.01.21
p4a.commit = 957a3e5f8c270f7aa648ba185e5a68c1077a798d

[buildozer]

log_level = 1
warn_on_root = 1
