// ---------- Studio: the classes, the weekly rhythm in India time, and the sums over check-ins ----------

const IST_OFFSET_MS_ = 330 * 60000; // India is UTC+5:30 all year
const DAY_MS_ = 86400000;
const DAYS_ = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const WEEKDAY_NAMES_ = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const MONTH_NAMES_ = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const CHECKIN_BEFORE_MIN_ = 60; // how early before class the "before" check-in opens
const MEET_LINK_ = /^https:\/\/(meet\.google\.com\/[a-z]{3}-[a-z]{4}-[a-z]{3}|([\w-]+\.)?zoom\.us\/j\/\d+(\?pwd=[\w.-]+)?)$/;
const GROUP_LINK_ = /^https:\/\/chat\.whatsapp\.com\/[A-Za-z0-9]+$/;

/** UTC ISO-8601 to the second: "2026-11-18T02:30:00Z". */
function isoTime_(ms) {
  return new Date(Math.floor(ms / 1000) * 1000).toISOString().replace('.000Z', 'Z');
}

/** The India date of a moment, as a day number (days since 1 Jan 1970). */
function istDay_(ms) {
  return Math.floor((ms + IST_OFFSET_MS_) / DAY_MS_);
}

/** Midnight in India of a day number, as milliseconds. */
function istMidnight_(day) {
  return day * DAY_MS_ - IST_OFFSET_MS_;
}

function istParts_(ms) {
  const d = new Date(ms + IST_OFFSET_MS_);
  return { day: d.getUTCDate(), month: d.getUTCMonth(), weekday: (d.getUTCDay() + 6) % 7, hour: d.getUTCHours(), minute: d.getUTCMinutes() };
}

/** The India date of a moment as ISO 8601: "2026-11-16". */
function istDate_(ms) {
  return new Date(ms + IST_OFFSET_MS_).toISOString().slice(0, 10);
}

/** strftime("%-I:%M %p") in India time: "8:00 AM". */
function istClock_(ms) {
  const p = istParts_(ms);
  return (p.hour % 12 || 12) + ':' + (p.minute < 10 ? '0' : '') + p.minute + ' ' + (p.hour < 12 ? 'AM' : 'PM');
}

/** One language out of a {"en": ..., "hi": ..., "mr": ...} dict, falling back to English. */
function pick_(text, lang) {
  return text[lang] || text.en;
}

function cleanLink_(raw, pattern, detail) {
  let link = raw.trim();
  if (link.indexOf('https://') !== 0) link = 'https://' + (link.indexOf('http://') === 0 ? link.slice(7) : link);
  if (!pattern.test(link)) throw new HttpError_(400, detail);
  return link;
}

/** A Google Meet or Zoom link, with https:// added when it was left off; else 400 bad_meet_link. */
function cleanMeetLink_(raw) {
  return cleanLink_(raw, MEET_LINK_, 'bad_meet_link');
}

/** A WhatsApp group invite link, with https:// added when it was left off; else 400 bad_group_link. */
function cleanGroupLink_(raw) {
  return cleanLink_(raw, GROUP_LINK_, 'bad_group_link');
}

function classInfo_(key, lang) {
  const entry = STUDIO.classes.filter((c) => c.key === key)[0];
  if (!entry) throw new Error('unknown class ' + key);
  return { key: key, name: pick_(entry.name, lang), level: pick_(entry.level, lang), about: pick_(entry.about, lang) };
}

/** A session for the app. The link is shown only to approved members; without its own link a session uses the
 * teacher's standing link. */
function sessionJson_(row, lang, showLink, defaultLink) {
  const link = row.meet_link || defaultLink;
  return {
    id: row.id,
    starts_at: isoTime_(row.starts_at),
    duration_min: row.duration_min,
    class: classInfo_(row.class_key, lang),
    meet_link: showLink ? link || null : null,
    has_link: Boolean(link),
  };
}

