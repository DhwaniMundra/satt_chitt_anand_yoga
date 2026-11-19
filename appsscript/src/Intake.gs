// ---------- Intake: a student's answers about themselves, for the teacher to place them in a batch ----------
// Age, height, weight, food habits, pain or conditions, and a self-assessment of a few asanas (in content/studio.json).
// Health data: only the student and the teacher read it, its tabs are hidden, and the Dashboard shows it only as
// counts.

const PAIN_AREAS_ = ['knee', 'back', 'neck', 'shoulder', 'hip', 'other'];

/** A student's intake for the app, with the batch it points to; null before they fill it. */
function intakeOf_(ctx, userId) {
  const row = ctx.db.t('intake').rows.filter((r) => r.user_id === userId)[0];
  if (!row) return null;
  const ratings = ctx.db.t('intake_ratings').rows.filter((r) => r.user_id === userId)
    .map((r) => ({ item: r.item, reaction: r.reaction, pain: r.pain }));
  const pain = painAreas_(row.pain);
  return {
    age: row.age, height_cm: row.height_cm, weight_kg: row.weight_kg, food: row.food, meals: row.meals, pain: pain, pain_note: row.pain_note,
    ratings: ratings, updated_at: isoTime_(row.updated_at), suggested_batch: suggestedBatch_(ctx, pain, ratings),
  };
}

function painAreas_(text) {
  return String(text || '').split(',').map((a) => a.trim().toLowerCase()).filter((a) => a);
}

/** The batch the answers point to, for the teacher to confirm: any pain, Pain management; most of the
 * self-assessment steady or at ease (four or more answered), Intermediate; else Beginner. Never Advanced, which is
 * the teacher's call. The first batch when the owner has renamed these. */
function suggestedBatch_(ctx, pain, ratings) {
  const batches = batches_(ctx);
  const said = ratings.filter((r) => r.reaction !== null);
  const easy = said.filter((r) => r.reaction >= 3).length;
  const key = pain.length || ratings.some((r) => r.pain === 1) ? 'pain_management'
    : said.length >= 4 && easy * 2 > said.length ? 'intermediate' : 'beginner';
  return batches[key] ? key : Object.keys(batches)[0] || null;
}

function myIntake_(ctx) {
  return { intake: intakeOf_(ctx, currentUser_(ctx).id) };
}

/** A student's intake, after sign-up (pending) or later from Me; a second send replaces the first. */
function saveIntake_(ctx) {
  const user = currentUser_(ctx);
  if (user.role !== 'student') throw new HttpError_(403, 'students_only');
  const { body } = ctx.check({ body: BODY_.intake });
  const pain = painAreas_(body.pain);
  if (pain.some((a) => PAIN_AREAS_.indexOf(a) < 0)) throw new HttpError_(400, 'bad_pain_area');
  const asked = STUDIO.intake.assessment.map((a) => a.item);
  const byItem = {};
  body.ratings.forEach((r) => {
    if (asked.indexOf(r.item) < 0) throw new HttpError_(400, 'unknown_item');
    byItem[r.item] = r;
  });
  const trimmed = (text) => (text === null ? null : text.trim() || null);
  const values = { age: body.age, height_cm: body.height_cm, weight_kg: body.weight_kg, food: body.food, meals: trimmed(body.meals),
    pain: pain.join(', ') || null, pain_note: trimmed(body.pain_note), updated_at: ctx.now };
  const table = ctx.db.t('intake');
  const row = table.rows.filter((r) => r.user_id === user.id)[0];
  if (row) table.update(row, values);
  else table.insert([Object.assign({ user_id: user.id }, values)]);
  const ratings = ctx.db.t('intake_ratings');
  ratings.remove(ratings.rows.filter((r) => r.user_id === user.id));
  ratings.insert(Object.keys(byItem).map((k) => byItem[k]).filter((r) => r.reaction !== null || r.pain === 1)
    .map((r) => ({ user_id: user.id, item: r.item, reaction: r.reaction, pain: r.pain })));
  return { intake: intakeOf_(ctx, user.id) };
}
