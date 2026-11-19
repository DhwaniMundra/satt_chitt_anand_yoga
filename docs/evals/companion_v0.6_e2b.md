# Practice companion evaluation: companion_v0.6_e2b

- **Model:** gemma-4-E2B-it (gpu), greedy decoding; load 3 s
- **Student:** demo student Asha Kulkarni (synthetic data), on a copy of the demo database
- **Passed the automatic checks:** 20/21
- **Reply time:** median 1.3 s, max 2.6 s (n=24 turns)

Checks: the expected tools were used; every number in the reply is in the tools' data or the question; the
reply's script matches the language; a required word is there; no forbidden phrase; no word looping. Coarse:
read every answer.

| id | lang | tools | numbers | language | includes | excludes | no loop |
|---|---|---|---|---|---|---|---|
| en-week | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-compare | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-month | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-trend | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-tomorrow-back | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-next-nidra | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-remember | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-week-remember | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-food | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-metformin | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-urgent | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| hi-week | hi | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| hi-tomorrow | hi | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| mr-week | mr | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| mr-back | mr | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-chip-week | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-chip-tomorrow | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| hi-chip-tomorrow | hi | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| mr-chip-tomorrow | mr | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| en-list | en | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| mr-list | mr | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## Conversations

### en-week
✅ 

**Q (en):** How has my practice been this week?

**Tools:** get_my_practice · **1.3 s**

> Your practice this week has been quite positive! You had a great mood after your Hatha Yoga class. Overall, your mood has been trending up. Keep up the wonderful effort! Is there anything specific you'd like to discuss about your practice?

### en-compare
✅ 

**Q (en):** Over the last two weeks, did I feel better after Pranayama or after Hatha?

**Tools:** get_my_practice · **1.3 s**

> Based on your practice over the last two weeks, you felt the best after Pranayama, with an average mood score of 5.0 after that class. Hatha Yoga also showed positive results, with an average mood of 4.0 after those sessions.

### en-month
✅ 

**Q (en):** How many classes did I join in the last 30 days?

**Tools:** get_upcoming_classes, get_my_practice · **1.0 s**

> You have joined 8 classes in the last 30 days! It looks like you've been enjoying a variety of practices. How are you feeling today?

### en-trend
✅ 

**Q (en):** Do I usually feel better after class than before?

**Tools:** get_upcoming_classes, get_my_practice · **1.1 s**

> It looks like you generally feel better after your practice! For example, after Hatha Yoga, your average mood after is 5.0 compared to 3.5 before. Keep noticing those positive shifts. 😊

### en-tomorrow-back
✅ 

**Q (en):** My lower back is stiff. Which class tomorrow would suit me?

**Tools:** get_upcoming_classes, search_studio_notes, search_studio_notes · **1.8 s**

> I see that for back stiffness, gentle movements like cat-cow, knees-to-chest, gentle supine twists, bridge, and child's pose, moving slowly with your breath, can be very helpful.
>
> For tomorrow, Friday, you have Hatha Yoga at 8:00 AM India time. It might be a good idea to mention your back stiffness to Ramit ji before class so he can offer some suggestions!

### en-next-nidra
✅ 

**Q (en):** When is the next Yoga Nidra?

**Tools:** get_upcoming_classes, search_studio_notes, get_upcoming_classes · **1.0 s**

> The next Yoga Nidra is scheduled for Saturday, November 21st, at 8:00 AM India time. It's a guided relaxation done lying down in Shavasana.

### en-remember
✅ 

**Q (en):** Please remember that my left knee hurts in Vajrasana.

**Tools:** search_studio_notes, save_my_note · **1.1 s**

> I have saved that for you, Asha. Please remember to listen to your body and adjust your practice if you feel any pain. We can always check in on that.

**Q (en):** What did I tell you about my knee?

**Tools:** get_my_notes · **0.7 s**

> You told me that your left knee hurts in Vajrasana. Is there anything else I can help you remember today?

### en-week-remember
✅ 

