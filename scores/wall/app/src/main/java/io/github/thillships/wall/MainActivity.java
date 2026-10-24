package io.github.thillships.wall;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.lang.ref.WeakReference;

/**
 * The wall board, full screen: no status bar, no navigation bar, no browser
 * bar, and the screen never sleeps while it is open.
 *
 * Opens the page it is given (adb: am start ... -d URL), or else the last
 * page it showed, or else the scores board. If the page fails to load (the
 * Wi-Fi drops), it tries again every 15 seconds.
 *
 * Also puts up the floating button (Bubble) that switches between the
 * calendar and the scores without a computer, if it has been allowed.
 */
public class MainActivity extends Activity {
    private static final String HOME = "https://thill-ships.github.io/scores/wall/";
    private static final long RETRY_MS = 15_000;

    private WebView web;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable retry = () -> { if (web != null) web.reload(); };

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        WebView.setWebContentsDebuggingEnabled(true);   // lets chrome://inspect see the page over adb

        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(3, 6, 15));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        web.setWebViewClient(new WebViewClient() {
            // Links stay in the app rather than opening a browser.
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                return false;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) {
                    handler.removeCallbacks(retry);
                    handler.postDelayed(retry, RETRY_MS);
                }
            }
        });
        setContentView(web);
        hideBars();
        open(getIntent());
        BubbleService.start(this);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        open(intent);
    }

    private void open(Intent intent) {
        SharedPreferences prefs = getSharedPreferences("wall", MODE_PRIVATE);
        Uri data = intent == null ? null : intent.getData();
        String url = data != null ? data.toString() : prefs.getString("url", HOME);
        prefs.edit().putString("url", url).apply();
        handler.removeCallbacks(retry);
        // GitHub Pages lets a page be reused for 10 minutes; whenever a page is
        // opened on purpose, start clean so it is always the newest version.
        // Between opens the cache stays on, so logos and pictures aren't refetched.
        web.clearCache(true);
        web.loadUrl(url);
    }

    // Sticky immersive: the bars stay hidden, and if a swipe brings them
    // back they slide away again by themselves.
    @SuppressWarnings("deprecation")
    private void hideBars() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideBars();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
        hideBars();
        Bubble.scores = new WeakReference<>(this);
        Bubble.show(this);
        Bubble.refresh();
    }

    @Override
    protected void onPause() {
        web.onPause();
        Bubble.scores = new WeakReference<>(null);
        Bubble.refresh();
        super.onPause();
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacks(retry);
        web.destroy();
        super.onDestroy();
    }
}
