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

/** The batches, from the batches tab, by key: names and words in each language, the default curriculum, the days
 * ("mon"…), the start in minutes after midnight in India, the length and the everyday Meet link. */
function batches_(ctx) {
  const out = {};
  ctx.db.t('batches').rows.forEach((r) => {
    if (!r.key) return;
    out[r.key] = {
      key: r.key,
      name: { en: r.name, hi: r.name_hi || r.name, mr: r.name_mr || r.name },
      about: { en: r.about, hi: r.about_hi || r.about, mr: r.about_mr || r.about },
      curriculum: r.curriculum,
      days: String(r.days || '').split(',').map((d) => d.trim().toLowerCase().slice(0, 3)).filter((d) => DAYS_.indexOf(d) >= 0),
      start_min: startMinutes_(r.time),
      duration_min: r.duration_min || 55,
      meet_link: r.meet_link,
    };
  });
  return out;
}

/** "07:00" (or a time the owner typed, which Sheets keeps as a time of day) as minutes after midnight in India. */
function startMinutes_(time) {
  const text = String(time || '');
  const iso = /T(\d\d):(\d\d)/.exec(text); // a time-of-day cell, read back as a UTC moment
  if (iso) return (Number(iso[1]) * 60 + Number(iso[2]) + IST_OFFSET_MS_ / 60000) % 1440;
  const plain = /(\d{1,2})[:.](\d\d)/.exec(text);
  return plain ? Number(plain[1]) * 60 + Number(plain[2]) : 0;
}

