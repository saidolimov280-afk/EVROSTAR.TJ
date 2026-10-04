package com.evrostar.shop;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.webkit.*;
import android.widget.*;
public class MainActivity extends Activity {
 private WebView web;
 private ProgressBar progress;
 private LinearLayout error;
 private static final String HOME="https://evrostarshop.com/";
 private boolean trusted(Uri u) { String h=u.getHost();return "https".equals(u.getScheme()) && ("evrostarshop.com".equals(h)||"www.evrostarshop.com".equals(h)); }
 private String launchUrl(Intent intent) { Uri u=intent.getData();return u!=null&&trusted(u)?u.toString():HOME; }
 private void external(Uri u) {
  String scheme=u.getScheme();
  if(!("https".equals(scheme)||"http".equals(scheme)||"tel".equals(scheme)||"mailto".equals(scheme)||"whatsapp".equals(scheme)))return;
  try { startActivity(new Intent(Intent.ACTION_VIEW,u)); }
  catch(ActivityNotFoundException e) { Toast.makeText(this,"Барнома ёфт нашуд / Приложение не найдено",Toast.LENGTH_LONG).show(); }
 }
 @Override public void onCreate(Bundle state) {
  super.onCreate(state);
  LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(Color.WHITE);
  progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(100);
  root.addView(progress,new LinearLayout.LayoutParams(-1,8));
  FrameLayout frame=new FrameLayout(this);root.addView(frame,new LinearLayout.LayoutParams(-1,0,1));
  web=new WebView(this);frame.addView(web,new FrameLayout.LayoutParams(-1,-1));
  error=new LinearLayout(this);error.setOrientation(LinearLayout.VERTICAL);error.setGravity(android.view.Gravity.CENTER);error.setPadding(32,32,32,32);error.setBackgroundColor(Color.WHITE);error.setVisibility(View.GONE);
  TextView text=new TextView(this);text.setText("EVROSTAR\n\nПайвастшавӣ ба интернетро санҷед.\nПроверьте подключение к интернету.");text.setTextSize(20);text.setGravity(android.view.Gravity.CENTER);error.addView(text);
  Button retry=new Button(this);retry.setText("Боз кӯшиш кунед / Повторить");error.addView(retry);retry.setOnClickListener(v->{error.setVisibility(View.GONE);web.reload();});frame.addView(error,new FrameLayout.LayoutParams(-1,-1));setContentView(root);
  WebSettings ws=web.getSettings();ws.setJavaScriptEnabled(true);ws.setDomStorageEnabled(true);ws.setAllowFileAccess(false);ws.setAllowContentAccess(false);ws.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);ws.setSupportMultipleWindows(false);ws.setMediaPlaybackRequiresUserGesture(true);
  web.setWebChromeClient(new WebChromeClient(){ @Override public void onProgressChanged(WebView view,int value){progress.setProgress(value);progress.setVisibility(value<100?View.VISIBLE:View.GONE);} });
  web.setWebViewClient(new WebViewClient(){
   @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
    Uri u=request.getUrl();if(trusted(u))return false;external(u);return true;
   }
   @Override public void onPageStarted(WebView view,String url,android.graphics.Bitmap icon){error.setVisibility(View.GONE);}
   @Override public void onPageFinished(WebView view,String url){
    view.evaluateJavascript("document.querySelectorAll('[data-install],.installStrip').forEach(function(e){e.style.display='none'});",null);
   }
   @Override public void onReceivedError(WebView view,WebResourceRequest req,WebResourceError err){if(req.isForMainFrame())error.setVisibility(View.VISIBLE);}
   @Override public void onReceivedHttpError(WebView view,WebResourceRequest req,WebResourceResponse res){if(req.isForMainFrame()&&res.getStatusCode()>=400)error.setVisibility(View.VISIBLE);}
  });
  web.setDownloadListener((url,ua,disposition,mime,size)->external(Uri.parse(url)));
  if(state==null||web.restoreState(state)==null)web.loadUrl(launchUrl(getIntent()));
 }
 @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);web.loadUrl(launchUrl(intent));}
 @Override protected void onSaveInstanceState(Bundle out){web.saveState(out);super.onSaveInstanceState(out);}
 @Override public void onBackPressed(){
  web.evaluateJavascript("Boolean(document.querySelector('dialog[open]'))",value->{
   if("true".equals(value)){web.evaluateJavascript("document.querySelectorAll('dialog[open]').forEach(function(d){d.close()})",null);return;}
   if(web.canGoBack()){web.goBack();return;}
   new AlertDialog.Builder(this).setTitle("EVROSTAR").setMessage("Барномаро пӯшед? / Закрыть приложение?").setPositiveButton("Ҳа / Да",(d,w)->finish()).setNegativeButton("Не / Нет",null).show();
  });
 }
 @Override protected void onDestroy(){web.destroy();super.onDestroy();}
}