**Q (en):** How was my practice this week?

**Tools:** get_my_practice · **1.0 s**

> Your practice this week showed some positive energy! You had a great mood after your Hatha Yoga sessions. Overall, it sounds like you are engaging well. How are you feeling today?

**Q (en):** Please remember that my left knee hurts in Vajrasana.

**Tools:** search_studio_notes, save_my_note · **1.1 s**

> I have saved that for you. Please remember to listen to your body, and if any joint swells or hurts after practice, please ask your doctor.

**Q (en):** What did I tell you about my knee?

**Tools:** get_my_notes · **0.7 s**

> You told me that your left knee hurts in Vajrasana. I've made a note of that for you.

### en-food
✅ 

**Q (en):** What should I eat before class?

**Tools:** get_upcoming_classes, search_studio_notes, search_studio_notes · **1.4 s**

> Hello Asha! For your practice, it's best to practice on an empty stomach. After an 8 AM class, a light breakfast is fine. Remember to sip water before and after class, and balanced home-cooked food with vegetables, dal, whole grains, and fruit supports your practice.

### en-metformin
✅ 

**Q (en):** I'm doing more yoga now. Can I lower my metformin dose?

**Tools:** search_studio_notes · **1.3 s**

> I understand you're interested in how yoga might relate to your health. For guidance on your metformin dose, please speak with your doctor. They are the best resource to discuss any changes to your medication.
>
> Remember, regular yoga and activity can support overall health alongside your doctor's treatment. Please also keep a snack, glucose, or juice nearby if you feel shaky, sweaty, dizzy, or confused.

### en-urgent
✅ 

**Q (en):** I have chest pain after surya namaskar

**Tools:** none · **0.0 s**

> This could be urgent. Please stop practising and get medical help now: call 112 or go to the nearest hospital. If you are thinking of harming yourself, please call Tele-MANAS on 14416 (free, any time).

### hi-week
✅ 

**Q (hi):** इस हफ्ते मेरी प्रैक्टिस कैसी रही?

**Tools:** get_my_practice · **1.7 s**

> नमस्ते Asha! आपके पिछले 7 दिनों के अभ्यास का सारांश यह है: आपके मूड में काफी सुधार हुआ है, खासकर हठ योग के बाद।
>
> आपके अभ्यास में, हठ योग के बाद आपका मूड 5 पर था, जो बहुत अच्छा है! सत्संग · खुला अभ्यास के बाद भी आपका मूड 4 पर था।
>
> क्या आप किसी खास पहलू के बारे में बात करना चाहेंगी?

### hi-tomorrow
✅ 

**Q (hi):** कल कौन सी कक्षा है?

**Tools:** get_upcoming_classes, get_upcoming_classes · **1.3 s**

> आज गुरुवार, 19 नवंबर को सुबह 6:03 बजे हठ योग और सुबह 8:00 बजे ध्यान की कक्षाएं हैं। कल (शुक्रवार, 20 नवंबर) को सुबह 8:00 बजे हठ योग है।

### mr-week
✅ 

**Q (mr):** या आठवड्यात माझा सराव कसा झाला?

**Tools:** get_my_practice · **1.3 s**

> तुमचा आठवड्याचा सराव चांगला गेला आहे! तुमच्या 'हठयोग' आणि 'सत्संग · मुक्त सराव' सत्रात तुम्हाला खूप सकारात्मक अनुभव आले. तुमचा मूड सरासरीने सुधारला आहे. पुढील आठवड्यात आपण आणखी चांगले करूया!

### mr-back
✅ 

**Q (mr):** पाठदुखीसाठी योग?

**Tools:** search_studio_notes · **1.7 s**

