// ---------- Studio: the classes, the weekly rhythm in India time, and the sums over check-ins ----------

const IST_OFFSET_MS_ = 330 * 60000; // India is UTC+5:30 all year
const DAY_MS_ = 86400000;
const DAYS_ = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const MONTH_NAMES_ = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const CHECKIN_BEFORE_MIN_ = 60; // how early before class the "before" check-in opens
const MEET_CODE_ = /^[a-z]{3}-[a-z]{4}-[a-z]{3}$/i;

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

/** A number of two digits at least: 7 is "07". */
function pad2_(n) {
  return (n < 10 ? '0' : '') + n;
}

/** Minutes after midnight as a time of day: 420 is "07:00". */
function clockOf_(minutes) {
  return pad2_(Math.floor(minutes / 60)) + ':' + pad2_(minutes % 60);
}

/** Text with its Devanagari digits written as 0-9: "१०" is "10". */
function latinDigits_(text) {
  return String(text).replace(/[०-९]/g, (d) => String(d.charCodeAt(0) - 0x966));
}

/** strftime("%-I:%M %p") in India time: "8:00 AM". */
function istClock_(ms) {
  const p = istParts_(ms);
  return (p.hour % 12 || 12) + ':' + pad2_(p.minute) + ' ' + (p.hour < 12 ? 'AM' : 'PM');
}

/** One language out of a {"en": ..., "hi": ..., "mr": ...} dict, falling back to English. */
function pick_(text, lang) {
  return text[lang] || text.en;
}

/** A link's parts, with or without its https:// (or http://): the host in small letters, the path ("/" when none),
 * the query string and the fragment as written, the query's values by name, and whether it began with http(s)://;
 * null if it is not a web link. */
