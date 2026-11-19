// ---------- Routes: one function per route ----------
// Each checks who is asking first, then the inputs, then the rules: a signed-out request is a 401 whatever its inputs,
// and a bad input is a 422 before any rule is applied. Routes marked LOCK_ in routes_() run entirely under the script
// lock; the others take it only around their writes, so a slow password hash never holds up everyone else.

// ---------- public ----------

function health_() {
  // The assistant runs on the phone; this server has none.
  return { ok: true, assistant: 'off', model: null };
}

function studio_(ctx) {
  const { query } = ctx.check({ query: QUERY_LANG_ });
  return studioJson_(query.lang);
}

function signup_(ctx) {
  const { body } = ctx.check({ body: BODY_.signup });
  const phone = normalizePhone_(body.phone);
  const code = body.code.trim().toUpperCase();
  const hasTeacher = () => ctx.db.t('users').rows.some((u) => u.role === 'teacher');
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
  } else if (code) {
    if (!codeMatches_(ctx, code, 'group_code')) throw new HttpError_(400, 'bad_group_code');
    status = 'approved';
  } else {
    status = 'pending';
  }
  if (ctx.db.t('users').rows.some((u) => u.phone === phone)) throw new HttpError_(409, 'phone_taken');
  const pwHash = hashPassword_(body.password);
  return ctx.lock(() => {
    const users = ctx.db.t('users');
    if (body.role === 'teacher' && hasTeacher()) throw new HttpError_(409, 'teacher_exists');
    if (users.rows.some((u) => u.phone === phone)) throw new HttpError_(409, 'phone_taken');
    const user = users.insert([{
      id: users.nextId(), name: body.name.trim(), phone: phone, role: body.role, status: status, pw_hash: pwHash,
      lang: body.lang, created_at: ctx.now,
    }])[0];
    return signIn_(ctx, user);
  });
}

/** Teacher and group codes are compared in capitals, so "ramit2024" and "RAMIT2024" are the same code. */
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
  const user = ctx.db.t('users').rows.filter((u) => u.phone === phone)[0];
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
  return { user: userJson_(user), stats: practiceStats_(ctx, user.id) };
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

