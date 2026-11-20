// ---------- Practice: the curriculum, each class's plan, how each item went, and each student's history ----------
// The curriculum lives in three tabs (library, curricula, curriculum_items), so the owner can change it in the Sheet.
// The teacher picks one curriculum per class; students react to its items after class, one tap each, and practise
// on their own with a stopwatch; the teacher reads each student's history per item and can write feedback on an
// item, which the student sees with it.

const MAX_HOLD_S_ = 3600; // the app's stopwatch stops at an hour

/** The library tab by key. */
function library_(ctx) {
  const library = {};
  ctx.db.t('library').rows.forEach((r) => {
    if (r.key) library[r.key] = r;
  });
  return library;
}

/** The curriculum as the Sheet holds it: the library by key, the curricula in tab order, each one's items in order. */
function curriculum_(ctx) {
  const library = library_(ctx);
  const items = {};
  ctx.db.t('curriculum_items').rows
    .filter((r) => r.curriculum && library[r.item])
    .sort((a, b) => a.position - b.position)
    .forEach((r) => {
      (items[r.curriculum] || (items[r.curriculum] = [])).push(r);
    });
  return { library: library, curricula: ctx.db.t('curricula').rows.filter((r) => r.key), items: items };
}

/** Each session's curriculum by session id: its own, else its batch's, else the first in the curricula tab. */
function sessionCurricula_(ctx) {
  const known = {};
  const keys = ctx.db.t('curricula').rows.filter((r) => r.key).map((r) => r.key);
  keys.forEach((k) => {
    known[k] = true;
  });
  const batches = batches_(ctx);
  const out = {};
  ctx.db.t('class_sessions').rows.forEach((r) => {
    const batch = batches[r.batch];
    out[r.id] = (known[r.curriculum] && r.curriculum) || (batch && known[batch.curriculum] && batch.curriculum) || keys[0] || null;
  });
  return out;
}

/** The library and the curricula in the student's language (the Devanagari names serve Hindi and Marathi). An item's
 * dose is always a whole number, rounded down (2.5 is 2), 0 when its cell holds none (the app then shows the unit or
 * the cue alone); a count that is not whole comes as written in dose_label too ("2.5"). */
function curricula_(ctx) {
  currentUser_(ctx);
  const { query } = ctx.check({ query: QUERY_LANG_ });
  const local = (row, col) => (query.lang === 'en' ? row[col] : row[col + '_' + query.lang]) || row[col];
  const c = curriculum_(ctx);
  return {
    library: Object.keys(c.library).map((key) => {
      const r = c.library[key];
      return { key: r.key, type: r.type, level: r.level, sanskrit: r.sanskrit, name: r.name, english: r.english,
        aliases: r.aliases.split(',').map((a) => a.trim()).filter((a) => a) };
    }),
    curricula: c.curricula.map((r) => ({
      key: r.key, name: local(r, 'name'), level: r.level, about: local(r, 'about'),
      items: (c.items[r.key] || []).map((i) => {
        const item = { item: i.item, dose: Math.floor(i.dose || 0), unit: i.unit, cue: local(i, 'cue') };
        if (i.dose !== null && !Number.isInteger(i.dose)) item.dose_label = String(i.dose); // "2.5"
        return item;
      }),
    })),
  };
}

function setCurriculum_(ctx) {
  teacher_(ctx);
  const { path, body } = ctx.check({ path: PATH_SESSION_, body: BODY_.curriculum });
  const row = sessionRow_(ctx, path.session_id);
  if (!ctx.db.t('curricula').rows.some((r) => r.key === body.curriculum)) throw new HttpError_(400, 'no_curriculum');
  ctx.db.t('class_sessions').update(row, { curriculum: body.curriculum, updated_at: ctx.now });
  return { ok: true, curriculum: body.curriculum };
}

/** After class, how each item went for this student. Open while the "after" check-in is, to one who checked in or
 * whose class it is ([ownClasses_]); a second send replaces the first. Entries with no reaction, no pain and no note
 * are not kept. Who is asking, the class, whose class it is and the library are read before the lock, as a class sends
 * this all at once; under it, only the tabs it writes, read there for the first time: the check-ins (whether the
 * student checked in) and the practice entries. */
