package io.github.thillships.wall;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.lang.ref.WeakReference;

/**
 * The floating button itself: tap it for a short menu of the wall's apps
 * (the calendar, the scores, Tyler's dashboard, and any added to APPS), drag
 * it anywhere. Apps in the list that aren't installed are left out.
 *
 * It is a window of its own, owned by the app rather than by any screen, so
 * it can be put up from anywhere: when the app opens, after a restart, or by
 * BubbleService. Android keeps an app with a window like this running.
 */
final class Bubble {
    static final String TAG = "WallBubble";

    /**
     * The menu, top to bottom: label, and what to open. CALENDAR is the
     * calendar (the home screen), SCORES is this app, anything else is another
     * app's package name. To add an app, add a row.
     */
    static final String CALENDAR = "calendar", SCORES = "scores";
    static final String[][] APPS = {
            { "📅  Calendar", CALENDAR },
            { "📊  Dashboard", "io.github.thillships.dashboard" },
            { "🏈  Scores", SCORES },
    };
    private static final long MENU_CLOSE_MS = 10_000;

    // The scores screen, while it is in front; set by MainActivity.
    static WeakReference<Activity> scores = new WeakReference<>(null);

    private static Context app;
    private static WindowManager wm;
    private static TextView view;
    private static WindowManager.LayoutParams lp;
    private static LinearLayout menu;
    private static final android.os.Handler handler = new android.os.Handler(android.os.Looper.getMainLooper());
    private static final Runnable closeMenu = Bubble::hideMenu;
    // A tap on the button while the menu is open first closes the menu as a tap
    // "outside" it; this keeps that same tap from opening the menu again.
    private static long menuClosedAt;

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

    /** The button shows the menu sign; the menu marks the scores when they are in front. */
    static void refresh() {
        if (view != null) view.setText("☰");
        if (menu != null) hideMenu();
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
        v.setTextSize(30);
        v.setTextColor(Color.WHITE);
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
                        else if (menu != null) hideMenu();
                        else if (System.currentTimeMillis() - menuClosedAt > 600) showMenu();
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

    /** A dark card next to the button with one big row per installed app. */
    private static void showMenu() {
        Context c = app;
        DisplayMetrics dm = c.getResources().getDisplayMetrics();
        PackageManager pm = c.getPackageManager();
        boolean scoresInFront = scores.get() != null;

        LinearLayout m = new LinearLayout(c);
        m.setOrientation(LinearLayout.VERTICAL);
        int pad = Math.round(10 * dm.density);
        m.setPadding(pad, pad, pad, pad);
        GradientDrawable bg = new GradientDrawable();
        bg.setCornerRadius(18 * dm.density);
        bg.setColor(0xF2111827);
        bg.setStroke(Math.round(2 * dm.density), 0x66FFFFFF);
        m.setBackground(bg);

        for (String[] row : APPS) {
            final String target = row[1];
            boolean here = SCORES.equals(target) && scoresInFront;
            if (!CALENDAR.equals(target) && !SCORES.equals(target) && pm.getLaunchIntentForPackage(target) == null) continue;
            TextView t = new TextView(c);
            t.setText(here ? row[0] + "  ·  here" : row[0]);
            t.setTextSize(26);
            t.setTextColor(here ? 0x99FFFFFF : Color.WHITE);
            t.setGravity(Gravity.CENTER_VERTICAL);
            t.setMinHeight(Math.round(72 * dm.density));
            t.setPadding(Math.round(18 * dm.density), 0, Math.round(28 * dm.density), 0);
            t.setOnClickListener(b -> { hideMenu(); open(target); });
            m.addView(t);
        }

        m.measure(View.MeasureSpec.UNSPECIFIED, View.MeasureSpec.UNSPECIFIED);
        int w = m.getMeasuredWidth(), h = m.getMeasuredHeight(), gap = Math.round(12 * dm.density);
        WindowManager.LayoutParams mlp = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                // A tap anywhere outside the menu closes it (and still reaches the screen below).
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
                PixelFormat.TRANSLUCENT);
        mlp.gravity = Gravity.TOP | Gravity.LEFT;
        // Beside the button, on whichever side has room, and kept on screen.
        boolean right = lp.x + lp.width / 2 < dm.widthPixels / 2;
        mlp.x = right ? lp.x + lp.width + gap : lp.x - w - gap;
        mlp.y = Math.max(gap, Math.min(lp.y + lp.height / 2 - h / 2, dm.heightPixels - h - gap));
        m.setOnTouchListener((b, e) -> {
            if (e.getActionMasked() == MotionEvent.ACTION_OUTSIDE) { hideMenu(); return true; }
            return false;
        });
        try {
            wm.addView(m, mlp);
            menu = m;
            handler.postDelayed(closeMenu, MENU_CLOSE_MS);
        } catch (RuntimeException e) {
            Log.w(TAG, "could not show the menu", e);
        }
    }

    private static void hideMenu() {
        handler.removeCallbacks(closeMenu);
        if (menu == null) return;
        try {
            wm.removeView(menu);
        } catch (RuntimeException ignored) {
        }
        menu = null;
        menuClosedAt = System.currentTimeMillis();
    }

    private static void open(String target) {
        try {
            if (CALENDAR.equals(target)) {
                // The calendar is the home screen. Stepping the scores back first keeps
                // their page loaded, the way the old toggle did.
                Activity a = scores.get();
                if (a == null || !a.moveTaskToBack(true)) {
                    app.startActivity(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                }
            } else if (SCORES.equals(target)) {
                if (scores.get() == null) app.startActivity(new Intent(app, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            } else {
                Intent i = app.getPackageManager().getLaunchIntentForPackage(target);
                if (i != null) app.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            }
        } catch (RuntimeException e) {
            Log.w(TAG, "could not open " + target, e);
        }
    }
}
