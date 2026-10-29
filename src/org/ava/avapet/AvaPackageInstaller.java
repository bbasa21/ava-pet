package org.ava.avapet;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.content.pm.PackageInstaller;
import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;

public final class AvaPackageInstaller {
    private AvaPackageInstaller() {}

    public static boolean installApk(Activity activity, String apkPath) throws Exception {
        File apk = new File(apkPath);
        if (!apk.isFile() || apk.length() <= 0) {
            throw new IllegalArgumentException("Downloaded APK is missing or empty.");
        }

        if (Build.VERSION.SDK_INT >= 26 &&
                !activity.getPackageManager().canRequestPackageInstalls()) {
            Intent settings = new Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:" + activity.getPackageName())
            );
            settings.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            activity.startActivity(settings);
            return false;
        }

        PackageInstaller installer = activity.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams params =
            new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        params.setAppPackageName("org.ava.avapet");

        int sessionId = installer.createSession(params);
        PackageInstaller.Session session = installer.openSession(sessionId);

        try {
            FileInputStream input = new FileInputStream(apk);
            try {
                OutputStream output = session.openWrite("ava-pet-update.apk", 0, apk.length());
                try {
                    byte[] buffer = new byte[1024 * 1024];
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        output.write(buffer, 0, count);
                    }
                    session.fsync(output);
                } finally {
                    output.close();
                }
            } finally {
                input.close();
            }

            Intent statusIntent = new Intent(activity, AvaInstallStatusReceiver.class);
            statusIntent.setAction("org.ava.avapet.INSTALL_STATUS");

            // PackageInstaller must be able to attach its status extras to this PendingIntent.
            // On Android 12+ this requires FLAG_MUTABLE. The receiver is explicit, so the
            // mutable PendingIntent cannot be redirected to another component.
            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= 31) {
                flags |= PendingIntent.FLAG_MUTABLE;
            }

            PendingIntent status = PendingIntent.getBroadcast(
                activity, sessionId, statusIntent, flags
            );
            session.commit(status.getIntentSender());
        } finally {
            session.close();
        }
        return true;
    }
}
