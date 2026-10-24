package io.github.thillships.wall;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;

/**
 * Keeps the app running in the background so the floating button (Bubble)
 * stays up, and keeps trying to put it up for a while after a restart, when
 * the permission can read as off at first.
 *
 * The button needs the "display over other apps" permission, granted once
 * over adb:
 *   adb shell appops set io.github.thillships.wall SYSTEM_ALERT_WINDOW allow
 * Some calendars won't start this service at all after a restart; the
 * button is then put up straight from BootReceiver instead.
 */
public class BubbleService extends Service {
    private static final String CHANNEL = "bubble";
    private static final long CHECK_MS = 20_000, CHECK_FOR_MS = 15 * 60_000;

    static void start(Context c) {
        try {
            c.startForegroundService(new Intent(c, BubbleService.class));
        } catch (RuntimeException e) {
            Log.w(Bubble.TAG, "could not start the service", e);
        }
    }

    private final Handler handler = new Handler(Looper.getMainLooper());
    private long startedAt;
    private final Runnable check = new Runnable() {
        @Override
        public void run() {
            Bubble.show(BubbleService.this);
            if (Bubble.showing()) return;
            if (System.currentTimeMillis() - startedAt < CHECK_FOR_MS) handler.postDelayed(this, CHECK_MS);
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(Bubble.TAG, "service started");
        // Android only lets an app keep running in the background if it says so
        // with a notification. It sits in the shade the calendar keeps hidden.
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Scores button", NotificationManager.IMPORTANCE_MIN));
        startForeground(1, new Notification.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.star_on)
                .setContentTitle("Scores button")
                .setContentText("Tap the floating button to switch between the calendar and the scores.")
                .build());
        startedAt = System.currentTimeMillis();
        check.run();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        handler.removeCallbacks(check);
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
