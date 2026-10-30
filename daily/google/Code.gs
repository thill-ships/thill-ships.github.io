/* ==========================================================================
   Daily board -- the Google feed.

   Runs inside Tyler's personal Google account, every 10 minutes. It reads
   (and can only read; see appsscript.json):
     - today's events on every calendar you have switched on, including the
       hillhq calendars shared to you;
     - the unread mail in your Primary inbox from the last three days;
     - the life tracker's `status` tab, once that Sheet exists.
   and sends a short summary of each to the daily board's database. Your
   Google login never leaves Google; the board only ever sees the summary.

   Setup, once (also in daily/SETUP.md):
     1. script.google.com -> New project. Paste this file over Code.gs.
     2. Project Settings -> "Show appsscript.json" -> paste appsscript.json.
     3. Project Settings -> Script properties -> add FEED_KEY (from the phone
        app's Settings) and, once the life tracker exists, TRACKER_SHEET_ID.
     4. Run `setup` once and allow access. It runs every 10 minutes after that.
   ========================================================================== */

var SUPABASE_URL = 'https://yehpygarkxdopdvugifk.supabase.co';
var SUPABASE_KEY = 'sb_publishable_sGJHMMHbmIyLcORXh2pauw_CePLfJDo';   // public by design

// Calendars to leave off the board entirely, by name (exactly as Google shows it).
var SKIP_CALENDARS = ['Holidays in United States', 'Birthdays', 'Tasks'];

// Recurring events count as routine and are hidden, unless the title matches this.
var ALWAYS_SHOW = /kenzie|date night|anniversary|birthday/i;

/* -------------------------------------------------------------------------- */

function setup(){
  ScriptApp.getProjectTriggers().forEach(function(t){
    if(t.getHandlerFunction() === 'syncAll') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('syncAll').timeBased().everyMinutes(10).create();
  syncAll();
  Logger.log('Set up. syncAll now runs every 10 minutes.');
}

function syncAll(){
  // Each on its own, so one failing never stops the others.
  [syncCalendar, syncGmail, syncUpkeep].forEach(function(fn){
    try{ fn(); }
    catch(e){ Logger.log(fn.name + ' failed: ' + e); }
  });
}

function put_(src, payload){
  var key = PropertiesService.getScriptProperties().getProperty('FEED_KEY');
  if(!key) throw new Error('Add FEED_KEY under Project Settings -> Script properties');
  var res = UrlFetchApp.fetch(SUPABASE_URL + '/rest/v1/rpc/daily_put', {
    method:'post', contentType:'application/json', muteHttpExceptions:true,
    headers:{ apikey:SUPABASE_KEY },
    payload:JSON.stringify({ k:key, src:src, payload:payload })
  });
  if(res.getResponseCode() >= 300) throw new Error(src + ': HTTP ' + res.getResponseCode() + ' ' + res.getContentText());
}

function tz_(){ return Session.getScriptTimeZone(); }
function day_(d){ return Utilities.formatDate(d, tz_(), 'yyyy-MM-dd'); }

/* ---- calendar: today, only what's different ---- */
function syncCalendar(){
  var start = new Date(); start.setHours(0, 0, 0, 0);
  var end = new Date(start.getTime()); end.setDate(end.getDate() + 1);
  var seen = {}, events = [], hidden = 0;
  CalendarApp.getAllCalendars().forEach(function(cal){
    if(cal.isHidden() || !cal.isSelected() || SKIP_CALENDARS.indexOf(cal.getName()) >= 0) return;
    cal.getEvents(start, end).forEach(function(e){
      if(e.getMyStatus && e.getMyStatus() === CalendarApp.GuestStatus.NO) return;   // declined
      var title = e.getTitle() || '(no title)';
      var id = title + '|' + e.getStartTime().getTime();                            // same event on two shared calendars
      if(seen[id]) return;
      seen[id] = true;
      if(e.isRecurringEvent() && !ALWAYS_SHOW.test(title)){ hidden++; return; }
      events.push({
        title:title.slice(0, 120),
        allDay:e.isAllDayEvent(),
        start:e.isAllDayEvent() ? day_(e.getAllDayStartDate()) : e.getStartTime().toISOString(),
        end:e.isAllDayEvent() ? day_(e.getAllDayEndDate()) : e.getEndTime().toISOString(),
        cal:cal.getName().slice(0, 40),
        location:(e.getLocation() || '').split(',')[0].slice(0, 60)
      });
    });
  });
  put_('calendar', { day:day_(start), events:events.slice(0, 20), hidden:hidden });
}

/* ---- inbox: unread, Primary, last three days ---- */
function syncGmail(){
  var me = Session.getActiveUser().getEmail().toLowerCase();
  var threads = GmailApp.search('in:inbox is:unread category:primary newer_than:3d', 0, 40);
  var emails = [];
  threads.forEach(function(t){
    var msgs = t.getMessages(), m = msgs[msgs.length - 1];
    var from = m.getFrom() || '';
    if(from.toLowerCase().indexOf(me) >= 0) return;
    var name = from.replace(/<.*>/, '').replace(/"/g, '').trim() || from;
    emails.push({ from:name.slice(0, 60), subject:(t.getFirstMessageSubject() || '').slice(0, 120),
                  at:t.getLastMessageDate().toISOString(), important:t.isImportant() });
  });
  emails.sort(function(a, b){ return (b.important - a.important) || (new Date(b.at) - new Date(a.at)); });
  put_('gmail', { unread:emails.length, emails:emails.slice(0, 8) });
}

/* ---- upkeep: the life tracker's status tab ---- */
function syncUpkeep(){
  var id = PropertiesService.getScriptProperties().getProperty('TRACKER_SHEET_ID');
  if(!id) return;                                   // not built yet: the board says so
  var book = SpreadsheetApp.openById(id);
  var rows = function(tab){
    var sh = book.getSheetByName(tab); if(!sh) return [];
    var v = sh.getDataRange().getValues(), head = v.shift();
    return v.map(function(r){ var o = {}; head.forEach(function(h, i){ o[h] = r[i]; }); return o; });
  };
  var fmt = function(x){ return x instanceof Date ? day_(x) : (x ? String(x) : null); };
  var prompts = {};
  rows('items').forEach(function(it){ if(it.checkpoint_prompt) prompts[it.item_id] = it.checkpoint_prompt; });
  var all = rows('status'), items = [], ok = 0;
  all.forEach(function(s){
    if(s.state === 'ok' || s.state === 'untracked'){ ok++; return; }
    items.push({ name:String(s.name).slice(0, 80), owner:s.owner || null, state:s.state,
                 days_until:s.days_until === '' ? null : Number(s.days_until),
                 next_due:fmt(s.next_due), last_done:fmt(s.last_done),
                 prompt:prompts[s.item_id] ? String(prompts[s.item_id]).slice(0, 80) : null });
  });
  items.sort(function(a, b){ return (a.days_until == null ? 999 : a.days_until) - (b.days_until == null ? 999 : b.days_until); });
  put_('upkeep', { items:items.slice(0, 12), ok:ok });
}
