// ---------- Auth: passwords, login tokens, codes, phone numbers, and the brakes on guessing ----------

// A password is stored as sha256x$<rounds>$<chars>$<salt>$<hash>: `rounds` SHA-256 digests in a row, each over about
// `chars` characters made from the previous digest, the salt and the password. Apps Script has no PBKDF2 and each
// call into Utilities costs a fixed overhead, so the work is put into long inputs rather than many tiny calls (see
// appsscript/README.md for the measured cost). The rounds and length are stored with each hash, so they can be raised
// later without breaking existing passwords.
const HASH_ROUNDS_ = 100;
const HASH_CHARS_ = 131072;
const DUMMY_HASH_ = 'sha256x$' + HASH_ROUNDS_ + '$' + HASH_CHARS_ + '$' + '0'.repeat(32) + '$' + '0'.repeat(64);
const CODE_ALPHABET_ = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // no 0/O or 1/I
const ATTEMPT_LIMIT_ = 5;
const ATTEMPT_WINDOW_S_ = 15 * 60;

function digestBytes_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text, Utilities.Charset.UTF_8).map((b) => b & 255);
}

function hex_(bytes) {
  return bytes.map((b) => (b < 16 ? '0' : '') + b.toString(16)).join('');
}

function sha256Hex_(text) {
  return hex_(digestBytes_(text));
}

/** Random bytes from Utilities.getUuid() (java.util.UUID.randomUUID, a SecureRandom): 366 random bits per digest. */
function randomBytes_(n) {
  let out = [];
  while (out.length < n) out = out.concat(digestBytes_(Utilities.getUuid() + Utilities.getUuid() + Utilities.getUuid()));
  return out.slice(0, n);
}

function base64Url_(bytes) {
  const abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
  let out = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const n = (bytes[i] << 16) | ((bytes[i + 1] || 0) << 8) | (bytes[i + 2] || 0);
    out += abc[(n >> 18) & 63] + abc[(n >> 12) & 63];
    if (i + 1 < bytes.length) out += abc[(n >> 6) & 63];
    if (i + 2 < bytes.length) out += abc[n & 63];
  }
  return out;
}

/** 32 random bytes as 43 URL-safe characters. The Sheet keeps only their SHA-256. */
function newToken_() {
  return base64Url_(randomBytes_(32));
}

/** A short code people can read out or type. 32 letters, so each random byte gives one letter without bias. */
function newCode_(length) {
  return randomBytes_(length || 6).map((b) => CODE_ALPHABET_[b & 31]).join('');
}

function stretch_(password, salt, rounds, chars) {
  let h = '';
  for (let i = 0; i < rounds; i++) {
    const block = h + salt + password;
    h = sha256Hex_(block.repeat(Math.max(1, Math.floor(chars / block.length))));
  }
  return h;
}

function hashPassword_(password) {
  const salt = hex_(randomBytes_(16));
  return ['sha256x', HASH_ROUNDS_, HASH_CHARS_, salt, stretch_(password, salt, HASH_ROUNDS_, HASH_CHARS_)].join('$');
}

function checkPassword_(password, stored) {
  const parts = String(stored || '').split('$');
  if (parts.length !== 5 || parts[0] !== 'sha256x') return false;
  const rounds = parseInt(parts[1], 10);
  const chars = parseInt(parts[2], 10);
  if (!(rounds > 0 && rounds <= 10000 && chars > 0 && chars <= 4194304)) return false;
  const candidate = stretch_(password, parts[3], rounds, chars);
  const expected = parts[4];
  if (candidate.length !== expected.length) return false;
  let diff = 0; // compare every character, so the time taken does not tell how much matched
  for (let i = 0; i < candidate.length; i++) diff |= candidate.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}

/**
 * The phone number as +<country><number>, so one person always gets one account however they type it:
 * "98765 43210", "098765 43210", "+91 98765 43210", "+91 098765 43210" and "0091 98765 43210" are all +919876543210.
 * A bare 10-digit number, or 11 digits with the trunk prefix 0, is taken as Indian (+91); a number from abroad starts
 * with + and its country code. Devanagari digits count as digits. With [keepZero], a 0 typed after +91 (or 0091) is
 * kept: "+91 098765 43210" is +9109876543210, as an account may be stored. Throws a 400 bad_phone if it is not a
 * plausible phone number.
 */
function normalizePhone_(raw, keepZero) {
  let digits = latinDigits_(raw).replace(/\D/g, '');
  if (digits.indexOf('00') === 0) digits = digits.slice(2); // international prefix
  else if (digits.length === 11 && digits.charAt(0) === '0') digits = digits.slice(1); // Indian trunk prefix
  if (!keepZero && digits.length === 13 && digits.indexOf('910') === 0) digits = '91' + digits.slice(3); // the trunk 0 after +91
  if (digits.length === 10) digits = '91' + digits;
  if (digits.length < 11 || digits.length > 15 || digits.charAt(0) === '0') throw new HttpError_(400, 'bad_phone');
  return '+' + digits;
}

/** A user's stored number as normalizePhone_ reads it, so an account stored as "+910…" still matches "+91…". */
function phoneOf_(user) {
  try {
    return normalizePhone_(user.phone);
  } catch (err) {
    return user.phone;
  }
}

