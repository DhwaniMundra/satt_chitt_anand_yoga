// ---------- Routes: one function per route ----------
// Each checks who is asking first, then the inputs, then the rules: a signed-out request is a 401 whatever its inputs,
// and a bad input is a 422 before any rule is applied. Routes marked LOCK_ in routes_() run entirely under the script
// lock; the others take it only around their writes, so a slow password hash never holds up everyone else.

// ---------- public ----------

function health_() {
  return { ok: true };
}

function studio_(ctx) {
  const { query } = ctx.check({ query: QUERY_LANG_ });
  return studioJson_(ctx, query.lang);
}

function signup_(ctx) {
  const { body } = ctx.check({ body: BODY_.signup });
  const phone = normalizePhone_(body.phone);
  // A code copied from a message may bring spaces, stars or a full stop with it.
  const code = body.code.replace(/^[^A-Za-z0-9]+|[^A-Za-z0-9]+$/g, '').toUpperCase();
  const hasTeacher = () => ctx.db.t('users').rows.some((u) => u.role === 'teacher');
  const taken = (users) => users.rows.some((u) => phoneOf_(u) === phone);
  let status;
  // The quick refusals come first, before the slow password hash; the lock below checks again.
  if (body.role === 'teacher') {
    if (hasTeacher()) throw new HttpError_(409, 'teacher_exists'); // one teacher per studio: the code works once
    ctx.lock(() => {
      if (attemptsBlocked_('login:teacher-code')) throw new HttpError_(429, 'too_many_attempts');
      if (!codeMatches_(ctx, code, 'teacher_code')) {
        attemptsFail_('login:teacher-code');
        throw new HttpError_(400, 'bad_teacher_code');
      }
    }, true);
    status = 'approved';
  } else {
    // The group code, which the teacher gives with the invite, keeps sign-ups to the class; the teacher then places
    // each student in a batch.
    const key = 'group-code:' + phone;
    ctx.lock(() => {
      if (attemptsBlocked_(key)) throw new HttpError_(429, 'too_many_attempts');
      if (!codeMatches_(ctx, code, 'group_code')) {
        attemptsFail_(key);
        throw new HttpError_(400, 'bad_group_code');
      }
    }, true);
    status = 'pending';
  }
  if (taken(ctx.db.t('users'))) throw new HttpError_(409, 'phone_taken');
  const pwHash = hashPassword_(body.password);
  return ctx.lock(() => {
    const users = ctx.db.t('users');
    if (body.role === 'teacher' && hasTeacher()) throw new HttpError_(409, 'teacher_exists');
    if (taken(users)) throw new HttpError_(409, 'phone_taken');
    const user = users.insert([{
      id: users.nextId(), name: body.name.trim(), phone: phone, role: body.role, status: status, pw_hash: pwHash,
      lang: body.lang, created_at: ctx.now,
    }])[0];
    return signIn_(ctx, user);
  });
}

/** Teacher and group codes are compared in capitals, so "yoga2024" and "YOGA2024" are the same code. */
function codeMatches_(ctx, code, key) {
  const want = (ctx.db.setting(key) || '').trim().toUpperCase();
  return want !== '' && code === want;
}

function login_(ctx) {
  const { body } = ctx.check({ body: BODY_.login });
  const phone = normalizePhone_(body.phone);
  const key = 'login:' + phone;
  // Counted as a failure until the password proves right, so parallel guesses cannot slip past the limit.
  ctx.lock(() => {
    if (attemptsBlocked_(key)) throw new HttpError_(429, 'too_many_attempts');
    attemptsFail_(key);
  }, true);
  const user = ctx.db.t('users').rows.filter((u) => phoneOf_(u) === phone)[0];
  const ok = checkPassword_(body.password, user ? user.pw_hash : DUMMY_HASH_); // the same work for an unknown number
  if (!user || !ok) throw new HttpError_(401, 'bad_login');
  return ctx.lock(() => {
    attemptsClear_(key);
    return signIn_(ctx, user);
  });
}

// ---------- signed in ----------

function logout_(ctx) {
  if (ctx.token) {
    const hash = sha256Hex_(ctx.token);
    const mine = (table) => table.rows.filter((r) => r.token_hash === hash);
    if (mine(ctx.db.t('tokens')).length) {
      ctx.lock(() => {
        const tokens = ctx.db.t('tokens');
        tokens.remove(mine(tokens));
        ctx.db.changedCache = true;
      });
    }
  }
  return { ok: true };
}

