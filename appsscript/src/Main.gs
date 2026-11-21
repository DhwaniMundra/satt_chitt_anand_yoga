// ---------- Main: the envelope and the router ----------
//
// Apps Script web apps cannot read request headers or set an HTTP status, and take only GET and POST. So every call
// is one POST whose body is an envelope:
//   {"method": "GET", "path": "/home", "query": {"lang": "hi"}, "token": "<login token>", "body": null}
// and every answer is HTTP 200 with
//   {"status": <the HTTP status of the answer: 200, 400, 401, ...>, "body": <the answer's JSON>}.
// A write may carry a "request_id": the same id again (the app retrying after a timeout) gets the first answer back;
// for sign-up and login, which carry no token, the same id with the same phone number.
// A GET with no envelope answers /health. appsscript/README.md describes the envelope and every route.

const METHODS_ = ['GET', 'POST', 'PUT', 'DELETE'];
const LOCK_ = true; // the route writes: it runs under the script lock from start to finish
// The route takes the lock itself, around its writes only, and under it looks for the answer a copy of the request (the
// same request id) kept, and keeps its own before letting the lock go (replayed_, keepAnswer_), so two copies arriving
// together write once, as under LOCK_. Its slow steps (a password hash) and its reads of tabs it does not write (who is
// asking, the class, the library) come before the lock, which then holds only the tabs it writes.
const OWN_REPLAY_ = 'own replay';
const REPLAY_S_ = 600; // how long the answer to a write with a request id is kept for a repeat of it
const AUTH_PATHS_ = ['/auth/signup', '/auth/login']; // answered again by the phone number and the request id

class HttpError_ extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : 'validation');
    this.status = status;
    this.detail = detail;
  }
}

/** A plain GET (a browser, an uptime check): the health check, in the envelope. */
function doGet() {
  return reply_(handle_({ method: 'GET', path: '/health', query: {}, token: '', body: null }));
}

function doPost(e) {
  const request = parseEnvelope_(e && e.postData ? e.postData.contents : '');
  return reply_(request.error ? request.error : handle_(request));
}

/** A hand edit to any tab makes the script forget what it cached. */
function onEdit() {
  try {
    bumpCacheGeneration_();
  } catch (err) {
    // a simple trigger must never fail the owner's edit
  }
}

function reply_(envelope) {
  return ContentService.createTextOutput(JSON.stringify(envelope)).setMimeType(ContentService.MimeType.JSON);
}

function parseEnvelope_(text) {
  const bad = (why) => ({ error: { status: 400, body: { detail: 'bad_envelope', why: why } } });
  let env;
  try {
    env = JSON.parse(text || '');
  } catch (err) {
    return bad('not JSON');
  }
  if (env === null || typeof env !== 'object' || Array.isArray(env)) return bad('not an object');
  const method = String(env.method || '').toUpperCase();
  if (METHODS_.indexOf(method) < 0) return bad('method');
  if (typeof env.path !== 'string' || env.path.charAt(0) !== '/') return bad('path');
  const query = {};
  let path = env.path;
  const mark = path.indexOf('?');
  if (mark >= 0) {
    path.slice(mark + 1).split('&').forEach((pair) => {
      if (!pair) return;
      const eq = pair.indexOf('=');
      const key = decodeQuery_(eq < 0 ? pair : pair.slice(0, eq));
      query[key] = decodeQuery_(eq < 0 ? '' : pair.slice(eq + 1));
    });
    path = path.slice(0, mark);
  }
  if (env.query && typeof env.query === 'object') {
    Object.keys(env.query).forEach((key) => {
      let value = env.query[key];
      if (Array.isArray(value)) value = value[value.length - 1];
      if (value !== null && value !== undefined) query[key] = String(value);
    });
  }
  let token = typeof env.token === 'string' ? env.token : '';
  if (token.indexOf('Bearer ') === 0) token = token.slice(7);
  const requestId = typeof env.request_id === 'string' ? env.request_id.trim().slice(0, 64) : '';
  return { method: method, path: path, query: query, token: token.trim(), body: env.body === undefined ? null : env.body, requestId: requestId };
}

function decodeQuery_(text) {
  try {
    return decodeURIComponent(text.replace(/\+/g, ' '));
  } catch (err) {
    return text;
  }
}

function handle_(request) {
  try {
    return { status: 200, body: route_(request) };
  } catch (err) {
    if (err instanceof HttpError_) return { status: err.status, body: { detail: err.detail } };
    console.error('%s %s failed: %s', request.method, request.path, err && err.stack ? err.stack : err);
    return { status: 500, body: { detail: 'Internal Server Error' } };
  }
}

