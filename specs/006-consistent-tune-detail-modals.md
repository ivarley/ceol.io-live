# 006 Consistent Tune Detail Modals

Modals in the system work slightly differently between desktop and mobile:

- On desktop, the modal is shown as a free floating panel centered in the browser, both horizontally and vertically; it appears instantaneously and disappears instantaneously. The background of the page has a dimming layer that intercepts all clicks, except for the hamburger menu that's on top of the dimming layer. It can be closed by clicking a small x in the top right of the modal, or clicking anywhere in the dimmed area outside the modal (except the hamburger menu).
- On mobile, it's a slide-in panel that slides in from the right to the left and covers the entire screen below the header. It also dims the background (of which the only visible part is the header), except for the hamburger menu that's on top of the dimming layer. It can be slid back out to the right by clicking a small ">" button in the top right of the panel, or clicking anywhere in the header (except the hamburger menu).

Unique session instance names: To visually indicate a session instance, there are two cases. If the session type is "regular", the label is "{Session Name} - {Date yyyy-mm-dd}" (like "B. D. Riley's Irish Pub - 2025-12-19"). If the session type is "festival" the label is "{Session Name} - {Date mm/dd} - {location_override}". If you're showing a list of instances WITHIN the context of a single session, you can leave out the session name and only show the latter part.

Right now, we have tune detail modals/panels in 4 places:

- the "my tunes" list (based on the person_tune talbe)
- the session_tune list (based on the session_tune table)
- the session instance tune log (based on the session_instance_tune table)
- the admin tune list (based on the tune table). 
They're all slightly different, visually, which is bad. They're also slightly different functionally, which is good (because they all have slightly different purposes and context). I'd like them to use the same actual jinja template and UX features, but with variable sections and configurations and different data sources in the different usess.

Here's how I want this modal to work:

- Ensure the appear / disappear actions are consistent as stated above, particularly with regard to the hamburger menu and dimming.
- The next section is the tune title, which should always look the same. Sometimes tune title wraps to a second line, which is fine. This shows:
    - My Tunes: person_tune.tune_alias if it exists, otherwise tune.name
    - Session & Session Instance Pages: session_tune.alias if it exists, otherwise tune.name
    - Clicking the tune title shows or hides the hidden configuration section (see below) on my tunes / session tune / session instance tune pages.
- To the right of the tune title is a link that goes to thesession.org. Ensure it always has the tune id and setting id (if there is one). CHANGE the icon to a blue hue.
- CHANGE: the tune type pill should always be to the left of the tune title. If the title is wrapped, the tune type is top-justified. There's no "type" or "tune type" label next to it, just the pill.
- CHANGE: The next section should be the "Configure" section (which is always shown on the admin page, but hidden by default on other pages until revealed) and contains:
    - The official tune name (tune.name) and tune_id (text labels)
    - An editable field for the tune name, which:
        - my_tunes: shows / edits person_tune.name_alias value, with label "I call this: "
        - Session & Session Instance Pages: shows / edits session_tune.alias with label "We call this: "
    - An editable field for the setting (not on admin page), which allows entering either a number or pasting a thesession.org tune URL which is instantly converted to just the setting_id if it's present:
        - my_tunes: shows / edits person_tune.setting_id value, label "My setting: "
        - Session Page: shows / edits session_tune.setting_id, label "Our setting: "
        - Session Instance Page: shows / edits session_instance_tune.setting_override, label "In this case, we played setting: "
    - Key: An editable droplist for key (not on admin page or my tunes page), with values in this list: [{empty}, Amajor, Aminor, Adorian, Amixolydian, Bminor, Cmajor, Dmajor, Dminor, Eminor, Fmajor, Gmajor, Dmixolydian, Bmixolydian, Edorian, Gdorian, Gminor, Ddorian, Cdorian, Fdorian, Gmixolydian, Emajor, Bdorian, Emixolydian]
      - Session Page: shows / edits the current value of the session_tune.key field, label "We play this in: "
      - Session Instance Page: shows / edits the current value of the session_instance_tune.key_override field, label "This time, we played this tune in: "
- The next (optional) section is about whether this tune is in the current user's tunebook. It doesn't appear on the tune Admin screen. It can be in 4 states:
    - Not in tunebook - red container (bright red border, dimmer red background), "This tune is not on your list.[button: Add]"
    - Want to learn - yellow container (bright yellow border, dimmer yellow background), "This tune is [droplist: on your list (selected) | in progress | learned]"
    - Learning - blue container (bright blue border, dimmer blue background), "This tune is on your list as [droplist: want to learn | in progress (selected) | learned]"
    - Learning - green container (bright green border, dimmer green background), "This tune is on your list as [droplist: want to learn | in progress  | learned (selected)]"
    - Selecting an item on the droplist updates the database (valid statuses corresponding to the three on-list states are "Want To Learn", "Learning" and "Learned") and refreshes the view with the new color / text
- Next (optional) section is the heard count, which doesn't appear on the admin tune view, and only appears on the other views if the tune is in "Want To Learn" or "Learning" status. It works just like on the "my tunes" list: label that says "You've heard this {N} time{s if N != 1}", with red minus and green plus button. 
- Next (optional) section is the notes box (only in the "my tunes" view). CHANGE: There should be no "Notes: " label, just the box with hint text if empty.
- Under that are action buttons: Cancel (closes the modal with no changes) and Save (disabled unless an editable field has been changed making the state dirty)
- Under the action buttons are more rare links:
    - My Tunes: Remove From My Tunes
    - My Tunes & Session & Session Instance: Configure This Tune (same result as clicking the title, toggles visibility of configuration section)
- At the botton, scrollable section extending to the bottom of the viewport with tabbed interface including:
    - Tab: "Stats"
        - Popularity On TheSession.org: {tunebook_count_cached}, followed by refresh button that updates that value, with "Last Updated {Date}" in small text underneath
        - My Tunes:
            - Times Played At My Sessions: {N} (where "my session" means any sessions I'm a member of)
            - Times Played Globally: {N}
        - Session / Session Instance
            - Times Played At This Session: {N}
            - Times Played Globally: {N}
        - Admin
            - Times Played Globally: {N}
            - Number Of Sessions Playing This Tune: {N} (distinct count of sessions where this tune is in the session_tune table)
    - Tab: "History"
        - My tunes - Plays at sessions I've been at: grid showing full unique session instance names with links (based on session_instance_id) to the session_instance_detail log view highlighting / scrolling to that tune based on querystring parameter.
        - Session / Session Instance - grid showing contextual unique session instance names (leave out the session name) with links (based on session_instance_id) to the session_instance_detail log view highlighting / scrolling to that tune based on querystring parameter. 
        - Admin - Plays at all sessions showing fully unique session instance names with links (based on session_instance_id) to the session_instance_detail log view highlighting / scrolling to that tune based on querystring parameter.
        - All views have the 3-row display of "Unique name / link" on the first row, Position in set on 2nd row, and setting id on third row.
