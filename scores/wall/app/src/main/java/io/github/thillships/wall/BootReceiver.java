package io.github.thillships.wall;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Puts the floating scores button back after the calendar restarts. */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent intent) {
        android.util.Log.i(BubbleService.TAG, "boot: " + intent.getAction());
        BubbleService.start(c);
    }
}
