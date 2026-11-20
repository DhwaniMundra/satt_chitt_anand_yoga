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
the data, the codes, the batches, the curriculum and an existing Dashboard alone.

A Sheet made before v0.9.1 needs `setup` run once after pasting: it adds the `app_link` row to `settings` (optional:
paste a download link for the app into its value, and the invite says where to get the app) and makes the `time`
column of `batches` plain text, so a time typed there stays as typed. A time Sheets had already taken as a time of day
or a number (7.15) is written back as the text it stands for ("07:15"). The app of v0.9 works with this backend as it
is.

**When a batch's time or length changes** (the owner edits the `batches` tab, or this backend reads a time cell
differently from the one before: v0.9 read a 07:00 time-of-day cell as 07:08), the coming classes follow it on the next
visit, one class per batch per day: each class that has not begun and nobody has checked in to is moved to the new
time in its own row, keeping its id, its own Meet link and its curriculum. A class someone has checked in to stays as
it is, and that day gets no second class. A class is removed only from a day its batch no longer meets (and only if it
has not begun and nobody has checked in to it).

A Sheet made before v1.0 needs these steps once, after pasting the new `Code.gs`:
1. Run `setup`. It adds the `batches` and `batch_changes` tabs, the hidden `intake` and `intake_ratings` tabs, and the
   new columns, and leaves the data alone.
2. Delete by hand what batches replaced: the `classes` tab, the `class_key` column of `class_sessions`, and the
   `default_meet_link` row of `settings`. Each batch's Meet link is now set from the teacher's Today.
3. For the Dashboard's new blocks (students per batch, batch changes, pain areas), delete the Dashboard tab and run
   `setup` again.
4. Deploy a new version (above), then place each existing student in a batch from the app (Students).
   Students who signed up before then can tell the teacher about themselves from Me.

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
  password reset do their slow password hash *before* taking the lock. A check-in, which many students send as class
  starts, reads everything else before the lock and, under it, only the check-ins tab, read afresh, and its one write.
  `/home` and `/teacher/home` take it only on the first visit of a day, to add that day's classes. Writes are flushed
  before the lock is let go.
- **A write sent twice is written once.** The app sends a `request_id`, the same for each try of the same action,
  with these writes: the check-in before class, a practice on one's own (`/me/solo`), feedback (`/feedback`), a
  password change (`/me/password`), and the teacher's feedback on an item, batch moves and placements, and new
  passwords for a student. The answer is kept for ten minutes in `CacheService`, by the login token's hash and the id,
  and a repeat gets it back instead of writing again.
- **Ids** are the largest id + 1, worked out under the lock.
- **Batches and their classes**: students are placed in batches (Beginner, Intermediate, Advanced, Pain management
  as seeded), each meeting on its own days at its own time with its own Meet link, as the `batches` tab says. The
  week is made on demand: every visit to `/home` or `/teacher/home` makes the next 7 days' classes match the batches,
  one class per batch per day: it adds each one missing, moves a class whose batch's time or length changed in its
  row (keeping its id, link and curriculum), and removes one from a day its batch no longer meets; it never moves or
  removes a class that has begun or that someone has checked in to.
- **Caching** (`CacheService`, ten minutes): the user a login token belongs to, and the settings. Each key carries a
  generation; a settings change, a logout, a password reset, or any hand edit in the Sheet (the `onEdit` trigger)
  starts a new generation after its writes are flushed, so no request reads a value older than the last write. A
  token row deleted by hand (deleting rows fires no `onEdit`) stops working within ten minutes. The lockout counters
  are kept in the cache too.
- **The studio content** (the name, the teacher, the batches as first seeded, three languages) is a constant in
  Code.gs, generated from `content/studio.json` by [`scripts/build.mjs`](scripts/build.mjs).

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
| `request_id` | string, optional | For a write: the same id for each try of the same action, so it is written once (above). |

**Answer:**

```json
{"status": 401, "body": {"detail": "signed_out"}}
```

