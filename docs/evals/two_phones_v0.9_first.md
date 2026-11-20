# Two-phone test: v0.9_first-two-phones

The first two-phone test of the v0.9 code, on 19 Nov 2026, before its release for testing: the teacher shares a
class, a student signs up with the group code, tells the teacher about herself and is placed in a batch, then
checks in and says how the class went. It ran the flow of the time, with a WhatsApp number to sign up and the
class link shared on WhatsApp. The fuller test of the same code after its release, on phones without WhatsApp,
is [`two_phones_v0.9`](two_phones_v0.9.md).

- **Server:** the dev backend at http://10.0.2.2:8000 (the laptop as the emulators see it)
- **Phones:** emulator-5554 (teacher), emulator-5556 (students), Android 16 emulators
- **Passed:** 18/18

- ✅ teacher phone shows the server address before sign-in
- ✅ teacher signed up
- ✅ WhatsApp message carries the link
- ✅ and names the batch
- ✅ the intake opens after sign-up, saying first who sees it
- ✅ the answers are sent
- ✅ then she waits to be placed
- ✅ teacher sees the answers and the batch they point to
- ✅ the placed student sees her batch
- ✅ before-class question appears in the check-in window
- ✅ after-class question appears on returning to the app
- ✅ the answers are kept
- ✅ a 2 GB phone says chat needs more memory
- ✅ teacher sees the student's before and after
- ✅ a wrong group code is refused
- ✅ with the code, she is asked about herself
- ✅ and waits to be placed
- ✅ the placed student leaves the waiting card, after returning to the app

Test people only. Screenshots and the recording are kept locally in .local/visualization/viz_v0.9/ (screens/v0.9_first-two-phones/ and tours/).
