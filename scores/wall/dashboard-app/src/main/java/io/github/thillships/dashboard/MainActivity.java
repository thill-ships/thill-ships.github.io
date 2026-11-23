package io.github.thillships.dashboard;

import android.app.Activity;
import android.content.Intent;
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

/**
 * Tyler's dashboard, full screen: no status bar, no navigation bar, no browser
 * bar, and the screen never sleeps while it is open (the page itself goes
 * dark at night).
 *
 * The login is kept in the web view's storage, so it is entered once. If the
 * page fails to load (the Wi-Fi drops), it tries again every 15 seconds.
 *
 * Coming back to it from Gameday Wall's button shows it as it was, without
 * reloading; the page keeps itself current. Opening it with a link over adb
 * (am start ... -d URL) loads that link instead, for testing.
 */
public class MainActivity extends Activity {
    private static final String HOME = "https://thill-ships.github.io/personal-dashboard/wall/";
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
        web.setBackgroundColor(Color.rgb(243, 244, 246));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);                   // keeps the Supabase login
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                // The dashboard's own pages stay in the app; other links (the Sundance
                // webcam page) open in the browser.
                Uri u = req.getUrl();
                if (u.toString().startsWith(HOME.substring(0, HOME.indexOf("/wall/")))) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                } catch (RuntimeException e) {
                    return false;
                }
                return true;
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
        Uri data = getIntent() == null ? null : getIntent().getData();
        load(data != null ? data.toString() : HOME);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (intent != null && intent.getData() != null) load(intent.getData().toString());
    }

    private void load(String url) {
        handler.removeCallbacks(retry);
        // GitHub Pages lets a page be reused for 10 minutes; start clean so a fresh
        // start always gets the newest version.
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
        web.resumeTimers();
        hideBars();
        // The page reloads its data when it becomes visible again.
    }

    @Override
    protected void onPause() {
        web.onPause();
        super.onPause();
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else moveTaskToBack(true);   // keep the screen (and its login) loaded
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacks(retry);
        web.destroy();
        super.onDestroy();
    }
}
