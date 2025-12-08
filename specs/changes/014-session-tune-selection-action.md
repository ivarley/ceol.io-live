# 014 Session Tune Selection & Action

We're going to make it so you can enter a mode where you can "select" individual tunes on a session's tune list and then take action (adding them to your tunebook, or to another session that you're an admin for).

In the filter pulldown section, under the sort options, add a button that says "Select Tunes ...", and next to it a button that starts disabled and says "And Copy To ...". When you click it, a round checkbox appears next to each tune in the list, which you can individually check or uncheck. Filter, search and sort still works as normal on the list and don't change which tunes are selected.

As soon as any tunes are selected, the "And Copy To ..." button becomes visible. When clicked, it shows a new modal with these choices:
"Copy the selected {N} checked tunes to:"

- My Tunes (as [want to learn | learning | learned])
- {Session I'm An Admin Of #1}
- {Session I'm An Admin Of #2}
- ...

When you select one, show a screen that says "{N} tunes will be copied to {destination}. Proceed?". If any filters are visible, and the number of VISIBLE checked tunes differs from the number of TOTAL checked tunes (i.e. some checked tunes are filtered out), "Warning: this will copy all {N} checked tunes, not just the {M} checked tunes visible right now with your filters and searches enabled!".

When you click "Copy Them!", it does, and the deposits you on that destination (either my tunes or the session tunes page indicated) with a toast saying "Copied {N} tunes to {destination}." If any tunes were skipped because they were already in that destination, add this to the toas message: "({M} tunes were skipped because they're already there.)"

In addition to the checkbox next to each tune, change the "{N} tunes" label above the list to a checkbox that says "Select all {N} tunes in this list". Clicking it selects all the checkboxes. If not all checkboxes are selected (e.g. if you do "select all" and then uncheck at least one), then the "Select all" checkbox reverts to unchecked. If any checkboxes are checked at all, follow the "Select all ..." line with a link to "(Deselect All)".