`status` is the HTTP status of the answer and `body` its JSON: on success the route's object (`status` 200), on an
error `{"detail": "<code>"}` with the same codes the app already translates (`bad_login`, `pending`, `no_session`,
`checkin_closed`, ...), or for invalid inputs `status` 422 with `detail` a list of problems
`[{"type", "loc", "msg", "input"}]` (the app names the field from `loc`). Text lengths are counted in code points, as
the app counts them. Besides the routes' own errors:

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
| `GET /studio?lang=` | anyone | | the studio in `en`, `hi` or `mr`: name, tagline, teacher, `batches: [{key, name, about, days, time}]` |
| `POST /auth/signup` | anyone | yes | `{name, phone, password, role, code, lang}` → `{token, user}`. The phone is normalised (a bare 10-digit number is Indian, "+91 0…" is the same as "0…", a number from abroad starts with + and its country code). One teacher, with the teacher code (any case; 5 wrong in 15 minutes lock it). A student needs the group code, which the teacher gives with the invite (any case, and spaces, stars or a full stop around it ignored; 5 wrong for a number in 15 minutes lock it), and waits, pending, until the teacher places them in a batch. Errors: `bad_phone`, `teacher_exists`, `bad_teacher_code`, `too_many_attempts`, `bad_group_code`, `phone_taken` |
| `POST /auth/login` | anyone | yes (a token) | `{phone, password}` → `{token, user}`: the account stored with the number exactly as typed, else the one whose number reads the same; `bad_login`; 5 failures for a number in 15 minutes → `too_many_attempts` |
| `POST /auth/logout` | anyone | yes | ends this token → `{ok: true}` |
| `GET /me` | signed in | | `{user, stats: {classes_joined, streak_days, mood_change, mood_pairs}}`. `streak_days` is the run of classes in a row the student came to: the classes of the batch they were in at the time of each, and any other they joined; a class still to come or under way does not break it, nor one nobody came to |
| `POST /me` | signed in | yes | `{name?, lang?}` → `{user}` |
| `POST /me/password` | signed in | yes | `{current_password, new_password}` (6 to 200) → `{ok}`: the current password is checked under the login's brake (5 wrong in 15 minutes, counted with the logins); this login stays signed in and every other is signed out; `bad_password`, `too_many_attempts` |
| `GET /me/intake` | signed in | | `{intake}`: the student's own answers about themselves, or null before they fill them |
| `PUT /me/intake` | student | yes | `{age, height_cm, weight_kg, food, meals?, pain?, pain_note?, ratings: [{item, reaction, pain}]}` → `{intake}`: age 5 to 100, height 80 to 230 cm, weight 15 to 250 kg, meals and the pain note up to 600; filled after sign-up (pending) or later; a second send replaces the first. `food` one of `vegetarian`, `eggetarian`, `non_vegetarian`, `vegan`; `pain` areas like `knee, back` from knee, back, neck, shoulder, hip, other (`bad_pain_area`); `ratings` for the assessment asanas of `content/studio.json` only (`unknown_item`); `students_only`. The intake comes back with `suggested_batch`: any pain, Pain management; four or more poses of the self-assessment steady or at ease, Intermediate; else Beginner, never Advanced |
| `GET /me/practice?days=&lang=` | approved student, teacher | | the student's classes over the last `days` (1 to 90, default 7) with the sums done: `{period_days, classes_joined, average_mood_before, average_mood_after, by_class, classes, solo, items_in_class, items_on_own}`, moods from 1 (very low) to 5 (great), each class's `date` its India date (`2026-11-16`), `at` its start (ISO time, for the phone to name the day in its own time zone) and its `curriculum`; `solo` lists the sessions on one's own, `[{date, at, minutes, items}]`, the item names in `lang`; `items_in_class` and `items_on_own` the five items practised most in the period in class and on one's own, kept apart, `[{asana, times, average_reaction, pain_times}]`, each average reaction from 1 (not yet) to 4 (at ease); `pending` |
| `POST /me/solo` | approved student | yes | practice on one's own: `{minutes, entries: [{item, hold_s, reaction, pain, note}]}` → `{ok, id, saved}`. The server dates it (it ends now and began `minutes` ago, up to 240); `hold_s` is the stopwatch's seconds (a longer hold than 3600 is kept as 3600); a note is up to 1000; an item with nothing timed or said is not kept; `nothing_said` when none is left, `unknown_item` |
| `GET /me/asanas` | approved student, teacher | | `{items: [{item, in_class, solo, last, reaction_trend, pain_times, teacher_said}]}`: each item the student practised, in class or on their own, or had feedback on: those with strain or pain first, then those with the teacher's feedback (the latest first), then the most practised; `teacher_said` is the date of the latest feedback |
| `GET /me/asanas/{item}` | approved student, teacher | | one item's history, worked out in code: `{item, in_class, solo, first, last, reaction_trend: {early_average, recent_average, each}, holds: {recent_seconds, longest_seconds}, strain_or_pain: {times, last}, teacher_said: {date, text}, your_notes: [{date, text}], entries: [{date, at, kind, hold_s, reaction, pain, note}], feedback: [{date, at, text}]}`, `kind` being `class` or `solo`, `date` the India date and `at` the moment. The trend sets the first `each` reactions against the latest `each` (up to three), in class and on one's own together; `holds` are the stopwatch's, on one's own |
| `POST /me/shared` | approved student | yes | `{text}` (1 to 1000) → `{ok, id}`; the same words again return the same id; `pending`, `empty_note` |
| `GET /home?lang=` | signed in | the day's classes, once | `{user, batch, studio, sessions, after_checkin, after_class, group_link}`: `sessions` are the student's batch's coming classes (none before they are placed), each `{id, starts_at, duration_min, batch: {key, name, about, days, time}, meet_link, has_link, checked_in, curriculum}`, links only for approved students. `after_class` is the latest class of the batch the student was in at its time (none from before they were placed), or one they checked in to, whose after-class window is open (from 10 minutes before its end to 12 hours after), with `checked_in` and `said`: null before the student answers, then `{mood, items: [{item, reaction, pain, note}]}`, so the app can change it (a second send replaces the first). `after_checkin` is the same for the classes checked in to only, for the app of v0.9. `group_link` is the class group's, if the teacher gave one |
| `GET /curricula?lang=` | signed in | | `{library: [{key, type, level, sanskrit, name, english, aliases}], curricula: [{key, name, level, about, items: [{item, dose, unit, cue}]}]}`, from the curriculum tabs, names, about and cues in `lang`; `dose` is always a whole number: "5 breaths" in the cell is 5, 2.5 is 3, and an empty or worded cell is 0 |
| `POST /sessions/{session_id}/checkin` | approved student | yes | `{phase: before\|after, mood: 1..5}` → `{ok, stats}`. "before" from an hour before class to its end, for the student's own batch (`other_batch`); "after" from 10 minutes before the end to 12 hours after, for a class checked in to or of the batch the student was in at its time: without a check-in before, it records that they came, with no mood before. `pending`, `no_session`, `checkin_closed` |
| `POST /sessions/{session_id}/practice` | approved student | yes | `{entries: [{item, reaction: 1..4\|null, pain: 0\|1, note?}]}` (at most 60, notes up to 1000) → `{ok, saved}`: how each item went, replacing what was sent before for this class; entries with nothing said are not kept. Open when the "after" check-in is, and records coming in the same way; `checkin_closed`, `unknown_item`, `pending`, `no_session` |
| `POST /feedback` | signed in | yes | `{screen, text}` → `{ok}` |
| `GET /teacher/home?lang=` | teacher | the day's classes, once | `{sessions, batches, settings, pending_students}`: `sessions` are the classes of the next day that has some left (today, or tomorrow once today's are over), every batch's, each with `own_link`, `joined` and `curriculum`; `batches` with their everyday `meet_link` |
| `PUT /teacher/batches/{key}` | teacher | yes | `{meet_link}` → `{ok, meet_link}`: the batch's everyday link, for its classes without their own, checked and made plain as below; empty or null removes it; `bad_meet_link`, `no_batch` |
| `PUT /teacher/sessions/{session_id}?lang=` | teacher | yes | `{meet_link}` → `{text}`, the class's message. A video call link, made plain: Google Meet (`https://meet.google.com/abc-defg-hij`, query, slash and capitals dropped; `g.co/meet/…` too), Zoom (`/j/<id>`, keeping `pwd` as given, or `/my/<name>`, on any `zoom.us` address), Microsoft Teams (a `/l/meetup-join/` link as given, or `/meet/<id>` keeping `p`, on `teams.microsoft.com` or `teams.live.com`) or Jitsi (`meet.jit.si/<room>`); `https://` added, words around it skipped; `bad_meet_link`, `no_session` |
| `GET /teacher/sessions/{session_id}/share?lang=` | teacher | | the class's message `{text}`, plain text for any app; `no_link`, `no_session` |
| `PUT /teacher/sessions/{session_id}/curriculum` | teacher | yes | `{curriculum}` → `{ok, curriculum}`. A class without its own follows its batch's default curriculum (the `batches` tab), else the first in the `curricula` tab; `no_curriculum`, `no_session` |
| `GET /teacher/sessions/{session_id}/practice?lang=` | teacher | | how the class went: `{id, starts_at, curriculum, joined, answered, items: [{item, reactions: [not yet, with effort, steady, at ease], pain: [{name, note}], notes: [{name, text}]}]}`, items with strain or pain first, then the plan's order; a student whose row was deleted is "A former student", in `lang` |
| `PUT /teacher/settings` | teacher | yes | `{group_link?}` → `{group_link, group_code}`: the class group's link, optional. Any web link (a Telegram or Signal group, say; a WhatsApp invite is kept without its query), always https; a word with `http(s)://` is taken first, and one without needs a path (`t.me/x`), so "Mr.Sharma" or "7.00" is no link. Checked before it is saved (`bad_group_link`); empty or null removes it; left out, it stays |
| `POST /teacher/group_code` | teacher | yes | a new group code → `{group_code}` |
| `GET /teacher/invite?lang=` | teacher | | `{text}`: the invite, plain text for any app, with the group code and, once the owner sets `app_link` in the settings tab, where to get the app |
| `GET /teacher/students` | teacher | | `{students: [user + joined, created_at, intake]}`, pending first, then newest; `intake` as `/me/intake` gives it, with `suggested_batch` |
| `PUT /teacher/students/{user_id}/batch` | teacher | yes | `{batch, note?}` (the note up to 600) → `{ok, student}`: places the student in the batch ("Approve into a batch" for a pending one, "Move to batch" after a review), approved from then; logged in `batch_changes`; `no_batch`, `no_student` |
| `POST /teacher/students/{user_id}/status` | teacher | yes | `{status: approved\|rejected}` → `{ok}`: removes a student, or takes a removed one back into their batch; `needs_batch` for one never placed, `no_student` |
| `GET /teacher/students/{user_id}/asanas`, `…/asanas/{item}` | teacher | | the same as `/me/asanas` and `/me/asanas/{item}`, for that student; `no_student` |
| `POST /teacher/students/{user_id}/feedback` | teacher | yes | `{item, text}` → `{ok, id}`: the teacher's word on one item, which the student sees with its history; `unknown_item`, `no_student` |
| `POST /teacher/students/{user_id}/password` | teacher | yes | a new 8-letter password, the student signed out everywhere → `{password}`, for the teacher to pass on (the student can change it from the Me tab); `no_student` |
| `GET /teacher/insights?lang=` | teacher | | the last 14 days of classes (named in `lang`), mood change, student counts, the last 20 feedback notes; `questions.count` is 0 |
| `GET /teacher/shared` | teacher | | `{shared: [{id, user_id, name, text, created_at}]}`, newest first, at most 50 |

