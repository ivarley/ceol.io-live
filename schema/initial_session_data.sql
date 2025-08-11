-- Initial session data - fill in the values manually
INSERT INTO session (
    thesession_id,
    name,
    path,
    location_name,
    location_website,
    location_phone,
    city,
    state,
    country,
    comments,
    unlisted_address,
    initiation_date,
    termination_date,
    recurrence
) VALUES (
    6247, -- thesession_id
    'B.D.Riley''s Irish Pub', -- name
    'austin/mueller', -- path
    'B.D.Riley''s Irish Pub', -- location_name
    'https://www.facebook.com/bdrileyssession/', -- location_website
    '(512) 580-3782', -- location_phone
    'Austin', -- city
    'Texas', -- state
    'USA', -- country
    'Weekly Thursday session, open to all levels.', -- comments
    FALSE, -- unlisted_address
    '4/20/2017', -- initiation_date
    NULL, -- termination_date
    'Thursdays from 7-10:30pm' -- recurrence
);

INSERT INTO session (
    thesession_id,
    name,
    path,
    location_name,
    location_website,
    location_phone,
    city,
    state,
    country,
    comments,
    unlisted_address,
    initiation_date,
    termination_date,
    recurrence
) VALUES (
    7219, -- thesession_id
    'Lockhart Arts And Craft', -- name
    'lockhart/artsandcraft', -- path
    'Lockhart Arts And Craft', -- location_name
    'https://www.ltxac.com/', -- location_website
    '(512) 560-5273', -- location_phone
    'Lockhart', -- city
    'Texas', -- state
    'USA', -- country
    '', -- comments
    FALSE, -- unlisted_address
    '10/3/2021', -- initiation_date
    '3/1/2025', -- termination_date
    'bi-weekly on Sundays from 4-8pm' -- recurrence
);


INSERT INTO session (
    thesession_id,
    name,
    path,
    location_name,
    location_website,
    location_phone,
    city,
    state,
    country,
    comments,
    unlisted_address,
    initiation_date,
    termination_date,
    recurrence
) VALUES (
    7219, -- thesession_id
    'O''Donnell''s', -- name
    'lockhart/odonnells', -- path
    'O''Donnell''s Irish Pub', -- location_name
    'https://odonnellstexas.com/', -- location_website
    '(512) 668-4166', -- location_phone
    'Lockhart', -- city
    'Texas', -- state
    'USA', -- country
    '', -- comments
    FALSE, -- unlisted_address
    '3/25/2025', -- initiation_date
    NULL, -- termination_date
    'monthly on Sundays from 4-8pm' -- recurrence
);