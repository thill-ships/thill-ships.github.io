package io.github.thillships.wall;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.TextView;

import java.lang.ref.WeakReference;

/**
 * The floating button itself: tap it on the calendar to open the scores, tap
 * it on the scores to go back to the calendar, drag it anywhere.
 *
 * It is a window of its own, owned by the app rather than by any screen, so
 * it can be put up from anywhere: when the app opens, after a restart, or by
 * BubbleService. Android keeps an app with a window like this running.
 */
final class Bubble {
    static final String TAG = "WallBubble";

    // The scores screen, while it is in front; set by MainActivity.
    static WeakReference<Activity> scores = new WeakReference<>(null);

    private static Context app;
    private static WindowManager wm;
    private static TextView view;
    private static WindowManager.LayoutParams lp;

    private Bubble() {}

    static boolean showing() { return view != null; }

    /** Puts the button up, if it is allowed and not up already. */
    static void show(Context c) {
        if (view != null) return;
        boolean ok = Settings.canDrawOverlays(c);
        Log.i(TAG, "show: canDrawOverlays=" + ok);
        if (!ok) return;
        try {
            add(c.getApplicationContext());
        } catch (RuntimeException e) {
            Log.w(TAG, "could not show the button", e);
            view = null;
        }
    }

    /** The football on the calendar, the calendar on the scores. */
    static void refresh() {
        if (view != null) view.setText(scores.get() != null ? "📅" : "🏈");
    }

    private static void add(Context c) {
        app = c;
        wm = c.getSystemService(WindowManager.class);
        DisplayMetrics dm = c.getResources().getDisplayMetrics();
        int size = Math.round(64 * dm.density);

        GradientDrawable bg = new GradientDrawable();
        bg.setShape(GradientDrawable.OVAL);
        bg.setColor(0xE6002E5D);
        bg.setStroke(Math.round(3 * dm.density), 0xFFFFFFFF);
        TextView v = new TextView(c);
        v.setBackground(bg);
        v.setGravity(Gravity.CENTER);
        v.setTextSize(28);
        v.setAlpha(0.85f);

        SharedPreferences prefs = c.getSharedPreferences("wall", Context.MODE_PRIVATE);
        lp = new WindowManager.LayoutParams(size, size,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.LEFT;
        // Right edge, a little above the middle, until it is dragged somewhere else.
        lp.x = prefs.getInt("bubbleX", dm.widthPixels - size - Math.round(12 * dm.density));
        lp.y = prefs.getInt("bubbleY", Math.round(dm.heightPixels * 0.38f));

        final int slop = Math.round(10 * dm.density);
        v.setOnTouchListener(new View.OnTouchListener() {
            float downX, downY; int startX, startY; boolean dragged;

            @Override
            public boolean onTouch(View b, MotionEvent e) {
                switch (e.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN:
                        downX = e.getRawX(); downY = e.getRawY(); startX = lp.x; startY = lp.y; dragged = false;
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        float dx = e.getRawX() - downX, dy = e.getRawY() - downY;
                        if (!dragged && Math.abs(dx) < slop && Math.abs(dy) < slop) return true;
                        dragged = true;
                        lp.x = startX + Math.round(dx); lp.y = startY + Math.round(dy);
                        wm.updateViewLayout(view, lp);
                        return true;
                    case MotionEvent.ACTION_UP:
                        if (dragged) prefs.edit().putInt("bubbleX", lp.x).putInt("bubbleY", lp.y).apply();
                        else toggle();
                        return true;
                }
                return false;
            }
        });
        wm.addView(v, lp);
        view = v;
        Log.i(TAG, "showing the button");
        refresh();
    }

    // Scores showing: step back to whatever was under them (the calendar).
    // Otherwise: bring the scores up.
    private static void toggle() {
        Activity a = scores.get();
        if (a != null) {
            if (!a.moveTaskToBack(true)) {
                app.startActivity(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            }
        } else {
            app.startActivity(new Intent(app, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        }
    }
}