Times are UTC ISO-8601 to the second (`2026-11-18T02:30:00Z` is 8:00 in India). A check-in is for the student's own batch's classes (`other_batch`).

## The Sheet

`setup()` makes these tabs, each with a header row. The code finds columns by name, so the owner may move them or
add columns of her own (to the right is tidiest); `setup()` adds back any column the code needs.

| Tab | Columns | Notes |
|---|---|---|
| `Dashboard` | formulas | first tab; see below |
| `users` | id, name, phone, role, status, pw_hash, lang, created_at, batch, batch_since | role `student`/`teacher`; status `pending`/`approved`/`rejected`; `batch` a key of `batches`, empty until placed |
| `batches` | key, name, name_hi, name_mr, curriculum, days, time, duration_min, meet_link, about, about_hi, about_mr | seeded once from `content/studio.json`, then the owner's to edit: `days` like `mon, wed, fri`, `time` like `17:30` or `5:30 pm` in India (a plain text column, read as typed), `curriculum` its classes' default, `meet_link` its everyday link |
| `batch_changes` | id, student_id, from, to, note, created_at | each placement and each move between batches, with the teacher's note: the review history |
| `class_sessions` | id, batch, starts_at, duration_min, meet_link, curriculum, updated_at | one per class of each batch, made a week ahead; `meet_link` and `curriculum` when the teacher set them for this class |
| `checkins` | user_id, session_id, phase, mood, created_at, class, class_date | phase `before`/`after`, mood 1 to 5. `class` and `class_date` copy the class's batch name and India date, for queries; the code goes by session_id |
| `practice` | id, user_id, session_id, item, reaction, pain, note, created_at, item_name, week, solo_id, hold_s | how each item went, in a class (`session_id`) or on one's own (`solo_id`, with the stopwatch's `hold_s`): reaction 1 not yet, 2 with effort, 3 steady, 4 at ease (or blank), pain 1 for "felt strain or pain". `item_name` and `week` (its Monday) copy the item's name and the week, for queries |
| `solo_sessions` | id, user_id, started_at, ended_at | a student's practice on their own; its items are the `practice` rows with its id |
| `asana_feedback` | id, student_id, item, text, created_at | the teacher's feedback to one student on one item |
| `library` | key, type, level, sanskrit, name, english, aliases, source | the asanas, pranayama and meditation the curricula draw on; type `asana`/`pranayama`/`meditation`, level 1 to 3, aliases comma-separated |
| `curricula` | key, name, name_hi, name_mr, level, about, about_hi, about_mr, source | the curricula the teacher picks from; the first is the default |
| `curriculum_items` | curriculum, position, item, dose, unit, cue, cue_hi, cue_mr | each curriculum's items in order; `dose` a whole number (words after it are ignored; an empty one shows the unit alone); unit `breaths`, `seconds`, `minutes`, `rounds` or `strokes` |
| `feedback` | id, user_id, screen, text, created_at | |
| `shared_notes` | id, user_id, text, created_at | notes students chose to share with the teacher |
| `intake` (hidden) | user_id, age, height_cm, weight_kg, food, meals, pain, pain_note, updated_at | each student's answers about themselves, for the teacher to place them: health data, on the Dashboard only as counts |
| `intake_ratings` (hidden) | user_id, item, reaction, pain | the intake's self-assessment, one row per asana answered |
| `tokens` (hidden) | token_hash, user_id, created_at | SHA-256 of each login token |
| `settings` (hidden) | key, value, about | teacher_code, group_code, group_link (optional, set from the app), app_link (optional, typed here: where students get the app, for the invite) |

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

