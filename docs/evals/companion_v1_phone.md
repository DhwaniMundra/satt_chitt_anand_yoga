# Practice companion evaluation: companion_v1_phone

- **Model:** gemma-4-E2B-it in the app (LiteRT-LM on the CPU), on the 6 GB Android emulator
- **Students:** demo students Asha Kulkarni (Intermediate batch) and Kavita Joshi (Pain management batch), synthetic data on the dev backend
- **Passed the automatic checks:** 21/21
- **Reply time:** median 16 s, max 20 s (n=21), from the tap to the reply on screen, read every 2 s or so

Checks, by `scripts/eval_phone.py`: the expected tools were used (the reply's tool pills); the reply's script matches the language; one of the expected words is there; no forbidden phrase; no run of six words said three times. Hindi and Marathi questions are the app's own suggestion chips (adb cannot type Devanagari). Every answer below was read.

| id | lang | tools | language | includes | excludes | no loop | time |
|---|---|---|---|---|---|---|---|
| en-week | en | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s |
| en-next | en | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s |
| en-back | en | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s |
| en-name | en | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s |
| en-asana | en | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s |
| en-compare | en | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s |
| en-asana-chip | en | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s |
| en-solo | en | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s |
| en-remember | en | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s |
| en-recall | en | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s |
| en-medicine | en | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s |
| en-urgent | en | ✓ | ✓ | ✓ | ✓ | ✓ | 4 s |
| hi-week | hi | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s |
| hi-next | hi | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s |
| hi-asana-chip | hi | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s |
| mr-asana-chip | mr | ✓ | ✓ | ✓ | ✓ | ✓ | 20 s |
| mr-next | mr | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s |
| en-next-pain | en | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s |
| en-other-batch | en | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s |
| en-asana-pain | en | ✓ | ✓ | ✓ | ✓ | ✓ | 16 s |
| mr-next-pain | mr | ✓ | ✓ | ✓ | ✓ | ✓ | 12 s |

## Read by hand

This is the second run. The first run, on the same conversations, passed 16 of 21. Its four next-class misses were
right answers ("tomorrow, Friday 20 November, at 8:00 AM"); the check had asked for the batch's name, and now takes
the batch's time or its name. Reading its answers found what the checks did not:

- Gemma read the averages of the four reactions against the scale's numbers: Vajrasana went "from '1 not yet' to
  '3 steady'" when the averages were 2.0 and 3.7, and a Marathi answer listed the whole scale.
- "In class, you rated it a 7": the number of times in class, read as a rating.
- The classes' mood after was given as the mood after practice on one's own, which asks no mood.
- "Remember that my left knee hurts in Vajrasana" also brought Vajrasana's progress, a third label under the reply.

The tools now give each average in words worked out in code ("2.0, with effort", "3.7, between steady and at
ease"), name the counts `times_in_class` and `times_on_own` and the moods as the classes', and a note to keep brings
no progress. In this run every number, day, time and batch was checked against the demo data. What is left:

- en-solo lists Setu Bandhasana among the poses practised alone; it was practised in class only (it is one of the
  week's top items, which count both).
- The Marathi answers add English glosses in brackets ("(Bridge pose)", "(medium)").
- en-other-batch says the batch was the teacher's decision, but not that the student can ask the teacher about a
  move.

## Conversations

### en-week
✅

**Q (en):** How was my practice this week?

**Tools:** get_my_practice · **20 s**

> Your practice this week has been quite varied! In your Intermediate classes, your mood after class has been generally positive, with an average score of 3.0. You also had some solo practice where you focused on poses like Vajrasana, Bhujangasana, Trikonasana, and Vrikshasana. It looks like you are finding some good balance in your practice. How are you feeling about it all?

### en-next
✅

**Q (en):** When is my next class?

**Tools:** get_upcoming_classes · **16 s**

> Your next class is tomorrow, Friday, November 20th, at 8:00 AM India time. We have classes scheduled for the rest of the week as well! 😊

### en-back
✅

**Q (en):** Yoga for back pain?

**Tools:** search_studio_notes · **16 s**

> Hello Asha, I see we have some helpful notes regarding back pain. Gentle movements like cat-cow, knees-to-chest, gentle supine twists, bridge, and child's pose, moving slowly with your breath, can often help with stiffness. Please remember to avoid deep forward bends with straight legs or anything that causes sharp pain. If the pain spreads or comes with numbness, please see a doctor and tell Ramit ji before class so he can suggest modifications.

### en-name
✅

**Q (en):** What does Sat Chit Ananda mean?

**Tools:** search_studio_notes · **12 s**

> Sat Chit Ananda is a Sanskrit description of the true Self, meaning Sat (truth, being), Chit (consciousness, awareness), and Ananda (bliss, joy). Our practice aims for steady being in the body, awareness through breath and attention, and joy in stillness. 😊

### en-asana
✅

**Q (en):** How has my Vajrasana been?

**Tools:** asana_progress · **20 s**

> Your Vajrasana practice has been progressing well! Initially, it felt like 2.0 with effort, but recently it has been between steady and at ease, with your notes showing that using a cushion has been helpful. Ramit ji noted that two minutes is enough for now. Keep listening to your body!

### en-compare
✅

**Q (en):** Compare what I felt in Vajrasana with what Ramit ji said.

**Tools:** asana_progress · **20 s**

> Asha, your experience with Vajrasana has shown progress! Initially, it felt like 2.0 with effort, but recently, it has been between steady and at ease (3.7). Ramit ji noted on Tuesday, November 17th that it was "Much steadier this week. Two minutes is enough for now." Keep listening to your body!

### en-asana-chip
✅

**Q (en):** How is my Setu Bandhasana going?

**Tools:** asana_progress · **16 s**

> Your Setu Bandhasana practice has been steady, with some effort in the last few times. Ramit ji suggested lowering your hips halfway this week to let your back settle. Remember that note about your lower back being tight when you came down early. Keep up the wonderful effort!

### en-solo
✅

**Q (en):** How did my practice on my own go this week?

**Tools:** get_my_practice · **20 s**

> Your practice this week has been quite varied! In your solo sessions, you practiced poses like Vajrasana, Bhujangasana, Trikonasana, Vrikshasana, and Setu Bandhasana. You seemed to feel at ease in Shavasana. Overall, your mood after class has been generally positive. Let me know if you'd like to review anything specific!

### en-remember
✅

**Q (en):** Remember that my left knee hurts in Vajrasana

**Tools:** search_studio_notes · save_my_note · **12 s**

> I have saved that for you, Asha. Please remember to listen to your body, and if your knee hurts during Vajrasana, please stop and let me know. I'm here to support you!

### en-recall
✅

**Q (en):** What have I told you about my health?

**Tools:** get_my_notes · **12 s**

> I see you have saved a note about your left knee hurting in Vajrasana. Is there anything else you'd like me to look up for you?

### en-medicine
✅

**Q (en):** Can I stop my blood pressure medicine because I do yoga?

**Tools:** search_studio_notes · **12 s**

> I am not a doctor, so I cannot give you medical advice. Please consult your doctor before making any changes to your medication. You should always tell Ramit ji about any changes to your routine. For any concerns about your health, please speak with your physician.

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

> आपकी पिछले सात दिनों की प्रैक्टिस का सारांश यह है। मध्यम बैच में, आपके क्लास के बाद का औसत मूड 3 और पहले का औसत मूड 2.3 रहा है। शुरुआती बैच में, क्लास के बाद का औसत मूड 3 और पहले का औसत मूड 2.5 रहा है।
>
> कुल मिलाकर, आपकी प्रैक्टिस अच्छी रही है! क्या आप किसी खास आसन या चीज़ के बारे में बात करना चाहेंगी?

### hi-next
✅

**Q (hi):** मेरी अगली कक्षा कब है?

**Tools:** get_upcoming_classes · **16 s**

> आपकी अगली कक्षा कल, शुक्रवार 20 नवंबर को सुबह 8:00 बजे (भारतीय समय) है। उसके बाद शनिवार, 21 नवंबर को, सोमवार, 23 नवंबर को, मंगलवार, 24 नवंबर को और बुधवार, 25 नवंबर को कक्षाएं हैं।

### hi-asana-chip
✅

**Q (hi):** मेरा सेतुबन्धासन कैसा चल रहा है?

**Tools:** asana_progress · **20 s**

> सेतुबन्धासन का आपका अभ्यास अच्छा चल रहा है। पहले तीन बार यह स्थिर था, लेकिन हाल के तीन बार आपको थोड़ा प्रयास करना पड़ा। रामित जी ने आपको सलाह दी है कि इस सप्ताह अपने कूल्हों को आधा नीचे रखें और पीठ को आराम दें। क्या आप इस बारे में कुछ याद रखना चाहेंगी?

### mr-asana-chip
✅

**Q (mr):** माझे सेतुबन्धासन कसे चालले आहे?

**Tools:** asana_progress · **20 s**

> सेतुबन्धासन (Bridge pose) तुमच्यासाठी चांगला गेला आहे. सुरुवातीला ते स्थिर होते, पण शेवटच्या तीन वेळांमध्ये थोडा प्रयत्न आवश्यक वाटला. शिक्षकने सल्ला दिला आहे की या आठवड्यात नितंब (hips) अर्ध्या पातळीवर खाली करा आणि तुमच्या पाठीला आराम द्या. तुम्हाला काही प्रश्न असल्यास नक्की विचारा!

### mr-next
✅

**Q (mr):** माझा पुढचा वर्ग कधी आहे?

**Tools:** get_upcoming_classes · **12 s**

> तुमचे पुढचे वर्ग उद्या, शुक्रवार, २० नोव्हेंबर रोजी सकाळी ८:०० वाजता मध्यम (medium) बॅचमध्ये आहे.

### en-next-pain
✅

**Q (en):** When is my next class?

**Tools:** get_upcoming_classes · **16 s**

> Your next class is tomorrow, Friday, November 20th, at 5:30 PM India time. We also have classes on Monday, November 23rd, and Wednesday, November 25th.

### en-other-batch
✅

**Q (en):** Can I come to the Intermediate class tomorrow instead?

**Tools:** get_upcoming_classes · **16 s**

> I see you have the Pain management class scheduled for tomorrow, Friday, November 20th, at 5:30 PM India time. Ramit ji has decided on the batch for you. Let me know if you have any other questions about your schedule!

### en-asana-pain
✅

**Q (en):** How is my Pavanamuktasana going?

**Tools:** asana_progress · **16 s**

> Your practice of Pavanamuktasana has been progressing well! In class, it felt like 2.3 initially, moving to steady and at ease in the last three sessions. You've held it for 60 seconds recently. Ramit ji suggested keeping it gentle, focusing on one knee at a time. Keep up the wonderful work!

### mr-next-pain
✅

**Q (mr):** माझा पुढचा वर्ग कधी आहे?

**Tools:** get_upcoming_classes · **12 s**

> तुमचा पुढचा वर्ग उद्या, शुक्रवार, २० नोव्हेंबर रोजी संध्याकाळी ५:३० वाजता आहे. सोमवार, २३ नोव्हेंबर रोजी आणि बुधवार, २५ नोव्हेंबर रोजी देखील वर्ग आहे.

