import hashlib
import json
import os
import threading
import urllib.request
from urllib.error import HTTPError, URLError

from kivy.clock import Clock
from jnius import autoclass


MANIFEST_URL = (
    "https://github.com/bbasa21/ava-pet/releases/download/"
    "ota-latest/update.json"
)
MAX_APK_BYTES = 150 * 1024 * 1024


class AvaOTA:
    """Small, verified Android updater for AVA PET."""

    def __init__(self, logger, status_callback):
        self.logger = logger
        self.status_callback = status_callback
        self.busy = False

    def _status(self, message):
        Clock.schedule_once(lambda *_: self.status_callback(message), 0)

    def _log(self, message):
        Clock.schedule_once(lambda *_: self.logger(message), 0)

    def check_for_updates(self, *_):
        if self.busy:
            self._status("UPDATE CHECK ALREADY RUNNING")
            return
        self.busy = True
        self._status("CHECKING FOR UPDATES...")
        threading.Thread(target=self._check_worker, daemon=True).start()

    def _check_worker(self):
        try:
            request = urllib.request.Request(
                MANIFEST_URL,
                headers={"User-Agent": "AVA-PET-Android-Updater"},
            )
            with urllib.request.urlopen(request, timeout=25) as response:
                raw = response.read(128 * 1024 + 1)
            if len(raw) > 128 * 1024:
                raise RuntimeError("Update manifest is unexpectedly large.")

            manifest = json.loads(raw.decode("utf-8"))
            version_name = str(manifest.get("version_name", "")).strip()
            version_code = int(manifest.get("version_code", 0))
            apk_url = str(manifest.get("apk_url", "")).strip()
            expected_sha256 = str(manifest.get("sha256", "")).lower().strip()

            if not version_name or version_code <= 0:
                raise RuntimeError("Update manifest has invalid version information.")
            if not apk_url.startswith("https://github.com/bbasa21/ava-pet/releases/download/"):
                raise RuntimeError("Update APK URL is not an approved HTTPS release URL.")
            if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
                raise RuntimeError("Update manifest has an invalid SHA-256 checksum.")

            Activity = autoclass("org.kivy.android.PythonActivity")
            activity = Activity.mActivity
            PackageManager = autoclass("android.content.pm.PackageManager")
            package_info = activity.getPackageManager().getPackageInfo(
                activity.getPackageName(), 0
            )
            try:
                installed_code = int(package_info.getLongVersionCode())
            except Exception:
                installed_code = int(package_info.versionCode)

            if version_code <= installed_code:
                self._status("AVA PET IS UP TO DATE")
                self._log(
                    f"OTA CHECK | installed={installed_code} | latest={version_code} | no update"
                )
                return

            self._status(f"DOWNLOADING AVA PET {version_name}...")
            self._log(f"OTA UPDATE AVAILABLE | version={version_name} | code={version_code}")

            cache_dir = str(activity.getCacheDir().getAbsolutePath())
            apk_path = os.path.join(cache_dir, "ava-pet-update.apk")
            request = urllib.request.Request(
                apk_url,
                headers={"User-Agent": "AVA-PET-Android-Updater"},
            )
            digest = hashlib.sha256()
            total = 0
            with urllib.request.urlopen(request, timeout=60) as response:
                with open(apk_path, "wb") as target:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_APK_BYTES:
                            raise RuntimeError("Update APK exceeds the size limit.")
                        digest.update(chunk)
                        target.write(chunk)

            if total == 0 or digest.hexdigest().lower() != expected_sha256:
                try:
                    os.remove(apk_path)
                except OSError:
                    pass
                raise RuntimeError("APK SHA-256 verification failed; installation cancelled.")

            Installer = autoclass("org.ava.avapet.AvaPackageInstaller")
            installed = bool(Installer.installApk(activity, apk_path))
            if installed:
                self._status("INSTALLER OPENED — CONFIRM THE UPDATE")
                self._log(f"OTA VERIFIED | bytes={total} | sha256={digest.hexdigest()}")
            else:
                self._status("ALLOW AVA PET TO INSTALL UPDATES, THEN TAP AGAIN")
                self._log("OTA INSTALL WAITING FOR ANDROID INSTALL PERMISSION")

        except HTTPError as exc:
            self._status(f"UPDATE CHECK FAILED: HTTP {exc.code}")
            self._log(f"OTA ERROR | HTTP {exc.code}")
        except URLError as exc:
            self._status("UPDATE CHECK FAILED: CHECK INTERNET")
            self._log(f"OTA ERROR | network={exc}")
        except Exception as exc:
            self._status("UPDATE FAILED — EXISTING APP WAS NOT REMOVED")
            self._log(f"OTA ERROR | {exc}")
        finally:
            self.busy = False