One tab of formulas, each block a single `QUERY` (click its first cell to read it): students by status, students per
batch, the latest batch changes, pain areas from the intake (counts only), mood per class (average after and before, all time), every student with their batch
and check-in count, attendance per class by date,
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
- **Guessing is slowed:** 5 wrong passwords for a number, 5 wrong teacher codes, or 5 wrong group codes from one
  number at sign-up, within 15 minutes, and that key is refused until the window has passed. The group code has 32⁶
  (about a billion) values, and each try takes a second.
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

No test reads the real clock: each runs at a fixed moment (`NOW` in [`test/helpers.mjs`](test/helpers.mjs),
Wednesday 6:00 in India), and a test about a particular moment pins its own. To check that the suite holds at any
moment, run it at others, for example just after a class, around midnight in India, and from Sunday into Monday:

```bash
for t in 2026-11-19T03:28:00Z 2026-11-18T18:31:00Z 2026-11-22T18:31:00Z; do
  SCA_TEST_NOW=$t node --test 'appsscript/test/*.test.mjs' | grep '^# fail'
done
```

- [`bundle.test.mjs`](test/bundle.test.mjs): `dist/` is the build of `src/` and the content files; the one scope;
  `setup()`, and run again on a Sheet in use; the main path.
- [`api.test.mjs`](test/api.test.mjs): every route's rules: one teacher and the teacher code in any case, the group
  code (pasted with stars or a full stop too), pending and approved, phone numbers however typed (from abroad, and
  "+91 0…"), the call links people paste, the optional group link of any kind, check-in windows, saying how class
  went without a check-in, the streak in classes (a Mon, Wed, Fri batch, a move), the check-in's lock, lockouts and
  their expiry, password resets and changes, the invite, the week of classes and their curricula (one per batch per
  day: a changed time moves them, keeping their links), a time typed in the batches tab (a time of day dated 1899, a
  number like 7.15), the batch at a class's time, two accounts for one number, a deleted student in a class review.
