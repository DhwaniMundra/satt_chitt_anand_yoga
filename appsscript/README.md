# The live backend: Apps Script over a Google Sheet

The app's server as a Google Apps Script web app bound to one Google Sheet in the studio's Drive folder. It answers
every route the app uses with the same rules and the same JSON as the FastAPI server it replaces, and the Sheet it
keeps its data in doubles as a database the owner can read, query and extend.

- [`dist/Code.gs`](dist/Code.gs): the one file to paste (built from [`src/`](src/) and `backend/content/studio.json`).
- [`dist/appsscript.json`](dist/appsscript.json): the manifest (optional, see step 3).

## Set up (5 minutes)

1. **The Sheet.** In the studio's Drive folder: New → Google Sheets. Name it, for example, "Satt Chitt Anand · live".
   Click **Share** and check that only you are listed: a Sheet in a shared folder is shared with everyone who can
   open the folder, and this one holds phone numbers and password hashes.
2. **The code.** In the Sheet: Extensions → Apps Script. Select everything in `Code.gs`, delete it, and paste the
   whole of [`dist/Code.gs`](https://raw.githubusercontent.com/DhwaniMundra/satt_chitt_anand_yoga/feature/sheets-backend/appsscript/dist/Code.gs).
   Click Save (the disk icon).
3. **The manifest (optional).** Code.gs works without it. It sets the project's time zone to India (for the
   execution log) and states the one permission the script needs. To paste it: Project Settings (the gear) → tick
   **Show "appsscript.json" manifest file in editor** → back in the Editor, open `appsscript.json`, replace its
   contents with [`dist/appsscript.json`](https://raw.githubusercontent.com/DhwaniMundra/satt_chitt_anand_yoga/feature/sheets-backend/appsscript/dist/appsscript.json),
   Save.
4. **Run setup.** In the toolbar's function menu pick **setup**, click **Run**, then **Review permissions**, choose
   your account and click **Allow**. It asks for one permission: to see and edit the spreadsheet the script is
   installed in, and no other file. If Google shows "Google hasn't verified this app", that is expected for a script
   of one's own: click **Advanced** → **Go to … (unsafe)** → Allow. The execution log then shows the **teacher
   sign-up code** (give it to Ramit ji; it works once) and the group code. Both stay in the hidden `settings` tab.
5. **Deploy.** Deploy → New deployment → the gear next to "Select type" → **Web app**. Description: "v0.7".
   Execute as: **Me**. Who has access: **Anyone**. Click Deploy (allow again if asked) and copy the **Web app URL**
   (it ends in `/exec`). Opening it in a browser shows `{"status":200,"body":{"ok":true,...}}`.

"Anyone" means the app can reach it without a Google sign-in; the app does its own sign-in with phone numbers and
passwords, and "Execute as Me" means it reads and writes your Sheet as you. Keep the URL out of public places: anyone
who has it can try to sign up (as a pending student, whom the teacher has to approve).

### Update later

Open the Sheet → Extensions → Apps Script, select everything in `Code.gs`, paste the new
[`dist/Code.gs`](dist/Code.gs), Save. Then Deploy → **Manage deployments** → the pencil (Edit) → Version: **New
version** → Deploy. The URL stays the same. Running `setup` again is always safe (it only adds what is missing).