function me_(ctx) {
  const user = currentUser_(ctx);
  return { user: userJson_(user), stats: practiceStats_(ctx, user) };
}

/** A student (or the teacher) changing their own password: the current one first, under the login's brake on
 * guessing. This login stays signed in; every other is signed out. */
function changePassword_(ctx) {
  const user = currentUser_(ctx);
  const { body } = ctx.check({ body: BODY_.password });
  const key = 'login:' + phoneOf_(user);
  // Counted as a failure until the password proves right, as at login.
  ctx.lock(() => {
    if (attemptsBlocked_(key)) throw new HttpError_(429, 'too_many_attempts');
    attemptsFail_(key);
  }, true);
  if (!checkPassword_(body.current_password, user.pw_hash)) throw new HttpError_(400, 'bad_password');
  const pwHash = hashPassword_(body.new_password);
  const mine = sha256Hex_(ctx.token);
  return ctx.lock(() => {
    attemptsClear_(key);
    const users = ctx.db.t('users');
    const me = users.rows.filter((u) => u.id === user.id)[0];
    if (!me) throw new HttpError_(401, 'signed_out');
    users.update(me, { pw_hash: pwHash });
    const tokens = ctx.db.t('tokens');
    tokens.remove(tokens.rows.filter((r) => r.user_id === user.id && r.token_hash !== mine));
    ctx.db.changedCache = true;
    return { ok: true };
  });
}

function updateMe_(ctx) {
  const user = currentUser_(ctx);
  const { body } = ctx.check({ body: BODY_.me });
  const changes = {};
  if (body.name !== null) changes.name = body.name.trim();
  if (body.lang !== null) changes.lang = body.lang;
  ctx.db.t('users').update(user, changes);
  return { user: userJson_(user) };
}

/** What the get_my_practice tool on the phone hands Gemma: this student's classes over the last `days` days. */
function myPractice_(ctx) {
  const user = member_(ctx);
  const { query } = ctx.check({ query: { days: F_.int({ def: 7 }), lang: QUERY_LANG_.lang } });
  return practiceSummary_(ctx, user.id, query.days, query.lang);
}

/** One note the student chose to share with the teacher. Sharing the same words again returns the same note. */
function shareNote_(ctx) {
  const user = member_(ctx);
  const { body } = ctx.check({ body: BODY_.shared });
  if (user.role !== 'student') throw new HttpError_(403, 'pending');
  const text = body.text.trim();
  if (!text) throw new HttpError_(422, 'empty_note');
  const notes = ctx.db.t('shared_notes');
  let row = notes.rows.filter((n) => n.user_id === user.id && n.text === text)[0];
  if (!row) row = notes.insert([{ id: notes.nextId(), user_id: user.id, text: text, created_at: ctx.now }])[0];
  return { ok: true, id: row.id };
}

/** Everything the student's Today tab needs in one call. */
function home_(ctx) {
  const user = currentUser_(ctx);
  const { query } = ctx.check({ query: QUERY_LANG_ });
  const lang = query.lang;
  const member = user.status === 'approved';
  // A student sees only their batch's classes, once placed. Made first, so the classes this call adds have their
  // curriculum below.
  const coming = member && user.batch ? upcoming_(ctx, 7, user.batch) : [];
  const batches = batches_(ctx);
  const checkins = ctx.db.t('checkins').rows.filter((c) => c.user_id === user.id);
  const joined = {};
  const answered = {};
  checkins.forEach((c) => {
    if (c.phase === 'before') joined[c.session_id] = true;
    else answered[c.session_id] = true;
  });
  ctx.db.t('practice').rows.forEach((p) => {
    if (p.user_id === user.id) answered[p.session_id] = true;
  });
  const plan = sessionCurricula_(ctx);
  const sessions = coming.map((r) => {
    const s = sessionJson_(r, lang, member, batches);
    s.checked_in = Boolean(joined[r.id]);
    s.curriculum = plan[r.id];
    return s;
  });
  // The class to say how it went: the latest whose after-class window is open, with what was said about it so far
  // (null before an answer), so it can be said or changed. `after_checkin` is one the student checked in to;
  // `after_class` may also be one of their batch's they did not (having joined from the class's message), with
  // `checked_in` saying which.
  const all = ctx.db.t('class_sessions').rows;
  const latest = (list) => list.filter((s) => afterOpen_(s, ctx.now)).sort((a, b) => b.starts_at - a.starts_at)[0];
  const said = (open) => {
    if (!open) return null;
    const out = sessionJson_(open, lang, false, batches);
    out.curriculum = plan[open.id];
    out.checked_in = Boolean(joined[open.id]);
    const mood = checkins.filter((c) => c.session_id === open.id && c.phase === 'after').map((c) => c.mood)[0];
    out.said = !answered[open.id] ? null : {
      mood: mood === undefined ? null : mood,
      items: ctx.db.t('practice').rows.filter((p) => p.user_id === user.id && p.session_id === open.id)
        .map((p) => ({ item: p.item, reaction: p.reaction, pain: p.pain, note: p.note })),
    };
    return out;
  };
  const afterJoined = latest(all.filter((s) => joined[s.id]));
  const afterOwn = latest(all.filter((s) => joined[s.id] || (user.batch && s.batch === user.batch)));
  // Classes are for approved students only: one waiting or removed gets none, nor a class to say how it went.
  return {
    user: userJson_(user),
    batch: member && user.batch ? batchJson_(batches[user.batch], user.batch, lang) : null,
    studio: studioJson_(ctx, lang),
    sessions: sessions,
    after_checkin: member ? said(afterJoined) : null,
    after_class: member ? said(afterOwn) : null,
    group_link: member ? ctx.db.setting('group_link') : null,
  };
}