// After ATTEMPT_LIMIT_ failures for one key (a phone number logging in, the teacher code, a number signing up with a
// group code) within the window, that key is refused until the window has passed. Kept in CacheService: an eviction
// only forgets recent failures. Callers hold the script lock.

function attempts_(key) {
  const raw = cache_().get('fail:' + key);
  const now = Date.now();
  return (raw ? JSON.parse(raw) : []).filter((t) => now - t < ATTEMPT_WINDOW_S_ * 1000);
}

function attemptsBlocked_(key) {
  return attempts_(key).length >= ATTEMPT_LIMIT_;
}

function attemptsFail_(key) {
  const list = attempts_(key);
  list.push(Date.now());
  cache_().put('fail:' + key, JSON.stringify(list), ATTEMPT_WINDOW_S_);
}

function attemptsClear_(key) {
  cache_().remove('fail:' + key);
}

// ---------- one account per number ----------
// The users tab, read under the lock, says whether a number has an account. As a second guard, each sign-up also keeps
// its number in the script properties ("phone:+919876543210" → {"id": 12, "at": <ms>}). A number kept there for an
// account the users tab, as read, does not show is refused for PHONE_TRUST_MS_ (a read that missed a sign-up written
// just before it) and forgotten after (the owner deleted the row by hand). The Sheet's menu forgets the numbers of the
// people it removes.

const PHONE_TRUST_MS_ = 6 * 60000; // how long an Apps Script execution may run: no read can miss an older sign-up

function phoneKey_(phone) {
  return 'phone:' + phone;
}

/** Under the lock, once the users tab has shown no account with `phone` (normalised): whether the number is kept for
 * one. An account the users tab shows (with another number, changed by hand) does not keep it. */
function phoneHeld_(ctx, phone, users) {
  const raw = PropertiesService.getScriptProperties().getProperty(phoneKey_(phone));
  let held = null;
  try {
    held = raw ? JSON.parse(raw) : null;
  } catch (err) {
    return false;
  }
  if (!held) return false;
  if (users.rows.some((u) => u.id === held.id) || ctx.now - held.at >= PHONE_TRUST_MS_) return false;
  console.error('signup: account %s keeps this number, but the users tab as read under the lock has no row with its id; refused as taken',
    held.id);
  return true;
}

/** Under the lock, once the sign-up's row is written: keeps its number for it. */
function holdPhone_(ctx, phone, userId) {
  PropertiesService.getScriptProperties().setProperty(phoneKey_(phone), JSON.stringify({ id: userId, at: ctx.now }));
}

/** Under the lock: forgets the numbers kept for `people` (every number, with `everything`). */
function forgetPhones_(people, everything) {
  const props = PropertiesService.getScriptProperties();
  const ids = {};
  const keys = {};
  people.forEach((u) => {
    ids[u.id] = true;
    keys[phoneKey_(phoneOf_(u))] = true;
  });
  props.getKeys().filter((key) => key.indexOf('phone:') === 0).forEach((key) => {
    let id = null;
    try {
      id = JSON.parse(props.getProperty(key)).id;
    } catch (err) {
      // a value typed by hand: forgotten with its number
    }
    if (everything || keys[key] || ids[id] === true) props.deleteProperty(key);
  });
}

// ---------- who is asking ----------

/** The users row with this id, or null. Two rows sharing an id (a row copied by hand, say: ids from newIds_ never
 * repeat) give null, and the execution log says so, so one person's token or a lookup never reaches another. */
function userById_(users, id) {
  const found = users.filter((u) => u.id === id);
  if (found.length > 1) console.error('users: %s rows share the id %s; none of them is used', found.length, id);
  return found.length === 1 ? found[0] : null;
}

function currentUser_(ctx) {
  if (ctx._user) return ctx._user;
  if (!ctx.token) throw new HttpError_(401, 'signed_out');
  const hash = sha256Hex_(ctx.token);
  const key = cacheKey_('t:' + hash);
  let userId = cacheGet_(key);
  if (userId === null || userId === undefined) {
    const row = ctx.db.t('tokens').rows.filter((r) => r.token_hash === hash)[0];
    if (!row) throw new HttpError_(401, 'signed_out');
    userId = String(row.user_id);
    cachePut_(key, userId);
  }
  const user = userById_(ctx.db.t('users').rows, Number(userId));
  if (!user) throw new HttpError_(401, 'signed_out');
  ctx._user = user;
  return user;
}

function teacher_(ctx) {
  const user = currentUser_(ctx);
  if (user.role !== 'teacher') throw new HttpError_(403, 'teacher_only');
  return user;
}

/** An approved student, or the teacher. */
function member_(ctx) {
  const user = currentUser_(ctx);
  if (user.role === 'student' && user.status !== 'approved') throw new HttpError_(403, 'pending');
  return user;
}

/** Under the lock: a new login token for `user`. */
function signIn_(ctx, user) {
  const token = newToken_();
  ctx.db.t('tokens').insert([{ token_hash: sha256Hex_(token), user_id: user.id, created_at: ctx.now }]);
  return { token: token, user: userJson_(user) };
}

function userJson_(u) {
  return { id: u.id, name: u.name, phone: u.phone, role: u.role, status: u.status, lang: u.lang, batch: u.batch || null,
    batch_since: u.batch_since ? isoTime_(u.batch_since) : null };
}
