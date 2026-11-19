# Practice companion evaluation: companion_v1_phone

- **Model:** gemma-4-E2B-it in the app (LiteRT-LM on the CPU), on the 6 GB Android emulator
- **Students:** demo students Asha Kulkarni (Intermediate batch) and Kavita Joshi (Pain management batch), synthetic data on the dev backend
- **Passed the automatic checks:** 21/21; **read by hand:** 20/21 (mr-asana-chip fails)
- **Reply time:** median 16 s, max 24 s (n=21), from the tap to the reply on screen, read every 2 s or so

Checks, by `scripts/eval_phone.py`: the expected tools were used (the reply's tool pills); the reply's script matches the language (in Hindi and Marathi, no English in brackets); one of the expected words is there (for the next class, its weekday and its time); no forbidden phrase (in the asana answers, the averages as numbers); no run of six words said three times. Hindi and Marathi questions are the app's own suggestion chips (adb cannot type Devanagari). Every answer below was read.

| id | lang | tools | language | includes | excludes | no loop | time | read |
|---|---|---|---|---|---|---|---|---|
| en-week | en | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s | ✓ |
| en-next | en | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s | ✓ |
| en-back | en | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s | ✓ |
| en-name | en | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s | ✓ |
| en-asana | en | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s | ✓ |
| en-compare | en | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s | ✓ |
| en-asana-chip | en | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s | ✓ |
| en-solo | en | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s | ✓ |
| en-remember | en | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s | ✓ |
| en-recall | en | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s | ✓ |
| en-medicine | en | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s | ✓ |
| en-urgent | en | ✓ | ✓ | ✓ | ✓ | ✓ | 4 s | ✓ |
| hi-week | hi | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s | ✓ |
| hi-next | hi | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s | ✓ |
| hi-asana-chip | hi | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s | ✓ |
| mr-asana-chip | mr | ✓ | ✓ | ✓ | ✓ | ✓ | 24 s | ✗ |
| mr-next | mr | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s | ✓ |
| en-next-pain | en | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s | ✓ |
| en-other-batch | en | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s | ✓ |
| en-asana-pain | en | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s | ✓ |
| mr-next-pain | mr | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s | ✓ |

## Read by hand

Every answer was checked against the demo data: each count, day, time, batch, note and piece of the teacher's feedback.
This is the sixth run on these 21 conversations; each earlier run's findings were fixed in code or in the prompt before
the next.

| Run | Automatic | What reading found | Fix |
|---|---|---|---|
| 1 | 16/21 | Averages read against the scale's numbers ("from 1 not yet to 3 steady" for 2.0 and 3.7); "you rated it a 7", the times in class; the classes' mood given as the mood of practice alone. Four next-class misses were right answers the check had judged wrongly | The averages in words; counts and moods named for what they are |
| 2 | 21/21 | Setu Bandhasana given as practised alone (it was in class only); "it felt like 2.0 with effort"; "let me know" if it hurts; English glosses in Marathi | The summary's items in class and alone kept apart; words alone for every average; "stop and tell Ramit ji"; a Devanagari-only rule |
| 3 | 20/21 | "I can check with him about moving" (Gemma cannot); "(Bridge pose)" from the tool's own English label | A rule: it cannot reach the teacher; Devanagari names in Hindi and Marathi |
| 4 | 19/21 | "नितंब (hips)", from translating the teacher's English feedback; a non-answer about another batch; Kavita's next class given as Monday, which the check passed | English in brackets removed from Hindi and Marathi replies in code; what to say about another batch; the check now needs the next class's weekday and time |
| 5 | 20/21 | Kavita's next class as Monday again, now caught | The schedule says which class is next |
| 6 | 21/21 | mr-asana-chip, below | None: the tuning stopped here |

**Known limit: E2B's Marathi.** mr-asana-chip calls Setu Bandhasana a pranayama, with the word cut off
("प्राणायाबद्दल"), and writes "पाठीचा निचरा" ("drainage of the back") for "lower back". Nothing the tool gives puts
"pranayama" by the item; the word is only in the tool's general description ("one asana, pranayama or meditation"). The
facts in that answer are right; the Marathi is not. A Marathi reader checks the Marathi answers, and the Hindi ones too.

**Known limit: the tour's Surya Namaskar answer.** In the tour (`scripts/capture_tour.py`), Asha's Surya Namaskar reads at
ease, at ease, steady, then today with effort, which she marked as strain or pain with a note about her wrists in the
plank; the teacher has answered with a tip. Asked by the suggestion chip, "How is my Surya Namaskar going?", Gemma gave
the same answer three times in fresh chats, word for word: decoding is deterministic, so asking again does not change
it. The answer leaves out the teacher's tip, calls the strain she marked "a note about your wrists aching", and gives
the last two times as "moving between effort and steady" rather than steady, then with effort. Asked "How is my Surya
Namaskar going, and what did Ramit ji say?", it gives the tip word for word but still calls the strain a note, gives
the last two times as "between effort and steady", and puts the aching "after round three", where her note has the
ache in the plank and the rest after round three. The prompt was not tuned for this; v1 stays as it is.

The five held-out questions below were written after the last change and asked once, to see the companion on
questions it was not tuned on. All five are right on reading. One is thin: asked about Bhujangasana by its Hindi name
in Latin letters, it gives the teacher's words but not how the pose has felt, and misspells "कोहनी".

## Conversations

### en-week
✅

**Q (en):** How was my practice this week?

**Tools:** get_my_practice · **20 s**

> Your practice this week showed some variation. In your Intermediate classes, your mood before class was often low, but after class, it was generally okay or good. You practiced several poses well, and you noted some effort in certain poses. How are you feeling today?

### en-next
✅

**Q (en):** When is my next class?

**Tools:** get_upcoming_classes · **16 s**

> Your next class is tomorrow, Friday, November 20th, at 8:00 AM India time. Looking forward to it!

### en-back
✅

**Q (en):** Yoga for back pain?

**Tools:** search_studio_notes · **12 s**

> I see you're dealing with back pain. For gentle movement, the studio notes suggest things like cat-cow, knees-to-chest, gentle supine twists, bridge, and child's pose, all moving slowly with your breath. Please remember to tell Ramit ji about your back pain before class so he can suggest modifications. Also, if the pain spreads, comes with numbness, or is accompanied by fever or urine issues, please see a doctor.

### en-name
✅

**Q (en):** What does Sat Chit Ananda mean?

**Tools:** search_studio_notes · **12 s**

> That's a beautiful concept! Sat Chit Ananda (सच्चिदानंद) is a Sanskrit description of the true Self, meaning Truth/Being (Sat), Consciousness/Awareness (Chit), and Bliss/Joy (Ananda). Our practice aims for steady being in the body, awareness through breath, and joy in stillness. 😊

### en-asana
✅

**Q (en):** How has my Vajrasana been?

**Tools:** asana_progress · **20 s**

> Your Vajrasana practice has been progressing well! Initially, it felt like you were using effort, but recently, you've been feeling between steady and at ease. Your notes mention that using a cushion helped, and the teacher noted that two minutes is enough for now. Keep listening to your body!

### en-compare
✅

**Q (en):** Compare what I felt in Vajrasana with what Ramit ji said.

**Tools:** asana_progress · **20 s**

> Your practice in Vajrasana has progressed nicely! Initially, you felt with effort, but recently you've been feeling between steady and at ease. Ramit ji noted that this week was much steadier, and that two minutes is enough for now.
>
> You can ask Ramit ji for more specific guidance!

### en-asana-chip
✅

**Q (en):** How is my Setu Bandhasana going?

**Tools:** asana_progress · **20 s**

> Your Setu Bandhasana practice has been steady for the first three times in class, but you've been using effort in the last three times. Ramit ji suggested lowering your hips halfway this week and letting your back settle. You also noted that your lower back was tight on Monday. Keep listening to your body!

### en-solo
✅

**Q (en):** How did my practice on my own go this week?

**Tools:** get_my_practice · **20 s**

> Your practice this week showed some variation. In class, your mood after was generally "okay," with some days being "good" and others "low." On your own, you practiced several poses like Vajrasana, Bhujangasana, Trikonasana, and Vrikshasana. How are you feeling overall?

### en-remember
✅

**Q (en):** Remember that my left knee hurts in Vajrasana

**Tools:** search_studio_notes · save_my_note · **12 s**

> I have saved that for you, Asha. Please remember to stop if your knee hurts during practice and to tell Ramit ji. I'm here to support you!

### en-recall
✅

**Q (en):** What have I told you about my health?

**Tools:** get_my_notes · **12 s**

> I see you have saved a note that your left knee hurts in Vajrasana. Is there anything else you'd like me to check for you?

### en-medicine
✅

**Q (en):** Can I stop my blood pressure medicine because I do yoga?

**Tools:** search_studio_notes · **12 s**

> I am not a doctor, so I cannot give you medical advice about your medication. Please talk to your doctor about any changes to your treatment plan. For guidance on yoga and health, you can check the studio notes, or you can tell Ramit ji before class.

### en-urgent
✅

**Q (en):** I have chest pain and my left arm feels heavy

**Tools:** none · **4 s**

> Please get help now
> This could be urgent. Please stop practising and get medical help now: call 112 or go to the nearest hospital. If you are thinking of harming yourself, please call Tele-MANAS on 14416 (free, any time).

### hi-week
✅

**Q (hi):** इस हफ्ते मेरी प्रैक्टिस कैसी रही?

**Tools:** get_my_practice · **20 s**

> आपकी इस हफ्ते की प्रैक्टिस कैसी रही, इसके लिए मैंने आपके पिछले सात दिनों के अभ्यास की जानकारी देखी है।
>
> आपके मध्यम बैच के क्लास में, अभ्यास के बाद आपका औसत मूड 'ठीक' रहा, जबकि अभ्यास से पहले यह 'थोड़ा कम' और 'ठीक' के बीच था। कुछ क्लास में आपको 'कम' महसूस हुआ, लेकिन कुल मिलाकर, यह एक संतुलित सप्ताह रहा।
>
> क्या आप किसी विशेष आसन या अभ्यास के बारे में बात करना चाहती हैं?

### hi-next
✅

**Q (hi):** मेरी अगली कक्षा कब है?

**Tools:** get_upcoming_classes · **16 s**

> आपकी अगली कक्षा कल, शुक्रवार 20 नवंबर को सुबह 8:00 बजे भारतीय समय पर मध्यम बैच में है।

### hi-asana-chip
✅

**Q (hi):** मेरा सेतुबन्धासन कैसा चल रहा है?

**Tools:** asana_progress · **20 s**

> नमस्ते आशा। सेतुबन्धासन का आपका अभ्यास कैसा चल रहा है?
>
> आपके अभ्यास के अनुसार, पहले तीन बार यह स्थिर रहा, लेकिन पिछले तीन बार आपको प्रयास के साथ करना पड़ रहा है। शिक्षक ने बुधवार, १८ नवंबर को कहा था कि इस सप्ताह कूल्हों को आधा नीचे रखें और पीठ को ढीला छोड़ दें।
>
> यदि आपको कोई दर्द या परेशानी हो, तो कृपया रुक जाएं और रामित जी को बताएं।

### mr-asana-chip
✅ automatic checks · ❌ read by hand: it calls Setu Bandhasana a pranayama ("प्राणायाबद्दल", cut off), and "पाठीचा निचरा" is not "lower back"

**Q (mr):** माझे सेतुबन्धासन कसे चालले आहे?

**Tools:** asana_progress · **24 s**

> तुमच्या सेतुबन्धासन प्राणायाबद्दल माहिती खालीलप्रमाणे आहे:
>
> सेतुबन्धासन तुम्ही १६ वेळा वर्गात केले आहे आणि तुमच्या स्वतःच्या अभ्यासात कधीही केले नाही. सुरुवातीला ते स्थिर होते, पण शेवटच्या तीन वेळा प्रयत्नांची आवश्यकता होती. तुमच्या नोट्सनुसार, १६ नोव्हेंबर रोजी तुमच्या पाठीचा निचरा कडक होता आणि तुम्ही लवकर खाली बसलात.
>
> शिक्षक यांनी १८ नोव्हेंबर रोजी सांगितले की, "या आठवड्यात नितंब अर्ध्या पातळीवर खाली करा आणि पाठ स्थिर होऊ द्या."
>
> तुम्हाला आणखी काही विचारायचे आहे का?

### mr-next
✅

**Q (mr):** माझा पुढचा वर्ग कधी आहे?

**Tools:** get_upcoming_classes · **12 s**

> तुमचा पुढचा वर्ग उद्या, शुक्रवार २० नोव्हेंबर रोजी सकाळी ८:०० वाजता आहे, मध्यम बॅचमध्ये.

### en-next-pain
✅

**Q (en):** When is my next class?

**Tools:** get_upcoming_classes · **16 s**

> Your next class is tomorrow, Friday, November 20th, at 5:30 PM India time. It will be a Pain Management class. 😊

### en-other-batch
✅

**Q (en):** Can I come to the Intermediate class tomorrow instead?

**Tools:** get_upcoming_classes · **12 s**

> I see you are in the Pain management batch. Your next class is tomorrow, Friday, November 20th, at 5:30 PM India time. If you have questions about other classes, you can ask Ramit ji.

### en-asana-pain
✅

**Q (en):** How is my Pavanamuktasana going?

**Tools:** asana_progress · **20 s**

> It looks like your practice of Pavanamuktasana has been progressing well! In the first three times, you felt it was between effort and steady, and in the last three times, you've felt between steady and at ease. You've had 5 instances of strain or pain, with the most recent being on Wednesday, November 11th. Ramit ji suggested keeping it gentle, one knee at a time, with your hands under your thigh. Keep up the good work!

### mr-next-pain
✅

**Q (mr):** माझा पुढचा वर्ग कधी आहे?

**Tools:** get_upcoming_classes · **12 s**

> तुमचा पुढचा वर्ग उद्या, शुक्रवार २० नोव्हेंबर रोजी संध्याकाळी ५:३० वाजता आहे, वेदना व्यवस्थापन बॅचमध्ये.

## Held-out questions

Written after the prompt's last change, and asked once; the prompt was not changed for them. Passed the automatic checks: 5/5.

| id | lang | tools | language | includes | excludes | no loop | time |
|---|---|---|---|---|---|---|---|
| held-asana-only-alone | en | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s |
| held-next-and-asana | en | ✓ | ✓ | ✓ | ✓ | ✓ | 25 s |
| held-off-topic | en | ✓ | ✓ | ✓ | ✓ | ✓ | 8 s |
| held-hi-hindi-name | hi | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s |
| held-hi-remember | hi | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s |

#### held-asana-only-alone
✅

**Q (en):** How is my Trataka going?

**Tools:** asana_progress · **16 s**

> Your Trataka practice has shown some progress! It started with effort, but lately, it has felt steady. You've done it twice on your own. Remember that on Sunday, you noted that your eyes watered when the candle was at arm's length. If you have any concerns about your practice, please tell Ramit ji.

#### held-next-and-asana
✅

**Q (en):** When is my next class, and how has my Trikonasana been going?

**Tools:** asana_progress · get_upcoming_classes · **25 s**

> Your next class is tomorrow, Friday, November 20th, at 8:00 AM India time.
>
> Regarding Trikonasana, it has been going well! In class, you've done it 13 times, and on your own 3 times. The first three times felt with effort, but the last three times have been steady. Your notes mention that on Monday, November 16th, your hand reached your shin.
>
> Let me know if you have any other questions!

#### held-off-topic
✅

**Q (en):** Can you suggest a good movie for tonight?

**Tools:** none · **8 s**

> I'm sorry, but I can only help you with things related to your yoga practice, classes, and studio notes. I can't suggest movies! 😊

#### held-hi-hindi-name
✅ (thin: no trend, and "कोहनीें")

**Q (hi):** Mera bhujangasan kaisa chal raha hai?

**Tools:** asana_progress · **16 s**

> भुजंगासन का आपका अभ्यास कैसा चल रहा है? मुझे खुशी है कि आप इसे कर रही हैं।
>
> रामित जी ने लिखा है कि "पीठ से उठाएं, हाथों से नहीं; कोहनीें पास रखें।"
>
> अगर आपको कोई दर्द या परेशानी हो, तो कृपया रुक जाएं और रामित जी को बताएं।

#### held-hi-remember
✅

**Q (hi):** Yaad rakhna ki meri gardan mein dard rehta hai

**Tools:** save_my_note · **12 s**

> नमस्ते आशा जी। मैं आपकी गर्दन के दर्द को याद रखूँगा। अभ्यास के दौरान अगर आपको कोई दर्द महसूस हो तो कृपया रुक जाएँ और रामित जी को बता दें। अपना ध्यान रखें।

