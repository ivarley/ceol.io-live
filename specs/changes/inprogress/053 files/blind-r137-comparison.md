# Night 137, the blind segmentation against the player's labels

Written after `blind-r137.md` / `.json` were committed (7a62ad1, sha256
f64dc3d7...). Nothing in the blind run or its cleaning rule was changed after
the labels were read. Scope: one night (2026-04-30, 69 labelled tunes) that
no setting in the lab was ever chosen on; the decoder as tuned on nights 1-5,
138 and 139; the night's own new tunes unknown to it.

## On the board's own measures (`lab eval`)

59 of 69 tunes right when they end (0.855; top-5 0.899); first right a median
15 s in; 2.6 changes of answer a tune. On night 140's held-out segments the
same follower was 0.902.

## As a segmentation

```
labels: 69 tunes (69 scored), 3 new to the session; blind: 88 cleaned segments
labelled tunes named right somewhere in their span: 64; named wrong: 4; nothing shown: 1
start error when right: median +9.1s, middle half +5.5 to +17.2s, within 10 s 0.55
cleaned segments: 64 the right tune, 17 a wrong tune over labelled music, 7 over no labelled tune

labelled tunes not named right:
  1:30:53-1:32:34 The New Rigged Ship (Jig) (new to the session): WRONG: Da Full Rigged Ship
  1:37:07-1:40:30 The King Of The Pipers (Jig): WRONG: Franc A'Phoill
  2:04:43-2:08:33 Wild Mountain Thyme (Barndance): WRONG: Bucks Of Oranmore, The
  2:42:26-2:44:05 Larry Redican's Mother (Slip Jig): WRONG: Bucks Of Oranmore, The
  2:59:01-3:00:54 Loch Lomond (Reel) (new to the session): MISSED (nothing shown)

cleaned segments over no labelled tune:
  0:04:34-0:05:20 Frieze Breeches, The shown 40s conf 0.94
  0:06:10-0:06:40 Frieze Breeches, The shown 24s conf 0.71
  0:06:34-0:07:08 Mason's Apron, The shown 28s conf 0.85
  0:28:02-0:28:32 Frieze Breeches, The shown 24s conf 0.73
  0:28:38-0:30:08 Tarbolton, The shown 76s conf 0.80
  0:35:58-0:36:44 Mason's Apron, The shown 40s conf 0.96
  1:11:22-1:12:04 Frieze Breeches, The shown 36s conf 0.91

new to the session:
  The Humours Of Carrigaholt: right
  The New Rigged Ship: WRONG: Da Full Rigged Ship
  Loch Lomond: MISSED (nothing shown)

sets: labelled 29, detected 35; labelled set starts with a detected one within 30 s: 25
```

## Reading it

- **Naming is the strong part.** 64 of 69 labelled tunes are named right
  somewhere in their span; 4 are named as another tune and 1 (Loch Lomond,
  new to the session) never named at all.
- **Starts are late**, a median 9 s after the labelled start, and only 55%
  within 10 s: the display has to be sure before it moves, and the estimate
  (first shown minus the 6 s window) does not recover that.
- **Sets:** 25 of the 29 labelled sets begin within 30 s of a detected set
  start; 35 detected against 29 labelled, so some sets are split.
- **Over audio with no labelled tune**, 7 cleaned segments, and every one is
  a hub: The Frieze Breeches (4), The Mason's Apron (2), Tarbolton (1).
  These are the candidates for the player's false starts, noodling or chat
  read as a tune; they are listed with times above for the player to check.
  The hubs are the tunes that match anything vaguely, so a cost per tune
  for many settings (plan item 4) or a hub-aware "not a tune" is the lever.
- **17 cleaned segments name a wrong tune over labelled music**: wobble that
  lasted over 20 s and survived the cleaning.
- **Tunes new to the session:** 1 of 3 named (The Humours of
  Carrigaholt); The New Rigged Ship shown as Da Full Rigged Ship; Loch Lomond
  not shown at all.
