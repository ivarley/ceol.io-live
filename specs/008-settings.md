# 008 Settings

We're going to add the ability to cache additional information (like abc notation and generated sheet music images) about "settings", which are specific variations of tunes. Like tunes, the source of truth for settings is on TheSession.org; settings are in a many-to-one relationship with tunes (one tune can have many settings). Setting ID is globally unique. Not all tunes in our system will have settings, so any time it’s joined to tunes, it must be an outer join.

Settings can be retrieved from TheSession.org via the same API as tune information. For example, within the response to https://thesession.org/tunes/1?format=json, you'll find this information:

```
    "settings": [
        {
            "id": 1,
            "url": "https://thesession.org/tunes/1#setting1",
            "key": "Edorian",
            "abc": "|:D2|EBBA B2 EB|B2 AB dBAG|FDAD BDAD|FDAD dAFD|! EBBA B2 EB|B2 AB defg|afec dBAF|DEFD E2:|! |:gf|eB B2 efge|eB B2 gedB|A2 FA DAFA|A2 FA defg|! eB B2 eBgB|eB B2 defg|afec dBAF|DEFD E2:|",
            "member": {
                "id": 1,
                "name": "Jeremy",
                "url": "https://thesession.org/members/1"
            },
            "date": "2001-05-14 18:45:18"
        },
        {
            "id": 12342,
            "url": "https://thesession.org/tunes/1#setting12342",
            "key": "Eminor",
            "abc": "|:F|CGGC G2 CG|G2 FG BGFE|(3DCB, FB, GB,FB,|DB,DF BFDB,|! CGGC G2 CG|G2 FG Bcde|fdcd BGFB|B,CDF C3:|! |:d|cG ~G2 cede|cG ~G2 ecBG|(3FGF DF B,FDF|GFDF Bcde|! cG ~G2 cede|cG ~G2 Bcde|fdcd BGFB|B,CDF C3:|",
            "member": {
                "id": 2673,
                "name": "donnchad",
                "url": "https://thesession.org/members/2673"
            },
            "date": "2002-06-11 15:43:50"
        },
```

The only information we're interested in here is the setting's id, abc, and key.

Create a new table called tune_setting, with the usual audit fields and history table. Columns:

- setting_id (primary key, based on the external ID from thesession.org)
- tune_id (foreign key to tune)
- key
- abc
- image
- incipit_abc
- incipit_image
- cache_updated_date

Write a reusable API-callable function in our system that populates (or updates) this table for a given tune_id and setting_id. Also include a version that can take just a tune_id and fetch the first setting in the list of settings (this is for cases where the user of our system hasn't specified a setting). When called, this method calls thesession.org and populate the tune_setting table with the setting_id, tune_id, key, abc, and cache_updated_date.

On the tune details panel (in all four places where it's used), attempt to show the value of "abc" for this tune right below the tune name header (above the hidden configuration section, not above it). Show the setting as follows:

- If there's a specific setting_id in the database for this situation, attempt to show that setting if it exists:
  - For my-tunes in the person_tune table, that would be in person_tune.setting_id
  - For session_details tunes in the session_tune table, that would be session_tune.setting_id
  - For session_instance_details tunes in the session_instance_tune table, that would be session_instance_tune.setting_override
  - For admin/tunes/{tune_id}, it would be the first setting that exists, ordered by setting_id asc

In all these cases, you're looking for a row in the tune_setting table corresponding to this setting id. Only show that setting, don't show any other tune settings for the tune.

When showing the abc notation, show it in fixed width font, replacing the "!" character with a newline.

Add a button on the tune details panel just to the right of the text input box for the setting id which calls this API, using the setting ID if present. After the API returns and the database row has been inserted, re-render the modal with the ABC notation present.