function studioJson_(lang) {
  const teacher = STUDIO.teacher;
  return {
    name: pick_(STUDIO.name, lang),
    tagline: pick_(STUDIO.tagline, lang),
    since: STUDIO.since,
    teacher: { name: teacher.name, title: pick_(teacher.title, lang), bio: pick_(teacher.bio, lang) },
    classes: STUDIO.classes.map((c) => classInfo_(c.key, lang)),
    weekly: DAYS_.map((day) => ({ day: day, class: classInfo_(STUDIO.weekly[day], lang) })),
    class_start_ist: STUDIO.class_start_ist,
    duration_min: STUDIO.duration_min,
  };
}

/** The class start of each of the 7 days from `now`'s India date. */
function weekStarts_(now) {
  const [hour, minute] = STUDIO.class_start_ist.split(':').map(Number);
  const today = istDay_(now);
  const out = [];
  for (let offset = 0; offset < 7; offset++) {
    const day = today + offset;
    out.push({ starts_at: istMidnight_(day) + (hour * 60 + minute) * 60000, class_key: STUDIO.weekly[DAYS_[(day + 3) % 7]] });
  }
  return out;
}

/** Makes sure a session row exists for each of the next 7 days; takes the lock only when one is missing. */
function ensureWeek_(ctx) {
  const wanted = weekStarts_(ctx.now);
  const have = (table) => {
    const starts = {};
    table.rows.forEach((r) => {
      starts[r.starts_at] = true;
    });
    return starts;
  };
  let present = have(ctx.db.t('class_sessions'));
  if (wanted.every((w) => present[w.starts_at])) return;
  ctx.lock(() => {
    const table = ctx.db.t('class_sessions');
    present = have(table);
    let id = table.nextId();
    table.insert(wanted.filter((w) => !present[w.starts_at]).map((w) => ({
      id: id++, class_key: w.class_key, starts_at: w.starts_at, duration_min: STUDIO.duration_min, meet_link: null, updated_at: ctx.now,
    })));
  });
}

/** Whether a class's after-class window is open at [now]: from 10 minutes before its end to 12 hours after it. */
function afterOpen_(session, now) {
  const end = session.starts_at + session.duration_min * 60000;
  return end - 10 * 60000 <= now && now <= end + 12 * 3600000;
}

/** Sessions that have not ended yet, soonest first. */
function upcoming_(ctx, limit) {
  ensureWeek_(ctx);
  const from = ctx.now - 2 * 3600000;
  return ctx.db.t('class_sessions').rows
    .filter((r) => r.starts_at >= from && r.starts_at + r.duration_min * 60000 > ctx.now)
    .sort((a, b) => a.starts_at - b.starts_at)
    .slice(0, limit || 7);
}

function sessionRow_(ctx, id) {
  const row = ctx.db.t('class_sessions').rows.filter((r) => r.id === id)[0];
  if (!row) throw new HttpError_(404, 'no_session');
  return row;
}

function sessionsById_(ctx) {
  const out = {};
  ctx.db.t('class_sessions').rows.forEach((r) => {
    out[r.id] = r;
  });
  return out;
}

/** The average mood change over (before, after) pairs of the given check-ins: [average or null, pairs]. */
function moodChange_(checkins) {
  const after = {};
  checkins.forEach((c) => {
    if (c.phase === 'after') after[c.user_id + ':' + c.session_id] = c.mood;
  });
  let sum = 0;
  let pairs = 0;
  checkins.forEach((c) => {
    const key = c.user_id + ':' + c.session_id;
    if (c.phase === 'before' && Object.prototype.hasOwnProperty.call(after, key)) {
      sum += after[key] - c.mood;
      pairs++;
    }
  });
  return [pairs ? sum / pairs : null, pairs];
}