/** [method, path pattern, handler, LOCK_ when the handler writes and holds the lock throughout, or OWN_REPLAY_]. A
 * writing route without LOCK_ takes the lock itself around its writes, to keep a slow step (a password hash) or its
 * reads (a check-in, an intake) out of it; what it writes it reads for the first time under the lock wherever it can. */
function routes_() {
  return [
    ['GET', '/health', health_],
    ['GET', '/studio', studio_],
    ['POST', '/auth/signup', signup_, OWN_REPLAY_],
    ['POST', '/auth/login', login_, OWN_REPLAY_],
    ['POST', '/auth/logout', logout_],
    ['GET', '/me', me_],
    ['POST', '/me', updateMe_, LOCK_],
    ['GET', '/me/intake', myIntake_],
    ['PUT', '/me/intake', saveIntake_],
    ['GET', '/me/practice', myPractice_],
    ['POST', '/me/solo', soloPractice_, OWN_REPLAY_],
    ['GET', '/me/asanas', myItems_],
    ['GET', '/me/asanas/{item}', myItem_],
    ['POST', '/me/shared', shareNote_, OWN_REPLAY_],
    ['POST', '/me/password', changePassword_, OWN_REPLAY_],
    ['GET', '/home', home_],
    ['GET', '/curricula', curricula_],
    ['POST', '/sessions/{session_id}/checkin', checkin_],
    ['POST', '/sessions/{session_id}/practice', sessionPractice_, OWN_REPLAY_],
    ['POST', '/feedback', feedback_, OWN_REPLAY_],
    ['GET', '/teacher/home', teacherHome_],
    ['PUT', '/teacher/sessions/{session_id}', setLink_, LOCK_],
    ['GET', '/teacher/sessions/{session_id}/share', share_],
    ['PUT', '/teacher/sessions/{session_id}/curriculum', setCurriculum_, LOCK_],
    ['PUT', '/teacher/sessions/{session_id}/time', setTime_, LOCK_],
    ['GET', '/teacher/sessions/{session_id}/practice', classReview_],
    ['PUT', '/teacher/settings', updateSettings_, LOCK_],
    ['PUT', '/teacher/batches/{key}', setBatchLink_, LOCK_],
    ['POST', '/teacher/group_code', rotateGroupCode_, LOCK_],
    ['GET', '/teacher/invite', invite_],
    ['GET', '/teacher/students', students_],
    ['POST', '/teacher/students/{user_id}/status', setStatus_, LOCK_],
    ['PUT', '/teacher/students/{user_id}/batch', placeInBatch_, LOCK_],
    ['POST', '/teacher/students/{user_id}/password', resetPassword_, OWN_REPLAY_],
    ['GET', '/teacher/students/{user_id}/asanas', studentItems_],
    ['GET', '/teacher/students/{user_id}/asanas/{item}', studentItem_],
    ['POST', '/teacher/students/{user_id}/feedback', itemFeedback_, LOCK_],
    ['GET', '/teacher/insights', insights_],
    ['GET', '/teacher/shared', sharedNotes_],
  ];
}

function route_(request) {
  const parts = request.path.split('/');
  let pathMatched = false;
  const all = routes_();
  for (let i = 0; i < all.length; i++) {
    const [method, pattern, handler, mode] = all[i];
    const want = pattern.split('/');
    if (want.length !== parts.length) continue;
    const params = {};
    let ok = true;
    for (let j = 0; j < want.length && ok; j++) {
      if (want[j].charAt(0) === '{') {
        params[want[j].slice(1, -1)] = parts[j];
        ok = parts[j] !== '';
      } else {
        ok = want[j] === parts[j];
      }
    }
    if (!ok) continue;
    pathMatched = true;
    if (method !== request.method) continue;
    const ctx = new Context_(request, params);
    if (mode === OWN_REPLAY_) return replayed_(request) || keepingRefusals_(request, () => handler(ctx));
    const run = () => once_(request, () => handler(ctx));
    return mode === LOCK_ ? ctx.lock(run) : run();
  }
  if (pathMatched) throw new HttpError_(405, 'Method Not Allowed');
  throw new HttpError_(404, 'Not Found');
}

/** Runs a write once per request id: a repeat (a retry after a timeout) gets the answer kept from the first time, for
 * REPLAY_S_, instead of writing again. Only answers that succeeded are kept, but for sign-up and login
 * (keepingRefusals_). A route that holds the lock throughout looks inside it, so two copies arriving together write
 * once; an OWN_REPLAY_ route looks again under its own lock. */