/** A mood before class ("before", from an hour before it to its end) or after it ("after", in the after-class
 * window). Many students check in as class starts, so everything but the check-ins tab is read before the lock, and
 * under it only that tab, read afresh, and the one write. */
function checkin_(ctx) {
  const user = currentUser_(ctx);
  const { path, body } = ctx.check({ path: PATH_SESSION_, body: BODY_.checkin });
  if (user.status !== 'approved') throw new HttpError_(403, 'pending');
  const row = sessionRow_(ctx, path.session_id);
  const own = row.batch === user.batch; // never for the teacher, who has no batch
  // Joining is for one's own batch's classes; a class joined before a move can still be answered after it.
  if (body.phase === 'before' && user.role === 'student' && !own) throw new HttpError_(403, 'other_batch');
  const start = row.starts_at;
  const end = start + row.duration_min * 60000;
  const entry = (phase, mood) => Object.assign({ user_id: user.id, session_id: row.id, phase: phase, mood: mood, created_at: ctx.now },
    checkinCopy_(ctx, row));
  const before = entry('before', body.phase === 'before' ? body.mood : null);
  const after = entry('after', body.mood);
  ctx.lock(() => {
    ctx.db.forget('checkins');
    const checkins = ctx.db.t('checkins');
    const mine = (phase) => checkins.rows.filter((c) => c.user_id === user.id && c.session_id === row.id && c.phase === phase)[0];
    const joined = mine('before');
    const open = body.phase === 'before'
      ? start - CHECKIN_BEFORE_MIN_ * 60000 <= ctx.now && ctx.now <= end
      : afterOpen_(row, ctx.now) && Boolean(joined || own);
    if (!open) throw new HttpError_(400, 'checkin_closed');
    const existing = mine(body.phase);
    if (existing) checkins.update(existing, { mood: body.mood });
    else if (body.phase === 'before') checkins.insert([before]);
    // Saying how class went with no check-in before it (having joined from the class's message) records coming to
    // it, with no mood before.
    else checkins.insert(joined ? [after] : [before, after]);
  }, true);
  return { ok: true, stats: practiceStats_(ctx, user) };
}

function feedback_(ctx) {
  const user = currentUser_(ctx);
  const { body } = ctx.check({ body: BODY_.feedback });
  const table = ctx.db.t('feedback');
  table.insert([{ id: table.nextId(), user_id: user.id, screen: body.screen, text: body.text.trim(), created_at: ctx.now }]);
  return { ok: true };
}

// ---------- teacher ----------

/** The teacher's day: the classes of the next day that has some left (today, or tomorrow once today's are over),
 * every batch's, each with its curriculum and link; the batches with their everyday links; the settings. */