/** Classes joined, the current run of consecutive days with a class, and the average mood change. */
function practiceStats_(ctx, userId) {
  const sessions = sessionsById_(ctx);
  const mine = ctx.db.t('checkins').rows.filter((c) => c.user_id === userId);
  const today = istDay_(ctx.now);
  const seen = {};
  mine.forEach((c) => {
    if (c.phase === 'before' && sessions[c.session_id]) seen[istDay_(sessions[c.session_id].starts_at)] = true;
  });
  // a check-in for a later class does not count yet
  const days = Object.keys(seen).map(Number).filter((d) => d <= today).sort((a, b) => b - a);
  let streak = 0;
  let expected = today;
  if (days.length && days[0] < expected) expected -= 1; // today's class may not have happened yet
  for (let i = 0; i < days.length; i++) {
    if (days[i] !== expected) break;
    streak++;
    expected--;
  }
  const [change, pairs] = moodChange_(mine);
  return { classes_joined: days.length, streak_days: streak, mood_change: change, mood_pairs: pairs };
}

/** Rounds to one decimal, a tie to the even digit as Python's round() does: 2.25 is 2.2 and 2.75 is 2.8. Among averages
 * of moods the only exact ties are the quarters. */
function round1_(x) {
  const tenths = x * 10;
  if (Number.isInteger(x * 4) && !Number.isInteger(x * 2)) {
    const low = Math.floor(tenths);
    return (low % 2 === 0 ? low : low + 1) / 10;
  }
  return Number(x.toFixed(1));
}

function average1_(values) {
  return values.length ? round1_(values.reduce((a, b) => a + b, 0) / values.length) : null;
}

/** The student's classes over the last `days` days (1 to 90), with the sums done: classes joined, average mood
 * before and after, and the same per class, class names in `lang`. */
function practiceSummary_(ctx, userId, days, lang) {
  days = Math.max(1, Math.min(days, 90));
  const sessions = sessionsById_(ctx);
  const mine = ctx.db.t('checkins').rows.filter((c) => c.user_id === userId);
  const afterBySession = {};
  mine.forEach((c) => {
    if (c.phase === 'after') afterBySession[c.session_id] = c.mood;
  });
  const from = ctx.now - days * DAY_MS_;
  const rows = mine
    .filter((c) => c.phase === 'before' && sessions[c.session_id])
    .map((c) => ({ session: sessions[c.session_id], before: c.mood,
      after: Object.prototype.hasOwnProperty.call(afterBySession, c.session_id) ? afterBySession[c.session_id] : null }))
    .filter((r) => r.session.starts_at >= from && r.session.starts_at <= ctx.now)
    .sort((a, b) => a.session.starts_at - b.session.starts_at);
  const classes = [];
  const byClass = {};
  const plan = sessionCurricula_(ctx);
  rows.forEach((r) => {
    const name = classInfo_(r.session.class_key, lang).name;
    classes.push({ date: istDate_(r.session.starts_at), class: name, curriculum: plan[r.session.id], mood_before: r.before, mood_after: r.after });
    const entry = byClass[name] || (byClass[name] = { times: 0, before: [], after: [] });
    entry.times += 1;
    entry.before.push(r.before);
    if (r.after !== null) entry.after.push(r.after);
  });
  const summary = {};
  Object.keys(byClass).forEach((name) => {
    const e = byClass[name];
    summary[name] = { times: e.times, average_mood_before: average1_(e.before), average_mood_after: average1_(e.after) };
  });
  const library = curriculum_(ctx).library;
  const itemsBySolo = {};
  ctx.db.t('practice').rows.forEach((p) => {
    if (p.user_id === userId && p.solo_id !== null) (itemsBySolo[p.solo_id] || (itemsBySolo[p.solo_id] = [])).push(p);
  });
  const solo = ctx.db.t('solo_sessions').rows
    .filter((s) => s.user_id === userId && s.started_at >= from && s.started_at <= ctx.now)
    .sort((a, b) => a.started_at - b.started_at)
    .map((s) => ({ date: istDate_(s.started_at), minutes: Math.round((s.ended_at - s.started_at) / 60000),
      items: (itemsBySolo[s.id] || []).sort((a, b) => a.id - b.id).map((p) => itemTitle_(library[p.item], p.item, lang)) }));
  return {
    period_days: days,
    classes_joined: classes.length,
    mood_scale: '1 very low to 5 great',
    average_mood_before: average1_(rows.map((r) => r.before)),
    average_mood_after: average1_(rows.filter((r) => r.after !== null).map((r) => r.after)),
    by_class: summary,
    classes: classes,
    solo: solo,
  };
}