- [`practice.test.mjs`](test/practice.test.mjs): `/me/practice` (the sums, the days clamp, languages, rounding as
  Python's `round()`), `/me/shared` and `/teacher/shared`.
- [`curriculum.test.mjs`](test/curriculum.test.mjs): the curriculum tabs seeded once, `/curricula` in each
  language, a dose typed as words or left empty, each class's curriculum and its default, the after-class practice
  send (its window, its checks, replacing), and the teacher's review of a class.
- [`history.test.mjs`](test/history.test.mjs): a student's history per item (the trend, strain or pain, the notes,
  the list), and the teacher's feedback on an item.
- [`intake.test.mjs`](test/intake.test.mjs): the intake: filling and changing it, the batch it points to, the checks
  (a pain note in Hindi, counted in code points), and that only the student and the teacher read it.
- [`solo.test.mjs`](test/solo.test.mjs): practice on one's own: what is kept, the holds (one over an hour kept as an
  hour), the history mixing classes and sessions on one's own, the practice summary, and the rules.
- [`store.test.mjs`](test/store.test.mjs): the envelope, a write repeated with its request id, validation shapes, text
  kept as typed, hashed tokens and passwords, columns by name, ids, the lock (busy, always let go), a failure inside a
  route, growing tabs, the cache and its invalidation, the Dashboard's formulas.
