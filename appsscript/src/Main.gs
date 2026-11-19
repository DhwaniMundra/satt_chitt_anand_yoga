// ---------- Main: the envelope and the router ----------
//
// Apps Script web apps cannot read request headers or set an HTTP status, and take only GET and POST. So every call
// is one POST whose body is an envelope:
//   {"method": "GET", "path": "/home", "query": {"lang": "hi"}, "token": "<login token>", "body": null}
// and every answer is HTTP 200 with
//   {"status": <the HTTP status of the answer: 200, 400, 401, ...>, "body": <the answer's JSON>}.
// A GET with no envelope answers /health. appsscript/README.md describes the envelope and every route.

const METHODS_ = ['GET', 'POST', 'PUT', 'DELETE'];
const LOCK_ = true; // the route writes: it runs under the script lock from start to finish

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
  return { method: method, path: path, query: query, token: token.trim(), body: env.body === undefined ? null : env.body };
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

/** [method, path pattern, handler, LOCK_ when the handler writes and has no slow step to keep outside the lock]. */
function routes_() {
  return [
    ['GET', '/health', health_],
    ['GET', '/studio', studio_],
    ['POST', '/auth/signup', signup_],
    ['POST', '/auth/login', login_],
    ['POST', '/auth/logout', logout_],
    ['GET', '/me', me_],
    ['POST', '/me', updateMe_, LOCK_],
    ['POST', '/me/group_code', joinGroup_, LOCK_],
    ['GET', '/me/practice', myPractice_],
    ['GET', '/me/asanas', myItems_],
    ['GET', '/me/asanas/{item}', myItem_],
    ['POST', '/me/shared', shareNote_, LOCK_],
    ['GET', '/home', home_],
    ['GET', '/curricula', curricula_],
    ['POST', '/sessions/{session_id}/checkin', checkin_, LOCK_],
    ['POST', '/sessions/{session_id}/practice', sessionPractice_, LOCK_],
    ['POST', '/feedback', feedback_, LOCK_],
    ['GET', '/teacher/home', teacherHome_],
    ['PUT', '/teacher/sessions/{session_id}', setLink_, LOCK_],
    ['GET', '/teacher/sessions/{session_id}/share', share_],
    ['PUT', '/teacher/sessions/{session_id}/curriculum', setCurriculum_, LOCK_],
    ['GET', '/teacher/sessions/{session_id}/practice', classReview_],
    ['PUT', '/teacher/settings', updateSettings_, LOCK_],
    ['POST', '/teacher/group_code', rotateGroupCode_, LOCK_],
    ['GET', '/teacher/invite', invite_],
    ['GET', '/teacher/students', students_],
    ['POST', '/teacher/students/{user_id}/status', setStatus_, LOCK_],
    ['POST', '/teacher/students/{user_id}/password', resetPassword_],
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
    const [method, pattern, handler, lock] = all[i];
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
    return lock ? ctx.lock(() => handler(ctx)) : handler(ctx);
  }
  if (pathMatched) throw new HttpError_(405, 'Method Not Allowed');
  throw new HttpError_(404, 'Not Found');
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

  /** Runs `fn` holding the script lock; re-entrant. Tabs read before the lock are read again inside it (unless
   * `keepReads`, for a lock that writes no tab), and writes are flushed before the lock is let go. */
  lock(fn, keepReads) {
    if (this.locked) return fn();
    const lock = LockService.getScriptLock();
    if (!lock.tryLock(LOCK_WAIT_MS_)) throw new HttpError_(503, 'busy');
    this.locked = true;
    if (!keepReads) {
      this.db.dropAll();
      CACHE_GENERATION_ = null; // and the cache generation, which a write may have moved on while this request waited
    }
    try {
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
