# Two-phone test: v0.4

- **Server:** http://10.0.2.2:8000 (the laptop as seen from the emulators; an APK built with -PscaServer uses the laptop's Wi-Fi address instead)
- **Phones:** emulator-5554 (teacher), emulator-5556 (students), Android 16 emulators
- **Passed:** 10/10

- ✅ teacher phone shows the server address before sign-in
- ✅ teacher signed up
- ✅ WhatsApp message carries the link
- ✅ student with group code sees the class
- ✅ before-class question appears in the check-in window
- ✅ after-class question appears on returning to the app
- ✅ Gemma answers the student
- ✅ teacher sees the student's before and after
- ✅ student without code waits for approval
- ✅ approved student is no longer waiting, after returning to the app

Test people only. Screenshots and the side-by-side recording are kept locally in `.local/visualization/tours/v0.4-two-phones/`;
the recording is in the README as a GIF (`docs/media/gifs/two_phones.gif`).