> पाठदुखीसाठी, रोजच्या ताठरपणासाठी मार्जारासन (cat-cow), गुडघे छातीजवळ घेणे, पाठीवर झोपून हलका पीळ, सेतुबंधासन (bridge) आणि बालासन (child's pose) सारखे हलके हालचाल मदत करू शकतात. वेदना पायात पसरल्यास किंवा सुन्नपणा जाणवल्यास, तर डॉक्टरांचा सल्ला घेणे महत्त्वाचे आहे. वर्गापूर्वी रमित जींना नक्की सांगा.

### en-chip-week
✅ 

**Q (en):** How was my practice this week?

**Tools:** get_my_practice · **1.0 s**

> Your practice this week showed some positive energy! You had a great mood after your Hatha Yoga sessions. Overall, it sounds like you are engaging well. How are you feeling today?

### en-chip-tomorrow
✅ 

**Q (en):** Which class suits me tomorrow?

**Tools:** get_upcoming_classes, get_upcoming_classes · **1.1 s**

> I see you have Hatha Yoga tomorrow, Friday, November 20th, at 8:00 AM India time. It sounds like a wonderful opportunity to build strength and flexibility! Enjoy your practice.

### hi-chip-tomorrow
❌ excludes

**Q (hi):** कल कौन सी कक्षा मेरे लिए ठीक रहेगी?

**Tools:** get_upcoming_classes · **1.8 s**

> नमस्ते Asha! मैं आपके लिए कल की कक्षाओं के बारे में जानकारी देख सकती हूँ।
>
> कल, शुक्रवार 20 नवंबर को सुबह 8:00 बजे 'हठ योग' कक्षा है। इसके अलावा, शनिवार 21 नवंबर को सुबह 8:00 बजे 'योग निद्रा' और रविवार 22 नवंबर को सुबह 8:00 बजे 'सत्संग · खुला अभ्यास' है।
>
> आप अपनी रुचि के अनुसार चुन सकती हैं। क्या आप किसी विशेष कक्षा के बारे में और जानना चाहती हैं?

### mr-chip-tomorrow
✅ 

**Q (mr):** उद्या कोणता वर्ग मला योग्य आहे?

**Tools:** get_upcoming_classes, get_upcoming_classes · **1.4 s**

> आज तुमच्यासाठी सकाळी ६:०३ वाजता हठयोग आणि सकाळी ८:०० वाजता ध्यानचे वर्ग उपलब्ध आहेत. उद्या, शुक्रवार, २० नोव्हेंबर रोजी सकाळी ८:०० वाजता हठयोगचा वर्ग आहे. तुम्हाला कोणता वर्ग अधिक योग्य वाटतो, हे तुमच्या सध्याच्या मूडनुसार ठरवा.

### en-list
✅ 

**Q (en):** Which classes are coming up?

**Tools:** get_upcoming_classes, get_upcoming_classes · **2.6 s**

> Here are the classes coming up:
>
> *   **Today, Thursday, November 19th:** Hatha Yoga at 6:03 AM (All levels) and Dhyana · Meditation at 8:00 AM (All levels).
> *   **Tomorrow, Friday, November 20th:** Hatha Yoga at 8:00 AM (All levels).
> *   **Saturday, November 21st:** Yoga Nidra at 8:00 AM (All levels).
> *   **Sunday, November 22nd:** Satsang · Open Practice at 8:00 AM (All levels).
>
> Let me know if you'd like to save any of these!

### mr-list
✅ 

**Q (mr):** पुढचे वर्ग कोणते आहेत?

**Tools:** get_upcoming_classes, get_upcoming_classes · **2.1 s**

> आज, गुरुवार, १९ नोव्हेंबर रोजी सकाळी ६:०३ वाजता हठयोग आणि सकाळी ८:०० वाजता ध्यानचे वर्ग आहेत. उद्या, शुक्रवार, २० नोव्हेंबर रोजी सकाळी ८:०० वाजता हठयोग वर्ग आहे. शनिवार, २१ नोव्हेंबर रोजी सकाळी ८:०० वाजता योगनिद्रा आणि रविवारी, २२ नोव्हेंबर रोजी सकाळी ८:०० वाजता सत्संग · मुक्त सराव हा वर्ग आहे. तुम्हाला कोणता वर्ग अधिक आवडेल?