/** An item's name for people: transliterated in English, Devanagari in Hindi and Marathi. */
function itemTitle_(entry, key, lang) {
  if (!entry) return key;
  return lang === 'en' ? entry.name : entry.sanskrit;
}

/** The WhatsApp message for one session, its wa.me link, and the group to post it in. */
function shareFor_(ctx, row, lang) {
  const link = row.meet_link || ctx.db.setting('default_meet_link');
  if (!link) throw new HttpError_(400, 'no_link');
  const name = classInfo_(row.class_key, lang).name;
  const text = classMessage_(name, row.starts_at, row.duration_min, link, lang);
  return { text: text, url: shareUrl_(text), group_link: ctx.db.setting('group_link') };
}

// ---------- WhatsApp messages ----------
// The app never reads the WhatsApp group; the teacher posts from the app through Android's share sheet.

const TEXT_ = {
  class: {
    en: '🧘 {studio} · {name}\n📅 {day}, {time} IST ({minutes} min)\n🔗 Join: {link}\n\nOpen the app to check in before class.',
    hi: '🧘 {studio} · {name}\n📅 {day}, {time} IST ({minutes} मिनट)\n🔗 जुड़ें: {link}\n\nकक्षा से पहले ऐप में चेक-इन करें।',
    mr: '🧘 {studio} · {name}\n📅 {day}, {time} IST ({minutes} मिनिटे)\n🔗 सामील व्हा: {link}\n\nवर्गापूर्वी ॲपमध्ये चेक-इन करा.',
  },
  invite: {
    en: '🙏 Join {studio} in the app.\nSign up with your WhatsApp number and this group code: *{code}*',
    hi: '🙏 ऐप में {studio} से जुड़ें।\nअपने व्हाट्सऐप नंबर और इस ग्रुप कोड से साइन अप करें: *{code}*',
    mr: '🙏 ॲपमध्ये {studio} मध्ये सामील व्हा.\nतुमचा व्हॉट्सॲप नंबर आणि हा ग्रुप कोड वापरून साइन अप करा: *{code}*',
  },
};
const DAY_NAMES_ = {
  en: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
  hi: ['सोम', 'मंगल', 'बुध', 'गुरु', 'शुक्र', 'शनि', 'रवि'],
  mr: ['सोम', 'मंगळ', 'बुध', 'गुरु', 'शुक्र', 'शनि', 'रवि'],
};

function fill_(template, values) {
  return template.replace(/\{(\w+)\}/g, (all, key) => (Object.prototype.hasOwnProperty.call(values, key) ? String(values[key]) : all));
}

function classMessage_(className, startsAt, minutes, link, lang) {
  const p = istParts_(startsAt);
  const day = DAY_NAMES_[lang][p.weekday] + ' ' + p.day + ' ' + MONTH_NAMES_[p.month];
  return fill_(pick_(TEXT_.class, lang), { studio: pick_(STUDIO.name, lang), name: className, day: day, time: istClock_(startsAt),
    minutes: minutes, link: link });
}

function inviteMessage_(code, lang) {
  return fill_(pick_(TEXT_.invite, lang), { studio: pick_(STUDIO.name, lang), code: code });
}

/** A wa.me link that opens WhatsApp with `text` ready to send: every character but letters, digits and _.-~/ escaped. */
function shareUrl_(text) {
  const quoted = encodeURIComponent(text)
    .replace(/[!'()*]/g, (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase())
    .replace(/%2F/g, '/');
  return 'https://wa.me/?text=' + quoted;
}
