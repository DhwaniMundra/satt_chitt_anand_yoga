# Decisions

Each decision with the options considered and the reason for the choice. When a decision changes, edit its row and
say so in the iteration log.

| # | Question | Options considered | Chosen | Why |
|---|---|---|---|---|
| 1 | How does the app connect to the class WhatsApp group? | (a) Read the group automatically with an unofficial WhatsApp Web library (whatsapp-web.js, Baileys). (b) WhatsApp Business Cloud API. (c) The teacher posts from the app through Android's share sheet; the app has its own accounts | **(c)** | (a) breaks WhatsApp's terms and can get the teacher's own number banned; it also needs a phone logged in 24/7. (b) is for business numbers messaging customers, not for reading a personal group. (c) keeps WhatsApp as the place the class already talks, with no risk to the teacher's number |
| 2 | How do we know a student belongs to the class? | (a) Membership of the WhatsApp group. (b) Teacher approves every sign-up. (c) A short **group code** posted in the WhatsApp group, plus teacher approval for anyone without it | **(c)** | Whoever can read the group has the code, so the code stands in for group membership. Anyone else can still sign up and wait for approval. The teacher can change the code at any time |
| 3 | Where do accounts and data live? | (a) Firebase. (b) Our own small server (FastAPI + SQLite) on the laptop. (c) Google Drive as the database | **(b)**, backed up to a private GitHub repository | The brief asked for a local server. SQLite is one file, easy to read and explain. GitHub's contents API gives free, versioned backups (every backup is a commit) and a restore on an empty server. Google Drive would also work; GitHub needs only a token, not OAuth |
| 4 | Where does Gemma run? | (a) On the phone (LiteRT-LM on Android, the same `.litertlm` file). (b) On the laptop server's GPU | **(b) for now** | The E4B model file is 3.7 GB, too large to ask every student to download, and most students' phones could not run it at a usable speed. On the laptop's RTX 3070 a warm answer takes about 2 s. On-device is the natural next step for privacy (see open questions) |
| 5 | How does Gemma know about yoga and the studio? | (a) Fine-tune. (b) Put the whole notes file in every prompt. (c) **Retrieve** the 1–3 most relevant sections of one notes file and put only those in the prompt | **(c)** | The notes file (`backend/knowledge/yoga_health.md`) is something the teacher can read and correct; no training run is needed. Retrieval (BM25 over sections, with Hindi and Marathi keywords) keeps prompts short and lets the app show which notes an answer came from |
| 6 | How do we stop the assistant giving medical advice? | Prompt rules only, or prompt rules plus checks in code | **Both** | The prompt forbids diagnosis, cures and medicine changes, and sends people to their doctor and the teacher. Before the model runs, a fixed list of emergency signs (chest pain, fainting, self-harm…) in three languages returns a fixed reply with 112 and Tele-MANAS (14416), with no model involved |
| 7 | Which languages? | English only, or English, Hindi and Marathi | **All three** | The students' own languages. The app's text, the class names, the WhatsApp message and the assistant all follow the chosen language. Translations are drafts until a native speaker has read them |
| 8 | How do students say how a class went? | Forms, star ratings, or **five faces before and after class** | **Faces** | One tap, no reading needed. Before-and-after pairs give the teacher (and the iteration log) a signal of whether classes help, without collecting health details |
| 9 | What does the studio keep of the questions people ask? | Everything, or nothing, or **only with consent** | **Only with consent** | Health questions are personal. Without the research consent switch, only the time, language and which notes were used are stored, never the words |
| 10 | Which demo data appears in screenshots and videos? | Real students, or **synthetic data** | **Synthetic**, labelled on every image | No real person's data in a public repository. The Insights numbers in the demo are invented and are never results |
| 11 | App technology? | Flutter, React Native, **Kotlin with Jetpack Compose** | **Kotlin + Compose** | Native Android is what LiteRT-LM supports for running Gemma on the phone later, and it needs no extra runtime |

## Open questions

- **Hosting.** The server runs on a laptop. Students outside the home Wi-Fi need it on the internet, over HTTPS:
  a small cloud machine, or a tunnel (for example Cloudflare Tunnel) in front of the laptop. Then the app's
  `usesCleartextTraffic` flag goes.
- **On-device Gemma** for students with capable phones, so questions never leave the phone.
- **Marathi answers** from Gemma 4 E4B are not yet reliable enough (see `docs/evals/`).
- **Consent from the studio** to use its name, schedule and teacher's bio in a public repository.
