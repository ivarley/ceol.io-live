# 010 User Action Logging

We have audit columns for timestamps on the database schema, but we don't currently have any information about which user created or edited a record. I'd like to add that.

All tables should currently have these two columns:

    created_date TIMESTAMPTZ,
    last_modified_date TIMESTAMPTZ

That's also in all the history tables. The history tables additional have:

    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(255),
    changed_at TIMESTAMPTZ DEFAULT (NOW() AT TIME ZONE 'UTC'),

However, the "changed_by" value always says "system" (if it's populated at all). 

Add a new pair of columns to every table as follows:

    created_by_user_id INTEGER
    last_modified_user_id INTEGER

Also add these to the audit tables (and remove the "changed_by" column). Update all DML statements in the entire system to pass the current user_id in along with any change and put it in the created_by_user_id or last_modified_by_user_id column as appropriate (and modify the history triggers to also preserve this new information).
