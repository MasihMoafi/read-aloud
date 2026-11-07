# Read Aloud demo

**Goal:** Show that selecting English text and pressing Super+R starts local
speech, with the real player available for control.

**Output:** 1920×1080 MP4 at 30 fps, approximately 16–19 seconds.

**Source:** Capture the installed Electron app and a real Chromium selection on
an isolated Xvfb display. Record only that display. Save the speech WAV emitted
by the app's own worker; route playback to a temporary null sink. No microphone,
user browser profile, network assets or downloads.

**Look:** Inter, 72 px display / 34 px support; off-white `#f5f7f6`, charcoal
`#182a2a`, teal `#147d78`. Use the approved app logo and the real player.
Content remains within a 90% action-safe area.

**Story:** One sample sentence is selected → Super+R → the player appears and
the sentence is heard → the speed menu opens → a real player close-up with
the voice button → the app mark and shortcut close. Use a 0.5-second camera
push toward the player; hold its close-up long enough to read. No invented
product controls.

**Sound:** The app's local voice is the main sound. Use a soft bundled click
and key press on the corresponding actions. No background track is installed.

**Avoid:** Fake UI, dark empty backgrounds, glow, decorative gradients,
unverified claims, tiny text and repeated fade-up transitions.

**Check:** Verify actual selection and player interactions, inspect every beat
and the 24 px player, measure audio, then check the final MP4 and its duration.