function teacherHome_(ctx) {
  teacher_(ctx);
  const { query } = ctx.check({ query: QUERY_LANG_ });
  const ahead = upcoming_(ctx, 100); // first, so the classes this call adds have their curriculum below
  const batches = batches_(ctx);
  const joined = {};
  ctx.db.t('checkins').rows.forEach((c) => {
    if (c.phase === 'before') joined[c.session_id] = (joined[c.session_id] || 0) + 1;
  });
  const plan = sessionCurricula_(ctx);
  const day = ahead.length ? istDay_(ahead[0].starts_at) : null;
  const sessions = ahead.filter((r) => istDay_(r.starts_at) === day).map((r) => {
    const s = sessionJson_(r, query.lang, true, batches);
    s.own_link = r.meet_link !== null && r.meet_link !== '';
    s.joined = joined[r.id] || 0;
    s.curriculum = plan[r.id];
    return s;
  });
  return {
    sessions: sessions,
    batches: Object.keys(batches).map((key) => Object.assign(batchJson_(batches[key], key, query.lang), { meet_link: batches[key].meet_link })),
    settings: { group_link: ctx.db.setting('group_link'), group_code: ctx.db.setting('group_code') },
    pending_students: ctx.db.t('users').rows.filter((u) => u.status === 'pending').length,
  };
}

/** A batch's everyday Meet link, for its classes without their own; an empty one removes it. */
function setBatchLink_(ctx) {
  teacher_(ctx);
  const { path, body } = ctx.check({ path: PATH_BATCH_, body: BODY_.link });
  const row = ctx.db.t('batches').rows.filter((r) => r.key === path.key)[0];
  if (!row) throw new HttpError_(404, 'no_batch');
  ctx.db.t('batches').update(row, { meet_link: (body.meet_link || '').trim() ? cleanMeetLink_(body.meet_link) : null });
  return { ok: true, meet_link: row.meet_link };
}

/** One class's own link, and the message to share it. */
function setLink_(ctx) {
  teacher_(ctx);
  const { path, query, body } = ctx.check({ path: PATH_SESSION_, query: QUERY_LANG_, body: BODY_.link });
  const row = sessionRow_(ctx, path.session_id);
  const link = cleanMeetLink_(body.meet_link || '');
  ctx.db.t('class_sessions').update(row, { meet_link: link, updated_at: ctx.now });
  return shareFor_(ctx, row, query.lang);
}

function share_(ctx) {
  teacher_(ctx);
  const { path, query } = ctx.check({ path: PATH_SESSION_, query: QUERY_LANG_ });
  return shareFor_(ctx, sessionRow_(ctx, path.session_id), query.lang);
}

/** The class group's link, optional: given, it is checked before it is saved; empty or null, it is removed. */
function updateSettings_(ctx) {
  teacher_(ctx);
  const { body } = ctx.check({ body: BODY_.settings });
  if (body.group_link !== undefined) {
    ctx.db.setSetting('group_link', (body.group_link || '').trim() ? cleanGroupLink_(body.group_link) : null);
  }
  return { group_link: ctx.db.setting('group_link'), group_code: ctx.db.setting('group_code') };
}

function rotateGroupCode_(ctx) {
  teacher_(ctx);
  ctx.db.setSetting('group_code', newCode_());
  return { group_code: ctx.db.setting('group_code') };
}

function invite_(ctx) {
  teacher_(ctx);
  const { query } = ctx.check({ query: QUERY_LANG_ });
  return { text: inviteMessage_(ctx.db.setting('group_code'), ctx.db.setting('app_link'), query.lang) };
}

function students_(ctx) {
  teacher_(ctx);
  const joined = {};
  ctx.db.t('checkins').rows.forEach((c) => {
    if (c.phase === 'before') joined[c.user_id] = (joined[c.user_id] || 0) + 1;
  });
  const rows = ctx.db.t('users').rows
    .filter((u) => u.role === 'student')
    .sort((a, b) => (b.status === 'pending') - (a.status === 'pending') || b.created_at - a.created_at || a.id - b.id);
  return { students: rows.map((u) => Object.assign(userJson_(u), { joined: joined[u.id] || 0, intake: intakeOf_(ctx, u.id) })) };
}

/** Removes a student, or takes a removed one back into their batch; placing a new student is placeInBatch_. */
function setStatus_(ctx) {
  teacher_(ctx);
  const { path, body } = ctx.check({ path: PATH_USER_, body: BODY_.status });
  const student = studentRow_(ctx, path.user_id);
  if (body.status === 'approved' && !student.batch) throw new HttpError_(400, 'needs_batch');
  ctx.db.t('users').update(student, { status: body.status });
  return { ok: true };
}

/** Places a student in a batch: a new one ("Approve into a batch"), or one moving after a review. Each is logged in
 * batch_changes, with the teacher's note. */
