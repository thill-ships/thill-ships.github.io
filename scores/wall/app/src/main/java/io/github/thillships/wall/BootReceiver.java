package io.github.thillships.wall;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

/**
 * Puts the floating scores button back after the calendar restarts: straight
 * away, and again a few times over the next minutes in case the permission
 * reads as off at first. The service is started too, to keep the app alive.
 */
public class BootReceiver extends BroadcastReceiver {
    private static final long[] RETRY_MS = { 5_000, 20_000, 60_000, 180_000, 600_000 };

    @Override
    public void onReceive(Context c, Intent intent) {
        Log.i(Bubble.TAG, "boot: " + intent.getAction());
        final Context app = c.getApplicationContext();
        Bubble.show(app);
        BubbleService.start(app);
        Handler h = new Handler(Looper.getMainLooper());
        for (long ms : RETRY_MS) h.postDelayed(() -> Bubble.show(app), ms);
    }
}
