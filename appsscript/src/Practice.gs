// ---------- Practice: the curriculum, each class's plan, and how each item went ----------
// The curriculum lives in three tabs (library, curricula, curriculum_items), so the owner can change it in the Sheet.
// The teacher picks one curriculum per class; students react to its items after class, one tap each.

/** The curriculum as the Sheet holds it: the library by key, the curricula in tab order, each one's items in order. */
function curriculum_(ctx) {
  const library = {};
  ctx.db.t('library').rows.forEach((r) => {
    if (r.key) library[r.key] = r;
  });
  const items = {};
  ctx.db.t('curriculum_items').rows
    .filter((r) => r.curriculum && library[r.item])
    .sort((a, b) => a.position - b.position)
    .forEach((r) => {
      (items[r.curriculum] || (items[r.curriculum] = [])).push(r);
    });
  return { library: library, curricula: ctx.db.t('curricula').rows.filter((r) => r.key), items: items };
}

/** Each session's curriculum by session id: its own, else the one last used for a class of its kind, else the first
 * in the curricula tab (Beginner, as seeded). */
function sessionCurricula_(ctx) {
  const known = {};
  const keys = ctx.db.t('curricula').rows.filter((r) => r.key).map((r) => r.key);
  keys.forEach((k) => {
    known[k] = true;
  });
  const last = {};
  const out = {};
  ctx.db.t('class_sessions').rows.slice().sort((a, b) => a.starts_at - b.starts_at).forEach((r) => {
    if (known[r.curriculum]) last[r.class_key] = r.curriculum;
    out[r.id] = last[r.class_key] || keys[0] || null;
  });
  return out;
}

/** The library and the curricula in the student's language (the Devanagari names serve Hindi and Marathi). */
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
      items: (c.items[r.key] || []).map((i) => ({ item: i.item, dose: i.dose, unit: i.unit, cue: local(i, 'cue') })),
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

/** After class, how each item went for this student. Open while the "after" check-in is; a second send replaces the
 * first. Entries with no reaction, no pain and no note are not kept. */
function sessionPractice_(ctx) {
  const user = currentUser_(ctx);
  const { path, body } = ctx.check({ path: PATH_SESSION_, body: BODY_.practice });
  if (user.status !== 'approved') throw new HttpError_(403, 'pending');
  const row = sessionRow_(ctx, path.session_id);
  const end = row.starts_at + row.duration_min * 60000;
  const joined = ctx.db.t('checkins').rows.some((c) => c.user_id === user.id && c.session_id === row.id && c.phase === 'before');
  if (!joined || ctx.now < end - 10 * 60000 || ctx.now > end + 12 * 3600000) throw new HttpError_(400, 'checkin_closed');
  const library = curriculum_(ctx).library;
  const byItem = {};
  body.entries.forEach((e) => {
    if (!library[e.item]) throw new HttpError_(400, 'unknown_item');
    byItem[e.item] = e;
  });
  const kept = Object.keys(byItem).map((k) => byItem[k])
    .map((e) => Object.assign({}, e, { note: e.note === null ? null : e.note.trim() || null }))
    .filter((e) => e.reaction !== null || e.pain === 1 || e.note !== null);
  const table = ctx.db.t('practice');
  table.remove(table.rows.filter((r) => r.user_id === user.id && r.session_id === row.id));
  const day = istDay_(row.starts_at);
  const week = istMidnight_(day - ((day + 3) % 7)); // the Monday of the class's week
  let id = table.nextId();
  table.insert(kept.map((e) => ({ id: id++, user_id: user.id, session_id: row.id, item: e.item, reaction: e.reaction, pain: e.pain,
    note: e.note, created_at: ctx.now, item_name: library[e.item].name, week: week })));
  return { ok: true, saved: kept.length };
}

/** How a class went, item by item, for the teacher: the reactions counted (not yet, with effort, steady, at ease),
 * items with strain or pain first, each with who and what they wrote, then the other notes. */
function classReview_(ctx) {
  teacher_(ctx);
  const { path } = ctx.check({ path: PATH_SESSION_ });
  const row = sessionRow_(ctx, path.session_id);
  const names = {};
  ctx.db.t('users').rows.forEach((u) => {
    names[u.id] = u.name;
  });
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
      pain: mine.filter((e) => e.pain === 1).map((e) => ({ name: names[e.user_id], note: e.note })),
      notes: mine.filter((e) => e.pain !== 1 && e.note).map((e) => ({ name: names[e.user_id], text: e.note })),
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
