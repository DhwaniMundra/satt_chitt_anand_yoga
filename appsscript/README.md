# The live backend: Apps Script over a Google Sheet

The app's server is a Google Apps Script web app bound to one Google Sheet in the studio's Drive folder. It answers
every route the app uses, and the Sheet it keeps its data in doubles as a database the owner can read, query and
extend. It costs nothing, needs no computer left running, and keeps the studio's data in the studio's own Drive.

- [`dist/Code.gs`](dist/Code.gs): the one file to paste, built from [`src/`](src/) and `content/studio.json`.
- [`dist/appsscript.json`](dist/appsscript.json): the manifest (optional, see step 3).

Contents: [Set up](#set-up-5-minutes) · [How it works](#how-it-works) · [The envelope](#the-envelope) ·
[Routes](#routes) · [The Sheet](#the-sheet) · [The Dashboard](#the-dashboard) ·
[Limits for a class of ten](#limits-for-a-class-of-ten) · [Security](#security) · [Tests](#tests) ·
[Developing](#developing)

## Set up (5 minutes)

1. **The Sheet.** In the studio's Drive folder: New → Google Sheets. Name it, for example, "Satt Chitt Anand · live".
   Click **Share** and check that only you are listed: a Sheet in a shared folder is shared with everyone who can
   open the folder, and this one holds phone numbers and password hashes.
2. **The code.** In the Sheet: Extensions → Apps Script. Select everything in `Code.gs` and delete it. Open
   [`dist/Code.gs`](dist/Code.gs) on GitHub, click **Copy raw file** (or **Raw**, then select all), paste it into the
   editor and click Save (the disk icon).
3. **The manifest (optional).** Code.gs works without it. It sets the project's time zone to India (for the
   execution log) and states the one permission the script needs. To paste it: Project Settings (the gear) → tick
   **Show "appsscript.json" manifest file in editor** → back in the Editor, open `appsscript.json`, replace its
   contents with [`dist/appsscript.json`](dist/appsscript.json), Save.
4. **Run setup.** In the toolbar's function menu pick **setup**, click **Run**, then **Review permissions**, choose
   your account and click **Allow**. It asks for one permission: to see and edit the spreadsheet the script is
   installed in, and no other file. If Google shows "Google hasn't verified this app", that is expected for a script
   of one's own: click **Advanced** → **Go to … (unsafe)** → Allow. The execution log then shows the **teacher
   sign-up code** (give it to the teacher; it works once) and the group code. Both stay in the hidden `settings` tab.
5. **Deploy.** Deploy → New deployment → the gear next to "Select type" → **Web app**. Description: "v1.0".
   Execute as: **Me**. Who has access: **Anyone**. Click Deploy (allow again if asked) and copy the **Web app URL**
   (it ends in `/exec`). Opening it in a browser shows `{"status":200,"body":{"ok":true,...}}`.

"Anyone" means the app can reach it without a Google sign-in; the app does its own sign-in with phone numbers and
passwords, and "Execute as Me" means it reads and writes your Sheet as you. Keep the URL out of public places (this
repository included): anyone who has it can try to sign up, as a pending student whom the teacher has to approve.

### Update later

Open the Sheet → Extensions → Apps Script, select everything in `Code.gs`, paste the new
[`dist/Code.gs`](dist/Code.gs), Save. Then Deploy → **Manage deployments** → the pencil (Edit) → Version: **New
version** → Deploy. The URL stays the same. Running `setup` again is always safe: it adds what is missing and leaves
the data, the codes and an existing Dashboard alone.

## How it works

```
phone app ──POST {"method","path","query","token","body"}──▶ the web app's doPost(e)
                                                               │ parse the envelope, find the route
                                                               │ who is asking (token → tokens tab, cached)
                                                               │ check the inputs (422), apply the rules
                                                               │ read tabs (each at most once per request)
                                                               │ write under the script lock, then flush
phone app ◀──── HTTP 200 {"status": 401, "body": {...}} ───────┘
```

- **One request, one view of the Sheet.** A request reads a tab on first use with one `getValues()` call and keeps
  it, in step with its own writes. Columns are found by their header names.
- **Writes take the script lock** (`LockService.getScriptLock()`, waiting up to 20 s, else `503 busy`). A route that
  writes holds it from start to finish, so what it reads and what it writes are consistent. Sign-up, login and a
  password reset do their slow password hash *before* taking the lock. `/home` and `/teacher/home` take it only on the
  first visit of a day, to add that day's class. Writes are flushed before the lock is let go.
- **Ids** are the largest id + 1, worked out under the lock.
- **The week of classes** is made on demand: every visit to `/home` or `/teacher/home` makes sure a session exists
  for each of the next 7 days at 08:00 India time, the class following the weekly rhythm in the studio content.
- **Caching** (`CacheService`, ten minutes): the user a login token belongs to, and the settings. Each key carries a
  generation; a settings change, a logout, a password reset, or any hand edit in the Sheet (the `onEdit` trigger)
  starts a new generation after its writes are flushed, so no request reads a value older than the last write. A
  token row deleted by hand (deleting rows fires no `onEdit`) stops working within ten minutes. The lockout counters
  are kept in the cache too.
- **The studio content** (classes, the weekly rhythm, the teacher, three languages) is a constant in Code.gs,
  generated from `content/studio.json` by [`scripts/build.mjs`](scripts/build.mjs).

## The envelope

Apps Script web apps cannot read request headers or set an HTTP status, and take only GET and POST. So every call is
a POST to the web app URL whose body is one JSON object, and every answer is HTTP 200 with one JSON object.

**Request** (send it as `Content-Type: text/plain;charset=utf-8` or `application/json`):

| Field | Type | Meaning |
|---|---|---|
| `method` | `"GET"`, `"POST"`, `"PUT"` or `"DELETE"` (any case) | The HTTP method of the route. |
| `path` | string starting with `/` | The route, e.g. `/home` or `/sessions/12/checkin`. It may carry a query string (`/studio?lang=hi`). |
| `query` | object, optional | Query parameters, e.g. `{"lang": "hi", "days": 30}`. Values are read as text; they win over the same name in `path`. |
| `token` | string, optional | The login token from sign-up or login, with or without `Bearer `. Empty or absent when signed out. |
| `body` | object or `null`, optional | The JSON body of the route. |

**Answer:**

```json
{"status": 401, "body": {"detail": "signed_out"}}
```

`status` is the HTTP status of the answer and `body` its JSON: on success the route's object (`status` 200), on an
error `{"detail": "<code>"}` with the same codes the app already translates (`bad_login`, `pending`, `no_session`,
`checkin_closed`, ...), or for invalid inputs `status` 422 with `detail` a list of problems
`[{"type", "loc", "msg", "input"}]` (the app shows a list as a generic error). Besides the routes' own errors:

| status | body | when |
|---|---|---|
| 400 | `{"detail": "bad_envelope", "why": "..."}` | the POST body is not an envelope (not JSON, no method or path) |
| 404 | `{"detail": "Not Found"}` | no such path (also `/chat`, `/ask` and `/me/notes`: the assistant runs on the phone) |
| 405 | `{"detail": "Method Not Allowed"}` | the path exists with another method |
| 500 | `{"detail": "Internal Server Error"}` | anything unexpected (the details go to the owner's execution log); `"not_set_up"` if a tab or column is missing |
| 503 | `{"detail": "busy"}` | the script lock was not free within 20 s |

A **GET** with no envelope (a browser, an uptime check) answers the health check:
`{"status":200,"body":{"ok":true,"assistant":"off","model":null}}`.

The web app answers a POST with a 302 redirect to `script.googleusercontent.com`; follow it with a **GET**, as curl's
`-L` and `fetch` do. Do not re-send the POST to the new address.

```bash
curl -sL "$URL" -H 'Content-Type: text/plain' \
  -d '{"method":"POST","path":"/auth/login","body":{"phone":"98765 43210","password":"..."}}'
```

## Routes

"Writes" says whether the route writes to the Sheet (and so takes the lock). Every signed-in route answers 401
`signed_out` without a valid token; teacher routes answer 403 `teacher_only` to students.

| Route | Who | Writes | Answer and rules |
|---|---|---|---|
| `GET /health` | anyone | | `{ok, assistant: "off", model: null}` |
| `GET /studio?lang=` | anyone | | the studio in `en`, `hi` or `mr`: name, tagline, teacher, classes, weekly rhythm |
| `POST /auth/signup` | anyone | yes | `{name, phone, password, role, code, lang}` → `{token, user}`. The phone is normalised (a bare 10-digit number is Indian). One teacher, with the teacher code (any case; 5 wrong in 15 minutes lock it); a student with the group code is approved, without it pending. Errors: `bad_phone`, `teacher_exists`, `bad_teacher_code`, `too_many_attempts`, `bad_group_code`, `phone_taken` |
| `POST /auth/login` | anyone | yes (a token) | `{phone, password}` → `{token, user}`; `bad_login`; 5 failures for a number in 15 minutes → `too_many_attempts` |
| `POST /auth/logout` | anyone | yes | ends this token → `{ok: true}` |
| `GET /me` | signed in | | `{user, stats: {classes_joined, streak_days, mood_change, mood_pairs}}` |
| `POST /me` | signed in | yes | `{name?, lang?}` → `{user}` |
| `POST /me/group_code` | signed in | yes | `{code}`: a pending student becomes approved → `{user}`; `bad_group_code`, 5 tries then `too_many_attempts` |
| `GET /me/practice?days=&lang=` | approved student, teacher | | the student's classes over the last `days` (1 to 90, default 7) with the sums done: `{period_days, classes_joined, mood_scale, average_mood_before, average_mood_after, by_class, classes}`, each class's `date` its India date (`2026-11-16`); `pending` |
| `GET /me/asanas` | approved student, teacher | | `{items: [{item, in_class, last, reaction_trend, pain_times, teacher_said}]}`: each item the student practised in class or had feedback on: those with strain or pain first, then those with the teacher's feedback (the latest first), then the most practised; `teacher_said` is the date of the latest feedback |
| `GET /me/asanas/{item}` | approved student, teacher | | one item's history, worked out in code: `{item, in_class, first, last, reaction_trend: {early_average, recent_average, each}, strain_or_pain: {times, last}, teacher_said: {date, text}, your_notes: [{date, text}], entries: [{date, reaction, pain, note}], feedback: [{date, text}]}`. The trend sets the first `each` reactions against the latest `each` (up to three) |
| `POST /me/shared` | approved student | yes | `{text}` (1 to 500) → `{ok, id}`; the same words again return the same id; `pending`, `empty_note` |
| `GET /home?lang=` | signed in | the day's class, once | `{user, studio, sessions, after_checkin, group_link}`; links only for approved students; each session's `curriculum`. `after_checkin` is the last class the student checked in to that ended (or is in its last 10 minutes) within 12 hours and that has no "after" check-in and no practice entries yet |
| `GET /curricula?lang=` | signed in | | `{library: [{key, type, level, sanskrit, name, english, aliases}], curricula: [{key, name, level, about, items: [{item, dose, unit, cue}]}]}`, from the curriculum tabs, names, about and cues in `lang` |
| `POST /sessions/{session_id}/checkin` | approved student | yes | `{phase: before\|after, mood: 1..5}` → `{ok, stats}`. "before" from an hour before class to its end; "after" from 10 minutes before the end to 12 hours after, once checked in before; `pending`, `no_session`, `checkin_closed` |
| `POST /sessions/{session_id}/practice` | approved student | yes | `{entries: [{item, reaction: 1..4\|null, pain: 0\|1, note?}]}` (at most 60) → `{ok, saved}`: how each item went, replacing what was sent before for this class; entries with nothing said are not kept. Open when the "after" check-in is; `checkin_closed`, `unknown_item`, `pending`, `no_session` |
| `POST /feedback` | signed in | yes | `{screen, text}` → `{ok}` |
| `GET /teacher/home?lang=` | teacher | the day's class, once | `{sessions (with own_link, joined, curriculum), settings, pending_students}` |
| `PUT /teacher/sessions/{session_id}?lang=` | teacher | yes | `{meet_link}` (Meet or Zoom; `https://` added) → `{text, url, group_link}`; `bad_meet_link`, `no_session` |
| `GET /teacher/sessions/{session_id}/share?lang=` | teacher | | the WhatsApp message `{text, url, group_link}`; `no_link`, `no_session` |
| `PUT /teacher/sessions/{session_id}/curriculum` | teacher | yes | `{curriculum}` → `{ok, curriculum}`. A class without its own follows the curriculum last used for a class of its kind, else the first in the `curricula` tab; `no_curriculum`, `no_session` |
| `GET /teacher/sessions/{session_id}/practice` | teacher | | how the class went: `{id, starts_at, curriculum, joined, answered, items: [{item, reactions: [not yet, with effort, steady, at ease], pain: [{name, note}], notes: [{name, text}]}]}`, items with strain or pain first, then the plan's order |
| `PUT /teacher/settings` | teacher | yes | `{group_link?, default_meet_link?}`, both checked before either is saved → `{group_link, group_code, default_meet_link}` |
| `POST /teacher/group_code` | teacher | yes | a new group code → `{group_code}` |
| `GET /teacher/invite?lang=` | teacher | | `{text, url, group_link}` |
| `GET /teacher/students` | teacher | | `{students: [user + joined, created_at]}`, pending first, then newest |
| `POST /teacher/students/{user_id}/status` | teacher | yes | `{status: approved\|rejected}` → `{ok}`; `no_student` |
| `GET /teacher/students/{user_id}/asanas`, `…/asanas/{item}` | teacher | | the same as `/me/asanas` and `/me/asanas/{item}`, for that student; `no_student` |
| `POST /teacher/students/{user_id}/feedback` | teacher | yes | `{item, text}` → `{ok, id}`: the teacher's word on one item, which the student sees with its history; `unknown_item`, `no_student` |
| `POST /teacher/students/{user_id}/password` | teacher | yes | a new 8-letter password, the student signed out everywhere → `{password}`; `no_student` |
| `GET /teacher/insights` | teacher | | the last 14 days of classes, mood change, student counts, the last 20 feedback notes; `questions.count` is 0 |
| `GET /teacher/shared` | teacher | | `{shared: [{id, user_id, name, text, created_at}]}`, newest first, at most 50 |

Times are UTC ISO-8601 to the second (`2026-11-18T02:30:00Z`); classes start at 08:00 India time (02:30 UTC).

## The Sheet

`setup()` makes these tabs, each with a header row. The code finds columns by name, so the owner may move them or
add columns of her own (to the right is tidiest); `setup()` adds back any column the code needs.

| Tab | Columns | Notes |
|---|---|---|
| `Dashboard` | formulas | first tab; see below |
| `users` | id, name, phone, role, status, pw_hash, lang, created_at | role `student`/`teacher`; status `pending`/`approved`/`rejected` |
| `class_sessions` | id, class_key, starts_at, duration_min, meet_link, curriculum, updated_at | one per day, made a week ahead; `curriculum` when the teacher picked one |
| `checkins` | user_id, session_id, phase, mood, created_at, class, class_date | phase `before`/`after`, mood 1 to 5. `class` and `class_date` copy the session's class name and India date, for queries; the code goes by session_id |
| `practice` | id, user_id, session_id, item, reaction, pain, note, created_at, item_name, week | how each item of a class went: reaction 1 not yet, 2 with effort, 3 steady, 4 at ease (or blank), pain 1 for "felt strain or pain". `item_name` and `week` (its Monday) copy the item's name and the class's week, for queries |
| `asana_feedback` | id, student_id, item, text, created_at | the teacher's feedback to one student on one item |
| `library` | key, type, level, sanskrit, name, english, aliases, source | the asanas, pranayama and meditation the curricula draw on; type `asana`/`pranayama`/`meditation`, level 1 to 3, aliases comma-separated |
| `curricula` | key, name, name_hi, name_mr, level, about, about_hi, about_mr, source | the curricula the teacher picks from; the first is the default |
| `curriculum_items` | curriculum, position, item, dose, unit, cue, cue_hi, cue_mr | each curriculum's items in order; unit `breaths`, `seconds`, `minutes`, `rounds` or `strokes` |
| `feedback` | id, user_id, screen, text, created_at | |
| `shared_notes` | id, user_id, text, created_at | notes students chose to share with the teacher |
| `tokens` (hidden) | token_hash, user_id, created_at | SHA-256 of each login token |
| `settings` (hidden) | key, value, about | teacher_code, group_code, group_link, default_meet_link |
| `classes` | key, name, name_hi, name_mr, level, about, days | the studio's classes, rewritten by every `setup()`, for lookups |

How values are stored: text with a leading apostrophe, so Sheets keeps `+919876543210`, a code like `2E5K7Q` or a
name starting with `=` exactly as typed (never a number, a date or a formula); times as date cells shown in India
time (the spreadsheet's time zone is set to Asia/Kolkata); ids, moods and minutes as numbers.

The curriculum tabs (`library`, `curricula`, `curriculum_items`) are filled from
[`content/curriculum.json`](../content/curriculum.json) while they are empty, and are the owner's to edit after that:
a new curriculum is a row in `curricula` and its items in `curriculum_items`; a new item is a row in `library`. The
seeded curricula are a mock for the teacher to confirm (the note on `curricula`'s first cell names the sources).

Editing by hand: the data tabs have a warning-only protection (Sheets asks "are you sure?"), and any edit makes the
script drop its cache. When typing text that looks like a number or a date (a code, a phone number), start it with
an apostrophe. Deleting a student's row leaves their check-ins in place.

## The Dashboard

One tab of formulas, each block a single `QUERY` (click its first cell to read it): students by status, mood per
class (average after and before, all time), every student with their check-in count, attendance per class by date,
mood by class and date, feedback with the student's name, shared notes, items with strain or pain in the last 14
days, and the average reaction per item, week by week (one column per week, headed by its Monday). Times show in
India time.

To extend it, add blocks anywhere, for example in column Z:

```
=QUERY(checkins!A1:G, "select F, count(A) where C = 'before' and G >= date '2026-11-01' group by F label count(A) 'check-ins'", 1)
```

`setup()` never rewrites an existing Dashboard. To get a fresh one (after a newer Code.gs, say), delete the tab and
run `setup` again. The formulas name columns by letter (`users!E` is status); if columns are moved, rebuild the
Dashboard this way.

## Limits for a class of ten

**Latency, measured** on the deployed web app (18 Nov 2026), end to end from the development machine, including the
redirect, with [`scripts/smoke.mjs`](scripts/smoke.mjs) (5 rounds) and 12 interleaved login/token pairs:

| Request | Touches | Median (min to max) |
|---|---|---|
| GET with no envelope | nothing | 1.07 s (0.66 to 3.3) |
| `/health`, `/studio` (en, hi, mr), 404, 405, 422, bad envelope | nothing | 0.81 to 1.08 s by request (0.68 to 3.9) |
| Sign-up with a wrong group code | settings, cached | 0.96 s (0.80 to 1.28) |
| `/home` with an unknown token | the tokens tab | 1.90 s (1.36 to 2.34) |
| Login with a wrong password | the users tab, the password hash, the lockout | 2.68 s (2.10 to 3.72) |
| The first request to read the Sheet after a quiet spell | | 2.7 s and 5.4 s (two runs) |

So Apps Script itself takes about a second per call, opening the Sheet and reading a tab about another second, and
the password hash with the lockout bookkeeping about 0.8 s (the difference of the login and token medians). A
student's `/home` (four tabs, settings and token cached) and a check-in (the lock, a write, a flush) were not timed
on the live Sheet, so as not to write rows to it; from the parts above, expect about 2 to 3 seconds for each.

**Quotas** (Google's published limits for a personal account; Workspace accounts have more):

- *Simultaneous executions: 30 per user.* The web app runs as the owner, so all students share these 30. Ten
  students opening the app at 8:00 use a handful.
- *6 minutes per execution*; a request here takes seconds.
- *One writer at a time.* Writes queue on the script lock, each holding it for about a second (an estimate from the
  reads above: read the tab, write, flush). A request that waits more than 20 s answers `503 busy`; ten check-ins
  at the same moment would wait about ten seconds at worst.
- *CacheService*: values up to 100 KB, kept at most 6 hours and possibly evicted earlier. An eviction costs only
  speed, except that recent failed logins are forgotten.
- *10 million cells per spreadsheet.* A year of the class is about 365 sessions, 7,300 check-ins and 70,000 practice
  rows (below), some 760,000 cells.

**The practice tab grows fastest:** about 10 students × 19 items × 7 days ≈ 1,300 rows a week, 70,000 a year. Each
request that reads it (a student's `/home`, the after-class send, the teacher's review of a class) reads the whole tab,
so its time grows with the rows. Measured on the Node fakes with a seeded year (69,350 rows), each of those requests
took 0.26 to 0.27 s, against 1 ms with a fresh tab; Sheets reads cells more slowly than the fakes, so the live cost is
higher. The remedy, once a year: copy the `practice` tab, name the copy `practice_2026`, and delete the copied rows
from `practice` (the app reads only `practice`).
- No triggers run on a timer, no URL fetches, no e-mail: none of those quotas apply.

## Security

- **One permission.** Code.gs carries `@OnlyCurrentDoc` and the manifest asks only for
  `spreadsheets.currentonly`: the script can open the spreadsheet it is bound to and no other file in the owner's
  Drive. It uses no Drive, mail or network service.
- **Execute as me, access anyone.** Requests run as the owner without a Google sign-in; the app authenticates its
  users itself. The URL is the only address of the backend: it is not in this repository.
- **Passwords** are salted (16 random bytes) and stretched: 100 SHA-256 digests in a row, each over about 128,000
  characters made from the previous digest, the salt and the password, about 12.8 MB hashed per guess. Apps Script
  has no PBKDF2, and each call to `Utilities.computeDigest` has a fixed overhead, so the work goes into long inputs
  rather than many short calls. A login spends about 0.8 s on this and the lockout bookkeeping (measured above). The rounds and length are stored with each hash
  (`sha256x$100$131072$<salt>$<hash>`), so they can be raised without breaking existing passwords. An unknown phone
  number is checked against a dummy hash of the same cost, so timing does not reveal who has an account.
- **Login tokens** are 32 random bytes (43 characters), stored only as their SHA-256; the cache keys are those
  hashes too. A token lasts until logout or a password reset.
- **Randomness** comes from `Utilities.getUuid()` (Java's `UUID.randomUUID()`, a `SecureRandom`), hashed: tokens,
  salts, the teacher and group codes, temporary passwords.
- **Guessing is slowed:** 5 wrong passwords for a number, 5 wrong teacher codes, or 5 wrong group codes by one
  student within 15 minutes are refused until the window has passed. A wrong group code at sign-up is not counted:
  the code has 32⁶ (about a billion) values and each try takes a second.
- **Text cannot become a formula**: every text value is written with a leading apostrophe.
- **The Sheet must stay private.** It holds phone numbers, password hashes and the codes. The `settings` and
  `tokens` tabs are hidden, which keeps them off screen, not from someone the file is shared with. To show the
  teacher the Dashboard, share a separate spreadsheet that reads it with `IMPORTRANGE`, not this one.
- **Errors** reach the app as a code only; stack traces go to the owner's execution log (Apps Script → Executions).
- **Sign-ups are open** to anyone with the URL, as pending students the teacher approves or rejects.

## Tests

One command, Node 22's built-in test runner, no packages and no Google account:

```bash
node --test 'appsscript/test/*.test.mjs'
```

On the studio laptop, Node is in `tools/node/bin` (`export PATH=$PWD/tools/node/bin:$PATH`). The tests load
`dist/Code.gs` (the file that gets pasted) into a Node `vm` context with small fakes of `SpreadsheetApp`,
`LockService`, `CacheService`, `Utilities`, `ContentService` and `Logger` ([`test/fakes.mjs`](test/fakes.mjs)).
The fake Sheet behaves like Sheets where it matters: a fixed grid, and text that looks like a number, a boolean, a
date or a formula is read as one unless it starts with an apostrophe.

- [`bundle.test.mjs`](test/bundle.test.mjs): `dist/` is the build of `src/` and the content files; the one scope;
  `setup()`; the main path.
- [`api.test.mjs`](test/api.test.mjs): every route's rules: one teacher and the teacher code in any case, the group
  code, pending and approved, phone numbers however typed, links cleaned and both-or-neither settings, check-in
  windows, the streak, lockouts and their expiry, password resets, the invite, the week of classes.
- [`practice.test.mjs`](test/practice.test.mjs): `/me/practice` (the sums, the days clamp, languages, rounding as
  Python's `round()`), `/me/shared` and `/teacher/shared`.
- [`curriculum.test.mjs`](test/curriculum.test.mjs): the curriculum tabs seeded once, `/curricula` in each
  language, each class's curriculum and its default, the after-class practice send (its window, its checks,
  replacing), and the teacher's review of a class.
- [`history.test.mjs`](test/history.test.mjs): a student's history per item (the trend, strain or pain, the notes,
  the list), and the teacher's feedback on an item.
- [`store.test.mjs`](test/store.test.mjs): the envelope, validation shapes, text kept as typed, hashed tokens and
  passwords, columns by name, ids, the lock (busy, always let go), a failure inside a route, growing tabs, the cache
  and its invalidation, the Dashboard's formulas.
- [`parity.test.mjs`](test/parity.test.mjs): a regression snapshot, 101 requests and their recorded answers
  ([`test/parity/`](test/parity/)); every status and every body must match. After a deliberate change to the
  answers, `node appsscript/test/parity/record.mjs` records them again; read its diff before committing.

[`scripts/smoke.mjs`](scripts/smoke.mjs) checks the deployed web app with requests that write no row:
`SCA_WEBAPP_URL=<url> node appsscript/scripts/smoke.mjs 5`. Its failed logins use numbers that cannot be real
mobiles (`+91 1…`); its one wrong teacher code counts toward that code's lockout (5 in 15 minutes), so before the
teacher has signed up, run it at most once a quarter of an hour.

## Developing

- [`src/`](src/): `Main.gs` (the envelope, the router, the request context and the lock), `Validate.gs` (input
  checks), `Store.gs` (tabs, encoding, the cache), `Auth.gs` (passwords, tokens, codes, phone numbers, lockouts,
  who is asking), `Studio.gs` (classes, India time, the week, the sums, WhatsApp messages), `Routes.gs` (one function
  per route), `Practice.gs` (the curriculum, each class's plan, how each item went, each student's history per
  item, the teacher's feedback), `Setup.gs` (`setup()`, the
  curriculum seed and the Dashboard), `appsscript.json`.
- `node appsscript/scripts/build.mjs` writes `dist/Code.gs` and `dist/appsscript.json`; `--check` fails if they are
  out of date (the tests check this too). Commit `dist/` with every change to `src/` or to `content/studio.json`
  and `content/curriculum.json`.
- Only `setup`, `doGet`, `doPost` and `onEdit` are public; every other function ends in `_`, so the editor's Run menu
  lists just those four (run `setup`; the others are for the web app and the edit trigger).
- `loadBackend()` in [`test/fakes.mjs`](test/fakes.mjs) runs Code.gs locally, as a stand-in backend for app
  development: it returns `{ss, state, cache, context, evaluate, call, Date, clock}`, where `call(method, path,
  {query, token, body})` goes through the envelope and `state.offsetMs` / `state.frozenMs` move or stop the clock.