function linkParts_(text) {
  const m = /^(https?:\/\/)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)(\/[^?#\s]*)?(?:\?([^#\s]*))?(?:#(\S*))?$/i.exec(text);
  if (!m) return null;
  const values = {};
  (m[4] || '').split('&').forEach((pair) => {
    const eq = pair.indexOf('=');
    if (eq > 0) values[pair.slice(0, eq)] = pair.slice(eq + 1);
  });
  return { scheme: Boolean(m[1]), host: m[2].toLowerCase(), path: m[3] || '/', query: m[4] || '', fragment: m[5] || '', values: values };
}

/** The first word of what was pasted that `clean` makes a link of, the punctuation around it aside ("Join:
 * https://meet.google.com/abc-defg-hij."), a word with its http(s):// before any without; else 400 `detail`. */
function firstLink_(raw, clean, detail) {
  const parts = String(raw).trim().split(/\s+/)
    .map((word) => linkParts_(word.replace(/^[("'<[]+|[)"'>\].,;:!?]+$/g, '')))
    .filter(Boolean);
  const ordered = parts.filter((p) => p.scheme).concat(parts.filter((p) => !p.scheme));
  for (let i = 0; i < ordered.length; i++) {
    const link = clean(ordered[i]);
    if (link) return link;
  }
  throw new HttpError_(400, detail);
}

/** A link to a video call, made plain: Google Meet (its code in small letters; g.co/meet/ too), Zoom (a meeting, /j/
 * with its pwd as given, or a personal room, /my/, on any zoom.us address), Microsoft Teams (a meetup-join link as
 * given, or /meet/<id> with its p) or Jitsi Meet, always https. Else 400 bad_meet_link. */
function cleanMeetLink_(raw) {
  return firstLink_(raw, (p) => {
    const path = p.path.replace(/\/+$/, '');
    let m;
    if (p.host === 'meet.google.com' && (m = /^\/([\w-]+)$/.exec(path)) && MEET_CODE_.test(m[1])) return 'https://meet.google.com/' + m[1].toLowerCase();
    if (p.host === 'g.co' && (m = /^\/meet\/([\w-]+)$/i.exec(path))) {
      return MEET_CODE_.test(m[1]) ? 'https://meet.google.com/' + m[1].toLowerCase() : 'https://g.co/meet/' + m[1];
    }
    if (/^([\w-]+\.)*zoom\.us$/.test(p.host)) {
      const pwd = p.values.pwd ? '?pwd=' + p.values.pwd : '';
      if ((m = /^\/j\/(\d+)$/.exec(path))) return 'https://' + p.host + '/j/' + m[1] + pwd;
      if ((m = /^\/my\/([\w.-]+)$/.exec(path))) return 'https://' + p.host + '/my/' + m[1];
    }
    if (p.host === 'teams.microsoft.com' || p.host === 'teams.live.com') {
      if (/^\/l\/meetup-join\/./.test(path)) return 'https://' + p.host + p.path + (p.query ? '?' + p.query : '');
      if ((m = /^\/meet\/(\d+)$/.exec(path))) return 'https://' + p.host + '/meet/' + m[1] + (p.values.p ? '?p=' + p.values.p : '');
    }
    if (p.host === 'meet.jit.si' && (m = /^\/([\w-]+)$/.exec(path))) return 'https://meet.jit.si/' + m[1];
    return null;
  }, 'bad_meet_link');
}

/** The class group's link: a WhatsApp group invite (its code alone, the rest of the address dropped), or any other
 * link as written (a Telegram or Signal group, say), always https. Its address ends in a name of letters (".com",
 * ".me"); without http(s)://, it needs a path or a fragment too ("t.me/x", "signal.group/#…"), so words like
 * "Mr.Sharma", "e.g." or "7.00" are no link. Else 400 bad_group_link. */
function cleanGroupLink_(raw) {
  return firstLink_(raw, (p) => {
    if (!/\.[a-z]{2,}$/.test(p.host) || (!p.scheme && p.path === '/' && !p.fragment)) return null;
    if (p.host === 'chat.whatsapp.com') {
      const m = /^\/(?:invite\/)?([A-Za-z0-9]+)\/?$/.exec(p.path);
      return m ? 'https://chat.whatsapp.com/' + m[1] : null;
    }
    const rest = (p.query ? '?' + p.query : '') + (p.fragment ? '#' + p.fragment : '');
    return 'https://' + p.host + (p.path === '/' && !rest ? '' : p.path) + rest;
  }, 'bad_group_link');
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

/** A batch's time as the owner typed it ("07:00", "7.00", "17", "5:30 pm", "7 am", Devanagari digits too) as minutes
 * after midnight in India; null when it is no time (empty while the owner retypes it, "17h30"). */
function startMinutes_(time) {
  const text = latinDigits_(time === null || time === undefined ? '' : time);
  const bare = /^\s*(\d{1,2})\s*$/.exec(text); // "7", "17": the hour alone
  const m = bare || /(\d{1,2})(?:[:.](\d\d))?\s*([ap])?\.?\s*m?\b/i.exec(text);
  if (!m || (!bare && m[2] === undefined && !m[3])) return null;
  const hour = m[3] ? (Number(m[1]) % 12) + (m[3].toLowerCase() === 'p' ? 12 : 0) : Number(m[1]);
  const minute = Number(m[2] || 0);
  return hour < 24 && minute < 60 ? hour * 60 + minute : null;
}

/** A batch for the app, in `lang`: its key, name, words, days and start ("07:00", or null while its time is no time). */
function batchJson_(batch, key, lang) {
  if (!batch) return { key: key, name: key || '', about: '', days: [], time: null };
  return { key: batch.key, name: pick_(batch.name, lang), about: pick_(batch.about, lang), days: batch.days,
    time: batch.start_min === null ? null : clockOf_(batch.start_min) };
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

/** Each batch's classes on its days, over the 7 days from `now`'s India date; none for a batch whose time is no time. */
function weekStarts_(now, batches) {
  const today = istDay_(now);
  const out = [];
  for (let offset = 0; offset < 7; offset++) {
    const day = today + offset;
    const weekday = DAYS_[(day + 3) % 7]; // 1 Jan 1970 was a Thursday
    Object.keys(batches).forEach((key) => {
      const b = batches[key];
      if (b.start_min !== null && b.days.indexOf(weekday) >= 0) {
        out.push({ batch: key, starts_at: istMidnight_(day) + b.start_min * 60000, duration_min: b.duration_min });
      }
    });
  }
  return out;
}

/** Makes the next 7 days' classes match the batches, one class per batch per day. A day without its class gets one.
 * A class whose time or length no longer matches the batch's (the owner changed it) is moved in its row, keeping its
 * id, its own link and its curriculum, when nobody has checked in to it and both its old and its new start are more
 * than an hour away (out of its check-in window, perhaps after its message was shared); otherwise it stays as it is,
 * and the day gets no second class. A class is removed only on a day its batch no longer meets, under the same
 * conditions. A batch whose time is no time (being retyped, say) is left as it is. Takes the lock only when there is
 * something to change. */
function ensureWeek_(ctx) {
  const batches = batches_(ctx);
  const wanted = weekStarts_(ctx.now, batches);
  const today = istDay_(ctx.now);
  const dayOf = (r) => r.batch + '@' + istDay_(r.starts_at);
  const away = (ms) => ms - ctx.now > CHECKIN_BEFORE_MIN_ * 60000;
  const changes = (table) => {
    const joined = {};
    ctx.db.t('checkins').rows.forEach((c) => {
      joined[c.session_id] = true;
    });
    const free = (r) => away(r.starts_at) && !joined[r.id];
    const byDay = {};
    table.rows.forEach((r) => {
      const day = istDay_(r.starts_at);
      const timed = !batches[r.batch] || batches[r.batch].start_min !== null;
      if (timed && day >= today && day < today + 7) (byDay[dayOf(r)] || (byDay[dayOf(r)] = [])).push(r);
    });
    const todo = { missing: [], moved: [], stale: [] };
    const want = {};
    wanted.forEach((w) => {
      want[dayOf(w)] = true;
      const rows = byDay[dayOf(w)] || [];
      const row = rows[0];
      if (!row) todo.missing.push(w);
      else if (rows.length === 1 && free(row) && away(w.starts_at) && (row.starts_at !== w.starts_at || row.duration_min !== w.duration_min)) {
        todo.moved.push([row, w]);
      }
    });
    Object.keys(byDay).forEach((key) => {
      if (!want[key]) todo.stale = todo.stale.concat(byDay[key].filter(free));
    });
    return todo;
  };
  let todo = changes(ctx.db.t('class_sessions'));
  if (!todo.missing.length && !todo.moved.length && !todo.stale.length) return;
  ctx.lock(() => {
    const table = ctx.db.t('class_sessions');
    todo = changes(table);
    todo.moved.forEach(([row, w]) => table.update(row, { starts_at: w.starts_at, duration_min: w.duration_min, updated_at: ctx.now }));
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

/** The average mood change over (before, after) pairs of the given check-ins: [average or null, pairs]. A class
 * attended with no mood before (said how it went without checking in first) makes no pair. */
function moodChange_(checkins) {
  const after = {};
  checkins.forEach((c) => {
    if (c.phase === 'after' && c.mood !== null) after[c.user_id + ':' + c.session_id] = c.mood;
  });
  let sum = 0;
  let pairs = 0;
  checkins.forEach((c) => {
    const key = c.user_id + ':' + c.session_id;
    if (c.phase === 'before' && c.mood !== null && Object.prototype.hasOwnProperty.call(after, key)) {
      sum += after[key] - c.mood;
      pairs++;
    }
  });
  return [pairs ? sum / pairs : null, pairs];
}

/** Which classes are a student's: a test of a class, true when they were in its batch at some moment while it ran
 * (placed before its end, not moved out before its start). Their batches come from their placements and moves in
 * batch_changes, and from the users tab: a batch set there by hand, with no change logged, counts from its
 * batch_since, or from always when that is empty. */
function ownClasses_(ctx, user) {
  const changes = ctx.db.t('batch_changes').rows.filter((c) => c.student_id === user.id).sort((a, b) => a.created_at - b.created_at);
  const steps = [{ at: -Infinity, batch: changes.length ? changes[0].from : null }].concat(changes.map((c) => ({ at: c.created_at, batch: c.to })));
  if (user.batch !== steps[steps.length - 1].batch) steps.push({ at: user.batch_since === null ? 0 : user.batch_since, batch: user.batch });
  steps.sort((a, b) => a.at - b.at);
  return (session) => {
    const end = session.starts_at + session.duration_min * 60000;
    return steps.some((step, i) => step.batch === session.batch && step.at < end && (i === steps.length - 1 || steps[i + 1].at > session.starts_at));
  };
}

/** Classes joined, the run of classes in a row the student came to, and the average mood change. The run goes back
 * through the classes of the batch the student was in at the time of each ([ownClasses_]; a move starts no new count), and any
 * other they joined; one checked in to counts at once. A class still to come or under way does not break it, nor
 * one nobody came to: it was probably not held. Sent as streak_days. */
function practiceStats_(ctx, user) {
  const sessions = ctx.db.t('class_sessions').rows;
  const checkins = ctx.db.t('checkins').rows;
  const held = {};
  const mine = {};
  checkins.forEach((c) => {
    if (c.phase !== 'before') return;
    held[c.session_id] = true;
    if (c.user_id === user.id) mine[c.session_id] = true;
  });
  const own = ownClasses_(ctx, user);
  const ended = (s) => s.starts_at + s.duration_min * 60000 <= ctx.now;
  const run = sessions
    .filter((s) => mine[s.id] || (held[s.id] && ended(s) && own(s)))
    .sort((a, b) => b.starts_at - a.starts_at);
  let streak = 0;
  while (streak < run.length && mine[run[streak].id]) streak++;
  const [change, pairs] = moodChange_(checkins.filter((c) => c.user_id === user.id));
  return { classes_joined: sessions.filter((s) => mine[s.id]).length, streak_days: streak, mood_change: change, mood_pairs: pairs };
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
 * before and after (a class attended with no mood before counts in neither), and the same per class, class names in
 * `lang`. */
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
    classes.push({ date: istDate_(r.session.starts_at), at: isoTime_(r.session.starts_at), class: name, curriculum: plan[r.session.id],
      mood_before: r.before, mood_after: r.after });
    const entry = byClass[name] || (byClass[name] = { times: 0, before: [], after: [] });
    entry.times += 1;
    if (r.before !== null) entry.before.push(r.before);
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
    .map((s) => ({ date: istDate_(s.started_at), at: isoTime_(s.started_at), minutes: Math.round((s.ended_at - s.started_at) / 60000),
      items: (itemsBySolo[s.id] || []).sort((a, b) => a.id - b.id).map((p) => itemTitle_(library[p.item], p.item, lang)) }));
  // The items practised most in the period, in class and on one's own apart, so neither is taken for the other: how
  // often, the average reaction, strain or pain.
  const soloById = {};
  mySolo.forEach((s) => {
    soloById[s.id] = s;
  });
  const inClass = {};
  const onOwn = {};
  ctx.db.t('practice').rows.forEach((p) => {
    if (p.user_id !== userId) return;
    const alone = p.solo_id !== null;
    const at = alone ? (soloById[p.solo_id] || {}).started_at : (sessions[p.session_id] || {}).starts_at;
    if (at === undefined || at < from || at > ctx.now) return;
    const byItem = alone ? onOwn : inClass;
    const e = byItem[p.item] || (byItem[p.item] = { times: 0, reactions: [], pain: 0 });
    e.times += 1;
    if (p.reaction !== null) e.reactions.push(p.reaction);
    e.pain += p.pain;
  });
  const most = (byItem) => Object.keys(byItem).sort((a, b) => byItem[b].times - byItem[a].times || a.localeCompare(b)).slice(0, 5)
    .map((item) => ({ asana: itemTitle_(library[item], item, lang), times: byItem[item].times,
      average_reaction: average1_(byItem[item].reactions), pain_times: byItem[item].pain }));
  return {
    period_days: days,
    classes_joined: classes.length,
    average_mood_before: average1_(rows.filter((r) => r.before !== null).map((r) => r.before)),
    average_mood_after: average1_(rows.filter((r) => r.after !== null).map((r) => r.after)),
    by_class: summary,
    classes: classes,
    solo: solo,
    items_in_class: most(inClass),
    items_on_own: most(onOwn),
  };
}

/** An item's name for people: transliterated in English, Devanagari in Hindi and Marathi. */
function itemTitle_(entry, key, lang) {
  if (!entry) return key;
  return lang === 'en' ? entry.name : entry.sanskrit;
}

/** The message for one session, for the teacher to share with the class. */
function shareFor_(ctx, row, lang) {
  const batch = batches_(ctx)[row.batch];
  const link = row.meet_link || (batch && batch.meet_link);
  if (!link) throw new HttpError_(400, 'no_link');
  const name = batchJson_(batch, row.batch, lang).name;
  return { text: classMessage_(name, row.starts_at, row.duration_min, link, lang) };
}

/** What a check-in row copies from its class for the owner's queries: the batch's name and the India date. */
function checkinCopy_(ctx, session) {
  return { class: batchJson_(batches_(ctx)[session.batch], session.batch, 'en').name, class_date: istMidnight_(istDay_(session.starts_at)) };
}

// ---------- messages for the class ----------
// The app reads no chat. The teacher shares from the app through Android's share sheet, to the class's group on
// WhatsApp or anywhere else; the messages are plain text, for any app or an SMS.

const TEXT_ = {
  class: {
    en: '🧘 {studio} · {name}\n📅 {day}, {time} IST ({minutes} min)\n🔗 Join: {link}\n\nOpen the app to check in before class.',
    hi: '🧘 {studio} · {name}\n📅 {day}, {time} IST ({minutes} मिनट)\n🔗 जुड़ें: {link}\n\nकक्षा से पहले ऐप में चेक-इन करें।',
    mr: '🧘 {studio} · {name}\n📅 {day}, {time} IST ({minutes} मिनिटे)\n🔗 सामील व्हा: {link}\n\nवर्गापूर्वी ॲपमध्ये चेक-इन करा.',
  },
  invite: {
    en: '🙏 Join {studio} in the app.\n{app}Sign up with your phone number and this group code: {code}',
    hi: '🙏 ऐप में {studio} से जुड़ें।\n{app}अपने फ़ोन नंबर और इस ग्रुप कोड से साइन अप करें: {code}',
    mr: '🙏 ॲपमध्ये {studio} मध्ये सामील व्हा.\n{app}तुमचा फोन नंबर आणि हा ग्रुप कोड वापरून साइन अप करा: {code}',
  },
  get_app: {
    en: '📲 Get the app: {link}\n',
    hi: '📲 ऐप यहाँ से लें: {link}\n',
    mr: '📲 ॲप इथून घ्या: {link}\n',
  },
  // In a class review, for one whose row the owner deleted from the users tab.
  former_student: { en: 'A former student', hi: 'एक पूर्व विद्यार्थी', mr: 'एक माजी विद्यार्थी' },
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

/** The invite: the group code, and where to get the app when the settings tab has an app_link. */
function inviteMessage_(code, appLink, lang) {
  const app = appLink ? fill_(pick_(TEXT_.get_app, lang), { link: appLink }) : '';
  return fill_(pick_(TEXT_.invite, lang), { studio: pick_(STUDIO.name, lang), app: app, code: code });
}