function sessionPractice_(ctx) {
  const user = currentUser_(ctx);
  const { path, body } = ctx.check({ path: PATH_SESSION_, body: BODY_.practice });
  if (user.status !== 'approved') throw new HttpError_(403, 'pending');
  const row = sessionRow_(ctx, path.session_id);
  if (!afterOpen_(row, ctx.now)) throw new HttpError_(400, 'checkin_closed');
  const own = ownClasses_(ctx, user)(row);
  const library = library_(ctx);
  const copy = checkinCopy_(ctx, row);
  return ctx.lock(() => {
    const kept = replayed_(ctx.request); // a copy of this send, with its request id, that had the lock first
    if (kept) return kept;
    const checkins = ctx.db.t('checkins');
    const joined = checkins.rows.some((c) => c.user_id === user.id && c.session_id === row.id && c.phase === 'before');
    if (!(joined || own)) throw new HttpError_(400, 'checkin_closed');
    const said = saidEntries_(body.entries, library);
    // Saying how it went records coming to the class, with no mood before, for one who did not check in.
    if (!joined && said.length) {
      checkins.insert([Object.assign({ user_id: user.id, session_id: row.id, phase: 'before', mood: null, created_at: ctx.now }, copy)]);
    }
    const table = ctx.db.t('practice');
    table.remove(table.rows.filter((r) => r.user_id === user.id && r.session_id === row.id));
    let id = table.nextId();
    table.insert(said.map((e) => ({ id: id++, user_id: user.id, session_id: row.id, item: e.item, reaction: e.reaction, pain: e.pain,
      note: e.note, created_at: ctx.now, item_name: library[e.item].name, week: mondayOf_(row.starts_at) })));
    return keepAnswer_(ctx.request, { ok: true, saved: said.length });
  }, true);
}

/** Practice on the student's own: each item with the stopwatch's seconds (an hour at most: a longer hold is kept as
 * an hour), how it went, strain or pain and a note. The server dates it: the session ends now and began `minutes`
 * ago. Items with nothing timed or said are not kept. Who is asking and the library are read before the lock; under
 * it, only the two tabs it writes. */
function soloPractice_(ctx) {
  const user = member_(ctx);
  const { body } = ctx.check({ body: BODY_.solo });
  const library = library_(ctx);
  const said = saidEntries_(body.entries, library);
  if (!said.length) throw new HttpError_(400, 'nothing_said');
  const started = ctx.now - body.minutes * 60000;
  return ctx.lock(() => {
    const kept = replayed_(ctx.request); // a copy of this send, with its request id, that had the lock first
    if (kept) return kept;
    const solo = ctx.db.t('solo_sessions');
    const row = solo.insert([{ id: solo.nextId(), user_id: user.id, started_at: started, ended_at: ctx.now }])[0];
    const table = ctx.db.t('practice');
    let id = table.nextId();
    table.insert(said.map((e) => ({ id: id++, user_id: user.id, solo_id: row.id, item: e.item, hold_s: Math.min(e.hold_s || 0, MAX_HOLD_S_) || null,
      reaction: e.reaction, pain: e.pain, note: e.note, created_at: ctx.now, item_name: library[e.item].name, week: mondayOf_(started) })));
    return keepAnswer_(ctx.request, { ok: true, id: row.id, saved: said.length });
  }, true);
}

/** The entries worth keeping, one per item (the last wins), notes trimmed: those with a reaction, strain or pain, a
 * note or a timed hold. An item outside the library is 400 unknown_item. */
function saidEntries_(entries, library) {
  const byItem = {};
  entries.forEach((e) => {
    if (!library[e.item]) throw new HttpError_(400, 'unknown_item');
    byItem[e.item] = e;
  });
  return Object.keys(byItem).map((k) => byItem[k])
    .map((e) => Object.assign({}, e, { note: e.note === null ? null : e.note.trim() || null }))
    .filter((e) => e.reaction !== null || e.pain === 1 || e.note !== null || Boolean(e.hold_s));
}

/** The Monday (midnight in India) of the week a moment falls in. */
function mondayOf_(ms) {
  const day = istDay_(ms);
  return istMidnight_(day - ((day + 3) % 7));
}

