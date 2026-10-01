# Listening on the server: a design, not yet built

2026-10-01. What it would take to run `lab listen` as a service the app's
phone page talks to, so a player can hold up a phone at a session. Written
before any of it is built; the decisions in the last section are the
player's.

## Why the server

A phone browser gives its microphone only to a page served over https (or
from localhost). The app is already served over https, so a page in the app
can capture the phone's microphone and stream it to a listening service; the
service runs the detector and sends back what it thinks. The laptop version
(`lab listen --phone`) can only show the meter on a phone, not listen with it.

## What it costs to run, measured

The listener's 4 s step, CPU only as on a Linux server (PESTO on the CPU,
Basic Pitch through ONNX), threads limited, over five minutes of night 137,
on this laptop's M5 cores (a shared cloud CPU may be two or three times
slower; to be measured on a real instance before relying on it):

| | per 4 s step, median / worst | peak memory |
|---|---|---|
| three trackers, one core | 0.62 s / 1.06 s | 3.0 GB |
| three trackers, two cores | 0.43 s / 0.72 s | 3.4 GB |
| yin alone, one core | 0.10 s | 1.6 GB |

Time: tracking about two thirds, scoring and tune-ness most of the rest.
Memory: the whole-corpus index and the aligner's sequences for every tune
(the fallback for tunes new to the session) and PyTorch for PESTO are the
large parts. One listener needs about one core while a session is on;
sessions rarely overlap.

## Shape

- **A separate service** (like the live-logging streaming sidecar): Python,
  the lab's detector packaged on its own, not loaded into the web app (the
  lab deliberately keeps its ~1 GB of audio dependencies off the app). One
  WebSocket per listening phone: 16-bit PCM in (about 44 KB/s at 22 kHz),
  the meter's state out every 4 s; taps in. Authenticated with the app's
  session cookie, as the sidecar is.
- **A page in the app** for a session instance: the certainty meter (top 3-5,
  ten-segment bars), "this is it", "none of these"; later, a confirmed tune
  proposed into the live log with its confidence, beside the human loggers.
- **Data** the service needs at start: the session's repertoire index, the
  whole-corpus index, the aligner's sequences, the tune-ness model; built by
  the lab and uploaded (S3), loaded at start (tens of seconds).
- **Kept**: each listened session's audio and taps, as the lab keeps them
  now, which is how the lab gets new nights to learn from.

## Choices for the player

1. **Size.** Three trackers and the fallback need a 4 GB instance; yin alone
   without the fallback might fit 2 GB, at a cost in accuracy not yet
   measured for the live decoder (on the retrieval bench at 30 s, yin with the
   aligner 0.902 against 0.950 for the three).
2. **Where the code lives.** App work happens in the app's worktrees, not on
   the lab branch; the detector would be extracted from `lab/` into a small
   package both can use, with the lab's tests kept as its agreement tests.
3. **First step.** A test deploy of the service alone, to measure a real
   instance's speed and memory, before the app page is built.