/** A batch for the app, in `lang`: its key, name, words, days and start ("07:00"). */
function batchJson_(batch, key, lang) {
  if (!batch) return { key: key, name: key || '', about: '', days: [], time: null };
  const h = Math.floor(batch.start_min / 60);
  const m = batch.start_min % 60;
  return { key: batch.key, name: pick_(batch.name, lang), about: pick_(batch.about, lang), days: batch.days,
    time: (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m };
}

/** A session for the app. The link is shown only to approved members; without its own link a session uses its batch's
 * everyday link. */
function sessionJson_(row, lang, showLink, batches) {
  const batch = batches[row.batch];
  const link = row.meet_link || (batch && batch.meet_link);
  return {
    id: row.id,
    starts_at: isoTime_(row.starts_at),
    duration_min: row.duration_min,
    batch: batchJson_(batch, row.batch, lang),
    meet_link: showLink ? link || null : null,
    has_link: Boolean(link),
  };
}

function studioJson_(ctx, lang) {
  const teacher = STUDIO.teacher;
  const batches = batches_(ctx);
  return {
    name: pick_(STUDIO.name, lang),
    tagline: pick_(STUDIO.tagline, lang),
    since: STUDIO.since,
    teacher: { name: teacher.name, title: pick_(teacher.title, lang), bio: pick_(teacher.bio, lang) },
    batches: Object.keys(batches).map((key) => batchJson_(batches[key], key, lang)),
  };
}

/** Each batch's classes on its days, over the 7 days from `now`'s India date. */
function weekStarts_(now, batches) {
  const today = istDay_(now);
  const out = [];
  for (let offset = 0; offset < 7; offset++) {
    const day = today + offset;
    const weekday = DAYS_[(day + 3) % 7]; // 1 Jan 1970 was a Thursday
    Object.keys(batches).forEach((key) => {
      const b = batches[key];
      if (b.days.indexOf(weekday) >= 0) out.push({ batch: key, starts_at: istMidnight_(day) + b.start_min * 60000, duration_min: b.duration_min });
    });
  }
  return out;
}

/** Makes the next 7 days' classes match the batches: adds each one missing and removes one outside the schedule (after
 * the owner changed a batch's days or time) that has not begun and nobody has checked in to. Takes the lock only
 * when there is something to change. */
function ensureWeek_(ctx) {
  const wanted = weekStarts_(ctx.now, batches_(ctx));
  const keyOf = (r) => r.batch + '@' + r.starts_at;
  const want = {};
  wanted.forEach((w) => {
    want[keyOf(w)] = true;
  });
  const horizon = istMidnight_(istDay_(ctx.now) + 7);
  const changes = (table) => {
    const present = {};
    table.rows.forEach((r) => {
      present[keyOf(r)] = true;
    });
    const joined = {};
    ctx.db.t('checkins').rows.forEach((c) => {
      joined[c.session_id] = true;
    });
    return {
      missing: wanted.filter((w) => !present[keyOf(w)]),
      stale: table.rows.filter((r) => r.starts_at > ctx.now && r.starts_at < horizon && !want[keyOf(r)] && !joined[r.id]),
    };
  };
  let todo = changes(ctx.db.t('class_sessions'));
  if (!todo.missing.length && !todo.stale.length) return;
  ctx.lock(() => {
    const table = ctx.db.t('class_sessions');
    todo = changes(table);
    if (todo.stale.length) table.remove(todo.stale);
    let id = table.nextId();
    table.insert(todo.missing.map((w) => ({
      id: id++, batch: w.batch, starts_at: w.starts_at, duration_min: w.duration_min, meet_link: null, updated_at: ctx.now,
    })));
  });
}

/** Whether a class's after-class window is open at [now]: from 10 minutes before its end to 12 hours after it. */
function afterOpen_(session, now) {
  const end = session.starts_at + session.duration_min * 60000;
  return end - 10 * 60000 <= now && now <= end + 12 * 3600000;
}

/** Sessions that have not ended yet, soonest first: [batch]'s, or every batch's. */
function upcoming_(ctx, limit, batch) {
  ensureWeek_(ctx);
  const from = ctx.now - 2 * 3600000;
  return ctx.db.t('class_sessions').rows
    .filter((r) => (!batch || r.batch === batch) && r.starts_at >= from && r.starts_at + r.duration_min * 60000 > ctx.now)
    .sort((a, b) => a.starts_at - b.starts_at || String(a.batch).localeCompare(String(b.batch)))
    .slice(0, limit);
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
  const batches = batches_(ctx);
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
    const name = batchJson_(batches[r.session.batch], r.session.batch, lang).name;
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
  const mySolo = ctx.db.t('solo_sessions').rows.filter((s) => s.user_id === userId);
  const solo = mySolo
    .filter((s) => s.started_at >= from && s.started_at <= ctx.now)
    .sort((a, b) => a.started_at - b.started_at)
    .map((s) => ({ date: istDate_(s.started_at), minutes: Math.round((s.ended_at - s.started_at) / 60000),
      items: (itemsBySolo[s.id] || []).sort((a, b) => a.id - b.id).map((p) => itemTitle_(library[p.item], p.item, lang)) }));
  // The items practised most in the period, in class and on one's own: how often, the average reaction, strain or pain.
  const soloById = {};
  mySolo.forEach((s) => {
    soloById[s.id] = s;
  });
  const byItem = {};
  ctx.db.t('practice').rows.forEach((p) => {
    if (p.user_id !== userId) return;
    const at = p.solo_id !== null ? (soloById[p.solo_id] || {}).started_at : (sessions[p.session_id] || {}).starts_at;
    if (at === undefined || at < from || at > ctx.now) return;
    const e = byItem[p.item] || (byItem[p.item] = { times: 0, reactions: [], pain: 0 });
    e.times += 1;
    if (p.reaction !== null) e.reactions.push(p.reaction);
    e.pain += p.pain;
  });
  const topItems = Object.keys(byItem).sort((a, b) => byItem[b].times - byItem[a].times || a.localeCompare(b)).slice(0, 5)
    .map((item) => ({ asana: itemTitle_(library[item], item, lang), times: byItem[item].times,
      average_reaction: average1_(byItem[item].reactions), pain_times: byItem[item].pain }));
  return {
    period_days: days,
    classes_joined: classes.length,
    mood_scale: '1 very low to 5 great',
    average_mood_before: average1_(rows.map((r) => r.before)),
    average_mood_after: average1_(rows.filter((r) => r.after !== null).map((r) => r.after)),
    by_class: summary,
    classes: classes,
    solo: solo,
    top_items: topItems,
  };
}

/** An item's name for people: transliterated in English, Devanagari in Hindi and Marathi. */
function itemTitle_(entry, key, lang) {
  if (!entry) return key;
  return lang === 'en' ? entry.name : entry.sanskrit;
}

/** The WhatsApp message for one session, its wa.me link, and the group to post it in. */
function shareFor_(ctx, row, lang) {
  const batch = batches_(ctx)[row.batch];
  const link = row.meet_link || (batch && batch.meet_link);
  if (!link) throw new HttpError_(400, 'no_link');
  const name = batchJson_(batch, row.batch, lang).name;
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
