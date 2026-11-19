# Companion probe: Gemma 4 E4B with tools over one student's history

The first probe behind the practice companion ([v0.5](../iterations/v0.5.md), "The probe"), run before the chat was
built, on 18 Nov 2026. Gemma 4 E4B on the laptop's GPU got tools that returned raw rows (every class, every mood) and
eight questions about the demo student's practice. Each question's tool calls and the answer are below, unedited. The
tool for saving was then called `save_practice_note` (later `save_my_note`).

What it showed: the right tool for every question that needed one (the metformin question used none; the notes were
not searched, which v0.5 later fixed by handing the matching notes over up front), and one slip with the sums. In
compare-moods, the Hatha classes of the last 14 days had after-class moods of 3, 4 and 5; the reply gave "a 4/5 and
5/5", leaving out the 3. So the tools now return summaries worked out in code.

Student: Asha Kulkarni (demo data)

Ground truth, last 7 days: `{"days": 7, "classes_joined": 3, "classes": [{"date": "Fri 13 Nov", "class": "Hatha Yoga", "mood_before": 4, "mood_after": 5}, {"date": "Sun 15 Nov", "class": "Satsang \u00b7 Open Practice", "mood_before": 2, "mood_after": 4}, {"date": "Wed 18 Nov", "class": "Vinyasa Flow", "mood_before": 3, "mood_after": null}]}`

Ground truth, last 14 days: `{"days": 14, "classes_joined": 7, "classes": [{"date": "Fri 06 Nov", "class": "Hatha Yoga", "mood_before": 3, "mood_after": 3}, {"date": "Sun 08 Nov", "class": "Satsang \u00b7 Open Practice", "mood_before": 4, "mood_after": null}, {"date": "Mon 09 Nov", "class": "Hatha Yoga", "mood_before": 3, "mood_after": 4}, {"date": "Tue 10 Nov", "class": "Pranayama", "mood_before": 3, "mood_after": 5}, {"date": "Fri 13 Nov", "class": "Hatha Yoga", "mood_before": 4, "mood_after": 5}, {"date": "Sun 15 Nov", "class": "Satsang \u00b7 Open Practice", "mood_before": 2, "mood_after": 4}, {"date": "Wed 18 Nov", "class": "Vinyasa Flow", "mood_before": 3, "mood_after": null}]}`

## practice-week

**Q:** How has my practice been this week?

**Tools:** `[{"type": "function", "function": {"name": "get_my_practice", "arguments": {"days": 7}}}]` · **2.3 s**

> It looks like you've been practicing 3 times this week! You felt great after your Hatha Yoga on Friday (5/5) and your Satsang on Sunday (4/5). Your Vinyasa Flow on Wednesday had a moderate feeling before class (3/5). How are you feeling today?

## compare-moods

**Q:** Did I feel better after Pranayama or after Hatha, over the last two weeks?

**Tools:** `[{"type": "function", "function": {"name": "get_my_practice", "arguments": {"days": 14}}}]` · **1.7 s**

> Based on your practice over the last two weeks, you reported feeling better after Pranayama (a 5/5) compared to Hatha Yoga (which had a 4/5 and 5/5).
> 
> Would you like to look at any other details?

## back-tomorrow

**Q:** My lower back is stiff today. Which class tomorrow would suit me?

**Tools:** `[{"type": "function", "function": {"name": "get_upcoming_classes", "arguments": {}}}, {"type": "function", "function": {"name": "search_studio_notes", "arguments": {"query": "stiff lower back"}}}]` · **3.1 s**

> Hello Asha. I see you're feeling stiff in your lower back today.
> 
> For tomorrow, **Friday's Hatha Yoga** class might be a good choice as it focuses on classical postures held with steady breath, which can be gentle.
> 
> However, please remember to tell Ramit ji about your stiffness before class so he can suggest modifications. Also, gentle movements like cat-cow or child's pose are often helpful for stiffness.
> 
> If the stiffness is severe, please consult your doctor first.

## remember-knee

**Q:** Please remember that my left knee hurts in Vajrasana.

**Tools:** `[{"type": "function", "function": {"name": "save_practice_note", "arguments": {"note": "left knee hurts in Vajrasana"}}}]` · **1.4 s**

> Of course, Asha. I have saved that note for you: "left knee hurts in Vajrasana." I'll keep it in mind for your practice!

**Q:** What did I tell you about my knee?

**Tools:** `[{"type": "function", "function": {"name": "get_my_notes", "arguments": {}}}]` · **0.7 s**

> You mentioned that your left knee hurts in Vajrasana. I have saved that note for you!

## hindi-week

**Q:** इस हफ्ते मेरी प्रैक्टिस कैसी रही?

**Tools:** `[{"type": "function", "function": {"name": "get_my_practice", "arguments": {"days": 7}}}]` · **4.9 s**

> नमस्ते आशा जी! इस हफ्ते आपने 3 क्लासेस लीं।
> 
> *   **शुक्रवार (13 नवंबर):** हठ योग (Hatha Yoga) - पहले से 4, बाद में 5 महसूस किया।
> *   **रविवार (15 नवंबर):** सत्संग · ओपन प्रैक्टिस (Satsang · Open Practice) - पहले से 2, बाद में 4 महसूस किया।
> *   **बुधवार (18 नवंबर):** विन्यासा फ्लो (Vinyasa Flow) - पहले से 3 महसूस किया।
> 
> कुल मिलाकर, आपकी प्रैक्टिस अच्छी रही! क्या आप कुछ और जानना चाहेंगी?

## metformin

**Q:** I'm doing more yoga now, can I lower my metformin dose?

**Tools:** `[]` · **0.9 s**

> I cannot give you medical advice. For any questions about your medication, please consult your doctor. It is also important to tell Ramit ji before your next class.

## next-nidra

**Q:** I missed class yesterday. When is the next Yoga Nidra?

**Tools:** `[{"type": "function", "function": {"name": "get_upcoming_classes", "arguments": {}}}]` · **1.3 s**

> The next Yoga Nidra class is on Saturday, November 21st, at 8:00 AM. I hope you can make it! 😊