/** How a class went, item by item, for the teacher: the reactions counted (not yet, with effort, steady, at ease),
 * items with strain or pain first, each with who and what they wrote, then the other notes. One whose row the owner
 * deleted is named "A former student", in `lang`. */
function classReview_(ctx) {
  teacher_(ctx);
  const { path, query } = ctx.check({ path: PATH_SESSION_, query: QUERY_LANG_ });
  const row = sessionRow_(ctx, path.session_id);
  const names = {};
  ctx.db.t('users').rows.forEach((u) => {
    names[u.id] = u.name;
  });
  const nameOf = (id) => names[id] || pick_(TEXT_.former_student, query.lang);
  const plan = sessionCurricula_(ctx)[row.id];
  const entries = ctx.db.t('practice').rows.filter((r) => r.session_id === row.id).sort((a, b) => a.id - b.id);
  const order = (curriculum_(ctx).items[plan] || []).map((i) => i.item);
  entries.forEach((e) => {
    if (order.indexOf(e.item) < 0) order.push(e.item);
  });
  const items = order.map((item) => {
    const mine = entries.filter((e) => e.item === item);
    return {
      item: item,
      reactions: [1, 2, 3, 4].map((n) => mine.filter((e) => e.reaction === n).length),
      pain: mine.filter((e) => e.pain === 1).map((e) => ({ name: nameOf(e.user_id), note: e.note })),
      notes: mine.filter((e) => e.pain !== 1 && e.note).map((e) => ({ name: nameOf(e.user_id), text: e.note })),
    };
  });
  const answered = {};
  entries.forEach((e) => {
    answered[e.user_id] = true;
  });
  return {
    id: row.id,
    starts_at: isoTime_(row.starts_at),
    curriculum: plan,
    joined: ctx.db.t('checkins').rows.filter((c) => c.session_id === row.id && c.phase === 'before').length,
    answered: Object.keys(answered).length,
    items: items.filter((i) => i.pain.length).concat(items.filter((i) => !i.pain.length)),
  };
}

// ---------- each student's history per item, and the teacher's feedback on it ----------

/** How one student's practice of one item has gone, worked out in code from its rows: the times in class and on their
 * own, the reaction trend (the first reactions against the latest, up to three of each), the holds timed on their own,
 * strain or pain, the teacher's latest feedback, the student's notes, and every entry and piece of feedback, newest
 * first. [when] gives a row's moment: its class's start, or its solo session's. */
function itemProgress_(item, rows, feedback, when) {
  const entries = rows
    .map((r) => ({ at: when(r), solo: r.solo_id !== null, hold: r.hold_s, reaction: r.reaction, pain: r.pain === 1, note: r.note }))
    .filter((e) => e.at !== null)
    .sort((a, b) => a.at - b.at);
  const holds = entries.filter((e) => e.hold).map((e) => e.hold);
  const said = feedback.slice().sort((a, b) => a.created_at - b.created_at || a.id - b.id);
  const reactions = entries.filter((e) => e.reaction !== null).map((e) => e.reaction);
  const k = Math.min(3, Math.floor(reactions.length / 2));
  const pains = entries.filter((e) => e.pain);
  const latest = said[said.length - 1];
  return {
    item: item,
    in_class: entries.filter((e) => !e.solo).length,
    solo: entries.filter((e) => e.solo).length,
    first: entries.length ? istDate_(entries[0].at) : null,
    last: entries.length ? istDate_(entries[entries.length - 1].at) : null,
    reaction_trend: k ? { early_average: average1_(reactions.slice(0, k)), recent_average: average1_(reactions.slice(-k)), each: k } : null,
    holds: holds.length ? { recent_seconds: holds[holds.length - 1], longest_seconds: Math.max.apply(null, holds) } : null,
    strain_or_pain: { times: pains.length, last: pains.length ? istDate_(pains[pains.length - 1].at) : null },
    teacher_said: latest ? { date: istDate_(latest.created_at), text: latest.text } : null,
    your_notes: entries.filter((e) => e.note).slice(-5).map((e) => ({ date: istDate_(e.at), text: e.note })),
    entries: entries.slice().reverse().map((e) => ({ date: istDate_(e.at), at: isoTime_(e.at), kind: e.solo ? 'solo' : 'class', hold_s: e.hold,
      reaction: e.reaction, pain: e.pain ? 1 : 0, note: e.note })),
    feedback: said.slice().reverse().map((f) => ({ date: istDate_(f.created_at), at: isoTime_(f.created_at), text: f.text })),
  };
}