function once_(request, fn) {
  return replayed_(request) || keepAnswer_(request, fn());
}

/** Where the answer to a write is kept for a repeat of it: by the login token's hash and the request id; for sign-up
 * and login, which carry no token, by the hash of the phone number, normalised (so "098765 43210" and "+91 98765
 * 43210" are one), and the request id. Null when there is none: a GET, a write without an id, or one without a token
 * other than those two. */
function replayKey_(request) {
  if (request.method === 'GET' || !request.requestId) return null;
  if (AUTH_PATHS_.indexOf(request.path) >= 0) {
    const body = request.body;
    let phone;
    try {
      phone = normalizePhone_(body && typeof body === 'object' && typeof body.phone === 'string' ? body.phone : '');
    } catch (err) {
      return null; // the route answers bad_phone
    }
    return 'req:auth:' + request.path + ':' + sha256Hex_(phone) + ':' + request.requestId;
  }
  return request.token ? 'req:' + sha256Hex_(request.token) + ':' + request.requestId : null;
}

/** The answer kept for a repeat of this request, or null; a refusal kept for it is thrown again. */
function replayed_(request) {
  const key = replayKey_(request);
  const kept = key ? JSON.parse(cache_().get(key) || 'null') : null;
  if (kept && kept.$refused) throw new HttpError_(kept.$refused, kept.detail);
  return kept;
}

/** Sign-up and login keep a refusal for a repeat too (a 4xx, but too_many_attempts, which passes with time; never busy
 * or a 5xx, which may go another way next time), so a retry after a lost answer is not counted as another wrong try. */
function keepingRefusals_(request, fn) {
  try {
    return fn();
  } catch (err) {
    const refusal = err instanceof HttpError_ && err.status >= 400 && err.status < 500 && err.status !== 429;
    if (refusal && AUTH_PATHS_.indexOf(request.path) >= 0) keepAnswer_(request, { $refused: err.status, detail: err.detail });
    throw err;
  }
}

/** Keeps `answer` for a repeat of this request (an OWN_REPLAY_ route does so under its lock, before letting it go);
 * returns it. */
function keepAnswer_(request, answer) {
  const key = replayKey_(request);
  if (key) cache_().put(key, JSON.stringify(answer), REPLAY_S_);
  return answer;
}

/** One request: its inputs, its view of the Sheet (each tab read at most once), the time, and the lock. */
class Context_ {
  constructor(request, params) {
    this.request = request;
    this.params = params;
    CACHE_GENERATION_ = null; // read afresh by each request, as each Apps Script execution starts clean
    this.token = request.token;
    this.db = new Db_();
    this.now = Date.now();
    this.locked = false;
    this._user = null;
  }

  /** Runs `fn` holding the script lock; re-entrant. It flushes first: Apps Script may answer a read of a tab from what
   * this execution read of it before (it fetches more than it is asked for, to answer the reads that follow), so a tab
   * read before the lock could come back under it without the rows another request wrote while this one waited (and
   * sign-ups at once would take the same id); a flush sends the next reads to the Sheet. The tabs read before the
   * lock are then read again (unless `keepReads`, for a lock that writes no tab or reads for the first time the ones
   * it writes), and writes are flushed before the lock is let go. A route that writes a tab reads it for the first
   * time under the lock wherever it can, so as not to rest on the flush alone. */
  lock(fn, keepReads) {
    if (this.locked) return fn();
    const lock = LockService.getScriptLock();
    if (!lock.tryLock(LOCK_WAIT_MS_)) throw new HttpError_(503, 'busy');
    this.locked = true;
    try {
      SpreadsheetApp.flush();
      if (!keepReads) {
        this.db.dropAll();
        CACHE_GENERATION_ = null; // and the cache generation, which a write may have moved on while this request waited
      }
      return fn();
    } finally {
      try {
        SpreadsheetApp.flush();
        if (this.db.changedCache) {
          bumpCacheGeneration_();
          this.db.changedCache = false;
        }
      } finally {
        this.locked = false;
        lock.releaseLock();
      }
    }
  }

  /** Checks the path, query and body against their specs (Validate.gs); all problems in one 422. */
  check(spec) {
    const errors = [];
    const out = {};
    if (spec.path) out.path = validateFields_(spec.path, this.params, ['path'], errors);
    if (spec.query) out.query = validateFields_(spec.query, this.request.query, ['query'], errors);
    if (spec.body) out.body = validateBody_(spec.body, this.request.body, errors);
    if (errors.length) throw new HttpError_(422, errors);
    return out;
  }
}
