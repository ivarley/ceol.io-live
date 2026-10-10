The decider's data file goes here for an app build that decides on the phone with no
connection (spec 053, "Listening on the phone, offline"). It is 16 MB and rebuilt with
the corpus, so it is not in the repo; from the lab's environment:

    python -m lab decider export --out ios/CeolKit/Sources/CeolDeciding/Data/decider-v1.bin

Without it the app still builds, and "This phone" hears on the phone and decides on
Ceol's server, as before.
