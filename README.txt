AVA PET v0.1
============

Goal
----
First native APK prototype for the AVA robot.

Flow
----
1. Scan for the BLE device named AVA.
2. Connect through GATT.
3. Subscribe to AVA EVENT notifications.
4. Send HELLO_AVA automatically.
5. Send basic eye commands:
   EYES_CALM
   EYES_HAPPY
   EYES_SAD
   EYES_SLEEPY
   EYES_THINKING
   EYES_LISTENING
   EYES_SURPRISED
   BLINK

AV A firmware UUIDs
-------------------
Service:
7b7a0001-6a76-4156-9a76-415641000001

COMMAND:
7b7a0002-6a76-4156-9a76-415641000001

EVENT:
7b7a0003-6a76-4156-9a76-415641000001

STATE:
7b7a0004-6a76-4156-9a76-415641000001

DATA:
7b7a0005-6a76-4156-9a76-415641000001

Build
-----
Build this on a normal Linux/WSL environment with Buildozer/python-for-android.
Pydroid is not required for the APK build.

Important
---------
This is deliberately a tiny first prototype. Do not add memory, games,
personality or Wi-Fi control until BLE Scan -> Connect -> HELLO -> ACK
works reliably.
