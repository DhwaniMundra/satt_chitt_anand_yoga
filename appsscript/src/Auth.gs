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
 * The WhatsApp number as +<country><number>, so one person always gets one account however they type it:
 * "98765 43210", "098765 43210", "+91 98765 43210" and "0091 98765 43210" are the same number. A bare 10-digit
 * number, or 11 digits with the trunk prefix 0, is taken as Indian (+91). Devanagari digits count as digits.
 * Throws a 400 bad_phone if it is not a plausible phone number.
 */
function normalizePhone_(raw) {
  let digits = String(raw)
    .replace(/[०-९]/g, (d) => String(d.charCodeAt(0) - 0x966))
    .replace(/\D/g, '');
  if (digits.indexOf('00') === 0) digits = digits.slice(2); // international prefix
  else if (digits.length === 11 && digits.charAt(0) === '0') digits = digits.slice(1); // Indian trunk prefix
  if (digits.length === 10) digits = '91' + digits;
  if (digits.length < 11 || digits.length > 15 || digits.charAt(0) === '0') throw new HttpError_(400, 'bad_phone');
  return '+' + digits;
}

// After ATTEMPT_LIMIT_ failures for one key (a phone number, the teacher code, a user entering a group code) within
// the window, that key is refused until the window has passed. Kept in CacheService: an eviction only forgets recent
// failures. Callers hold the script lock.

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

// ---------- who is asking ----------

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
  const user = ctx.db.t('users').rows.filter((u) => u.id === Number(userId))[0];
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
