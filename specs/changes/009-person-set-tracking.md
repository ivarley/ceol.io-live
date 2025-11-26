# 009 Person Set Tracking

We now need to create a place to store the "who started the set". That'll be a new column on session_instance_tune (we don't have an explicit table for "sets", they're just described by which tunes have "continues_set" set to false versus true). Name the column "started_by_person_id". When the user selects a value on the droplist, update all the tunes in the set with the appropriate person_id value.

When showing this popup, it should show a person as selected if any of the tunes list that person_id as the started-by value. If the tunes in the set have different values for who they were started by, show the one that's a majority, or the first one if there's no clear majority.

Also, when saving the tune set, if *any* of the tunes in a set have a "started_by_person_id" value, it should be set for any tunes in the set that do not have a started_by_person_id value (using the same majority logic as above). It doesn't replace cases where different values are already set (because we maybe also allow for cases where people want to set these values different for different tunes in a set in the future).