/** Each item one student has practised or had feedback on: {item: progress}. */
function progressByItem_(ctx, userId) {
  const rows = {};
  const feedback = {};
  ctx.db.t('practice').rows.forEach((r) => {
    if (r.user_id === userId) (rows[r.item] || (rows[r.item] = [])).push(r);
  });
  ctx.db.t('asana_feedback').rows.forEach((f) => {
    if (f.student_id === userId) (feedback[f.item] || (feedback[f.item] = [])).push(f);
  });
  const sessions = sessionsById_(ctx);
  const solos = {};
  ctx.db.t('solo_sessions').rows.forEach((s) => {
    if (s.user_id === userId) solos[s.id] = s;
  });
  const when = (r) => {
    const at = r.solo_id !== null ? solos[r.solo_id] && solos[r.solo_id].started_at : sessions[r.session_id] && sessions[r.session_id].starts_at;
    return at === undefined ? null : at;
  };
  const out = {};
  Object.keys(rows).concat(Object.keys(feedback)).forEach((item) => {
    if (!out[item]) out[item] = itemProgress_(item, rows[item] || [], feedback[item] || [], when);
  });
  return out;
}

/** For the Practice tab: each item with its counts and trend. What needs attention comes first: items with strain or
 * pain, then those the teacher wrote on (the latest first), then the rest, the most practised first. */
function itemList_(ctx, userId) {
  const all = progressByItem_(ctx, userId);
  return {
    items: Object.keys(all).map((item) => {
      const p = all[item];
      return { item: item, in_class: p.in_class, solo: p.solo, last: p.last, reaction_trend: p.reaction_trend,
        pain_times: p.strain_or_pain.times, teacher_said: p.teacher_said ? p.teacher_said.date : null };
    }).sort((a, b) => (b.pain_times > 0) - (a.pain_times > 0) || (b.teacher_said || '').localeCompare(a.teacher_said || '') ||
      b.in_class + b.solo - a.in_class - a.solo || a.item.localeCompare(b.item)),
  };
}

function oneItem_(ctx, userId, item) {
  return progressByItem_(ctx, userId)[item] || itemProgress_(item, [], [], () => null);
}

/** The student the teacher asks about, or 404 no_student (also when two rows share the id: userById_). */
function studentRow_(ctx, id) {
  const student = userById_(ctx.db.t('users').rows, id);
  if (!student || student.role !== 'student') throw new HttpError_(404, 'no_student');
  return student;
}

function myItems_(ctx) {
  return itemList_(ctx, member_(ctx).id);
}

function myItem_(ctx) {
  const user = member_(ctx);
  const { path } = ctx.check({ path: PATH_ITEM_ });
  return oneItem_(ctx, user.id, path.item);
}

function studentItems_(ctx) {
  teacher_(ctx);
  const { path } = ctx.check({ path: PATH_USER_ });
  return itemList_(ctx, studentRow_(ctx, path.user_id).id);
}

function studentItem_(ctx) {
  teacher_(ctx);
  const { path } = ctx.check({ path: Object.assign({}, PATH_USER_, PATH_ITEM_) });
  return oneItem_(ctx, studentRow_(ctx, path.user_id).id, path.item);
}

/** The teacher's word to one student about one item; the student sees it with that item's history. */
function itemFeedback_(ctx) {
  teacher_(ctx);
  const { path, body } = ctx.check({ path: PATH_USER_, body: BODY_.itemFeedback });
  const student = studentRow_(ctx, path.user_id);
  if (!curriculum_(ctx).library[body.item]) throw new HttpError_(400, 'unknown_item');
  const table = ctx.db.t('asana_feedback');
  const row = table.insert([{ id: table.nextId(), student_id: student.id, item: body.item, text: body.text.trim(), created_at: ctx.now }])[0];
  return { ok: true, id: row.id };
}
