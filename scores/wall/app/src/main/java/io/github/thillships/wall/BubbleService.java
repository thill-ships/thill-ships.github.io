package io.github.thillships.wall;

import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.IBinder;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.TextView;

import java.lang.ref.WeakReference;

/**
 * A small round button that floats over everything, the calendar included:
 * tap it on the calendar to open the scores, tap it on the scores to go back
 * to the calendar. Drag it anywhere; it stays where it was left.
 *
 * It needs the "display over other apps" permission, granted once over adb:
 *   adb shell appops set io.github.thillships.wall SYSTEM_ALERT_WINDOW allow
 * Without it nothing here runs and the app works as before. It starts when
 * the app opens and again whenever the calendar restarts.
 */
public class BubbleService extends Service {
    private static final String CHANNEL = "bubble";

    // The scores screen, while it is open; set by MainActivity.
    static WeakReference<Activity> scores = new WeakReference<>(null);
    private static WeakReference<BubbleService> running = new WeakReference<>(null);

    private WindowManager wm;
    private TextView bubble;
    private WindowManager.LayoutParams lp;

    static void start(Context c) {
        if (!Settings.canDrawOverlays(c)) return;
        c.startForegroundService(new Intent(c, BubbleService.class));
    }

    // MainActivity calls this when the scores come to the front or leave it.
    static void refresh() {
        BubbleService s = running.get();
        if (s != null && s.bubble != null) s.bubble.setText(scores.get() != null ? "📅" : "🏈");
    }

    @Override
    public void onCreate() {
        super.onCreate();
        running = new WeakReference<>(this);
        // Android only lets an app keep running in the background if it says so
        // with a notification. It sits in the shade the calendar keeps hidden.
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Scores button", NotificationManager.IMPORTANCE_MIN));
        startForeground(1, new Notification.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.star_on)
                .setContentTitle("Scores button")
                .setContentText("Tap the floating button to switch between the calendar and the scores.")
                .build());
        if (Settings.canDrawOverlays(this)) addBubble();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    private void addBubble() {
        wm = getSystemService(WindowManager.class);
        DisplayMetrics dm = getResources().getDisplayMetrics();
        int size = Math.round(64 * dm.density);

        GradientDrawable bg = new GradientDrawable();
        bg.setShape(GradientDrawable.OVAL);
        bg.setColor(0xE6002E5D);
        bg.setStroke(Math.round(3 * dm.density), 0xFFFFFFFF);
        bubble = new TextView(this);
        bubble.setBackground(bg);
        bubble.setGravity(Gravity.CENTER);
        bubble.setTextSize(28);
        bubble.setAlpha(0.85f);

        SharedPreferences prefs = getSharedPreferences("wall", MODE_PRIVATE);
        lp = new WindowManager.LayoutParams(size, size,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.LEFT;
        // Right edge, a little above the middle, until it is dragged somewhere else.
        lp.x = prefs.getInt("bubbleX", dm.widthPixels - size - Math.round(12 * dm.density));
        lp.y = prefs.getInt("bubbleY", Math.round(dm.heightPixels * 0.38f));

        final int slop = Math.round(10 * dm.density);
        bubble.setOnTouchListener(new View.OnTouchListener() {
            float downX, downY; int startX, startY; boolean dragged;

            @Override
            public boolean onTouch(View v, MotionEvent e) {
                switch (e.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN:
                        downX = e.getRawX(); downY = e.getRawY(); startX = lp.x; startY = lp.y; dragged = false;
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        float dx = e.getRawX() - downX, dy = e.getRawY() - downY;
                        if (!dragged && Math.abs(dx) < slop && Math.abs(dy) < slop) return true;
                        dragged = true;
                        lp.x = startX + Math.round(dx); lp.y = startY + Math.round(dy);
                        wm.updateViewLayout(bubble, lp);
                        return true;
                    case MotionEvent.ACTION_UP:
                        if (dragged) prefs.edit().putInt("bubbleX", lp.x).putInt("bubbleY", lp.y).apply();
                        else toggle();
                        return true;
                }
                return false;
            }
        });
        wm.addView(bubble, lp);
        refresh();
    }

    // Scores showing: step back to whatever was under them (the calendar).
    // Otherwise: bring the scores up.
    private void toggle() {
        Activity a = scores.get();
        if (a != null) {
            if (!a.moveTaskToBack(true)) {
                startActivity(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            }
        } else {
            startActivity(new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        }
    }

    @Override
    public void onDestroy() {
        if (bubble != null) wm.removeView(bubble);
        bubble = null;
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