- [`snapshot.test.mjs`](test/snapshot.test.mjs): a regression snapshot, 105 requests and their recorded answers
  ([`test/snapshot/`](test/snapshot/)); every status and every body must match. After a deliberate change to the
  answers, `node appsscript/test/snapshot/record.mjs` records them again; read its diff before committing.

[`scripts/smoke.mjs`](scripts/smoke.mjs) checks the deployed web app with requests that write no row:
`SCA_WEBAPP_URL=<url> node appsscript/scripts/smoke.mjs 5`. Its failed logins use numbers that cannot be real
mobiles (`+91 1…`); its one wrong teacher code counts toward that code's lockout (5 in 15 minutes), so before the
teacher has signed up, run it at most once a quarter of an hour.

## Developing

- [`src/`](src/): `Main.gs` (the envelope, the router, the request context and the lock), `Validate.gs` (input
  checks), `Store.gs` (tabs, encoding, the cache), `Auth.gs` (passwords, tokens, codes, phone numbers, lockouts,
  who is asking), `Studio.gs` (batches and their classes, India time, the week, the sums, call and group links, the
  messages for the class), `Routes.gs` (one
  function per route), `Practice.gs` (the curriculum, each class's plan, how each item went, practice on one's own,
  each student's history per item, the teacher's feedback), `Intake.gs` (a student's answers about themselves and the
  batch they point to), `Setup.gs` (`setup()`, the
  curriculum seed and the Dashboard), `appsscript.json`.
- `node appsscript/scripts/build.mjs` writes `dist/Code.gs` and `dist/appsscript.json`; `--check` fails if they are
  out of date (the tests check this too). Commit `dist/` with every change to `src/` or to `content/studio.json`
  and `content/curriculum.json`.
- Only `setup`, `doGet`, `doPost` and `onEdit` are public; every other function ends in `_`, so the editor's Run menu
  lists just those four (run `setup`; the others are for the web app and the edit trigger).
- `loadBackend()` in [`test/fakes.mjs`](test/fakes.mjs) runs Code.gs locally, as a stand-in backend for app
  development: it returns `{ss, state, cache, context, evaluate, call, Date, clock}`, where `call(method, path,
  {query, token, body})` goes through the envelope and `state.offsetMs` / `state.frozenMs` move or stop the clock.