function placeInBatch_(ctx) {
  teacher_(ctx);
  const { path, body } = ctx.check({ path: PATH_USER_, body: BODY_.place });
  const student = studentRow_(ctx, path.user_id);
  if (!batches_(ctx)[body.batch]) throw new HttpError_(400, 'no_batch');
  const changes = ctx.db.t('batch_changes');
  changes.insert([{ id: changes.nextId(), student_id: student.id, from: student.batch || null, to: body.batch,
    note: body.note === null ? null : body.note.trim() || null, created_at: ctx.now }]);
  ctx.db.t('users').update(student, { batch: body.batch, batch_since: ctx.now, status: 'approved' });
  return { ok: true, student: userJson_(student) };
}

/** A new temporary password for a student who forgot theirs, for the teacher to pass on however the class keeps in
 * touch; the student can change it from the Me tab. Signs the student out everywhere. */
function resetPassword_(ctx) {
  teacher_(ctx);
  const { path } = ctx.check({ path: PATH_USER_ });
  const isStudent = (u) => u.id === path.user_id && u.role === 'student';
  if (!ctx.db.t('users').rows.some(isStudent)) throw new HttpError_(404, 'no_student');
  const password = newCode_(8);
  const pwHash = hashPassword_(password);
  return ctx.lock(() => {
    const users = ctx.db.t('users');
    const student = users.rows.filter(isStudent)[0];
    if (!student) throw new HttpError_(404, 'no_student');
    users.update(student, { pw_hash: pwHash });
    const tokens = ctx.db.t('tokens');
    tokens.remove(tokens.rows.filter((r) => r.user_id === student.id));
    ctx.db.changedCache = true;
    return { password: password };
  });
}

/** How the last two weeks of classes went, from the students' one-tap check-ins and feedback. */
function insights_(ctx) {
  teacher_(ctx);
  const { query } = ctx.check({ query: QUERY_LANG_ });
  const batches = batches_(ctx);
  const now = ctx.now;
  const checkins = ctx.db.t('checkins').rows;
  const bySession = {};
  checkins.forEach((c) => {
    (bySession[c.session_id] || (bySession[c.session_id] = [])).push(c);
  });
  const mean = (values) => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : null);
  const sessions = ctx.db.t('class_sessions').rows
    .filter((s) => s.starts_at >= now - 14 * DAY_MS_ && s.starts_at <= now)
    .sort((a, b) => b.starts_at - a.starts_at)
    .map((s) => {
      const list = bySession[s.id] || [];
      const before = list.filter((c) => c.phase === 'before');
      const moods = (rows) => rows.map((c) => c.mood).filter((m) => m !== null); // one who came with no mood before has none
      return { id: s.id, starts_at: isoTime_(s.starts_at), class: batchJson_(batches[s.batch], s.batch, query.lang).name, joined: before.length,
        mood_before: mean(moods(before)), mood_after: mean(moods(list.filter((c) => c.phase === 'after'))) };
    });
  const [change, pairs] = moodChange_(checkins);
  const users = ctx.db.t('users').rows;
  const count = (status) => users.filter((u) => u.role === 'student' && u.status === status).length;
  const names = {};
  users.forEach((u) => {
    names[u.id] = u.name;
  });
  const feedback = ctx.db.t('feedback').rows
    .filter((f) => Object.prototype.hasOwnProperty.call(names, f.user_id))
    .sort((a, b) => b.created_at - a.created_at || a.id - b.id) // equal times in the order written
    .slice(0, 20)
    .map((f) => ({ screen: f.screen, text: f.text, created_at: isoTime_(f.created_at), name: names[f.user_id] }));
  return {
    students: { approved: count('approved') },
    mood_change: change,
    mood_pairs: pairs,
    sessions: sessions,
    feedback: feedback,
  };
}

/** The notes students chose to share, newest first (the last 50). */
function sharedNotes_(ctx) {
  teacher_(ctx);
  const names = {};
  ctx.db.t('users').rows.forEach((u) => {
    names[u.id] = u.name;
  });
  const all = ctx.db.t('shared_notes').rows
    .filter((n) => Object.prototype.hasOwnProperty.call(names, n.user_id))
    .sort((a, b) => b.created_at - a.created_at || b.id - a.id);
  // The newest 50 to read; the count is of them all.
  const shared = all.slice(0, 50)
    .map((n) => ({ id: n.id, user_id: n.user_id, name: names[n.user_id], text: n.text, created_at: isoTime_(n.created_at) }));
  return { shared: shared, count: all.length };
}