/** A pending student who later gets the group code from the WhatsApp group is approved at once. */
function joinGroup_(ctx) {
  const user = currentUser_(ctx);
  const { body } = ctx.check({ body: BODY_.code });
  const key = 'code:' + user.id;
  if (attemptsBlocked_(key)) throw new HttpError_(429, 'too_many_attempts');
  if (!codeMatches_(ctx, body.code.trim().toUpperCase(), 'group_code')) {
    attemptsFail_(key);
    throw new HttpError_(400, 'bad_group_code');
  }
  if (user.status === 'pending') ctx.db.t('users').update(user, { status: 'approved' });
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

/** Everything the student's Today screen needs in one call. */
function home_(ctx) {
  const user = currentUser_(ctx);
  const { query } = ctx.check({ query: QUERY_LANG_ });
  const lang = query.lang;
  const member = user.status === 'approved';
  const defaultLink = ctx.db.setting('default_meet_link');
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
  const sessions = upcoming_(ctx).map((r) => {
    const s = sessionJson_(r, lang, member, defaultLink);
    s.checked_in = Boolean(joined[r.id]);
    s.curriculum = plan[r.id];
    return s;
  });
  // The last class this person joined that has (nearly) ended, with no "after" check-in and nothing said about its items.
  const byId = sessionsById_(ctx);
  const waiting = Object.keys(joined)
    .map((id) => byId[id])
    .filter((s) => s && s.starts_at <= ctx.now && !answered[s.id])
    .sort((a, b) => b.starts_at - a.starts_at)[0];
  let after = null;
  if (waiting) {
    const end = waiting.starts_at + waiting.duration_min * 60000;
    if (end - 10 * 60000 <= ctx.now && ctx.now <= end + 12 * 3600000) {
      after = sessionJson_(waiting, lang, false, null);
      after.curriculum = plan[waiting.id];
    }
  }
  return {
    user: userJson_(user),
    studio: studioJson_(lang),
    sessions: sessions,
    after_checkin: after,
    group_link: member ? ctx.db.setting('group_link') : null,
  };
}

function checkin_(ctx) {
  const user = currentUser_(ctx);
  const { path, body } = ctx.check({ path: PATH_SESSION_, body: BODY_.checkin });
  if (user.status !== 'approved') throw new HttpError_(403, 'pending');
  const row = sessionRow_(ctx, path.session_id);
  const start = row.starts_at;
  const end = start + row.duration_min * 60000;
  const now = ctx.now;
  const checkins = ctx.db.t('checkins');
  const mine = (phase) => checkins.rows.filter((c) => c.user_id === user.id && c.session_id === row.id && c.phase === phase)[0];
  let open;
  if (body.phase === 'before') {
    open = start - CHECKIN_BEFORE_MIN_ * 60000 <= now && now <= end;
  } else {
    open = Boolean(mine('before')) && end - 10 * 60000 <= now && now <= end + 12 * 3600000;
  }
  if (!open) throw new HttpError_(400, 'checkin_closed');
  const existing = mine(body.phase);
  if (existing) {
    checkins.update(existing, { mood: body.mood });
  } else {
    checkins.insert([{ user_id: user.id, session_id: row.id, phase: body.phase, mood: body.mood, created_at: now,
      class: classInfo_(row.class_key, 'en').name, class_date: istMidnight_(istDay_(start)) }]);
  }
  return { ok: true, stats: practiceStats_(ctx, user.id) };
}

function feedback_(ctx) {
  const user = currentUser_(ctx);
  const { body } = ctx.check({ body: BODY_.feedback });
  const table = ctx.db.t('feedback');
  table.insert([{ id: table.nextId(), user_id: user.id, screen: body.screen, text: body.text.trim(), created_at: ctx.now }]);
  return { ok: true };
}

// ---------- teacher ----------

function teacherHome_(ctx) {
  teacher_(ctx);
  const { query } = ctx.check({ query: QUERY_LANG_ });
  const defaultLink = ctx.db.setting('default_meet_link');
  const joined = {};
  ctx.db.t('checkins').rows.forEach((c) => {
    if (c.phase === 'before') joined[c.session_id] = (joined[c.session_id] || 0) + 1;
  });
  const plan = sessionCurricula_(ctx);
  const sessions = upcoming_(ctx).map((r) => {
    const s = sessionJson_(r, query.lang, true, defaultLink);
    s.own_link = r.meet_link !== null && r.meet_link !== '';
    s.joined = joined[r.id] || 0;
    s.curriculum = plan[r.id];
    return s;
  });
  return {
    sessions: sessions,
    settings: { group_link: ctx.db.setting('group_link'), group_code: ctx.db.setting('group_code'), default_meet_link: defaultLink },
    pending_students: ctx.db.t('users').rows.filter((u) => u.status === 'pending').length,
  };
}

function setLink_(ctx) {
  teacher_(ctx);
  const { path, query, body } = ctx.check({ path: PATH_SESSION_, query: QUERY_LANG_, body: BODY_.link });
  const row = sessionRow_(ctx, path.session_id);
  const link = cleanMeetLink_(body.meet_link);
  ctx.db.t('class_sessions').update(row, { meet_link: link, updated_at: ctx.now });
  return shareFor_(ctx, row, query.lang);
}

function share_(ctx) {
  teacher_(ctx);
  const { path, query } = ctx.check({ path: PATH_SESSION_, query: QUERY_LANG_ });
  return shareFor_(ctx, sessionRow_(ctx, path.session_id), query.lang);
}

function updateSettings_(ctx) {
  teacher_(ctx);
  const { body } = ctx.check({ body: BODY_.settings });
  // Check both before saving either, so a bad link never leaves the other half-saved.
  const updates = {};
  if (body.group_link !== null) updates.group_link = cleanGroupLink_(body.group_link);
  if (body.default_meet_link !== null) updates.default_meet_link = cleanMeetLink_(body.default_meet_link);
  Object.keys(updates).forEach((key) => ctx.db.setSetting(key, updates[key]));
  return { group_link: ctx.db.setting('group_link'), group_code: ctx.db.setting('group_code'),
    default_meet_link: ctx.db.setting('default_meet_link') };
}

function rotateGroupCode_(ctx) {
  teacher_(ctx);
  ctx.db.setSetting('group_code', newCode_());
  return { group_code: ctx.db.setting('group_code') };
}

function invite_(ctx) {
  teacher_(ctx);
  const { query } = ctx.check({ query: QUERY_LANG_ });
  const text = inviteMessage_(ctx.db.setting('group_code'), query.lang);
  return { text: text, url: shareUrl_(text), group_link: ctx.db.setting('group_link') };
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
  return { students: rows.map((u) => Object.assign(userJson_(u), { joined: joined[u.id] || 0, created_at: isoTime_(u.created_at) })) };
}

function setStatus_(ctx) {
  teacher_(ctx);
  const { path, body } = ctx.check({ path: PATH_USER_, body: BODY_.status });
  const users = ctx.db.t('users');
  const student = users.rows.filter((u) => u.id === path.user_id && u.role === 'student')[0];
  if (!student) throw new HttpError_(404, 'no_student');
  users.update(student, { status: body.status });
  return { ok: true };
}

/** A new temporary password for a student who forgot theirs; the teacher passes it on in person or on WhatsApp.
 * Signs the student out everywhere. */
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
      const before = list.filter((c) => c.phase === 'before').map((c) => c.mood);
      const after = list.filter((c) => c.phase === 'after').map((c) => c.mood);
      return { id: s.id, starts_at: isoTime_(s.starts_at), class: classInfo_(s.class_key, 'en').name, joined: before.length,
        mood_before: mean(before), mood_after: mean(after), answered_after: after.length };
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
    students: { approved: count('approved'), pending: count('pending') },
    mood_change: change,
    mood_pairs: pairs,
    sessions: sessions,
    questions: { count: 0, gemma_latency_s: null }, // the assistant runs on the phone; questions never reach the server
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
  const shared = ctx.db.t('shared_notes').rows
    .filter((n) => Object.prototype.hasOwnProperty.call(names, n.user_id))
    .sort((a, b) => b.created_at - a.created_at || b.id - a.id)
    .slice(0, 50)
    .map((n) => ({ id: n.id, user_id: n.user_id, name: names[n.user_id], text: n.text, created_at: isoTime_(n.created_at) }));
  return { shared: shared };
}
