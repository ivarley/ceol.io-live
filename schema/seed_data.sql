-- =============================================================================
-- ceol.io Seed Data for Local Development
-- =============================================================================
-- This file populates the database with realistic test data.
-- Run this after full_schema.sql to get a working local development database.
--
-- Usage:
--   psql -h localhost -U test_user -d ceol_test -f schema/seed_data.sql
--
-- Includes:
--   - 150 tunes (real tune IDs and names from TheSession.org)
--   - 5 sessions in different cities
--   - 20 people (musicians)
--   - 5 user accounts (including 1 admin)
--   - Session instances over the past 3 months
--   - Tune logs for most session instances
--   - Attendance records
-- =============================================================================

-- Note: Triggers remain active during seed data load

-- =============================================================================
-- TUNES (150 real tunes from TheSession.org)
-- =============================================================================

INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date) VALUES
-- Popular reels
(27, 'Drowsy Maggie', 'Reel', 1800, '2024-01-15'),
(55, 'Kesh, The', 'Jig', 1800, '2024-01-15'),
(1307, 'Lucy Farr''s', 'Barndance', 1800, '2024-01-15'),
(6, 'This Is My Love, Do You Like Her?', 'Jig', 1800, '2024-01-15'),
(74, 'Mason''s Apron, The', 'Reel', 1750, '2024-01-15'),
(108, 'Out On The Ocean', 'Jig', 1750, '2024-01-15'),
(4195, 'Bear Dance, The', 'Polka', 1600, '2024-01-15'),
(19, 'Connaughtman''s Rambles, The', 'Jig', 1600, '2024-01-15'),
(75, 'Miss McLeod''s', 'Reel', 1600, '2024-01-15'),
(248, 'Tam Lin', 'Reel', 1600, '2024-01-15'),
(775, 'Banks Of Lough Gowna, The', 'Jig', 1550, '2024-01-15'),
(15, 'Calliope House', 'Jig', 1550, '2024-01-15'),
(138, 'Toss The Feathers', 'Reel', 1550, '2024-01-15'),
(208, 'Congress, The', 'Reel', 1500, '2024-01-15'),
(116, 'Wind That Shakes The Barley, The', 'Reel', 1500, '2024-01-15'),
(21, 'Castle Kelly', 'Reel', 1450, '2024-01-15'),
(12, 'Cliffs Of Moher, The', 'Jig', 1450, '2024-01-15'),
(197, 'Star Of Munster, The', 'Reel', 1450, '2024-01-15'),
(537, 'Creel Of Turf, The', 'Jig', 1400, '2024-01-15'),
(62, 'Lark In The Morning, The', 'Jig', 1400, '2024-01-15'),
(103, 'Saint Anne''s', 'Reel', 1400, '2024-01-15'),
(105, 'Swallow''s Tail, The', 'Reel', 1400, '2024-01-15'),
(273, 'Castle, The', 'Jig', 1350, '2024-01-15'),
(373, 'Connie The Soldier', 'Jig', 1350, '2024-01-15'),
(1, 'Cooley''s', 'Reel', 1350, '2024-01-15'),
(418, 'Ievan Polkka', 'Polka', 1350, '2024-01-15'),
(517, 'Pigeon On The Gate, The', 'Reel', 1350, '2024-01-15'),
(86, 'Rakish Paddy', 'Reel', 1350, '2024-01-15'),
(87, 'Rolling In The Ryegrass', 'Reel', 1350, '2024-01-15'),
(88, 'Rolling Waves, The', 'Jig', 1350, '2024-01-15'),

-- More reels and jigs
(281, 'Master Crowley''s', 'Reel', 1300, '2024-01-15'),
(71, 'Morrison''s', 'Jig', 1300, '2024-01-15'),
(872, 'Fisher''s', 'Hornpipe', 1250, '2024-01-15'),
(34, 'Frieze Breeches, The', 'Jig', 1250, '2024-01-15'),
(92, 'Irish Washerwoman, The', 'Jig', 1250, '2024-01-15'),
(736, 'Jump At The Sun', 'Jig', 1250, '2024-01-15'),
(3842, 'Lisnagun, The', 'Jig', 1250, '2024-01-15'),
(222, 'Man Of The House, The', 'Reel', 1250, '2024-01-15'),
(73, 'Musical Priest, The', 'Reel', 1250, '2024-01-15'),
(2204, 'O''Sullivan''s March', 'Jig', 1250, '2024-01-15'),
(8, 'Banshee, The', 'Reel', 1200, '2024-01-15'),
(448, 'Frost Is All Over, The', 'Jig', 1200, '2024-01-15'),
(217, 'Orphan, The', 'Jig', 1200, '2024-01-15'),
(106, 'Swallowtail, The', 'Jig', 1200, '2024-01-15'),
(1148, 'Drag Her Round The Road', 'Reel', 1150, '2024-01-15'),
(33, 'Farewell To Ireland', 'Reel', 1150, '2024-01-15'),
(605, 'Greig''s Pipes', 'Reel', 1150, '2024-01-15'),
(803, 'I Ne''er Shall Wean Her', 'Jig', 1150, '2024-01-15'),
(6170, 'Ray''s Classic', 'Polka', 1150, '2024-01-15'),
(235, 'Seán Buí', 'Jig', 1150, '2024-01-15'),
(2320, 'Shoe The Donkey', 'Mazurka', 1150, '2024-01-15'),
(2828, 'Wren, The', 'March', 1150, '2024-01-15'),
(1076, 'Black Rogue, The', 'Jig', 1100, '2024-01-15'),
(5405, 'Chapel Bell, The', 'Jig', 1100, '2024-01-15'),
(1244, 'Condon''s Frolics', 'Jig', 1100, '2024-01-15'),
(1426, 'Dálaigh''s', 'Polka', 1100, '2024-01-15'),
(544, 'Garrett Barry''s', 'Jig', 1100, '2024-01-15'),
(559, 'Green Cottage, The', 'Polka', 1100, '2024-01-15'),
(228, 'Humours Of Ennistymon, The', 'Jig', 1100, '2024-01-15'),
(4883, 'Jenny Lind', 'Polka', 1100, '2024-01-15'),

-- Various other types
(793, 'Jimmy Ward''s', 'Jig', 1100, '2024-01-15'),
(68, 'Mountain Road, The', 'Reel', 1100, '2024-01-15'),
(79, 'Paddy Ryan''s Dream', 'Reel', 1100, '2024-01-15'),
(905, 'Princess Royal, The', 'Reel', 1100, '2024-01-15'),
(83, 'Rights Of Man, The', 'Hornpipe', 1100, '2024-01-15'),
(2, 'Bucks Of Oranmore, The', 'Reel', 1050, '2024-01-15'),
(10, 'Butterfly, The', 'Slip Jig', 1050, '2024-01-15'),
(29, 'Dusty Windowsills', 'Jig', 1050, '2024-01-15'),
(2549, 'Flowers Of Edinburgh, The', 'Reel', 1050, '2024-01-15'),
(482, 'Foxhunter, The', 'Slip Jig', 1050, '2024-01-15'),
(312, 'Good Natured Man, The', 'Hornpipe', 1050, '2024-01-15'),
(211, 'Inisheer', 'Waltz', 1050, '2024-01-15'),
(589, 'Julia Delaney''s', 'Reel', 1050, '2024-01-15'),
(948, 'Kitty Lie Over', 'Jig', 1050, '2024-01-15'),
(566, 'Little Beggarman, The', 'Hornpipe', 1050, '2024-01-15'),
(64, 'Maid Behind The Bar, The', 'Reel', 1050, '2024-01-15'),
(69, 'Morning Dew, The', 'Reel', 1050, '2024-01-15'),
(1615, 'Road To Glountane, The', 'Barndance', 1050, '2024-01-15'),
(2576, 'Sheep In The Boat, The', 'Jig', 1050, '2024-01-15'),
(711, 'Tap Room, The', 'Reel', 1050, '2024-01-15'),
(113, 'Toss The Feathers', 'Reel', 1050, '2024-01-15'),
(238, 'Ballydesmond, The', 'Polka', 1000, '2024-01-15'),
(1197, 'Boys On The Hilltop, The', 'Reel', 1000, '2024-01-15'),
(440, 'Christmas Eve', 'Reel', 1000, '2024-01-15'),
(514, 'Down The Broom', 'Reel', 1000, '2024-01-15'),
(634, 'Galway Rambler, The', 'Reel', 1000, '2024-01-15'),
(1936, 'Green Grow The Rushes', 'Barndance', 1000, '2024-01-15'),
(829, 'Hag At The Churn, The', 'Jig', 1000, '2024-01-15'),
(441, 'John Ryan''s', 'Polka', 1000, '2024-01-15'),
(52, 'Kid On The Mountain, The', 'Slip Jig', 1000, '2024-01-15'),
(475, 'King Of The Fairies', 'Hornpipe', 1000, '2024-01-15'),
(264, 'Lanigan''s Ball', 'Jig', 1000, '2024-01-15'),
(883, 'Laurel Tree, The', 'Reel', 1000, '2024-01-15'),
(432, 'Maids Of Mount Kisco, The', 'Reel', 1000, '2024-01-15'),
(1511, 'Meelick Team, The', 'Jig', 1000, '2024-01-15'),
(70, 'Merrily Kiss The Quaker', 'Slide', 1000, '2024-01-15'),
(72, 'Merry Blacksmith, The', 'Reel', 1000, '2024-01-15'),
(527, 'Moll Roe', 'Slip Jig', 1000, '2024-01-15'),
(67, 'Monaghan, The', 'Jig', 1000, '2024-01-15'),
(828, 'Morning Star, The', 'Reel', 1000, '2024-01-15'),

-- More tunes
(1091, 'Moving Cloud, The', 'Reel', 1000, '2024-01-15'),
(76, 'My Darling Asleep', 'Jig', 1000, '2024-01-15'),
(398, 'Pull The Knife And Stick It Again', 'Jig', 1000, '2024-01-15'),
(89, 'Rambling Pitchfork, The', 'Jig', 1000, '2024-01-15'),
(515, 'Rolling Waves, The', 'Jig', 1000, '2024-01-15'),
(399, 'Sligo Maid, The', 'Reel', 1000, '2024-01-15'),
(8895, 'Toureendarby', 'Polka', 1000, '2024-01-15'),
(112, 'Trip To Pakistan, The', 'Reel', 1000, '2024-01-15'),
(2192, 'Baltimore Salute, The', 'Reel', 950, '2024-01-15'),
(5252, 'Bó Mhín Na Toitean', 'March', 950, '2024-01-15'),
(703, 'Catharsis', 'Reel', 950, '2024-01-15'),
(1218, 'Cock O'' The North', 'Jig', 950, '2024-01-15'),
(1662, 'Contentment Is Wealth', 'Jig', 950, '2024-01-15'),
(647, 'Cutting Bracken', 'Strathspey', 950, '2024-01-15'),
(1649, 'Dornoch Links', 'March', 950, '2024-01-15'),
(160, 'Gallagher''s Frolics', 'Jig', 950, '2024-01-15'),
(5418, 'Girl I Left Behind Me, The', 'Polka', 950, '2024-01-15'),
(45, 'Humours Of Glendart, The', 'Jig', 950, '2024-01-15'),
(1357, 'Jenny Picking Cockles', 'Reel', 950, '2024-01-15'),
(667, 'Killavil, The', 'Jig', 950, '2024-01-15'),
(1843, 'Kitty''s Rambles', 'Jig', 950, '2024-01-15'),
(256, 'Mist Covered Mountain, The', 'Jig', 950, '2024-01-15'),
(1133, 'Off She Goes', 'Jig', 950, '2024-01-15'),
(636, 'Otter''s Holt, The', 'Reel', 950, '2024-01-15'),
(182, 'Silver Spear, The', 'Reel', 950, '2024-01-15'),
(430, 'Sporting Paddy', 'Reel', 950, '2024-01-15'),
(1251, 'Tolka, The', 'Polka', 950, '2024-01-15'),
(321, 'Woman Of The House, The', 'Reel', 950, '2024-01-15'),
(750, 'A Fig For A Kiss', 'Slip Jig', 900, '2024-01-15'),
(2772, 'Ballyhoura Mountains, The', 'Polka', 900, '2024-01-15'),
(9, 'Banish Misfortune', 'Jig', 900, '2024-01-15'),
(651, 'Boys Of Bluehill, The', 'Hornpipe', 900, '2024-01-15'),
(858, 'Captain O''Kane', 'Waltz', 900, '2024-01-15'),
(17, 'Coleraine, The', 'Jig', 900, '2024-01-15'),
(219, 'Fermoy Lasses, The', 'Reel', 900, '2024-01-15'),
(1214, 'Girl Of The House, The', 'Jig', 900, '2024-01-15'),
(1744, 'Gladstone, The', 'Reel', 900, '2024-01-15'),
(496, 'Glen Of Aherlow, The', 'Reel', 900, '2024-01-15'),
(974, 'Golden Eagle, The', 'Hornpipe', 900, '2024-01-15'),
(1376, 'If We Hadn''t Any Women In The World', 'Barndance', 900, '2024-01-15'),
(361, 'Kylebrack Rambler, The', 'Reel', 900, '2024-01-15'),
(3262, 'Lord Moira''s Welcome To Scotland', 'Strathspey', 900, '2024-01-15'),
(1316, 'Maggie''s Pancakes', 'Reel', 900, '2024-01-15'),
(302, 'Maudabawn Chapel', 'Reel', 900, '2024-01-15'),
(2706, 'New Mown Meadows, The', 'Reel', 900, '2024-01-15'),
(1709, 'New York, The', 'Jig', 900, '2024-01-15'),
(1892, 'Niel Gow''s Lament For His Second Wife', 'Jig', 900, '2024-01-15'),
(741, 'Paddy O''Rafferty', 'Jig', 900, '2024-01-15'),
(510, 'Rambler, The', 'Jig', 900, '2024-01-15'),
(5976, 'Ridée Six Temps', 'Three-Two', 900, '2024-01-15');

-- =============================================================================
-- SESSIONS
-- =============================================================================

INSERT INTO session (session_id, name, path, city, state, country, timezone, location_name, location_street, location_website, recurrence, comments, initiation_date) VALUES
(1, 'Mueller Session', 'austin/mueller', 'Austin', 'TX', 'USA', 'America/Chicago',
 'BD Riley''s Irish Pub', '2000 Manor Rd', 'https://bdrileys.com',
 '{"schedules": [{"type": "weekly", "weekday": "tuesday", "start_time": "19:00", "end_time": "22:00", "every_n_weeks": 1}]}',
 'Weekly Irish session, all levels welcome. Slow session from 7-8pm, faster tunes after.',
 '2015-03-15'),

(2, 'Downtown Session', 'austin/downtown', 'Austin', 'TX', 'USA', 'America/Chicago',
 'The Driskill Hotel Bar', '604 Brazos St', 'https://driskillhotel.com',
 '{"schedules": [{"type": "weekly", "weekday": "thursday", "start_time": "20:00", "end_time": "23:00", "every_n_weeks": 2}]}',
 'Intermediate to advanced session. Focus on Clare style tunes.',
 '2018-09-01'),

(3, 'Boston Celtic Session', 'boston/celtic', 'Boston', 'MA', 'USA', 'America/New_York',
 'The Burren', '247 Elm St', 'https://burren.com',
 '{"schedules": [{"type": "weekly", "weekday": "sunday", "start_time": "17:00", "end_time": "20:00", "every_n_weeks": 1}]}',
 'Sunday afternoon session. Great for families. All levels.',
 '2012-01-08'),

(4, 'Chicago Traditional', 'chicago/trad', 'Chicago', 'IL', 'USA', 'America/Chicago',
 'Chief O''Neill''s Pub', '3471 N Elston Ave', 'https://chiefoneillspub.com',
 '{"schedules": [{"type": "weekly", "weekday": "wednesday", "start_time": "19:30", "end_time": "22:30", "every_n_weeks": 1}]}',
 'Named after the famous Chicago police chief and tune collector.',
 '2010-06-15'),

(5, 'San Francisco Session', 'sf/sunset', 'San Francisco', 'CA', 'USA', 'America/Los_Angeles',
 'The Plough and Stars', '116 Clement St', 'https://theploughandstars.com',
 '{"schedules": [{"type": "weekly", "weekday": "monday", "start_time": "21:00", "end_time": "00:00", "every_n_weeks": 1}]}',
 'Late night session. Experienced players. Fast and furious!',
 '2008-11-20');

-- =============================================================================
-- PEOPLE
-- =============================================================================

INSERT INTO person (person_id, first_name, last_name, email, city, state, country) VALUES
(1, 'Ian', 'Varley', 'ian@ceol.io', 'Austin', 'TX', 'USA'),
(2, 'Sarah', 'O''Connor', 'sarah.oconnor@example.com', 'Austin', 'TX', 'USA'),
(3, 'Michael', 'Murphy', 'mmurphy@example.com', 'Austin', 'TX', 'USA'),
(4, 'Aoife', 'Kelly', 'aoife.kelly@example.com', 'Austin', 'TX', 'USA'),
(5, 'Patrick', 'Ryan', 'pryan@example.com', 'Austin', 'TX', 'USA'),
(6, 'Siobhan', 'Walsh', 'siobhan.w@example.com', 'Boston', 'MA', 'USA'),
(7, 'Brendan', 'Doyle', 'brendan.doyle@example.com', 'Boston', 'MA', 'USA'),
(8, 'Niamh', 'McCarthy', 'niamh.mc@example.com', 'Boston', 'MA', 'USA'),
(9, 'Sean', 'O''Brien', 'sobrien@example.com', 'Chicago', 'IL', 'USA'),
(10, 'Ciara', 'Sullivan', 'ciara.s@example.com', 'Chicago', 'IL', 'USA'),
(11, 'Declan', 'Fitzgerald', 'declan.f@example.com', 'Chicago', 'IL', 'USA'),
(12, 'Maeve', 'Brennan', 'maeve.brennan@example.com', 'San Francisco', 'CA', 'USA'),
(13, 'Cormac', 'Gallagher', 'cormac.g@example.com', 'San Francisco', 'CA', 'USA'),
(14, 'Orla', 'Quinn', 'orla.quinn@example.com', 'San Francisco', 'CA', 'USA'),
(15, 'Roisin', 'Kennedy', 'roisin.k@example.com', 'Austin', 'TX', 'USA'),
(16, 'Eamon', 'Hayes', 'eamon.hayes@example.com', 'Austin', 'TX', 'USA'),
(17, 'Grainne', 'Nolan', 'grainne.n@example.com', 'Boston', 'MA', 'USA'),
(18, 'Cathal', 'Power', 'cathal.p@example.com', 'Chicago', 'IL', 'USA'),
(19, 'Aisling', 'Burke', 'aisling.burke@example.com', 'Austin', 'TX', 'USA'),
(20, 'Liam', 'Casey', 'liam.casey@example.com', 'San Francisco', 'CA', 'USA');

-- =============================================================================
-- USER ACCOUNTS
-- Password for all accounts is 'password123'
-- Hash generated with bcrypt cost factor 12
-- =============================================================================

INSERT INTO user_account (user_id, person_id, username, user_email, hashed_password, timezone, is_active, is_system_admin, email_verified) VALUES
(1, 1, 'ian', 'ian@ceol.io', '$2b$12$/YvbW.M2JbUhytoG1so4be2RgUcFEHghuIWGeOGaSIx1Rt7zdl1im', 'America/Chicago', TRUE, TRUE, TRUE),
(2, 2, 'sarah_fiddle', 'sarah.oconnor@example.com', '$2b$12$/YvbW.M2JbUhytoG1so4be2RgUcFEHghuIWGeOGaSIx1Rt7zdl1im', 'America/Chicago', TRUE, FALSE, TRUE),
(3, 6, 'siobhan_flute', 'siobhan.w@example.com', '$2b$12$/YvbW.M2JbUhytoG1so4be2RgUcFEHghuIWGeOGaSIx1Rt7zdl1im', 'America/New_York', TRUE, FALSE, TRUE),
(4, 9, 'sean_banjo', 'sobrien@example.com', '$2b$12$/YvbW.M2JbUhytoG1so4be2RgUcFEHghuIWGeOGaSIx1Rt7zdl1im', 'America/Chicago', TRUE, FALSE, TRUE),
(5, 12, 'maeve_accordion', 'maeve.brennan@example.com', '$2b$12$/YvbW.M2JbUhytoG1so4be2RgUcFEHghuIWGeOGaSIx1Rt7zdl1im', 'America/Los_Angeles', TRUE, FALSE, FALSE);

-- =============================================================================
-- PERSON INSTRUMENTS
-- =============================================================================

INSERT INTO person_instrument (person_id, instrument) VALUES
(1, 'fiddle'), (1, 'mandolin'),
(2, 'fiddle'),
(3, 'tin whistle'), (3, 'flute'),
(4, 'concertina'),
(5, 'guitar'), (5, 'bouzouki'),
(6, 'flute'),
(7, 'uilleann pipes'),
(8, 'fiddle'),
(9, 'banjo'), (9, 'mandolin'),
(10, 'harp'),
(11, 'accordion'),
(12, 'accordion'), (12, 'melodeon'),
(13, 'fiddle'),
(14, 'concertina'),
(15, 'bodhrán'),
(16, 'tin whistle'),
(17, 'flute'),
(18, 'fiddle'),
(19, 'fiddle'),
(20, 'guitar');

-- =============================================================================
-- SESSION PERSONS (regulars and admins)
-- =============================================================================

INSERT INTO session_person (session_id, person_id, is_regular, is_admin) VALUES
-- Mueller Session regulars
(1, 1, TRUE, TRUE), (1, 2, TRUE, FALSE), (1, 3, TRUE, FALSE), (1, 4, TRUE, FALSE),
(1, 5, TRUE, FALSE), (1, 15, TRUE, FALSE), (1, 16, TRUE, FALSE), (1, 19, TRUE, FALSE),
-- Downtown Session
(2, 1, TRUE, TRUE), (2, 2, TRUE, FALSE), (2, 4, TRUE, FALSE),
-- Boston Celtic
(3, 6, TRUE, TRUE), (3, 7, TRUE, FALSE), (3, 8, TRUE, FALSE), (3, 17, TRUE, FALSE),
-- Chicago Traditional
(4, 9, TRUE, TRUE), (4, 10, TRUE, FALSE), (4, 11, TRUE, FALSE), (4, 18, TRUE, FALSE),
-- San Francisco
(5, 12, TRUE, TRUE), (5, 13, TRUE, FALSE), (5, 14, TRUE, FALSE), (5, 20, TRUE, FALSE);

-- =============================================================================
-- SESSION INSTANCES (past 3 months)
-- =============================================================================

-- Mueller Session (Tuesdays) - session_id 1
INSERT INTO session_instance (session_instance_id, session_id, date, start_time, end_time, comments) VALUES
(1, 1, '2024-09-03', '19:00', '22:00', 'Great turnout after Labor Day'),
(2, 1, '2024-09-10', '19:00', '22:00', NULL),
(3, 1, '2024-09-17', '19:00', '22:00', 'Visiting musician from Ireland!'),
(4, 1, '2024-09-24', '19:00', '22:00', NULL),
(5, 1, '2024-10-01', '19:00', '22:00', NULL),
(6, 1, '2024-10-08', '19:00', '22:00', NULL),
(7, 1, '2024-10-15', '19:00', '22:00', 'Played lots of polkas tonight'),
(8, 1, '2024-10-22', '19:00', '22:00', NULL),
(9, 1, '2024-10-29', '19:00', '22:00', 'Halloween costumes!'),
(10, 1, '2024-11-05', '19:00', '22:00', 'Election night session'),
(11, 1, '2024-11-12', '19:00', '22:00', NULL),
(12, 1, '2024-11-19', '19:00', '22:00', NULL);

-- Downtown Session (Thursdays, biweekly) - session_id 2
INSERT INTO session_instance (session_instance_id, session_id, date, start_time, end_time, comments) VALUES
(20, 2, '2024-09-05', '20:00', '23:00', NULL),
(21, 2, '2024-09-19', '20:00', '23:00', NULL),
(22, 2, '2024-10-03', '20:00', '23:00', NULL),
(23, 2, '2024-10-17', '20:00', '23:00', 'Clare set night'),
(24, 2, '2024-10-31', '20:00', '23:00', 'Halloween special'),
(25, 2, '2024-11-14', '20:00', '23:00', NULL);

-- Boston Celtic (Sundays) - session_id 3
INSERT INTO session_instance (session_instance_id, session_id, date, start_time, end_time, comments) VALUES
(30, 3, '2024-09-01', '17:00', '20:00', NULL),
(31, 3, '2024-09-08', '17:00', '20:00', NULL),
(32, 3, '2024-09-15', '17:00', '20:00', NULL),
(33, 3, '2024-09-22', '17:00', '20:00', 'Fall equinox session'),
(34, 3, '2024-09-29', '17:00', '20:00', NULL),
(35, 3, '2024-10-06', '17:00', '20:00', NULL),
(36, 3, '2024-10-13', '17:00', '20:00', NULL),
(37, 3, '2024-10-20', '17:00', '20:00', NULL),
(38, 3, '2024-10-27', '17:00', '20:00', NULL),
(39, 3, '2024-11-03', '17:00', '20:00', NULL),
(40, 3, '2024-11-10', '17:00', '20:00', NULL),
(41, 3, '2024-11-17', '17:00', '20:00', NULL);

-- Chicago Traditional (Wednesdays) - session_id 4
INSERT INTO session_instance (session_instance_id, session_id, date, start_time, end_time, comments) VALUES
(50, 4, '2024-09-04', '19:30', '22:30', NULL),
(51, 4, '2024-09-11', '19:30', '22:30', NULL),
(52, 4, '2024-09-18', '19:30', '22:30', NULL),
(53, 4, '2024-09-25', '19:30', '22:30', NULL),
(54, 4, '2024-10-02', '19:30', '22:30', NULL),
(55, 4, '2024-10-09', '19:30', '22:30', NULL),
(56, 4, '2024-10-16', '19:30', '22:30', NULL),
(57, 4, '2024-10-23', '19:30', '22:30', NULL),
(58, 4, '2024-10-30', '19:30', '22:30', NULL),
(59, 4, '2024-11-06', '19:30', '22:30', NULL),
(60, 4, '2024-11-13', '19:30', '22:30', NULL),
(61, 4, '2024-11-20', '19:30', '22:30', NULL);

-- San Francisco (Mondays) - session_id 5
INSERT INTO session_instance (session_instance_id, session_id, date, start_time, end_time, comments) VALUES
(70, 5, '2024-09-02', '21:00', '00:00', NULL),
(71, 5, '2024-09-09', '21:00', '00:00', NULL),
(72, 5, '2024-09-16', '21:00', '00:00', NULL),
(73, 5, '2024-09-23', '21:00', '00:00', NULL),
(74, 5, '2024-09-30', '21:00', '00:00', NULL),
(75, 5, '2024-10-07', '21:00', '00:00', NULL),
(76, 5, '2024-10-14', '21:00', '00:00', NULL),
(77, 5, '2024-10-21', '21:00', '00:00', NULL),
(78, 5, '2024-10-28', '21:00', '00:00', NULL),
(79, 5, '2024-11-04', '21:00', '00:00', NULL),
(80, 5, '2024-11-11', '21:00', '00:00', 'Veterans Day session'),
(81, 5, '2024-11-18', '21:00', '00:00', NULL);

-- =============================================================================
-- SESSION INSTANCE TUNES (tune logs for most sessions)
-- Using real TheSession.org tune_ids:
--   Reels: 27 (Drowsy Maggie), 1 (Cooley's), 74 (Mason's Apron), 138 (Toss the Feathers),
--          116 (Wind That Shakes), 64 (Maid Behind the Bar), 182 (Silver Spear),
--          8 (Banshee), 73 (Musical Priest), 21 (Castle Kelly), 2 (Bucks of Oranmore),
--          103 (Saint Anne's), 105 (Swallow's Tail), 86 (Rakish Paddy), 68 (Mountain Road)
--   Jigs: 55 (The Kesh), 71 (Morrison's), 108 (Out on the Ocean), 62 (Lark in the Morning),
--         106 (Swallowtail), 12 (Cliffs of Moher), 19 (Connaughtman's Rambles),
--         88 (Rolling Waves), 9 (Banish Misfortune), 15 (Calliope House)
--   Hornpipes: 872 (Fisher's), 83 (Rights of Man), 651 (Boys of Bluehill), 475 (King of Fairies)
--   Slip Jigs: 10 (Butterfly), 52 (Kid on the Mountain), 750 (Fig for a Kiss)
--   Polkas: 441 (John Ryan's), 238 (Ballydesmond), 4195 (Bear Dance)
--   Slides: 70 (Merrily Kiss the Quaker)
-- =============================================================================

-- Mueller Session tune logs (session instances 1-12)
INSERT INTO session_instance_tune (session_instance_id, tune_id, order_number, continues_set, started_by_person_id) VALUES
-- Instance 1: Reels, jigs, polkas
(1, 27, 1, FALSE, 2), (1, 1, 2, TRUE, NULL), (1, 74, 3, TRUE, NULL),
(1, 55, 4, FALSE, 3), (1, 71, 5, TRUE, NULL), (1, 108, 6, TRUE, NULL),
(1, 116, 7, FALSE, 1), (1, 138, 8, TRUE, NULL),
(1, 441, 9, FALSE, 4), (1, 238, 10, TRUE, NULL), (1, 4195, 11, TRUE, NULL),
(1, 10, 12, FALSE, 2), (1, 52, 13, TRUE, NULL),
(1, 83, 14, FALSE, 1), (1, 872, 15, TRUE, NULL),
-- Instance 2
(2, 8, 1, FALSE, 1), (2, 2, 2, TRUE, NULL), (2, 64, 3, TRUE, NULL),
(2, 12, 4, FALSE, 2), (2, 19, 5, TRUE, NULL),
(2, 103, 6, FALSE, 3), (2, 105, 7, TRUE, NULL), (2, 86, 8, TRUE, NULL),
(2, 651, 9, FALSE, 4), (2, 475, 10, TRUE, NULL),
(2, 70, 11, FALSE, 1), (2, 70, 12, TRUE, NULL),
-- Instance 3
(3, 182, 1, FALSE, 2), (3, 21, 2, TRUE, NULL), (3, 73, 3, TRUE, NULL),
(3, 62, 4, FALSE, 3), (3, 106, 5, TRUE, NULL), (3, 88, 6, TRUE, NULL),
(3, 68, 7, FALSE, 1), (3, 75, 8, TRUE, NULL),
(3, 750, 9, FALSE, 4), (3, 527, 10, TRUE, NULL),
(3, 559, 11, FALSE, 2), (3, 1426, 12, TRUE, NULL), (3, 418, 13, TRUE, NULL),
-- Instance 4
(4, 248, 1, FALSE, 1), (4, 197, 2, TRUE, NULL), (4, 208, 3, TRUE, NULL),
(4, 9, 4, FALSE, 2), (4, 15, 5, TRUE, NULL),
(4, 87, 6, FALSE, 3), (4, 281, 7, TRUE, NULL), (4, 222, 8, TRUE, NULL),
(4, 312, 9, FALSE, 4), (4, 566, 10, TRUE, NULL),
(4, 482, 11, FALSE, 1), (4, 527, 12, TRUE, NULL),
-- Instance 5
(5, 517, 1, FALSE, 2), (5, 1148, 2, TRUE, NULL), (5, 33, 3, TRUE, NULL),
(5, 537, 4, FALSE, 3), (5, 273, 5, TRUE, NULL), (5, 373, 6, TRUE, NULL),
(5, 605, 7, FALSE, 1), (5, 589, 8, TRUE, NULL),
(5, 905, 9, FALSE, 4), (5, 79, 10, TRUE, NULL),
(5, 6170, 11, FALSE, 2), (5, 4883, 12, TRUE, NULL),
-- Instance 6
(6, 803, 1, FALSE, 1), (6, 217, 2, TRUE, NULL), (6, 448, 3, TRUE, NULL),
(6, 736, 4, FALSE, 2), (6, 3842, 5, TRUE, NULL),
(6, 235, 6, FALSE, 3), (6, 228, 7, TRUE, NULL), (6, 793, 8, TRUE, NULL),
(6, 1076, 9, FALSE, 4), (6, 5405, 10, TRUE, NULL),
(6, 1244, 11, FALSE, 1), (6, 544, 12, TRUE, NULL),
-- Instance 7 (polka night)
(7, 441, 1, FALSE, 4), (7, 238, 2, TRUE, NULL), (7, 4195, 3, TRUE, NULL),
(7, 559, 4, FALSE, 2), (7, 1426, 5, TRUE, NULL), (7, 418, 6, TRUE, NULL),
(7, 6170, 7, FALSE, 1), (7, 4883, 8, TRUE, NULL), (7, 8895, 9, TRUE, NULL),
(7, 2772, 10, FALSE, 3), (7, 1251, 11, TRUE, NULL),
(7, 27, 12, FALSE, 2), (7, 138, 13, TRUE, NULL),
-- Instance 8
(8, 1197, 1, FALSE, 1), (8, 440, 2, TRUE, NULL), (8, 514, 3, TRUE, NULL),
(8, 829, 4, FALSE, 2), (8, 264, 5, TRUE, NULL), (8, 1511, 6, TRUE, NULL),
(8, 634, 7, FALSE, 3), (8, 883, 8, TRUE, NULL),
(8, 974, 9, FALSE, 4), (8, 312, 10, TRUE, NULL),
(8, 52, 11, FALSE, 1), (8, 750, 12, TRUE, NULL),
-- Instance 9
(9, 27, 1, FALSE, 2), (9, 8, 2, TRUE, NULL), (9, 1, 3, TRUE, NULL),
(9, 67, 4, FALSE, 3), (9, 76, 5, TRUE, NULL), (9, 89, 6, TRUE, NULL),
(9, 72, 7, FALSE, 1), (9, 828, 8, TRUE, NULL),
(9, 647, 9, FALSE, 4), (9, 3262, 10, TRUE, NULL),
(9, 70, 11, FALSE, 2), (9, 70, 12, TRUE, NULL),
-- Instance 10
(10, 321, 1, FALSE, 1), (10, 1091, 2, TRUE, NULL), (10, 399, 3, TRUE, NULL),
(10, 398, 4, FALSE, 2), (10, 515, 5, TRUE, NULL),
(10, 112, 6, FALSE, 3), (10, 2192, 7, TRUE, NULL), (10, 703, 8, TRUE, NULL),
(10, 160, 9, FALSE, 4), (10, 45, 10, TRUE, NULL),
(10, 1357, 11, FALSE, 1), (10, 667, 12, TRUE, NULL),
-- Instance 11
(11, 1843, 1, FALSE, 2), (11, 256, 2, TRUE, NULL), (11, 1133, 3, TRUE, NULL),
(11, 636, 4, FALSE, 3), (11, 182, 5, TRUE, NULL), (11, 430, 6, TRUE, NULL),
(11, 116, 7, FALSE, 1), (11, 74, 8, TRUE, NULL),
(11, 858, 9, FALSE, 4), (11, 211, 10, TRUE, NULL),
(11, 9, 11, FALSE, 2), (11, 219, 12, TRUE, NULL),
-- Instance 12
(12, 1214, 1, FALSE, 1), (12, 1744, 2, TRUE, NULL), (12, 496, 3, TRUE, NULL),
(12, 361, 4, FALSE, 2), (12, 1316, 5, TRUE, NULL),
(12, 302, 6, FALSE, 3), (12, 2706, 7, TRUE, NULL), (12, 1709, 8, TRUE, NULL),
(12, 1892, 9, FALSE, 4), (12, 741, 10, TRUE, NULL),
(12, 510, 11, FALSE, 1), (12, 5976, 12, TRUE, NULL);

-- Downtown Session tune logs (session instances 20-25)
INSERT INTO session_instance_tune (session_instance_id, tune_id, order_number, continues_set, started_by_person_id) VALUES
-- Instance 20
(20, 27, 1, FALSE, 1), (20, 1, 2, TRUE, NULL), (20, 74, 3, TRUE, NULL),
(20, 55, 4, FALSE, 2), (20, 12, 5, TRUE, NULL),
(20, 83, 6, FALSE, 4), (20, 872, 7, TRUE, NULL),
-- Instance 21
(21, 8, 1, FALSE, 2), (21, 2, 2, TRUE, NULL), (21, 64, 3, TRUE, NULL),
(21, 108, 4, FALSE, 1), (21, 19, 5, TRUE, NULL), (21, 62, 6, TRUE, NULL),
(21, 10, 7, FALSE, 4), (21, 52, 8, TRUE, NULL),
-- Instance 22
(22, 182, 1, FALSE, 1), (22, 21, 2, TRUE, NULL), (22, 73, 3, TRUE, NULL),
(22, 9, 4, FALSE, 2), (22, 15, 5, TRUE, NULL),
(22, 651, 6, FALSE, 4), (22, 475, 7, TRUE, NULL),
-- Instance 23 (Clare set night)
(23, 248, 1, FALSE, 2), (23, 103, 2, TRUE, NULL), (23, 105, 3, TRUE, NULL),
(23, 537, 4, FALSE, 1), (23, 273, 5, TRUE, NULL), (23, 373, 6, TRUE, NULL),
(23, 312, 7, FALSE, 4), (23, 566, 8, TRUE, NULL),
-- Instance 24
(24, 68, 1, FALSE, 1), (24, 75, 2, TRUE, NULL), (24, 116, 3, TRUE, NULL),
(24, 736, 4, FALSE, 2), (24, 3842, 5, TRUE, NULL),
(24, 750, 6, FALSE, 4), (24, 527, 7, TRUE, NULL),
-- Instance 25
(25, 74, 1, FALSE, 2), (25, 197, 2, TRUE, NULL), (25, 208, 3, TRUE, NULL),
(25, 829, 4, FALSE, 1), (25, 264, 5, TRUE, NULL), (25, 1511, 6, TRUE, NULL),
(25, 905, 7, FALSE, 4), (25, 79, 8, TRUE, NULL);

-- Boston Celtic tune logs (session instances 30-41)
INSERT INTO session_instance_tune (session_instance_id, tune_id, order_number, continues_set, started_by_person_id) VALUES
-- Instance 30
(30, 27, 1, FALSE, 6), (30, 8, 2, TRUE, NULL), (30, 1, 3, TRUE, NULL),
(30, 55, 4, FALSE, 7), (30, 71, 5, TRUE, NULL),
(30, 83, 6, FALSE, 8), (30, 872, 7, TRUE, NULL),
-- Instance 31
(31, 2, 1, FALSE, 7), (31, 182, 2, TRUE, NULL), (31, 21, 3, TRUE, NULL),
(31, 12, 4, FALSE, 6), (31, 108, 5, TRUE, NULL), (31, 19, 6, TRUE, NULL),
(31, 10, 7, FALSE, 8), (31, 52, 8, TRUE, NULL),
-- Instance 32
(32, 74, 1, FALSE, 6), (32, 64, 2, TRUE, NULL), (32, 73, 3, TRUE, NULL),
(32, 62, 4, FALSE, 7), (32, 106, 5, TRUE, NULL),
(32, 441, 6, FALSE, 8), (32, 238, 7, TRUE, NULL), (32, 4195, 8, TRUE, NULL),
-- Instance 33
(33, 248, 1, FALSE, 7), (33, 103, 2, TRUE, NULL), (33, 105, 3, TRUE, NULL),
(33, 9, 4, FALSE, 6), (33, 15, 5, TRUE, NULL), (33, 537, 6, TRUE, NULL),
(33, 651, 7, FALSE, 8), (33, 475, 8, TRUE, NULL),
-- Instance 34
(34, 68, 1, FALSE, 6), (34, 75, 2, TRUE, NULL), (34, 116, 3, TRUE, NULL),
(34, 273, 4, FALSE, 7), (34, 373, 5, TRUE, NULL),
(34, 750, 6, FALSE, 8), (34, 527, 7, TRUE, NULL),
-- Instance 35
(35, 74, 1, FALSE, 7), (35, 197, 2, TRUE, NULL), (35, 208, 3, TRUE, NULL),
(35, 736, 4, FALSE, 6), (35, 3842, 5, TRUE, NULL), (35, 829, 6, TRUE, NULL),
(35, 70, 7, FALSE, 8), (35, 70, 8, TRUE, NULL),
-- Instance 36
(36, 138, 1, FALSE, 6), (36, 87, 2, TRUE, NULL), (36, 281, 3, TRUE, NULL),
(36, 264, 4, FALSE, 7), (36, 1511, 5, TRUE, NULL),
(36, 312, 6, FALSE, 8), (36, 566, 7, TRUE, NULL),
-- Instance 37
(37, 222, 1, FALSE, 7), (37, 517, 2, TRUE, NULL), (37, 1148, 3, TRUE, NULL),
(37, 67, 4, FALSE, 6), (37, 76, 5, TRUE, NULL), (37, 89, 6, TRUE, NULL),
(37, 482, 7, FALSE, 8), (37, 527, 8, TRUE, NULL),
-- Instance 38
(38, 33, 1, FALSE, 6), (38, 605, 2, TRUE, NULL), (38, 589, 3, TRUE, NULL),
(38, 398, 4, FALSE, 7), (38, 515, 5, TRUE, NULL),
(38, 559, 6, FALSE, 8), (38, 1426, 7, TRUE, NULL), (38, 418, 8, TRUE, NULL),
-- Instance 39
(39, 803, 1, FALSE, 7), (39, 217, 2, TRUE, NULL), (39, 448, 3, TRUE, NULL),
(39, 1076, 4, FALSE, 6), (39, 5405, 5, TRUE, NULL), (39, 1244, 6, TRUE, NULL),
(39, 905, 7, FALSE, 8), (39, 79, 8, TRUE, NULL),
-- Instance 40
(40, 235, 1, FALSE, 6), (40, 228, 2, TRUE, NULL), (40, 793, 3, TRUE, NULL),
(40, 361, 4, FALSE, 7), (40, 1316, 5, TRUE, NULL),
(40, 52, 6, FALSE, 8), (40, 750, 7, TRUE, NULL),
-- Instance 41
(41, 27, 1, FALSE, 7), (41, 138, 2, TRUE, NULL), (41, 1197, 3, TRUE, NULL),
(41, 264, 4, FALSE, 6), (41, 829, 5, TRUE, NULL), (41, 67, 6, TRUE, NULL),
(41, 6170, 7, FALSE, 8), (41, 4883, 8, TRUE, NULL);

-- Chicago Traditional tune logs (session instances 50-61)
INSERT INTO session_instance_tune (session_instance_id, tune_id, order_number, continues_set, started_by_person_id) VALUES
-- Instance 50
(50, 27, 1, FALSE, 9), (50, 8, 2, TRUE, NULL), (50, 1, 3, TRUE, NULL),
(50, 55, 4, FALSE, 10), (50, 71, 5, TRUE, NULL),
(50, 83, 6, FALSE, 11), (50, 872, 7, TRUE, NULL),
-- Instance 51
(51, 2, 1, FALSE, 10), (51, 182, 2, TRUE, NULL), (51, 21, 3, TRUE, NULL),
(51, 12, 4, FALSE, 9), (51, 108, 5, TRUE, NULL), (51, 19, 6, TRUE, NULL),
(51, 647, 7, FALSE, 11), (51, 3262, 8, TRUE, NULL),
-- Instance 52
(52, 74, 1, FALSE, 9), (52, 64, 2, TRUE, NULL), (52, 73, 3, TRUE, NULL),
(52, 62, 4, FALSE, 10), (52, 106, 5, TRUE, NULL),
(52, 10, 6, FALSE, 11), (52, 52, 7, TRUE, NULL),
-- Instance 53
(53, 248, 1, FALSE, 10), (53, 103, 2, TRUE, NULL), (53, 105, 3, TRUE, NULL),
(53, 9, 4, FALSE, 9), (53, 15, 5, TRUE, NULL), (53, 537, 6, TRUE, NULL),
(53, 651, 7, FALSE, 11), (53, 475, 8, TRUE, NULL),
-- Instance 54
(54, 68, 1, FALSE, 9), (54, 75, 2, TRUE, NULL), (54, 116, 3, TRUE, NULL),
(54, 273, 4, FALSE, 10), (54, 373, 5, TRUE, NULL),
(54, 441, 6, FALSE, 11), (54, 238, 7, TRUE, NULL), (54, 4195, 8, TRUE, NULL),
-- Instance 55
(55, 74, 1, FALSE, 10), (55, 197, 2, TRUE, NULL), (55, 208, 3, TRUE, NULL),
(55, 736, 4, FALSE, 9), (55, 3842, 5, TRUE, NULL), (55, 829, 6, TRUE, NULL),
(55, 312, 7, FALSE, 11), (55, 566, 8, TRUE, NULL),
-- Instance 56
(56, 138, 1, FALSE, 9), (56, 87, 2, TRUE, NULL), (56, 281, 3, TRUE, NULL),
(56, 264, 4, FALSE, 10), (56, 1511, 5, TRUE, NULL),
(56, 750, 6, FALSE, 11), (56, 527, 7, TRUE, NULL),
-- Instance 57
(57, 222, 1, FALSE, 10), (57, 517, 2, TRUE, NULL), (57, 1148, 3, TRUE, NULL),
(57, 67, 4, FALSE, 9), (57, 76, 5, TRUE, NULL), (57, 89, 6, TRUE, NULL),
(57, 70, 7, FALSE, 11), (57, 70, 8, TRUE, NULL),
-- Instance 58
(58, 33, 1, FALSE, 9), (58, 605, 2, TRUE, NULL), (58, 589, 3, TRUE, NULL),
(58, 398, 4, FALSE, 10), (58, 515, 5, TRUE, NULL),
(58, 905, 6, FALSE, 11), (58, 79, 7, TRUE, NULL),
-- Instance 59
(59, 803, 1, FALSE, 10), (59, 217, 2, TRUE, NULL), (59, 448, 3, TRUE, NULL),
(59, 1076, 4, FALSE, 9), (59, 5405, 5, TRUE, NULL), (59, 1244, 6, TRUE, NULL),
(59, 482, 7, FALSE, 11), (59, 527, 8, TRUE, NULL),
-- Instance 60
(60, 235, 1, FALSE, 9), (60, 228, 2, TRUE, NULL), (60, 793, 3, TRUE, NULL),
(60, 361, 4, FALSE, 10), (60, 1316, 5, TRUE, NULL),
(60, 559, 6, FALSE, 11), (60, 1426, 7, TRUE, NULL), (60, 418, 8, TRUE, NULL),
-- Instance 61
(61, 27, 1, FALSE, 10), (61, 138, 2, TRUE, NULL), (61, 1197, 3, TRUE, NULL),
(61, 264, 4, FALSE, 9), (61, 829, 5, TRUE, NULL), (61, 67, 6, TRUE, NULL),
(61, 858, 7, FALSE, 11), (61, 211, 8, TRUE, NULL);

-- San Francisco tune logs (session instances 70-81)
INSERT INTO session_instance_tune (session_instance_id, tune_id, order_number, continues_set, started_by_person_id) VALUES
-- Instance 70
(70, 27, 1, FALSE, 12), (70, 8, 2, TRUE, NULL), (70, 1, 3, TRUE, NULL),
(70, 55, 4, FALSE, 13), (70, 71, 5, TRUE, NULL),
(70, 83, 6, FALSE, 14), (70, 872, 7, TRUE, NULL),
-- Instance 71
(71, 2, 1, FALSE, 13), (71, 182, 2, TRUE, NULL), (71, 21, 3, TRUE, NULL),
(71, 12, 4, FALSE, 12), (71, 108, 5, TRUE, NULL), (71, 19, 6, TRUE, NULL),
(71, 10, 7, FALSE, 14), (71, 52, 8, TRUE, NULL),
-- Instance 72
(72, 74, 1, FALSE, 12), (72, 64, 2, TRUE, NULL), (72, 73, 3, TRUE, NULL),
(72, 62, 4, FALSE, 13), (72, 106, 5, TRUE, NULL),
(72, 441, 6, FALSE, 14), (72, 238, 7, TRUE, NULL), (72, 4195, 8, TRUE, NULL),
-- Instance 73
(73, 248, 1, FALSE, 13), (73, 103, 2, TRUE, NULL), (73, 105, 3, TRUE, NULL),
(73, 9, 4, FALSE, 12), (73, 15, 5, TRUE, NULL), (73, 537, 6, TRUE, NULL),
(73, 651, 7, FALSE, 14), (73, 475, 8, TRUE, NULL),
-- Instance 74
(74, 68, 1, FALSE, 12), (74, 75, 2, TRUE, NULL), (74, 116, 3, TRUE, NULL),
(74, 273, 4, FALSE, 13), (74, 373, 5, TRUE, NULL),
(74, 750, 6, FALSE, 14), (74, 527, 7, TRUE, NULL),
-- Instance 75
(75, 74, 1, FALSE, 13), (75, 197, 2, TRUE, NULL), (75, 208, 3, TRUE, NULL),
(75, 736, 4, FALSE, 12), (75, 3842, 5, TRUE, NULL), (75, 829, 6, TRUE, NULL),
(75, 70, 7, FALSE, 14), (75, 70, 8, TRUE, NULL),
-- Instance 76
(76, 138, 1, FALSE, 12), (76, 87, 2, TRUE, NULL), (76, 281, 3, TRUE, NULL),
(76, 264, 4, FALSE, 13), (76, 1511, 5, TRUE, NULL),
(76, 312, 6, FALSE, 14), (76, 566, 7, TRUE, NULL),
-- Instance 77
(77, 222, 1, FALSE, 13), (77, 517, 2, TRUE, NULL), (77, 1148, 3, TRUE, NULL),
(77, 67, 4, FALSE, 12), (77, 76, 5, TRUE, NULL), (77, 89, 6, TRUE, NULL),
(77, 482, 7, FALSE, 14), (77, 527, 8, TRUE, NULL),
-- Instance 78
(78, 33, 1, FALSE, 12), (78, 605, 2, TRUE, NULL), (78, 589, 3, TRUE, NULL),
(78, 398, 4, FALSE, 13), (78, 515, 5, TRUE, NULL),
(78, 559, 6, FALSE, 14), (78, 1426, 7, TRUE, NULL), (78, 418, 8, TRUE, NULL),
-- Instance 79
(79, 803, 1, FALSE, 13), (79, 217, 2, TRUE, NULL), (79, 448, 3, TRUE, NULL),
(79, 1076, 4, FALSE, 12), (79, 5405, 5, TRUE, NULL), (79, 1244, 6, TRUE, NULL),
(79, 905, 7, FALSE, 14), (79, 79, 8, TRUE, NULL),
-- Instance 80
(80, 235, 1, FALSE, 12), (80, 228, 2, TRUE, NULL), (80, 793, 3, TRUE, NULL),
(80, 361, 4, FALSE, 13), (80, 1316, 5, TRUE, NULL),
(80, 52, 6, FALSE, 14), (80, 750, 7, TRUE, NULL),
-- Instance 81
(81, 27, 1, FALSE, 13), (81, 138, 2, TRUE, NULL), (81, 1197, 3, TRUE, NULL),
(81, 264, 4, FALSE, 12), (81, 829, 5, TRUE, NULL), (81, 67, 6, TRUE, NULL),
(81, 6170, 7, FALSE, 14), (81, 4883, 8, TRUE, NULL);

-- =============================================================================
-- SESSION INSTANCE PERSON (attendance records)
-- =============================================================================

-- Mueller Session attendance (all instances)
INSERT INTO session_instance_person (session_instance_id, person_id, attendance) VALUES
(1, 1, 'yes'), (1, 2, 'yes'), (1, 3, 'yes'), (1, 4, 'yes'), (1, 5, 'yes'),
(2, 1, 'yes'), (2, 2, 'yes'), (2, 3, 'no'), (2, 4, 'yes'), (2, 15, 'yes'),
(3, 1, 'yes'), (3, 2, 'yes'), (3, 3, 'yes'), (3, 4, 'yes'), (3, 15, 'yes'),
(4, 1, 'yes'), (4, 2, 'no'), (4, 3, 'yes'), (4, 4, 'yes'), (4, 16, 'yes'),
(5, 1, 'yes'), (5, 2, 'yes'), (5, 3, 'yes'), (5, 4, 'no'), (5, 19, 'yes'),
(6, 1, 'yes'), (6, 2, 'yes'), (6, 3, 'no'), (6, 4, 'yes'), (6, 5, 'yes'),
(7, 1, 'yes'), (7, 2, 'yes'), (7, 3, 'yes'), (7, 4, 'yes'), (7, 15, 'yes'), (7, 16, 'yes'),
(8, 1, 'yes'), (8, 2, 'no'), (8, 3, 'yes'), (8, 4, 'yes'), (8, 19, 'yes'),
(9, 1, 'yes'), (9, 2, 'yes'), (9, 3, 'yes'), (9, 4, 'yes'), (9, 5, 'yes'), (9, 15, 'yes'),
(10, 1, 'yes'), (10, 2, 'yes'), (10, 3, 'yes'), (10, 4, 'yes'), (10, 16, 'yes'), (10, 19, 'yes'),
(11, 1, 'yes'), (11, 2, 'yes'), (11, 3, 'no'), (11, 4, 'yes'), (11, 5, 'yes'),
(12, 1, 'yes'), (12, 2, 'yes'), (12, 3, 'yes'), (12, 4, 'yes'), (12, 15, 'yes');

-- Downtown Session attendance
INSERT INTO session_instance_person (session_instance_id, person_id, attendance) VALUES
(20, 1, 'yes'), (20, 2, 'yes'), (20, 4, 'yes'),
(21, 1, 'yes'), (21, 2, 'no'), (21, 4, 'yes'),
(22, 1, 'yes'), (22, 2, 'yes'), (22, 4, 'yes'),
(23, 1, 'yes'), (23, 2, 'yes'), (23, 4, 'no'),
(24, 1, 'yes'), (24, 2, 'yes'), (24, 4, 'yes'),
(25, 1, 'yes'), (25, 2, 'no'), (25, 4, 'yes');

-- Boston session attendance
INSERT INTO session_instance_person (session_instance_id, person_id, attendance) VALUES
(30, 6, 'yes'), (30, 7, 'yes'), (30, 8, 'yes'),
(31, 6, 'yes'), (31, 7, 'no'), (31, 8, 'yes'), (31, 17, 'yes'),
(32, 6, 'yes'), (32, 7, 'yes'), (32, 8, 'yes'),
(33, 6, 'yes'), (33, 7, 'yes'), (33, 8, 'no'), (33, 17, 'yes'),
(34, 6, 'yes'), (34, 7, 'yes'), (34, 8, 'yes'),
(35, 6, 'yes'), (35, 7, 'no'), (35, 8, 'yes'), (35, 17, 'yes'),
(36, 6, 'yes'), (36, 7, 'yes'), (36, 8, 'yes'),
(37, 6, 'yes'), (37, 7, 'yes'), (37, 8, 'no'),
(38, 6, 'yes'), (38, 7, 'yes'), (38, 8, 'yes'), (38, 17, 'yes'),
(39, 6, 'yes'), (39, 7, 'no'), (39, 8, 'yes'),
(40, 6, 'yes'), (40, 7, 'yes'), (40, 8, 'yes'),
(41, 6, 'yes'), (41, 7, 'yes'), (41, 8, 'yes'), (41, 17, 'yes');

-- Chicago session attendance
INSERT INTO session_instance_person (session_instance_id, person_id, attendance) VALUES
(50, 9, 'yes'), (50, 10, 'yes'), (50, 11, 'yes'),
(51, 9, 'yes'), (51, 10, 'no'), (51, 11, 'yes'), (51, 18, 'yes'),
(52, 9, 'yes'), (52, 10, 'yes'), (52, 11, 'yes'),
(53, 9, 'yes'), (53, 10, 'yes'), (53, 11, 'no'),
(54, 9, 'yes'), (54, 10, 'yes'), (54, 11, 'yes'), (54, 18, 'yes'),
(55, 9, 'yes'), (55, 10, 'no'), (55, 11, 'yes'),
(56, 9, 'yes'), (56, 10, 'yes'), (56, 11, 'yes'),
(57, 9, 'yes'), (57, 10, 'yes'), (57, 11, 'no'), (57, 18, 'yes'),
(58, 9, 'yes'), (58, 10, 'yes'), (58, 11, 'yes'),
(59, 9, 'yes'), (59, 10, 'no'), (59, 11, 'yes'),
(60, 9, 'yes'), (60, 10, 'yes'), (60, 11, 'yes'), (60, 18, 'yes'),
(61, 9, 'yes'), (61, 10, 'yes'), (61, 11, 'yes');

-- San Francisco session attendance
INSERT INTO session_instance_person (session_instance_id, person_id, attendance) VALUES
(70, 12, 'yes'), (70, 13, 'yes'), (70, 14, 'yes'),
(71, 12, 'yes'), (71, 13, 'no'), (71, 14, 'yes'), (71, 20, 'yes'),
(72, 12, 'yes'), (72, 13, 'yes'), (72, 14, 'yes'),
(73, 12, 'yes'), (73, 13, 'yes'), (73, 14, 'no'),
(74, 12, 'yes'), (74, 13, 'yes'), (74, 14, 'yes'), (74, 20, 'yes'),
(75, 12, 'yes'), (75, 13, 'no'), (75, 14, 'yes'),
(76, 12, 'yes'), (76, 13, 'yes'), (76, 14, 'yes'),
(77, 12, 'yes'), (77, 13, 'yes'), (77, 14, 'no'), (77, 20, 'yes'),
(78, 12, 'yes'), (78, 13, 'yes'), (78, 14, 'yes'),
(79, 12, 'yes'), (79, 13, 'no'), (79, 14, 'yes'),
(80, 12, 'yes'), (80, 13, 'yes'), (80, 14, 'yes'), (80, 20, 'yes'),
(81, 12, 'yes'), (81, 13, 'yes'), (81, 14, 'yes');

-- =============================================================================
-- SESSION TUNES (tunes associated with each session)
-- =============================================================================

-- Mueller session tunes (using real tune_ids)
INSERT INTO session_tune (session_id, tune_id, key) VALUES
(1, 27, 'Em'), (1, 8, 'G'), (1, 1, 'Em'), (1, 74, 'A'), (1, 138, 'Em'),
(1, 64, 'G'), (1, 55, 'G'), (1, 71, 'Em'), (1, 108, 'G'), (1, 83, 'Emin'),
(1, 10, 'Em'), (1, 441, 'D'), (1, 103, 'G'), (1, 116, 'Em'), (1, 182, 'D');

-- Downtown session tunes
INSERT INTO session_tune (session_id, tune_id, key) VALUES
(2, 27, 'Em'), (2, 8, 'G'), (2, 2, 'A'), (2, 74, 'A'), (2, 248, 'G'),
(2, 12, 'Em'), (2, 83, 'Emin'), (2, 10, 'Em');

-- Boston session tunes
INSERT INTO session_tune (session_id, tune_id, key) VALUES
(3, 27, 'Em'), (3, 1, 'Em'), (3, 55, 'G'), (3, 71, 'Em'), (3, 108, 'G'),
(3, 872, 'D'), (3, 10, 'Em'), (3, 441, 'D');

-- Chicago session tunes
INSERT INTO session_tune (session_id, tune_id, key) VALUES
(4, 27, 'Em'), (4, 8, 'G'), (4, 1, 'Em'), (4, 55, 'G'), (4, 71, 'Em'),
(4, 83, 'Emin'), (4, 647, 'G'), (4, 10, 'Em');

-- San Francisco session tunes
INSERT INTO session_tune (session_id, tune_id, key) VALUES
(5, 27, 'Em'), (5, 8, 'G'), (5, 1, 'Em'), (5, 55, 'G'), (5, 71, 'Em'),
(5, 83, 'Emin'), (5, 10, 'Em'), (5, 441, 'D');

-- =============================================================================
-- PERSON TUNES (learning status for some users)
-- =============================================================================

INSERT INTO person_tune (person_id, tune_id, learn_status, heard_count, notes) VALUES
(1, 27, 'learned', 50, 'Drowsy Maggie - one of my favorites'),
(1, 1, 'learned', 45, 'Cooley''s Reel - classic'),
(1, 74, 'learned', 40, 'Mason''s Apron'),
(1, 55, 'learned', 35, 'The Kesh'),
(1, 10, 'learned', 30, 'The Butterfly - love this slip jig'),
(1, 12, 'learning', 10, 'Cliffs of Moher - working on the B part'),
(1, 68, 'want to learn', 5, 'Mountain Road - heard this at Fleadh'),
(1, 83, 'learned', 25, 'Rights of Man - classic hornpipe'),
(1, 441, 'learned', 20, 'John Ryan''s Polka'),
(1, 211, 'learning', 8, 'Inisheer - beautiful waltz'),
(2, 27, 'learned', 60, 'Drowsy Maggie'),
(2, 1, 'learned', 55, 'Cooley''s'),
(2, 64, 'learning', 15, 'Maid Behind the Bar'),
(2, 83, 'want to learn', 8, 'Rights of Man - need to learn this classic'),
(2, 55, 'learned', 40, 'The Kesh'),
(2, 71, 'learned', 35, 'Morrison''s');

-- =============================================================================
-- TUNE SETTINGS (ABC notation from TheSession.org)
-- 2 settings per tune, ~300 total
-- =============================================================================

INSERT INTO tune_setting (setting_id, tune_id, key, abc, incipit_abc) VALUES
(27, 27, 'Edor', '|:E2BE dEBE|E2BE AFDF|E2BE dEBE|BABc dAFD:|
d2fd c2ec|defg afge|d2fd c2ec|BABc dAFA|
d2fd c2ec|defg afge|afge fdec|BABc dAFD|', ''),
(12406, 27, 'Edor', '|:E2 GE BEGE|(3EEE GE BEGE|D2 FD ADFD|(3DDD FD ADFD|
E2 GE BEGE|(3EEE GE BEGE|G2 EF GABc|1 dBAF E2 A,C:|2 dBAF E2 Bc||
|:d2 fd c2 ec|d2 fd c2 Bc|d2 fd c2 ec|BABc dAFA|
d2 fd c2 ec|d2 fd c2 Bc|d2 fd c2 ec|Bdce dAFA:|', ''),
(55, 55, 'Gmaj', '|:G3 GAB|A3 ABd|edd gdd|edB dBA|
GAG GAB|ABA ABd|edd gdd|BAF G3:|
|:B2B d2d|ege dBA|B2B dBG|ABA AGA|
BAB d^cd|ege dBd|gfg aga|bgg g3:|', ''),
(12492, 55, 'Dmaj', '|:{g}A{d}A{e}A {g}ABc|{g}B{d}B{e}B {g}Bce|{g}fe{A}e ae{A}e|{g}fec {g}ec{d}B|
{g}A{d}A{e}A {g}ABc|{g}B{d}B{e}B {g}Bce|{g}fe{A}e aec|{g}B{d}A{e}A [1 {GAG}A3:|2 {GAG}A2 B||
|:{g}c{d}c{e}c {g}ece|{g}faf {g}ec{d}A|{g}c{d}c{e}c {g}ec{d}A|{g}B{d}B{e}B {g}B{d}A{e}B|
{g}c{d}c{e}c {g}ece|{g}faf {g}ec{d}A|{g}ce{A}e {g}ece|{g}fa{g}a [1 A2 B:|2 A3|', ''),
(1307, 1307, 'Gmaj', '|:DE/F/|G2 G2 G2 G2|GABG E2 D2|B2 B2 B2 B2|BcdB A3 A|
BcdB G2 G2|GABG E2D2|DEGA BddB|A2 G2 G2:|
|:A2|BcdB G2 G2|GABG E2 D2|DEGA BddB|B2 A2 A3 A|
BcdB G2 G2|GABG E2 D2|DEGA BddB|A2 G2 G2:|', ''),
(7298, 1307, 'Gmaj', '|:D2|G2G2 G2G2|FGAF G2D2|B2B2 B2B2|ABcA B2G2|
e2e2 d3B|c2c2 B3G|E2A2 A3G|FDEF GABd|
e2e2 d3B|c2c2 B3G|E2A2 A3G|FDEF G2:|', ''),
(6, 6, 'Emin', '|:"Em"E2E EDB,|"G"G3 GAB|"D"A2A ABA|d3 d2e|
d2B GAB|A2F DEF|"G"G2E "D"FED|"Em"E3 E3:|
|:"Em"e2e edB|"D"d3 def|"Em"e2e edB|"D"d3 d2e|
d2B GAB|A2F DEF|"G"G2E "D"FED|"Em"E3 E3:|', ''),
(1680, 6, 'Ador', '|:ABA AGE|c3 d3|ege edB|~g3 e2a|
age g2e|dBG GAB|cBA BGE|ABA A3:|
|:aba age|~g3 ged|e2a age|~g3 e2a|
age g2e|dBG GAB|cBA BGE|ABA A3:|', ''),
(74, 74, 'Amaj', '|:e2|aAA2 ABAF|EFAc dcBA|dBB2 BcBA|Bcde fefg|
aAA2 ABAF|EFAc dcBA|dcde fefa|A2 cB A2:|
|:ed|cAeA fAeA|cAeA fedc|dBfB aBfB|defg afed|
cAeA fAeA|EFAc dcBA|d2dc defa|A2 cB A2:|
|:ed|ceee feee|ceee fedc|dfff afff|dfff agfe|
ceee feee|EFAc dcBA|dcde fefa|A2 cB A2:|
|:e2|aeee aeee|aege feee|beee beee|beae gefg|
aeee aeee|aege feee|dcde fefa|A2 cB A2:|
|:ed|c2Ac eAce|AceA cecA|d2 Ad fAdf|AdfA dfed|
c2Ac eAce|AceA cecA|d2dc defa|A2 cB A2:|', ''),
(12546, 74, 'Gmaj', '|:dBAB GAGE|DEGA BGGz|AcBG AGEG|Gz(3Bcd edge|
dBAB GAGE|DEGA BGGz|c2cd edge|dBAB G2z2:|
|:~G2dz egdG|~G2dg egdB|A2eg ~g2ec|c2eg gedz|
~G2dz egdG|~G2dg egdB|BA(3Bcd edge|dBAB G2z2:|', ''),
(108, 108, 'Gmaj', '|:GE|D2B BAG|BdB A2B|GED G2A|B2B AGE|
D2B BAG|BdB A2B|GED G2A|BGE G:|
Bd|e2e edB|ege edB|d2B def|gfe dBA|
G2A B2d|ege d2B|AGE G2A|BGE G:|', ''),
(12682, 108, 'Gmaj', '|:F/E/|D2 B BAG|B/c/dB ABA|GED G2 A|BcB AGE|
D2 B BAG|BdB A2 B|GED G2 A|BGF G2:|
d|efe edB|ege edB|ded dBA|ded dBA|
G2 A B2 d|ege dBA|GED G2 A|BGF GB/c/d|
e2 e edB|e/f/ge edB|d2 d dd/e/f|gfe dBA|
G2 A B2 d|e/f/ge dBA|GED G2 A|BGF G2||', ''),
(4195, 4195, 'Amin', '|:eA A2|eA A>B|cc Bc|d2 d2|
ee dd|cc B2|A/B/c BG|A2 A2:|
|:A/B/c A/B/c|BG G2|A/B/c A/B/c|d2 d2|
ea ea|ea e>d|cA BG|A2 A2:|', ''),
(10453, 4195, 'Dmaj', '|:BEE B/A/|BEE G/A/|BBAG|A3 G/A/|
BB A/G/F|GG F/E/D|EG F/E/D|E4:|
|:E/F/G E/F/G|FDD2|E/F/G E/F/G|A3 G/A/|
BB A/G/F|GG F/E/D|EG F/E/D|E4:|', ''),
(19, 19, 'Dmaj', '|:FAA dAA|BAA dAG|FAA dfe|dBB BAG|
FAA dAA|BAA def|gfe dfe|1 dBB BAG:|2 dBB B3||
|:fbb faf|fed ede|fbb faf|fed e3|
fbb faf|fed def|gfe dfe|1 dBB B3:|2 dBB BAG||', ''),
(12390, 19, 'Dmaj', 'G|:FA,A, DA,A,|FA,A, DEG|FA,A, DFE|DB,B, B,A,B,|
FA,A, DA,A,|FA,A, DEG|FA,A, DFE|1 DB,B, B,2A,/G/:|2 DB,B, B,2||
G|:FBB FAA|FEF DEG|FBB FAA|FED EDE|
FBB FAA|FEF DEF|GFE DFE|DB,B,B,2:|', 'G'),
(75, 75, 'Gmaj', '|:G2 BG AGBG|B2 BA BcBA|G2 BG AGBG|A2 AG AcBA|
G2 BG AGBG|B2 BA B2 d2|e2 ef edef|gfed BcBA:|
|:G2 gf edeg|B2 BA BcBA|G2 gf edeg|a2 ag aeef|
g2 gf edeg|BcBA B2 d2|edef edef|gfed BcBA:|', ''),
(340, 75, 'Amaj', 'cB|:A2 a2 fefa|cccB c2cB|A2 a2 fefa|BBBA B2cB|
A2 a2 fefa|cccB c2 e2|fffe f2ef|afec B2cB:|
|:ABcd eAcA|cccB c2cB|ABcd eAcA BBBA B2cB|
ABcd eAcA|cccB c2 e2|fffe f2ef|afec B2cB:|', 'cB'),
(248, 248, 'Dmin', '|:A,2DA, FA,DA,|B,2DB, FB,DB,|C2EC GCEC|FEDC A,DDC|
A,2DA, FA,DA,|B,2DB, FB,DB,|C2EC GCEC|FEDC A,DD2:|
|:dA~A2 FADA|dA~A2 FADA|cG~G2 EG~G2|cG~G2 cdec|
dA~A2 FADA|dA~A2 FADA,|~B,3A, B,CDE|FDEC A,DD2:|', ''),
(12958, 248, 'Dmin', '|:B,DFD B,DFD|CEGE CEGE|FAGE FEDC|
A,DFD A,DFD|B,DFD B,DFD|CEGE CEGE|FDEC D3A:|
|:d^cdA FDD2|d^cdA FDD2|cEEE cEdE|cEEE A=BcA|
d^cdA FDD2|d^cdA FDD2|B,DFD CEGE|FDEC D3:|', ''),
(775, 775, 'Bmin', '|:BcB BAF|FEF DFA|BcB BAF|d2e fed|
BcB BAF|FEF DFA|def geg|1 fdB Bdc:|2 fdB ~B3||
|:def ~a3|afb afe|dFA def|geg fdB|
def ~a3|afb afe|def geg|1 fdB ~B3:|2 fdB Bdc||', ''),
(9202, 775, 'Ador', '|:ABG AGE|EDE G3|ABG AGE|c2d edc|
ABG AGE|EDE G3|cde ged|1 BcB A2G:|2 BcB A2B||
cde g2a|gea ged|cde g2a|geg a2B|
cde g2a|gea ged|cde ged|1 cAA A2B:|2 BcB A3||', ''),
(15, 15, 'Dmaj', '|:dAA fAA|eAA fAA|Bee e2d|efe dBA|FAA A2F|
A2B d2e|1 f2f fed|e3 e2A:|2 f2f edc|d3 efg||
|:a2a faa|eaa faa|g2g fgf|efe dBA|FAA A2F|
A2B d2e|1 f2f fed|e3 efg:|2 f2f edc|d3 d3||', ''),
(12381, 15, 'Dmaj', '|:aa/a/a faa|eaa dd/e/f|gag fgf|efe edB|A>BA A2 F|
A2 B d2 e|1 fgf fed|e3:|2 fgf efe|d3- dAB||
dAA fAA|eAA fed|Bee e2 d|efd BdB|ABA A2 F|
A2 B d2 e|1 f3 fed|e3- edc:|2 fgf efe|d3||', ''),
(138, 138, 'Dmix', '|:D2 FD ADFD|ABcA G~E3|D2 (3FED ADFA|d2 ed cAGE|
(3DDD AD (3DDD AD|ABcA G~E3|cABG A2 AB|1 cded cAGE:|2 cded cAGc||
|:Ad (3ddd Ad (3ddd|Ad (3ddd ed^cd|eaag a2 ag|eaag ed^cd|
efge afge|dfed cAGB|cABG A2 AB|1 cded cAGc:|2 cded cAGE||', ''),
(12700, 138, 'Dmix', '|:D2 ED ADED|ABcA GEDE|D2 F/E/D ADED|AddB cAGE
D2 DA D2 ED|ABcA GE E2|cABG A2 AB|1 cded cAGE:|
Ad d2 ad d2|Ad d2 ed^cd|eaag a2 ge|a2 ag aged
efge a2 fg|efed dcAB|cABG A2 AB|1 cded cAGB:|', ''),
(208, 208, 'Ador', '|:eAAG A2Bd|eaaf gedg|eAcA eAcA|BGGA Bdeg|
eAAG A2Bd|eaaf gedB|cBcd eged|cABG A2Bd:|
|:eaag abag|eaag egdg|egdg egdg|eaaf gedg|
eaag a2ag|eaaf gedB|c2cd e2ed|cABG A2Bd:|', ''),
(12873, 208, 'Ador', 'eAAG A2 (3Bcd|eaaf gedg|eA ~A2 eAcA|BdGB dG (3Bcd|
eAAG A2 (3Bcd|eaaf gedB|~c3 d (3efg ed|cdBc A2(3Bcd|
eA ~A2 EAcd|eAaf gafg|ea ~a2 AecA|BG ~G2 B,DGB|
AE ~E2 cA (3Bcd|eaaf gedB|~c3 d eged|cdBc A2Bd|
eaa^g ~a3 =g|eaaf gedg|(3efg dg (3efg dg|eaaf gabg|
eaa^g aba=g|eaaf gedB|~c3 d (3efg ed|cdBc A2(3Bcd|
eaa^g ~a3 =g|eaaf gedg|(3efg dg cgBg|eaaf gabg|
eaa^g ab=ga|eaaf gedB|~c3 d eged|cd (3efg agfg|', 'eAAG A2 (3Bcd'),
(116, 116, 'Dmaj', 'A2AB AFED|B2BA BcdB|A2AB AFED|gfed BcdB|
A2AB AFED|B2BA BcdB|A2AB AFED|gfed Bcde||
f2fd g2ge|f2fd Bcde|f2fd g2fg|afed Bcde|
f2fd g2ge|f2fd Bcde|defg a2ab|afed BcdB||', 'A2AB AFED'),
(12707, 116, 'Emin', 'B2Gc BGFE|c2cB cdec|B2Gc BGFE|agfe cdec|
~B3c BGFG|EccB cdec|B2Gc BGFE|agfe cdef||
~g3e ~a3f|~g3e cdef|~g3e a2ga|bgfe cdef|
~g3e ~a3f|~g3e cdef|efga bgc''g|bgfe cdec||', 'B2Gc BGFE'),
(21, 21, 'Amin', '|:A2 cA ABcA|GcEG G2 EG|A2 cA ABcd|ecdB cA A2:|
agec dfed|cAGE G2 eg|agec d2cd|eaag a2ba|
gedc dfed|cAGE|G2 EG|A2 cA ABcd|ecdB cA A2|', ''),
(12397, 21, 'Amin', '|:A3 G ABcA|GE{G}E^F G2 EG|A2 cA GAcd|1 egdB cAAG:|2 egdB cAAg||
age^c dfed|cAGE G2 eg|age^c d2 =cd|eaag a3 a|
age^c dfed|cAGE G2 EG A2 cA GAcd|1 egdB cAAa:|2 egdB cAAG||', ''),
(12, 12, 'Ador', '|:a3 bag|eaf ged|c2A BAG|EFG ABd|
eaa bag|eaf ged|c2A BAG|EFG A3:|
e2e dBA|e2e dBA|GAB dBA|GAB dBd|
e2e dBA|e2e dBA|GAB dBA|EFG A3|
efe dBA|efe dBA|GAB dBA|GAB dBd|
efe ded|cec BeB|GAB dBA|EFG A3|', ''),
(12375, 12, 'Gmaj', '|:d|~a3 bag|eaf ged|c2A BAG|EFG A2e|
~a3 bag|e/f/af ged|cBA BAG|EFG A2:|
|:d|~e3 dBA|~e dBA|G2B dBA|~G3 dBd|
[1~e3 dBA|e/f/ge dBA|GAB dB/c/d|edB A2:|
[2~d3 dee|cee Bee|EFG AGE|dBe A2||', ''),
(197, 197, 'Ador', '|:ed|c2Ac B2GB|AGEF GEDG|EAAB cBcd|eaaf gfed|
cBAc BAGB|AGEF GEDG|EAAB cded|cABG A2:|
|:de|eaab ageg|agbg agef|gfga gfef|gfaf gfdf|
eaab ageg|agbg agef|g2ge a2ga|bgaf ge:|', ''),
(12854, 197, 'Gmin', '|:GA|((3Bcd B)G ((3ABc A)F|GFDG FDCF|(3DD(G {A}GF G)ABc|(3ddd {e}dd cAFA|
BG[BG]G [A3F3] G|D ~G3 FD[DC]F|(3DD(G {A}GF G)ABc|1 ((3dcB (3cBA B) ~G2 A:|2 (3dd(B {d}BA) ~G3 =B||
dgg^f gd (3ddd|gdad gdd(=e|=f2) =eg f ~c3|fgag fdcA|
dgg^f gd (3ddd|gdad gdd=e|({=fg}f=e fa) (f ~g3)|ga{b}ag fdcA:|', ''),
(537, 537, 'Emin', '|:EBB BAG|Fdd AFD|EBB EBB|AGF EFD|
EBB BAG|Fdd AB^c|ded BGB|AGF E2D:|
|:Bee ede|fef dBA|Bee Bee|fe^c d2A|
Bee ede|fef dBA|BdB GBd|AGF E2E:|', ''),
(13482, 537, 'Edor', 'BEE {c}BAG|FAA AFD|BEE BEE|AGF ~E3|
BEE {c}BAG|FAA ABc|~d3 ~B3|AGF ~E3||
Bee ede|fdd dBA|Bee ede|fdc ~d3|
Bee ede|~f3 dBA|~d3 ~B3|AGF ~E3||', 'BEE {c}BAG'),
(62, 62, 'Dmaj', '|:AFA AFA|BGB BdB|AFA AFA|fed BdB|
AFA AFA|BGB BdB|def afe|dBB BdB:|
|:def afe|bff afe|def afe|dBB BdB|
def afe|bff afe|g2e f2d|edB BdB:|
|:dff fef|fef fef|dff fef|edB BdB|
dff fef|fef def|g2e f2d|edB BdB:|
|:Add fdd|edd fdd|Add fdd|edB BdB|
Add fdd|edB def|g2e f2d|edB BdB:|', ''),
(12506, 62, 'Dmaj', '|:A3 AFA|B3 BdB|A3 AFA|fge fdB|
A3 AFA|B3 BAB|def afe|fdB BAB:|
|:def a3|baf afe|def afe|fdB BdB|
def a3|baf a2f|g3 f3|edB BAB:|
|:d2f fef|fef fef|d2f fef|edB BAB|
d2f fef|fef def|g2e f2d|edB BdB:|
|:Add fdd|edd fdB|Add fdd|edB BAB|
Add fdd|edB def|g2e f2d|edB BdB:|', ''),
(103, 103, 'Dmaj', '|:fedf edcB|A2FA DAFA|B2GB EBGB|A2FA DAFA|
fedf edcB|A2FA DAFA|BGed cABc|eddc d2 de:|
|:f2fg fedc|Bggf g2gf|edcB ABce|baa^g abag|
f2fg fedc|Bggf g2gf|edcB ABcd|eddc d2 de:|', ''),
(12663, 103, 'Dmaj', 'f3g fedB|A2FA DAFA|BG~G2 G3B|AGFG ~F2F2|
f3g fedB|A2FB AFA=c|BGBd cAce|d2e/d/c defg|
fdfa fdfg|aggf g2gf|eceg eceg|baa^g a2a=g|
fdfa fdfg|aggf g2gf|eceg eceg|fdec d2 A2|', 'f3g fedB'),
(105, 105, 'Ador', '|:eAcA eAcA|cdef gedB|G2BG dGBG|cdef g2fg|
eA (3cBA eA (3cBA|cdef g2fg|afge dBGB|AcBG A2 gf:|
|:eaag abag|edef gedB|(3GFG BG dGBG|cdef g2fg|
eaag abag|edef g2fg|afge dBGB|AcBG A2 gf:|', ''),
(10141, 105, 'Ador', '|:e2eg eA~A2|eAfA g2ga|gedB dG~G2|BGBd g2fg|
egfg eA~A2|eAfA g3a|bagb aged|egdB A2Bd:|
e2a2 aged|B/c/d ef g2ga|gedB dG~G2|BGBd g2fg|
ea~a2 aged|B/c/d ef g3a|bagb aged|e/f/g dB A2Bd:|', ''),
(273, 273, 'Ador', '|:~c3 BAG|AGE DB,G,|~A,3 EDB,|DEG AGE|
cBA BAG|AGE DB,G,|A,2 E EDE|DB,G, A,2 B:|
|:cBA ~a3|bag edB|GBd ~g3|GBd cBA|
cBc dcd|ede gab|age dBG|EFG A2 B:|', ''),
(13014, 273, 'Ador', '|:cBA afa|bag edB|GBd gfg|GBd cBA|
[1 cBA afa|bag edB|GBd gdc|BAG A2B:|
[2 cBc dcd|ede gab|age dBG|EFG A2 B||', ''),
(373, 373, 'Dmaj', '|:EAA A2 d|cAG EFD|DGG DEE|DGG GED|
EAA A2 d|cAG EFD|EFG AGE|EDD D2:|
(d/e/)|fdd ede|fdd d2 e|fed ded|cAA A2 (d/e/)|
fdd ede|fed A2 G|DFG AGE|EDD D2:|', ''),
(2762, 373, 'Dmix', '|:E/F/G|A3 B3|cBc E2D|E>FG E>FG|E/F/GA G>ED|
E2A A2B|c>Bc E2d|^c2A B>AG|1 F2D D:|2 F2D D2||
|:g|f>ed d2g|f>ed d2g|f>ed e2d|^c>AA A2g|
f>ga e>fg|f/g/fe d>^cA|G>AG E>FG|1 F2D D2:|2 F2D D3||', ''),
(1, 1, 'Edor', '|:D2|EBBA B2 EB|B2 AB dBAG|FDAD BDAD|FDAD dAFD|
EBBA B2 EB|B2 AB defg|afec dBAF|DEFD E2:|
|:gf|eB B2 efge|eB B2 gedB|A2 FA DAFA|A2 FA defg|
eB B2 eBgB|eB B2 defg|afec dBAF|DEFD E2:|', ''),
(12342, 1, 'Emin', '|:F|CGGC G2 CG|G2 FG BGFE|(3DCB, FB, GB,FB,|DB,DF BFDB,|
CGGC G2 CG|G2 FG Bcde|fdcd BGFB|B,CDF C3:|
|:d|cG ~G2 cede|cG ~G2 ecBG|(3FGF DF B,FDF|GFDF Bcde|
cG ~G2 cede|cG ~G2 Bcde|fdcd BGFB|B,CDF C3:|', ''),
(418, 418, 'Bmin', '|:B>B Bc|dB Bd|cA Ac|d/c/B/A/ BF|
B>B Bc|dB B2|ef/e/ dc|B2 B2:|
|:f>d df|ec cd|ef/e/ dc|Bc de|
f>d df|ec cd|ef/e/ dc|B2 B2:|', ''),
(13274, 418, 'Amin', '|:E|A>A AB|cA Ac|BG GB|c/B/A/G/ AE|
A>A AB|cA Ac|de/d/ cB|1 A2 A:|2 A2 A2||
|:Ec ce|dB Bc|de/d/ cB|AB cd|
ec ce|dB Bc|de/d/ cB|1 A2 A2:|2 A2 A||', ''),
(517, 517, 'Edor', '|:dc|BE ~E2 BEdE|BE ~E2 dBAF|D2 (3FED ADFE|DEFA BAFA|
BE ~E2 BEdE|BE ~E2 B2 AF|D2 FA dfec|dBAF E2:|
FA|Beed efed|(3Bcd ef gedB|Addc d3 B|A2 FE DEFA|
Beed efed|(3Bcd ef g2 fg|af (3gfe fd ec|dBAF E2:|', ''),
(13448, 517, 'Edor', 'ag|e~A3 egag|~e2=fd edBF|G2ge dGBA|GBga bgag|
e~A3 egag|~e2dg edBD|G2ga bgae|gedB ~A2ag|
e~A3 egag|~e2dg edBD|G2ge dGBA|GBga bgag|
e~A3 EABd|eAAG AGEF|G2ga bgae|gedB ~A2ag|
eaae abag|ebae gbag|edd^c dega|bgae gbag|
~e2ab (3c''ae ag|ebae gbag|edd^c dgba|gedB ~A2ag|
e2ae aeag|ebae gbag|edd^c dega|bgae gbag|
~e2ab (3c''ae ag|ebae gbag|edd^c dgba|gedB AGag|', 'ag'),
(86, 86, 'Ador', '|:c4 c2 AB|cBAG Ec c2|Add^c defe|dcAG FGAB|
c4 c2 AB|cBAG EDCE|DEFG ABcA|dcAG F2 D2:|
|:eg g2 ag g2|eg g2 ed^cd|ea a2 ba a2|ea a2 egdg|
eg g2 ag g2|fed^c defg|afge fde^c|dcAG F2 D2:|', ''),
(12601, 86, 'Ador', '|:c3 B c2 AB|cBAG EG G2|Add^c defe|dcAG FGAB|
c3 B c2 AB|cBAG EFGE|DEFG ABcA|dcAG FD D2:|
|:eg g2 ag g2|eg g2 ed^cd|eaag a2 ag|eaag ed^cd|
eg g2 ag g2|f2 fe defg|afge defe|dcAG FD D2:|
c3 B c2 AB|cBAG EG G2|Add^c defe|dcAG FGAB|
c3 B c2 AB|cBAG EFGE|DEFG ABcA|1 dcAG FGAB:|2 dcAG FD D2||
|:eg g2 ag g2|eg g2 edBd|eaa2 bgag|eaag edBd|
eg g2 ag g2|egge defg|afge fde^c|1 dcAG FD D2:|2 dcAG FGAB||', ''),
(87, 87, 'Dmaj', '|:A2AB AFDF|G2BG dGBG|ABAF DFAF|GBAG E2D2:|
|:ABde f2fd|g2ge fedB|ABde fefa|gfdf e2d2:|', ''),
(12608, 87, 'Dmaj', '|:A2AF DFAF|G2BG DGBG|A3F DFAF|GBAF E2D2:|
|:ABde f3d|g3e fedB|ABde fefg|afdf e2d2:|', ''),
(88, 88, 'Dmaj', '|:FEF DED|D2d cAG|FEF FED|A2F GFE|
FEF DED|D2d cAG|FAF GBG|A2F GFE:|
D2d cAd|cAd cAG|FEF cAd|A2F GFE|
D2d cAd|fed cAG|FAF GBG|A2F GFE:|', ''),
(12618, 88, 'Dmaj', '|:~F3 DED|D2d cAG|FAF DED|A2F GFE|
FEF DED|D2d cAG|FAF GBG|A2F GFE:|
D2d cAd|cAd cAG|F2d cAG|FAF GEA|
D2d cAd|fed cAG|FAF GBG|A2F GFE:|', ''),
(281, 281, 'Edor', '|:B,E (3EEE B,EFE|EDB,D A,DFD|B,E (3EEE B,EGB|AFDE FEED|
B,E (3EEE B,EFE|EDB,D A,DFD|B,E (3EEE B,EGB|1 AFdF FEED:|2 AFdF FEEA||
|:Bbab fgeg|fd (3ddd Adfd|Bbab fgeg|fdAF FEEA|
Bbab fgeg|fd (3ddd Adfd|EFGA BABd|1 AFdF FEEA:|2 AFdF FEED||', ''),
(13030, 281, 'Ddor', '|:A,D (3DDD A,DFD|C2B,C G,CEC|A,D (3DDD A,FAF|EGcG EDDC|
A,D (3DDD A,DFD|C2B,C G,CEC|A,D (3DDD _B,3D|EGcG ED (3DDD:|
|:da^ga efdf|ec (3ccc Gcec|da^ga efdB|cAAG AD (3DDD|
da^ga efdf|ec (3ccc Gcec|DEFG AGAc|GEcE ED D2:|', ''),
(71, 71, 'Edor', '|:E3 B3|EBE AFD|EDE B3|dcB AFD|
E3 B3|EBE AFD|G3 FGA|dAG FED:|
Bee fee|aee fee|Bee fee|a2g fed|
Bee fee|aee fee|gfe d2A|BAG FGA|
Bee fee|aee fee|Bee fee|faf def|
g3 gfe|def g2d|edc d2A|BAG FED|', ''),
(27175, 71, 'Emin', '|:TE3 BEB|EBE AFD|TE3 BEB|edB AFD|
E3 BEB|EBE AFD|EBE BEB|edB AFD:|
eee fee|aee fee|efe fef|a2 g fed|
eee fee|bee fee|e/f/ge fde|dcB AFD||
eee fee|bee fee|bee fef|a2 f def|
gba/g/ fag/f/|egf/e/ def/g/|egf/e/ d2 A|BAG FED||', ''),
(872, 872, 'Gmaj', '(3def|:gdBd cedc|BGBd cedc|BGBd Bedc|BdcB AB (3def|
gdBd cedc|BGBd cedc|defg agfa|1 g2 b2 g2 (3def:|2 g2 b2 g2 fg||
|:afdg afdg|bgdg bgdg|afdf ad''_d''b|agfe dg=fg|
ecGc egfe|dBGB dgfe|defg fgaf|1 g2 b2 g2 fg:|2 g2 b2 g2||', '(3def'),
(1322, 872, 'Gmaj', '|:d2|gdBG cedc|BGBd cedc|Bbgb Acac|Bbgb Aafa|
gdBG cedc|BGBd cedc|Bdce dfac''|bagf g2:|
|:d2|afdf afc''a|bgdg bgd''b|afdf afc''b|agfe e2d2|
ecGc ecge|dBGB dBge|dafd dcBA|G2B2 G2:|', ''),
(34, 34, 'Dmaj', '|:FED EFG|Add cAG|A2A BAG|F2F GED|
FED EFG|Add cAG|F2F GEA|DED D3:|
|:d2e fed|efd cAG|A2A BAG|FAF GED|
d2e fed|efd cAG|F2F GEA|DED D3:|
K:Dmix
|:DED c3|AdB cAG|ABc ded|ded cAG|
DED c3|AdB cAG|F2F GEA|DED D3:|
K:Dmaj
|:d2e fed|Add fed|c2d ecA|fed ecA|
d2e fed|Add fed|faf gfe|dfe d3:|
|:fed ecA|ded cAG|A2A BAG|F2F GED|
fed ecA|ded cAG|F2F GEA|DED D3:|', ''),
(12434, 34, 'Dmaj', '|:FED EFG|AdB cAG|~A3 BAG|FAF GED|
FED EFG|AdB cAG|~F3 GEA|1 DDD D3:|2 DDD D2A||
|:d2e fed|efd cAG|~A3 BAG|FAF GED|
d2e fed|efd cAG|~F3 GEA|DDD D3:|
|:DDD =c3|AdB =cAG|ABc ded|ded cAF|
DDD =c3|AdB =cAG|~F3 GEA|1 DDD D3:|2 DDD D2A||
|:d2e fdd|Add fdd|c2d eAA|fed ecA|
d2e fdd|Add fdd|faf gfe|1 dfe d2A:|2 dfe d2e||
|:fed ecA|ded cAG|~A3 BAG|FAF GED|
[1fed ecA|ded cAG|~F3 GEA|DDD D3:|
[2fdf ~g3|afd cAG|~F3 GEA|DDD D3||', ''),
(92, 92, 'Gmaj', '|:BGG DGG|BGB dcB|cAA EAA|cAc edc|
BGG DGG|BGB dcB|cBc Adc|BGG G3:|
|:BGG DGG|BGB BAG|AFF DFF|AFA AGF|
EGG DGG|CGG B,GG|cBc Adc|BGG G3:|', ''),
(12633, 92, 'Gmaj', '|:dc|BAB DGB|DGB dcB|cBc EGc|EGc edc|
BAB DGB|DGB dcB|1 cBc ed^c|dfa g:|2 cBc BGB|AFA G||
|:ef|gfg Bdg|Bdg bag|fef Adf|Adf agf|
gbg faf|gfe dBG|cBc BGB|AFA G:|', ''),
(736, 736, 'Dmin', '|:DFA ^G2 A|DFA ^G2 A|dAA dAA|BAG F3|
DFA ^G2 A|DFA ^G2 A|dAA BAG|FGE D3:|
d2 e fed|e2 f gfe|d2 e fed|A^GA B2 A|
d2 e fed|e2 f gfe|dAA BAG|FGE D3:|', ''),
(8158, 736, 'Emin', '|:EGB ^A2 B|EGB ^A2 B|eBB eBB|BcA G2 F|
EGB ^A2 B|EGB ^A2 B|eBB eBB|G2 F E3:|
|:eBe gfe|fdf agf|eBe gfe|fBB c2 B|
eBe gfe|fdf agf|BeB cBA|G2 F E3:|', ''),
(3842, 3842, 'Cmaj', '|:cAG ~c3|deg ~e3|deg edc|dcA cAG|
cAG ~c3|deg ~e3|deg edc|1 dcA c3:|2 dcA cde||
~g3 edc|deg ~e3|deg edc|dcA cAG|
~g3 edc|deg e2c|deg edc|dcA cde|
~g3 age|deg ~e3|deg edc|dcA cAG|
cAG ~c3|deg ~e3|deg edc|dcA c3||', ''),
(6316, 3842, 'Amaj', '|:AFE ~A3|Bce c3|Bce cBA|BAF AFE|
AFE ~A3|Bce c3|Bce cBA|1 BAF A3:|2 BAF ABd||
e2d cBA|Bce cBA|ece cBA|BAF AFE|
~e3 cBA|Bce cBA|ece cBA|BAF A3|
~e3 cBA|Bce cBA|ece cBA|BAF AFE|
AFE ~A3|Bce c3|Bce cBA|BAF A3:|', ''),
(222, 222, 'Emin', '|:E2BE GABG|E2BE FDAD|E2BE GABc|1 dBcA BGED:|2 dBcA BGE2||
e2ge f2af|gfed edBd|e2ge f2af|gfed Beed|
efge fgaf|gfed efga|bgaf gfed|edBA GEED||', ''),
(824, 222, 'Edor', 'E2BE GABG|E2BG AFDB|E2BE GABe|dBBA BEED|
E2BE GABG|E2BG AFD2|EBBA GABc|dBcA BEE2||
efge f2af|gfed edBd|efge fedB|e2BA BEE2|
efge f2af|gfed edBd|bgaf gefd|e2BA GEFD||', 'E2BE GABG'),
(73, 73, 'Bmin', '|:BA|FBBA B2Bd|cBAf ecBA|FBBA B2Bd|cBAc B2:|
|:Bc|d2dc dfed|(3cBA eA fAeA|dcBc defb|afec B2:|
Bc|dBB2 bafb|afec ABce|dB B2 bafb|afec B2Bc|
dB B2 bafb|afec ABce|dcBc defb|afec B2|', ''),
(12543, 73, 'Bmin', '|:BA|FB~B2 BABd|cBAf ecBA|FB~B2 BABd|cBAF B2:|
|:Bc|d2dc dfed|(3cBA eA fAeA|1 dcBc dfaf|edcd B2:|2 dcBc dbaf|edcd B2||
|:Bc|dB~B2 bafb|afec Acec|dB~B2 bafb|afec B2:|', ''),
(2204, 2204, 'Gmaj', 'D|:GBA ABd|edB A2 G|GBA ~B3|1 AGG G2 D:|2 AGG G2 g||
|:e2 g e2 g|ege edB|ded dBd|deB {d}BAG|
cBc dcd|e/f/gB A2 G|GBA ~B3|1 AGG G2 g:|2 AGG G2 D||
|:GAB dBA|GAB ~B3|GAB edB|dBA A2 B|
GAB dBA|BAB ~g3|fed edB|1 dBA A2 D:|2 dBA A2 B||
|:dBB gBB|dBB d2 e|dBB gfg|edB A2 B/A/|
GAB dBA|BAB ~g3|fed edB|dBA A2 B:|', 'D'),
(15569, 2204, 'Gmaj', '|:DBA B2d|edB AGF|GBA B3|AGE EGE|
DBA B2d|edB AGF|GBA B3|AGF G3:|
e2g edg|edg ed^c|d3 dge|dge dBG|
cEc dFd|gdB AGF|GBA B3|AGF G3:|', ''),
(8, 8, 'Gmaj', '|:G2 GD EDEG|AGAB d2 Bd|eged BAGA|BAGE EDDE|
G2 GD EDEG|AGAB d2 Bd|eged BAGA|BAGE ED D2:|
|:ea a2 efgf|eBBA B2 Bd|eB B2 efgf|eBBA B2 Bd|
ea a2 efgf|eBBA B2 Bd|eged BAGA|BAGE EDD2:|', ''),
(12365, 8, 'Gmaj', '|:G3D EDB,D|GFGB d2 Bd|eged BAGA|BAGE EDDE|
G2 GD EDB,D|GFGB d2 Bd|eged BAGA|1 BAGE EDDE:|2 BAGE ED D2||
|:eaag efge|dBBA B2 Bd|eB ~B2 gBfB|eBBA B2 Bd|
eaag efge|dBBA B2 Bd|eged BAGA|1 BAGE EDD2:|2 BAGE EDDE||', ''),
(448, 448, 'Dmaj', '|:~d3 edc|dAF GFE|DFA dFA|Bcd efg|
fed edc|dAF GFE|DFA dFA|B2c d3:|
|:~f3 ~a3|~g3 bag|f2a afd|1 ~g3 efg|
fef afd|~g3 bag|fga efg|fdc d3:|
[2 ~g3 e2g|fga efg|fdB AFA|Bcd ece|fd/e/f gfe||', ''),
(977, 448, 'Dmaj', '|:def edc|dAF GFE|DFA DFA|Bcd edc|
def edc|dAF GFE|DFA DFA|1 Bdc d2A:|2 Bdc d2e||
~f3 afd|~g3 bag|~f3 afd|gfg efg|
~f3 afd|~g3 bag|fga efg|fdc d2e|
~f3 afd|~g3 bag|~f3 afd|~g3 e2g|
fga efg|fdB AFA|Bcd ede|fdc d3||', ''),
(217, 217, 'Emin', 'B,|E2 E EFB,|GFG AGA|~B3 ABA|GFG EDB,|
A,2 E EDB,|~G3 AGA|~B3 ABA|GED E2 B,|
E2 E EFB,|~G3 AGA|~B3 ABA|GE/F/G EDB,|
A,2 E EDB,|~G3 AGA|~B3 ABA|GED E3||
efe dBA|GAB dBd|edB AGA|BdB AGF|
G2 F EDB,|~G3 AGA|BdB ABA|GED E3|
[g3B] dBA|GAB dBd|edB AGA|~B3 AGF|
G2 F EDB,|~G3 AGA|~B3 ABA|GED E3||', 'B,'),
(12896, 217, 'Emin', '~E3 EDE|~G3 AGA|~B3 ABA|GE/F/G EDB|
A2 E EDE|~G3 AGA|~B3 ABA|GED E3||
~e3 dBA|GAB dBd|edB AGA|~B3 AGF|
G2 F EDE|~G3 AGA|~B3 ABA|GED E3||
~E3 EDE|~G3 ~A3|~B3 ~A3|~G3 EDG|
~E3 EDE|~G3 ~A3|~B3 ~A3|GED E3||', '~E3 EDE'),
(106, 106, 'Ador', '|:cBA eAA|cBA edc|BGG dGG|gfe dcB|
cBA eAA|cBA e2f|gfe dcB|cBA A2d:|
efg a2b|a2b age|efg a2b|age g2d|
efg a2b|a2b age|gfe dcB|cBA A2d:|', ''),
(9103, 106, 'Amin', 'AB|:cAA eAA|cBA edc|BGG dGG|gfe dcB|
cAA eAA|cBA efg|age dcB|cAA A3:|
|:efg a3|age dBG|GBd g3|egd BAG|
efg a3|age efg|age dcB|cAA A3:|', 'AB'),
(1148, 1148, 'Emin', '|:BEED E2GE|E2GE DEGA|BEED E2DE|1 GABG A2GA:|2 GABG A2BA||
~G3F GBdB|c2AB cded|~B3A GBde|dBGB A2BA|
~G3F GBdB|c2AB cdef|gedB c2ge|dBGB A2GA||
|:BEED E2DE|GEDB, DEGA|BEED E2DE|1 GABG A2GA:|2 GABG ~A3F||
~G3F GBdB|cBAB cded|B2AB GBdB|GABG ~A3F|
DGGF GBdB|cBAB cdea|gedB cege|dBGA BA~A2||', ''),
(14414, 1148, 'Emin', 'GA|BEED E2DE|GEDB, D2B,D|GEED E2DE|GABG ABGA|
BE~E2 B,E~E2|GEDB, D2B,D|GEED E2DE|GABG AGEF||
G2GF GBdc|B2BA BcBA|GFGB dedB|(3ABA GB A2(3DEF|
G2FA GBdc|B2Ac BcBA|GFGB dedB|(3ABA GB A2||', 'GA'),
(33, 33, 'Ador', '|:A,3 C E3 F|GEDB, G,B,DB,|A,3 C E3 F|GEDF EA,A,G,|
A,3 C E3 F|GEDB, D2 g2|edeg a2 ba|gedB BA A2:|
K:AMix
|:a2 ag agef|g2 ga gede|a2 ag agef|gedB BA A2|
agef gage|d2 dB GABd|cAeA Bdef|gedB BA A2:|
|:eABA eABA|d2 dB GABd|eABA eAAa|gedB BA A2|
eABA eABA|d2 dB GABd|c2 BA Bdef|gedB BA A2:|
|:aece aece|gdBd gdBd|aece a2 af|gedB BA A2|
agef g2 ge|dedB GA B2|cAeA d2 ef|gedB BA A2:|', ''),
(12428, 33, 'Ador', '|:A3 c E3 F|GEDB GBDB|A3 c E3 F|GEDF EAAG|
A3 c E3 F|GEDB D2 g2|edeg a2 ba|gedB BA A2:|', ''),
(605, 605, 'Gmaj', '~B2BA BAGA|B2GB AGEG|~B2BA BAGB|cABG AGEG|
~B2BA BAGA|B2GB AGEG|Bd~d2 eBdB|AcBG AGEG||
DG~G2 DGBG|DGBG AGEG|DGGF GABc|d2BG ABGE|
AG~G2 AGBG|DGBG AGEG|DGGF GABc|dBAc BG~G2||
d2 (3Bcd edge|dGBG AGEG|d2 (3Bcd eg~g2|agbg ageg|
d2 (3Bcd edge|dGBG AGEG|d2 (3Bcd eg~g2|agab aged||', '~B2BA BAGA'),
(13622, 605, 'Gmaj', 'd2Bd egge|d2BG AGEG|d2Bd egge|agbg ageg|
d2Bd egge|d2BG AGEG|d2Bd egge|dBAB G3A|
B2B/B/B BAGA|B2BG AGEG|B2B/B/B BAGA|BGAF G2GA|
B2B/B/B BAGA|B2BG AGEG|B2B/B/B BAGA|BGAF G2D/D/D|
DGBG AGBG|DGBG AGEG|DGBG AGBd|gedB ABGE|
DGBG AGBG|DGBG AGEG|DGBG AGBd|gedB G4|', 'd2Bd egge'),
(803, 803, 'Ador', '|:G|EGG GED|EGG c2B|AcA AGA|cde ecd|
cde g2a|ged c2d|eaa e2d|cAA A2:|
|:d|egg ged|egg g2d|eaa aga|baa a2g|
cde g2a|ged c2d|eaa e2d|cAA A2:|', ''),
(13954, 803, 'Ador', '|:EGG GED|EGG c2 B|AcA AGA|cde e2 d|
cde g2 a|ged c2 d|e2 a edB|cAG A2:|
e2 g ged|egg g2 d|e2 a aga|bag a2 g|
cc/d/e g2 a|ged c2 B|Aaa e2 d|cAG A2:|', ''),
(6170, 6170, 'Amaj', '|:A2 AE|FA E2|FB BA/B/|cB cB|
A2 AE|FA E2|FB BA/B/|1 cA GB:|2 cA Af||
e>f ec|Af fe|Bf Bf|g2 gf|
cg cg|a2 af|ec BA/B/|1 cA Af:|2 cA GB||', ''),
(18016, 6170, 'Amaj', '|:A2 A>E|FA FE|FB BA/B/|cB B2|A2 A>E|FA FE|AA BA/B/|cA A2:|
|:Ae Ae|f2 f2|Bf Bf|g2 g2|cg cg a2|g>f|ec BA/B/|cA A2:|', ''),
(235, 235, 'Dmaj', '|:DAD AFA|BGB AFA|D3 AFA|B2c d3:|
dfd ecA|dcB AFA|dfd ecA|B2c d2A|
dfd ecA|dcB AFA|D3 AFA|B2c d2A|
dfd ecA|dcB AFA|dfd ecA|B2c dfg|
afd gec|dcd AFA|D3 AFA|B2c d3|', ''),
(882, 235, 'Gmaj', '|:GBd edB ege dBG|GBd edB e2 f g3|
GBe edB ege dBG|GBe edB e2 f g3:|
|:bag agd efg dBG|bag agd e2 a a3|
bag agd efg dBG|GBd edB e2 f g3:|', ''),
(2320, 2320, 'Gmaj', 'DG|:B2 B2 DG|B2 B2 DG|B2 c2 B2|A4 DF|
A2 A2 DF|A2 A2 DF|A2 B2 A2|1 G4 DG:|2 G3 ABc||
|:d2 g2 f2|A3 GAB|c2 e2 d2|B4 BB|
B2 A2 B2|c3 Bcd|1 e2 d2 G2|B3 ABc:|2 e2 d2 F2|G4 DG||', 'DG'),
(15686, 2320, 'Gmaj', '|:G>A|B2 D2 G>A|B2 D2 G>A|B2 c2 B2|A4 F>G|
A2 D2 F>G|A2 D2 F>G|A2 c2 F2|G4:|
|:Bc|d2 g2 f2|c4 A>B|c2 e2 d2|B4 G>A|
B2 A2 B2|c4 c>e|e2 E2 A2|G4:|', ''),
(2828, 2828, 'Bmin', '|:B2f2f2 ef|g2e2 edcd|eAce efed|c2c2 dcBA|
B2f2f2 ef|g2e2 edcd|eAce efed|c2B2 BAFA:|
B3A Bcdc|B2 B2 c3d|eAce efed|c2 c2 dcBA|
B3A Bcdc|B2 B2 c3d|eAce efed|c2B2B2A2:|', ''),
(6932, 2828, 'Emin', '|:E2B2 B2AB|c3B A2FG|A2A2 AB AG|FE FG G2F2|
E2B2 B2AB|c3B A2FG|A2A2 AB AG|FE FG E4:|
E2E2 F2G2|E2E2 F2G2|A2A2 AB AG|FE FG G2F2|
E2E2 F2G2|E2E2 F2G2|A2A2 AB AG|FE FG E4:|', ''),
(1076, 1076, 'Amix', '|:cAA BGG|cAA ABd|cAA BAG|AFD D2 B|
cAA BGG|cAA AFD|G2 A (B/c/d)B|1 AFD D2 B:|2 AFD D3||
|:~f3 ~g3|afd cBA|~f3 gfg|afd dfg|
agf gfe|fed e/f/ed|cBA BAG|AFD D3:|', ''),
(14305, 1076, 'Dmix', '|:d/B/|c2A BAG|cAA AdB|c2A BAG|AFD DdB|
c2A BAG|cAA BAG|FGA BAG|AFD D2:|
e|fef gfg|afd cBA|fef gfg|afd efg|
agf gfe|efd {ef}e2d|cAA BAG|AFD D2:|', ''),
(5405, 5405, 'Edor', '|:BEE EFA|Bee d2f|edB BAF|d2B AFE|
BEE EFA|Bee d2f|edB BAF|AFE EFA:|
|:Bee efe|def f2e|edB BAF|d2f edB|Bee efe|
[1def f2e|edB BAF|AFE EFA:|
[2def b2a|fed BAF|AFE EFA||', ''),
(17570, 5405, 'Edor', '|:B2E EFA|Bde ~d3|edB BAF|d2e dBA|
B2E EFA|Bde ~d3|edB BAF|AFE EFA:|
|:Bee efe|def f2e|dBB BAB|d2e dBA|
Bee efe|def f2e|dBB BAF|AFE EFA:|', ''),
(1244, 1244, 'Ador', '|:eAB c2d|edc BAG|eAB c2d|e2d eag|
eAB c2d|edc ~B3|GBd gdB|1 ~A3 ABd:|2 ~A3 A2d||
|:eaa efg|dec BAG|cBc dcd|e2d efg|
eaa efg|dec BAB|GBd gdB|1 ~A3 A2d:|2 ~A3 ABd||', ''),
(14543, 1244, 'Edor', '|:A|Bee Bcd|ABG FED|GFG AGA|B2A Bcd|
Bee Bcd|ABG FEF|DFA dAF|EFE E2:|
A|BEF G2A|BAG FED|BEF G2A|B2A Bed|
BEF G2A|BAG FEF|DFA dAF|EFE E2:|', ''),
(1426, 1426, 'Edor', '|:D|E2 FA|Be ed|Bd/B/ AF|EF D2|
E>F GA|Be ed|Bd/B/ AF|1 FE E:|2 FE E2||
|:Be ef|af ed|Be ef|af d2|
Be ef|af ed|Bd/B/ AF|1 FE EA:|2 FE E||', ''),
(3956, 1426, 'Amin', '|:A>B cd|ea ge|d>e dB|GB dB|
A>B cd|ea ge|dB gB|BA A2:|
|:ea ag/a/|ba ge|ea ag/a/|ba g2|
ea ag/a/|ba ge|d/e/d/B/ gB|BA A2:|', ''),
(544, 544, 'Gmaj', 'A|:DEF ~G3|AGE c2A|dcA d2e|fed cAG|
~F3 GFG|AGE (3Bcd e|dcA GEA|DED D2 A:|
|:dcA d2e|fed (3efg e|dcA c2d|efd ecA|
dAA d2e|fed (3efg e|dcA GEA|DED D2 A:|', 'A'),
(13502, 544, 'Gmaj', '|:A,B,C|DEF ~G3|AGE c2A|dcA d2e|fed cAG|
~=F3 GFG|AGE B/c/de|dcA GEc|DED:|D3|
|:dcA d2e|fed (3efg e|dcA c2d|e=fd ecA|
dcA d2e|1 fed e/f/ge|dcA GEc|DED D2 A
:|2 =fdA Gce|dcA GEc|DED A,B,C||', ''),
(559, 559, 'Edor', 'ba|:"Em"(ge) (ed)|"Em"(Be) (ef)|"Em"g>f ed|"Em"(ga) "B"(b>a)|
"Em"ge (ed)|"Em"(Be) e2|"B"(b>a) (gf)|1 "Em"e2 eb/a/:|2 "Em"e2 (eA)||
"Em" Be (e>f)|"Em" ed BA|"Em" Be "Bm"df|e2 (ef)|
"Em"gg/g/ "Bm"gg/g/|"Em"ed (BA)|"Em" B>E E/F/G/A/|1 "B" B2 (BA):|2 "B" B2B2||', 'ba'),
(13527, 559, 'Ador', 'A/B/|:cB AG|EA A>B|cB AG|B/c/d e>d|
cB AG|ED Dc/d/|ed cB|1 A2 A>B:|2 A2 Ac/d/||
|:ea a>b|ae ed|ea ag|a2 AB|
c2 B{c}B|Ae e>d|eA A/B/c/d/|1 e2 e>d:|2 e2 eA/B/||', 'A/B/'),
(228, 228, 'Gmaj', 'A|:~B3 GBd|cBc ABc|BdB GBd|cAG FGA|
~B3 GBd|cBc ABc|~d3 edc|1 BAF G2 A:|2 BAF G2 e||
|:~f3 fed|cBA FGA|Ggg gfg|afd d2 e|
f/g/ag fed|cBA FGA|~B3 cAF|1 AGF G2 e:|2 AGF GBd||
gdB gdB|ecA ecA|~B3 GBd|cBA FGA|
gdB gdB|ecA ecA|BdB cAF|1 AGF GBd:|2 AGF G2 A||', 'A'),
(12915, 228, 'Gmaj', '|:d/c/|BGB BGB|AFA AFA|~B3 ABA|GBd ged|
~B3 BAG|ABA DFA|ded cAF|AGF G2:|d|
~f3 fed|cAG FGA|g2g gfg|agf d2e|
f/g/fd e/f/ed|cAG FGA|BGB cAF|AGF G2:|', ''),
(4883, 4883, 'Dmaj', 'A/G/|:FA GB|Af f/e/f|Ge e/d/e/A/|Fd d/c/d/A/|
FA GB|Af f/e/f|Ge e/d/c/d/|1 ed/c/ dA/G/:|2 ed d (3A/B/c/||
K:G
|:dg B/c/d/B/|GA B2|c/B/A/B/ cc/d/|ed dB/c/|
dg B/c/d/B/|GA B2|c/B/A/B/ cF|1 AG GB/c/:|2 AG G2||', 'A/G/'),
(11663, 4883, 'Dmaj', '|:Af Ge|Fd d/c/B/A/|Ge e/d/c/B/|Ad d/c/B/A/|
Af/A/ Ge/G/|Fd d/c/B/A/|ge c/d/e/c/|df d2:|
|:dB B/c/d/B/|AF FE/F/|GE E/F/G/A/|BA/^G/ AF/A/|dB B/c/d/B/|
AF AF/A/|1 GE [C/c/][D/d/][E/e/][C/c/]|[Dd][Cc] d2:|2 ge c/d/e/c/|df d2||', ''),
(793, 793, 'Gmaj', '|:G3 GAB|AGE GED|GGG AGE|GED DEF|
G3 GAB|AGE GAB|cBA BGE|1 DED DEF:|2 DED D2B||
|:cBA BAG|ABA AGB|cBA BGE|DED GAB|
cBA BAG|ABA ABc|dcB AGE|1 GED D2B:|2 GED DEF||G6||', ''),
(13938, 793, 'Gmaj', '|:G3 G2B|AGE GED|GFG AGE|GED D2E|
G3 G2B|AGE GAB|cBA BGE|1 DED DEF:|2 DED D3||
|:c2A BAG|ABA AGE|c2A BGE|DED DAB|
c2A BAG|ABA ABc|dcA AGE|1 DED D3:|2 DED DEF||', ''),
(68, 68, 'Dmaj', 'F2 AF BFAF|F2 AF EFDE|F2 AF BFAF|G2 FG EFDE|
F2 AF BFAF|F2 AF EFD2|FAA2 BAFA|BABd eddA|
d2dA BAFA|d2 de fgfe|d2 dA BAFA|G2 FG EDFA|
d2 dA BAFA|d2 de fgfe|d2 dA BAFA|G2 FG EFDE|', 'F2 AF BFAF'),
(12522, 68, 'Dmaj', 'F2 AF BFAF|F/A/F AF EFDE|F2 AF BFAF|G2 FG EFGE|
F2 AF BFAF|F/A/F AF EFDE|FA~A2 BAFB|ABde fgfe||
d2 dA BAFA|dcde fgfe|~d3A BAFA|G2 FG EFGA|
d2 dA BAFA|dcde fgfe|dcdA BAFA|G2 FG EFGE||', 'F2 AF BFAF'),
(79, 79, 'Amin', '|:AEDE cABG|EGEC B,CDB,|A,G,A,B, CDEG|cABG ABcB:|
Aaa^g aecA|Ggg^f gdBG|Aaa^g aefd|ecdB ABcB|
Aaa^g aecA|Ggg^f gdBG|AcBd cedf|edcB ABcB|', ''),
(8544, 79, 'Bmin', '|:b~f3 dBcA|F~c3 ABcA|~B3c dcBd|cBAc Bcdc|
B~F3 dBcA|F~c3 AB(3cBA|~B3c dcBd|cBAc ~B3B:|
f~b3 bfdB|Aa^gb afee|f~b3 bfde|{e}~f2ef dBcA|
Bz~b3 fdB|Aa^gb afee|(3Bcdce dfeg|fedc ~B3B:|', ''),
(905, 905, 'Gmin', 'GA|:"Gm" B2AB G2dc|"Gm" B2AB G2d2|"Cm" e2ed "F7" c2fe|"Bb" de "F" cd "Gm" B2{c}BA|
"Gm" B2gB "Dm" A2fA|"Eb" GABG "D7" D2dc|"Gm" BABG "D7" D2[C2^F2]|"Gm" [B,4G4] [B,2G2]:|
d2|"Gm" g2g^f "D7" {a}gfga|"Bb" b2B2 B2ba|"Gm" bagf "Cm" edcB|"F" ABcA "F7" F2GA|
"Bb" [F2B2]AB "F" [F2c2]Bc|"Bb" [F2d2][F2d2] "Eb" [G4B4g4]|"Bb" [F2B2f2][F2B2] "F7" [F4A4e4]|"Bb" [F2B2d2] "Gm" G2 "Adim" [E4G4c4]|
"Gm" BcBA GABG|"D" ^FGAF "D7" D2dc|"Gm" BABG "D7" D2[C2^F2]|"Gm" [B,4G4] [B,2G2]||', 'GA'),
(7148, 905, 'Emin', '|:BA G2 F2 E2|BA G2 F2 E2|B2 c2 B2 A2|dc Bc BA G2|
B2 AB AG FA|FE DD EF G2|BA G2 FE GF|ED E2 E2 E2:|
|:B2 e2 cd e2|f2 g2 G2 G2|g2 gf ed cB|AG FG FE D2|
EF G2 FG A2|GA B2 B2 e2|c2 d2 G2 c2|dc B2 G2 A2|
BA AG FE DD|EF G2 BA G2|FE GF ED E2|E4 E4:|', ''),
(83, 83, 'Emin', '|:GA|B2A2 G2F2|EFGA B2ef|gfed edBd|cBAG A2GA|
BcAB GAFG|EFGA B2ef|gfed Bgfg|e2 E2 E2:|
|:ga|babg efga|babg egfe|d^cde fefg|afdf a2gf|
edef gfga|bgaf gfef|gfed Bgfg|e2 E2 E2:|', ''),
(12583, 83, 'Emin', '|:G>A|B2 (3ABA G2 (3FGF|E>FG>A B2 e>f|g>fe>d e>d (3Bcd|c>BA<G A2 (3FGA|
(3BcB A2 (3GAG F>G|E>FG<A B2 e>f|g2 (3fed B2 (3fgf|e>E E>^D E2:|
|:g>a|b2- b>g e2 (3fga|b>^ab>g e2 (3gfe|d3 e f3 g|a>f (3def a2 (3agf|
e^def g>fg>a|b2 (3agf g>fe>f|g>fe<d B2 (3gfg|e2 E2 E2:|', ''),
(2, 2, 'Dmaj', 'A2FA A2dB|A2FA BEE2|A2FA A2Bd|egfd edBd|
A2FA A2dB|A2FA BEE2|DEFG AFAB|defd edBd||
ADFD A2dB|ADFD BEE2|ADFD A2Bd|egfd edBd|
ADFD A2dB|ADFD BEE2|DEFG AFAB|defd efge||
a2fd edef|a2fd ed B2|a2fd edef|gefd edB2|
a2fd edef|a2fd edB2|faaf bfaf|defd edBd||
f2df e2de|f2df edBd|f2df e2de|gefd edBd|
f2df e2de|f2df edBd|faaf bfaf|defd edBd||
Adfd edfd|Adfd edBd|Adfd edfd|gefd edBd|
Adfd edfd|Adfd edB2|faaf bfaf|defd edBd||', 'A2FA A2dB'),
(12344, 2, 'Dmaj', 'dB|{G}A2FA ~A2dB|~A2FA BE~E2|~A2FB ~A2B/c/d|ed{g}fd efdB|
~A2FA- ~A2dB|AzFA BE~E2|DE{F}ED ~A3B|dzfd efdB|
AD~D2 ADBD|AD~D2 BE~E2|AD~D2 ~A3B|dzfd efdB|
AD~D2 AD~D2|AD~D2 BE~E2|~D3F ~A3B|dzfd efdf||
Ja2{g}fd efdf|adfd edB/c/d|azfd ~e3f|{g}fe{f}ed edB/c/d|
azfd efdf|adfd edB/c/d|fa~a2 bzaf|ea{g}fd efdf-||
~f2df efdf-|~f2df {f}edB/c/d|~f2df ~e3f|{g}fe{f}ed edB/c/d|
fzdf efdf-|~f2df {f}edB/c/d|fa~a2 bzaf|ea{g}fd efdB||
Ad{g}fd ed{g}fd|Ad{g}fd edB/c/d|azfd ~e3f|{g}fe{f}ed edB/c/d|
Ad{g}fd ed{g}fd|Ad{g}fd edB/c/d|fa~a2 bzaf|ea{g}fd efdB||
~A2FA- ~A2dB|~A2FA BE~E2|~A2FB AzB/c/d|gBfB eBdB|
~A2DA- ~A2DA-|~A2Fz BE~E2|DE{F}ED ~A3B|dzfd efdB|
AD~D2 ADBD|AD~D2 BE~E2|AD~D2 ~A3B|dzfd efdB|
AD~D2 ADBD|AD~D2 BE~E2|d2fd ~A3B|dzfd efdf||
Ja2fd efdf|ad{g}fd edB/c/d|azfd ~e3f|{g}fe{f}ed edB/c/d|
~a2fd efdf|ad{g}fd edB/c/d|fa~a2 bzaf|ea{g}fd efdg||
~f2df efdf-|~f2df {f}edB/c/d|fzdf ~e3f|{g}fe{f}ed edB/c/d|
~f2dz efdf-|~f2df {f}edB/c/d|fa~a2 bzaf|ea{g}fd efdB||
Ad{g}fd ed{g}fd|Ad{g}fd edB/c/d|azfd ~e3f|{g}fe{f}ed edB/c/d|
Ad{g}fd ed{g}fd|Ad{g}fd edB/c/d|fa~a2 bzaf|ea{g}fd efdB||
~A2FA- ~A2dB|AzFA BE~E2|~A2FB ~A2B/c/d|gdfd efdB|
~A2FA- ~A2dB|~A2Fz BE~E2|DE{A}FD ~A3B|dzfd efdB|
AD~D2 ADBD|AD~D2 BE~E2|AD~D2 ~A3B|dzfd efdB|
AD~D2 AD~D2|AD~D2 BE~E2|dzfd ~A3B|defd efgb||
azfd efdf|adfd edB/c/d|~a2fd ~e3f|{g}fe{f}ed edB/c/d|
azfd efdf|adfd edB/c/d|fa~a2 bzaf|ea{g}fd efdf-||
~f2df efdf-|~f2df {f}edB/c/d|~f2df ~e3f|gzfd edB/c/d|
~f2df efdf-|~f2df {f}edB/c/d|fa~a2 bzaf|ea{g}fd efdB||
Ad{g}fd ed{g}fd|Ad{g}fd edB/c/d|azfd ~e3f|{g}fe{f}ed edB/c/d|
Ad{g}fd ed{g}fd|Ad{g}fd edB/c/d|fa~a2 ba{b}af|ea{g}fd efdB||A2.F.E D4||', 'dB'),
(10, 10, 'Emin', '|:B2E G2E F3|B2E G2E FED|B2E G2E F3|B2d d2B AFD:|
|:B2d e2f g3|B2d g2e dBA|B2d e2f g2a|b2a g2e dBA:|
|:B3 B2A G2A|B3 BAB dBA|B3 B2A G2A|B2d g2e dBA:|', ''),
(12370, 10, 'Emin', '|:B2 E G2 E F3|B2 E G2 E FF/G/A|B2 E G2 E F3|B2 d d2 B AFD:|
|:B2 d e2 f g2 d|B2 d g2 e dBA|B2 d dd/e/f g2 a|b2 a g2 e dBA:|
|:B3- B2 A G2 A|B3 B^AB dB=A|BcB B2 A G2 A|Bcd g2 e dB^A:|', ''),
(29, 29, 'Ador', '|:A2B cBA|eAB cBA|GAG FGG|EGG EFG|
A2B cBA|e2d efg|age dBG|ABA A3:|
a3 age|dBd g3|gag gfe|dBA GAG|
EGG DGG|EFG ABc|Bee dBG|ABA A3:|
A2A gAf|A2A gAf|G2G eGd|G2G edB|
A2A gAf|A2d efg|age dBG|ABA A3:|', ''),
(12420, 29, 'Ador', 'E|:A2B cBA|eAB cBA|GAG EGG|DGG EGG|
A2B cBA|e2d efg|age dBG|BAG A3:|
aba age|def gfg|gag gfe|dBA GFG|
EGG DGG|EGG ABc|Bed BAG|BAG A3:|
ABA gAf|ABA edB|GFG eGd|GFG edB|
ABA gAf|ABA efg|age dBG|BAG A3:|', 'E'),
(2549, 2549, 'Gmaj', '|:GE|D2DE G2GA|BGBd cBAG|FGFE DEFG|AFdF E2GE|
D2DE G2GA|BGBd efge|dcBA GFGA|B2 G2 G2:|
|:d2|g2g2 gbag|f2f2 fagf|edef gfed|B2e2 e2ge|
dBGB d2 d2|edef g2fe|dcBA GFGA|B2 G2 G2:|', ''),
(15820, 2549, 'Gmaj', '|:D3E ~G3A|BGBd cBAG|(3FGF EF DEFG|AFdF E2GE|
D3E ~G2A|BGBd efge|dcBA GFGA|1 BGGF GAGE:|2 BGGF GABd||
|:g2gf gbag|f2fe fagf|edef gfed|Beed efge|
dBGB d2Bd|edef g2fe|dcBA GFGA|1 BGGF GABd:|2 BGGF GAGE||', ''),
(482, 482, 'Dmaj', '|:FDF F2D G2E|FDF F2D E2D|FDF F2D G2B|AFD DEF E2D:|
|:B3 BAG FGA|B2E E2F G2B|ABc dcB ABc|d2 D D2 F E2 D:|
|:fdf f2d g2e|fdf f2d e2d|fdf f2d g2b|afd def e2d:|
|:gfe dcB AGF|B2 E E2 F G2 B|ABc dcB ABc|d2 D DEF E2 D:|', ''),
(2502, 482, 'Dmaj', '|:F2 FD GE|F2 FD ED|~F2 F2 GB|AF DF ED:|
|:B2 BA GA|BE ED GA|B2 BA GB|AD DE FD:|', ''),
(312, 312, 'Gmaj', '(3def|:g2 bg d2 gd|BcdB G2 AB|cded cBAG|(3FGF EF D2 ef|
g2 bg d2 gd|BcdB GBAB|cedc BGAF|1 DGGF G2 (3def:|2 DGGF GABc||
|:dcdB gfgd|e^dec a^gae|~f3 e dfaf|gage de (3fed|
g2 bg d2 gd|BcdB GBAB|cedc BAGF|1 AGGF GABc:|2 AGGF G2 (3def||', '(3def'),
(13080, 312, 'Gmaj', '|:d2|g2bg d2gd|B2dB G2G2|F2AF D2d2|c2B2 B2d2|
g2bg d2gd|B2dB G2BG|FGAB cAGF|G2G2 G2:|
|:Bc|d2de dBGB|c2cd cAFA|GABc defg|edcB A2Bc|
d2de dBGB|c2cd cAFA|Ggec BdFA|G2G2 G2:|
|:(3def|g2bg d2gd|BcdB G2AB|c2ec A2cA|FGAB cdef|
g2bg d2gd|BcdB G2AB|cedc BAGF|A2G2 G2:|
|:Bc|dBdB g2gd|ecec a2ae|fefd gfgb|agfe defd|
g2bg d2gd|BcdB G2AB|cedc BAGF|A2G2 G2:|', ''),
(211, 211, 'Dmix', '|:B3A Bd|B3A Bd|E3B AB|D3B AG|
B3A Bd|B3A Bd|G3B A/G/F|1 G3E DG:|2 G3A Bd||
e3f ed|B3A Bd|ef ed B/c/d|
e3A Bd|e3f ed|B3A Bd|G3B A/G/F|
G3A Bd|e3f ed|B3A Bd|gf ed B/c/d|
e3A Bd|e3f ed|B3A Bd|D3B A/G/F|G6||', ''),
(12879, 211, 'Gmaj', '|:DGA|B3 A B<d|B3 A B<d|E3 cBG|A3
DGA|B3 A B<d|B3 AB<d|D3 B A/G/F|G3:|
ABd|e3 fed|B3 ABd|e3 dBd|e3 fgf|
e3 fed|B3 ABd|D3 B A/G/F|G3:|', ''),
(589, 589, 'Ddor', '|:dcAG ~F2EF|~E2 DE FD D2|dcAG FGAA|Addc d2 fe:|
|:f2fe fagf|ecgc acgc|f2fe fagf|edcG Add2:|', ''),
(13587, 589, 'Ddor', '|:d=cAG F2DF|E2CE FEFA|d=cAG F2EF|Add^c defe|
d=cAG F2DF|E2CE FEFA|dBAG F2EF|1 Add^c d4:|2 Add^c d2de||
|:fede fagf|e=cgc acgc|fede fagf|edcB Adde|
fede fagf|ecgc acgc|fedf edcB|Add^c d2de:|', ''),
(948, 948, 'Dmaj', '|:B|AFD DFA|BdB BAF|ABA F2D|FEE E2B|
AFD DFA|BdB BAF|ABA F2E|1 FDD D2:|2 FDD D2e||
|:fdd dcd|fdd d2e|fef def|gfg eag|
fed B2d|A2d F2G|ABA F2E|1 FDD D2e:|2 FDD D2||', ''),
(4322, 948, 'Dmaj', 'FG|:AFD DFA|Bcd B2A|Bcd AGF|GFG EFG|
AFD DFA|Bcd B2A|Bcd F2E|FDD D3:|
|:f3 dBA|Bdd d2e|fef def|gfg e2a|
fed B2d|A2d F2A|Bdd F2E|FDD D3:|', 'FG'),
(566, 566, 'Amix', '|:"A"EAAG ABcd|efec "D"d2 cd|"A"eAAA ABcA|"G"B=GEF "G"G2 FG|
"A"EAAG ABcd|efec "D"d2 cd|"A"eaaa afed|cA"E"BG "A"A4:|
|:"G"g2 g"G"a gfef|gfec "D"d2 cd|"A"eAAA ABcA|"G"B=GEF G2 FG|
"A"EAAG ABcd|efec "D"d2 cd|"A"eaaa afed|cA"E"BG "A"A4:|', ''),
(13540, 566, 'Amix', '|:AG|E2A2 AB cd|ef ec d2cd|e2A2 AB cA|BA EF G2 GF|
E2A2 AB cd|ef ec d2cd|e a2 b ag ed|c2A2A2:|
|:ef|gf ga gf ef|gf ec d2cd|e2A2 AB cA|BA EF G3F|
E2A2 AB cd|ef ec d2cd|e a2 b ag ed|c2 A2 A2:|', ''),
(64, 64, 'Dmaj', '|:FAAB AFED|FAAB ABde|fBBA Bcde|fBBA BcdA|
FAAB AFED|FAAB ABde|fBBA BcdB|AFEF D4:|
|:faab afde|fdad fd d2|efga beef|gebe gfeg|
fgaf bfaf|defd e2 de|fBBA BcdB|AFEF D4:|', ''),
(12512, 64, 'Dmaj', '|:E|FAAB AFED|FAAB A2de|fBBA Bcde|fdgf efdB|
FAAB AFED|FAAB A2de|fBBA BcdB|AFEF D3:|
e|faag fdde|fdad fdd2|efga beef|gebe gee2|
faaf b2af|defd e2de|fBBA BcdB|AFEF D3:|', ''),
(69, 69, 'Edor', '|:E3B2AFD|EDEB BAFD|E3B2AFA|BcdB AFDF:|
B2eB fBeB|B2eB AFDF|B2eB fBeB|BcdB AFDF|
B2eB fBeB|B2eB AFDF|Bdeg fdec|d2dA BAFD|
B2EB GBEB|B2EB AFDF|B2EB GBEB|BcdB AFDF|
B2EB GBEB|B2EB AFDF|Bdeg fdec|d2dA BAFD|
|:BAGF EFGA|B2GB A2GA|BAGF EFGA|BcdB AFDF:|', ''),
(12525, 69, 'Dmin', '|:D3A zG FE|DE FA GE FC|D3A zG FG|AB cA GE FC:|
G_A dc eg dc/_e/|_zd zc AG FG|Ac df de e2|c3A GE FG|
G_A dc eg dc/_e/|_zd dc zG FG|G/8A/1c df e3d|z3A GE FG|
G/4G3/4F GF DE FG|A2 FA GA =B/4A3/4F|GF GF DE FG|AF cA G2 FG|
G/4G3/4F GF DE FG/B/|z2 FA GA A/4G3/4F|G/8G/1F GF DE FG/B/|zF cA G2 FG||', ''),
(1615, 1615, 'Dmaj', '|:E2EF A2AB|ceec BAF2|f2 ec ABcA|ecBA FAAF|
E2EF A2AB|ceec BAF2|f2 ec ABcA|1 ecBc A2AF:|2 ecBc A4||
|:ecef a2 af|ecBA FAAB|cBAB cBBA|cABA ceaf|
ecef a2 af|ecBA FAAB|cBAB cBBA|1 ceBc A4:|2 ceBc A2AF||', ''),
(15025, 1615, 'Dmaj', '|:E2EF A2AB|ceec BAF2|f2 ec ABBA|ecBA FAAF|
E2EF ~A3B|ceec BAF2|f2 ec ABBA|1 ecBc A2AF:|2 ecBc A4||
|:e2ef a2 af|ecBA FAA2|cBAB cBBA|ceBA faaf|
e2ef ~a3f|ecBA FAA2|cBAB cBBA|1 ceBc A4:|2 ceBc A2AF||', ''),
(2576, 2576, 'Edor', '|:BEF GFE|FEF def|edB BAF|AFE FED|
BEF G2 A|FEF def|edB {d}BAF|AFE E2 A:|
|:B2 e ede|fef d2 f|edB BAF|AFE FGA|
Bee ede|fef def|edB BAF|AFE E2 A|
Bee ede|~f3 def|edB BAF|AFE FED|
B,EF GFE|~F3 def|edB {d}BAF|AFE EFA|', ''),
(15842, 2576, 'Ddor', '|:ADE FDE|~E3 cde|dcA AGE|GED EDC|
ADE F2 G|EDE c2 e|dcA AGE|GED D3:|
A2 d dcd|ede c2 e|dcA AGE|GED EFG|
Add dcd|ede cde|dcA AGE|GED DE/F/G|
A2 d dcd|ede c2 e|dcA AGE|GED EDC|
A,DE FED|~E3 cde|dcA AGE|GED D3||', ''),
(711, 711, 'Emin', '|:E2 B^c dBBB|dBAF DEFD|E2 B^c dBBB|dBAF BEED|
E2 B^c dBBB|dBAF DEF2|afge fde^c|dBAF DEFD:|
B/^c/d ef gfed|B2 AF DEFD|B/^c/d ef gfed|B2 Ac BE E2|
B/^c/d ef gfed|B2 AF DEFD|afge fde^c|dBAF DEFD:|', ''),
(13772, 711, 'Emin', '|:E2BE [Dd]EBE|dBAF DEFD|E2BE [Dd]EBE|dBAF BEED|
E2BE [Dd]EBE|dBAF DEFA|afge fdec|dBAF BEE2:|
;e3f gfec|dBAF DFGD|Beef gfec|dBAF BEE2|
Beef gfec|dBAF DFGA|afge fdec|dBAF BEE2:|', ''),
(113, 113, 'Edor', '|:EBBB dBBB|EBBB FAFA|BE E2 BABc|dfed BAFA:|
Beed e2 de|fede fe e2|febe febe|fede fee2|
Beed e2 de|fede fa a2|b2bf a2af|egfe dBAF|', ''),
(12699, 113, 'Edor', '|:EBBB dBBB|EBBA FEFA|BE E2 BABc|1 d2 fe dBAF:|2 d2 fe dBAd||
Beed e2 de|fede fe e2|febe febe|fede fe e2|
Beed e2 de|fede fgaf|b2 bg a2 af|egfe dBAF||', ''),
(238, 238, 'Ador', '|:E>A AB|cd e2|G>F GA|GF ED|
E>A AB|cd ef|ge dB|A2 A2:|
|:a2 ab|ag ef|g2 ga|ge de|
ea ab|ag ef|ge dB|A2 A2:|', ''),
(12940, 238, 'Ador', '|:"Am"EA AB|cd e2|"G"G>F GA|GE ED|
"Am"EA AB|B/c/d ef|"G"g/f/e"Em" dB|"Am"A2 A2:|
|:"Am"a>g ab|ag ef|"G"g>f ga|ge d2|
"Am"ea ab|ag ef|"G"ge "E7"dB|"Am"A2 A2:|
|:"Am"c2 "Em"Bc/B/|"Am"AB/A/ G>A|"G"Bd ed|g2 gd|
"Am"e/g/a "Em"ge|"G"dB GA/B/|"Am"ce "Em"dB|"Am"A2 A2:|
|:"Am"ea ag/e/|"G"dg ge/d/|"Am"ea ab|"Em"g2 ed|
"Am"ea "Em"g/a/g/e/|"G"dB GA/B/|"Am"ce "Em"dB|"Am"A2 A2:|', ''),
(1197, 1197, 'Ador', 'A2 Ac B2 AG|EGGF G2 AG|EA ~A2 BGBd|egdB BAGB|
AGAc BGAG|EGGF G2 AB|c2 ec B2 GB|dBGA BAGB||
A2 Bd egdB|GBd^c defg|agfd egdB|GBdB BA A2|
~a2 fd egdB|GBd^c defg|afge fdef|g2 ag gedB||', 'A2 Ac B2 AG'),
(1939, 1197, 'Ador', '~A3B B2AG|EG~G2 EGBG|A2AB B2AB|egdB BAAG|
~A3B B2AG|EG~G2 EGBG|cEGc dB~B2|dBAG EAAG|
A2 (3Bcd egdB|GB~B2 defg|a2gd egdB|GBdB BAA2|
a2gd egdB|GB~B2 defg|a2gd egdB|fggf gedB|', '~A3B B2AG'),
(440, 440, 'Gmaj', 'GE|:DB,DE G2 GA|(3BBB dB ABGA|BAGE DB,DE|G2 BG ABGE|
DB,DE GFGA|B2 dB ABGA|BAAB G~E3|1 ABGF G2 EG:|2 ABGF ~G3A||
|:BG (3Bcd edeg|a2 ge gfeg|a2 af ~g3e|dBgB BAGA|
BG (3Bcd edeg|abge gfeg|abge dBGB|1 ABGF ~G3A:|2 ABGF GAdc||
|:BGGA BGBd|e~g3 egdc|BGEG DGBG|FAAG FADA|
BGGA BGBd|e~g3 efga|bgaf gedB|1 ABGF GAdc:|2 ABGF G EG||', 'GE'),
(13300, 440, 'Gmaj', '|:GE|D3E GEGA|B2dB ABGB|ABGE DB,DE|G2BG ABGE|
DB,DE GEGA|B2dB ABGA|B2AB GEBG|ABGE G2:|
|:GA|BABd edeg|abge g2eg|a2eg gage|dedB A2GA|
BABd edeg|abge g2eg|a2ge d2BG|ABGE G2:|
|:dB|BAG2 DGBd|egg2 egdB|BAG2 DGBG|EAA2 EAA2|
BGG2 DGBd|egg2 egdg|b2ag egdB|ABGE G2:|', ''),
(514, 514, 'Ador', '|:EAAG ~A2Ad|eg~g2 (3efg ed|BGGF {A}G2GE|DEGA BA~A2|
EAAG {B}A2Bd|eg~g2 eg~g2|eggf gaba|1 gedB BAAG:|2 gedB BAeg||
|:a2eg ageg|agbg agef|~g2eg dgeg|gbaf gedg|
a2eg ageg|agbg aged|eg~g2 gaba|1 gedB BAeg:|2 gedB BAFA||', ''),
(837, 514, 'Ador', '|:A2BG A2Bd|egdg eGGD|~G3D G2AB|cABA GEDE|
A2BG A2Bd|egdg eaae|gedB c2{B}cd|1 egdB BAGE:|2 egdB BAA2||
abae abae|gaba gede|~g3d g2Bd|gaba ged2|
abae abae|gaba gede|gedB c2{B}cd|1 egdB BAA2:|2 egdB BAGE||', ''),
(634, 634, 'Gmaj', '(3GGG dG eGdG|(3GGG dB AGEF|GFGA BABd|gedB AGEF|
(3GGG dG eGdG|(3GGG dB AGEF|GFGA BABd|gedB A2 Bd||
gfgb a2ab|gabg agef|~g3 b a2ab|gedB A2 Bd|
gabg gabg|gabg a2ga|bgag (3efg fa|gedB AGEF||', '(3GGG dG eGdG'),
(3332, 634, 'Gmaj', '|GGdG eGdG|GBdB AGEF|GGGA BABd|eedB AGEF|
GGdG eGdG|GBdB AGEF|GGGA BABd|eedB AAef|
gggb aaab|gabg agef|gggb aaab|gedB A3 g|
gabg gabg|gabg aaga|bgab gede|gedB AGEF||', ''),
(1936, 1936, 'Gmaj', '|:G2GA BGG2|ABcd eAAB|c2ec B2dB|1 AcBA GEDE:|2 AcBA GED2||
|:g2ga ged2|eaab agef|g2ga gedB|1 AcBA GED2:|2 AcBA GEDE||', ''),
(15356, 1936, 'Gmaj', '|:G>ABA BGGB|Aeed eAAB|c>Bce d/c/B/A/ GB|1 AcBA GEEF:|2 AcBA GEE2||
g>fga gddg|eaag aeef|g>age d/c/B/A/ GB|1 AcBA GEE2:|2 AcBA GEEF||', ''),
(829, 829, 'Dmix', '|:A2G ADD|A2G Adc|A2G ADD|EFG EFG:|
AdB c3|Add efg|AdB c2A|GEG AED|
AdB c3|Add efg|age dcA|GEG AED||', ''),
(22286, 829, 'Emix', '|:B2A BEE|B2A Bed|B2A BEE|FGA FGA:|
Bec d3|Bee fga|Bec d2B|AFA BFE|
Bec d3|Bee fga|baf edB|AFA BFE||', ''),
(441, 441, 'Dmaj', 'dd B/c/d/B/|AF ED|dd B/c/d/B/|AF E2|
dd B/c/d/B/|AF Ad|fd ec|d2 d2||
fd de/f/|gf ed|fd de/f/|gf a2|
fd de/f/|gf ed|fd ec|d2 d2||', 'dd B/c/d/B/'),
(13304, 441, 'Dmaj', 'dd Bd/B/|AF AF|dd B/c/d/B/|AF ED|
dd B/c/d/B/|AF Ad/e/|fd ec|d2 d2|
d2 Bd/B/|AF A/B/c|d2 B/c/d|AF E/F/E/D/|
dd B2|A/B/A/F/ A>e|fd ec|d>A B/c/d/e/||
fd- de/f/|g/a/g/f/ ed/e/|fd ad/e/|fd/f/ aa/g/|
fd d>f|gf e2|fd e/d/c|d2 de|
f2 fd/f/|gf ed|fd Ad|fd/f/ a/b/a/g/|
f/g/f/e/ de/f/|g>f ea/g/|f2 e/d/c|d4||', 'dd Bd/B/'),
(52, 52, 'Emin', '|:EFE FEF G2 F|E3 cBA BGE|EFE FED G2 A|BAG FAG FED:|
|:BGB AFA G2 D|GAB dge dBA|BGB AFA G2 A|BAG FAG FED:|
|:gfg efe e2 f|gfg efg afd|gfg efe e2 a|bag fag fed:|
|:eBB e2f g2f|eBB efg afd|eBB e2f g2a|bag fag fed:|
|:edB dBA G2D|GAB dge dBA|edB dBA G2A|BAG FAG FED:|', ''),
(12488, 52, 'Emin', '|:E3 FEF G2 F|E2 E BcA BGE|E^DE F^EF G2 A|BAG F/G/AG FED:|
|:B2 B AF/G/A G2 D|G2 B dge dBA|BG/A/B AFA G2 A|BAG FAG F2 D:|
|:g*fg eBe e2 f|g2 g ee/f/g afd|gag eB/^c/d e2 g/a/|bag f/g/ag f2 d:|
|:eBB e2f g>fg|e2 B efg a>fd|eBB e2f g2 a|b>ag fag fed:|
|:edB d2 A G3|G2 B dge dB/c/d|e2 B dBA G2 A|BB/A/G F>AG FED:|
|:B,EE EcA B2 ^A|B,EE E2 F/G/ AFD|B,2 E EE/F/G A2 G|B2 G A2 G F>GA:|', ''),
(475, 475, 'Edor', '|:B,2|EDEF GFGA|B2B2 G2GA|B2E2 EFGE|FGFE D2B,2|
EDEF GFGA|BAGB d3c|B2E2 GFE_E|E6:|
|:d2|e2e2 Bdef|gagf e3f|e2B2 BABc|dedc BcdB|
e2B2 Bdef|gagf efed|Bdeg fedf|e6 ef|
g3e f3d|edBc d3e|dBAF GABc|dBAF GFED|
B,2E2 EFGA|B2e2 edef|e2B2 BAGF|E6:|', ''),
(13361, 475, 'Edor', '|:z>B|E>^DE>F G>FG>A|B2- B>A G>FG>A|B>E (3EEE E>F (3GFE|F>GF>E D2- D>B|
.E<zE>F .G<zG>A|B>AG>B d2- d>=c|B2 E2 G<FE>^D|E2 E2 E2:|
|:(3Bcd|e2 B2- B>de>f|g>ag>f e>fe>^d|e2 B2 B>^AB>c|d2 d>c B>c (3dcB|
e2 B2 (3Bcd e>f|g>ag>f e>fe>d|(3Bcd e>g f>e (3def|e2- e>^d e2 e>f|
g2- g>e f2 f>d|e>dB>c d2- d>e|d>BA>G F<GA>B|d>BA>F G<FE>D|
B>E (3EE^D E>FG>A|B2 e2 e>^de>f|e2 B2- B>AG>F|E2 (3EEE E2:|', ''),
(264, 264, 'Emin', '|:E2F G2A|B2A B^cd|DED F2G|AdB AFD|
E2F G2A|B2A B^cd|edB cBA|BGE E3:|
|:e2f g2e|fag fed|e2f g2e|fdB B2B|
e2f g2e|fag fed|edB cBA|BGE E3:|', ''),
(13003, 264, 'Emin', '|:EFE G2A|B2A B^cd|D2E F2G|ABA AFD|
EFE G2A|B2A B^c^d|e=dB =cBA|BGE E2:|
|:d|e2f gfg|eag fe^d|e2f gfg|fdB B3|
e2f gfg|eag fe^d|e=dB cBA|BGE E2:|', ''),
(883, 883, 'Ador', '|:eA~A2 e2dc|BAGA Bcdg|eA~A2 e2dc|BAGA BA~A2|
eA~A2 e2dc|BAGA Bcd2|~e3f gaaf|gedB A2 (3Bcd:|
eaag egdc|BAGA Bcdg|eaag egdc|BAGA BA~A2|
eaag egdc|BAGA Bcd2|~e3f gaaf|gedB A2 (3Bcd|
eaag egdc|BAGA Bcdg|eaag a2ga|bagb ~a3g|
eaag egdc|BAGA Bcd2|~e3f gaaf|gedB A2 (3Bcd||', ''),
(14065, 883, 'Ador', '|:eaag egdc|BAGA Bcdg|eaag egdc|BAGA A2 (3Bcd|
eaag egdc|BAGA Bcd2|~e3f gaaf|gedB A2 (3Bcd:|
|:eaag egdc|BAGA Bcdg|eaag a2ga|bagb ~a3g|
eaag egdc|BAGA Bcd2|~e3f gaaf|gedB A2 (3Bcd:|', ''),
(432, 432, 'Ador', '|:EA~A2 BA~A2|EA~A2 BGAG|EG~G2 AG~G2|EG~G2 EGDG|
EA~A2 BAAG|EA~A2 BABd|efge afge|1 dBGB ~A3G:|2 dBGB A2dB||
|:~A3B dBAB|G2BG DGBG|~A3B dGBd|1 e~g3 gedB:|2 edge d2 Bd||
|:ea~a2 bgaf|gfed GABd|ea~a2 bgaf|gede g2eg|
~a3f ~g3e|dedB GABd|eA~A2 efge|1 dBGB A2 Bd:|2 dBGB ~A3G||', ''),
(21878, 432, 'Ador', '|:AG|EA~A2 BGAG|EA~A2 B2AG|EG~G2 AGBG|cGBG AGED|
EA~A2 BGAG|EA~A2 B2Bd|eg~g2 afge|dBGB A2:|
zG|~A2AB dBAF|~G2GB dG (3BAG|~A2AB ~d2cd|eg~g2 gedB|
~A2AB dBAF|~G2GB dG (3BAG|~A2AB ~d2cd|eg~ge d2||
(3Bcd|ea~a2 bgab|gedB GA (3Bcd|eaag agba|gede ga (3bag|
a2af ~g2ge|d2dB GA (3Bcd|eA~A2 egge|dBGB A2:|', ''),
(1511, 1511, 'Emin', '|:~e3 dBA|BAG EDB,|DEG Eed|BAG ABd|
dee dBA|BAG EDB,|DEG Eed|BAF ~E3:|
|:~e3 gfe|beg fed|Beg beg|fed e2f|
~g3 edB|BAF DFA|d2e fed|BAF ~E3:|', ''),
(12158, 1511, 'Dmaj', '|:dBA BAG|EDB, DEG|Eed BAG|ABd ege|
fBA BAG|EDB. DEG|Eef BAG|1 E2 A B2 e:|2 e3 z2 d||
|:e2 f gfe|beg fed|Beg beg|fed e2 f|
g2 f edB|AFD DFA|dcd fed|1 AFE D2 d:|2 AFE D3||', ''),
(70, 70, 'Gmaj', '|:D|GAB G2B c2A BGE|GAB DEG A2A AGE|
GAB GAB cBA BGE|GAB AGF G3 G2:|
|:A|BGG AGG BGG AGG|GAB DEG A2A AGA|
BGG AGG BGG AGG|GAB AGF G3 G2:|
|:d|g2g a2a bag edB|g2g gab a2a agf|
g2g f2f ege dBA|GAB AGF G3 G2:|', ''),
(12535, 70, 'Gmaj', '|:GAB DED ~c2A BGE|GAB DED ~A2B AGE|
GAB DED ~c2A BGE|GAB DED ~G3 G3:|
|:G2B ~d3 edB d2B|G2B d2B ~A3 AGE|
~G2B ~d3 edB d2B|GAB ~D3 ~G3 G2D:|
|:~G2B d2d edB ~g2e|dBA GBd ~e2f g2g|
ged BAB d2B AGE|GAB DED ~G3 G2D:|', ''),
(72, 72, 'Dmaj', '|:AB|d2dA BAFA|ABdA BAFA|ABde fded|Beed egfe|
d3A BAFA-|ABdA BAFA-|ABde fdec|dBAF D2:|
|:fg|a2ag f2fe|d2dA BAFA-|ABde fded|Beed egfg|
abag fgfe|dcdA BAFA|ABde fdec|dBAF D2:|', ''),
(12541, 72, 'Dmaj', '|:d3 A BAFB|A2 dA BAFB|ABde fded|Beed egfe|
d3 A BAFB|A2 dA BAFB|ABde fedB|1 AFEF D3 z:|2 AFEF D3 e||
faag ~f3 e|d2 fd efdB|ABde fded|Beed egfg|
~a3 g ~f3 e|d2 fd efdB|ABde fedB|1 AFEF D3 e:|2 AFEF D3 z||', ''),
(527, 527, 'Gmaj', '|:DGG GAG FGA|BGG GAB ~c3|DGG GAG FGA|BAB cAF G2 E:|
|:DED cAG FED|DED cAB ~c3|DED cAG FGA|BAB cAF G2 E:|', ''),
(993, 527, 'Gmaj', '|:DGG GAG FGA|BBB GAB ~c3|DGG GAG FGA|BAB cAF G2 E:|
|:ded cAG FED|ded cAB ~c3|ded cAG FGA|BAB cAF G2 E:|', ''),
(67, 67, 'Emin', '|:BGE F2E|BGE FGA|BGE F2E|AFD FGA|
GBE F2E|BGE FGA|d^cd ABG|FDF AGF:|
|:EGB efg|fed edB|EGB dBG|FDF AGF|
EGB efg|fed edB|d^cd ABG|FDF AGF:|
|:g2e efe|gfg bge|g2e efe|fdf afd|
g2e efe|gfg bge|d^cd ABG|FDF AGF:|
|:EGB edB|dBG AFD|EGB dBG|FDF AGF|
EGB GBd|Beg efg|d^cd ABG|FDF AGF:|', ''),
(12519, 67, 'Gmaj', '|:G|B2e dBG|A>BA A2G|B2e dBG|d>BB TB2
A|B2e dBG|A>BA g2a|g>eg dBG|B>cB B2:|
G|g2g gab|d>ed dBG|g2g gab|g>ee e2
d|def gfe|def g>ab|g>eg dBG|B>cB B2:|
G2e dBG|~B3 dBA|G2e dBG|~A3 BGE|
G2e dBG|~B3 deg|age dBG|~A3 BGE:|
~g3 faf|e/f/ge def|gfg efg|aga bge|
gbg f/g/af|ege deg|age dBG|~A3 BGE:|', ''),
(828, 828, 'Dmaj', '|:~B3 A BGEF|~G2 Bd ef{b}gd|~B3 A BGEF|GB{c}AF ~G3 A:|
(3Bcd ef ~g3 e|~f3 e {a}edBG|(3Bcd ef g2 fg|{c''}afdf ~e3 d|
(3Bcd ef ~g3 e|~f3 e {a}edBG|Bddc d3 e|f ~a3 gfed||', ''),
(13979, 828, 'Dmaj', '|:GA|B2 BA BGEF|G2Bd efgd|B2BA BGEF|GBAF G2GA|
B2BA BGEF|GABd efgd|B2 BA BGEF|GBAG G2:|
|:GA|Bdef g2 ef|f2df edBA|Bdef gfga|afdfe2ed|
Bdefg2eg|f2ef edBA|Bdd{e}c deef|g{e}faf e2:|', ''),
(1091, 1091, 'Gmaj', '|:DGBG ^DGcG|DGBG AGFG|c3A (3Bcd gb|aged BAGE|
DGBG ^DGcG|DGBG AGFG|cBAc BAGB|ADEF G3z:|
|:~d2 bd adgd|~d2 bd adgd|~e2 c''e beae|~e2 c''e beae
~d2 bd adgd|~d2 bd adgd|cBAc BAGB|ADEF G3z:|
|:Bd~d2 ed~d2|Bd~d2 edcB|ce~e2 fe~e2|fefe fedc
Bd~d2 ed~d2|Bd~d2 edcB|cBAc BAGB|ADEF G3z:|', ''),
(14330, 1091, 'Gmaj', 'DGBG EGBG|DGBG dGBG|AeeA (^de)Ae|eABe d/c/B G/F/E|
DGB(^D E)GBG|DGBG FGBG|AB ~d2 efge|aged BA G/F/E||
DGB(^D E)GBG|DGBG E/E/G BG|A2 ~d2 ^cAAe|eABd ^cAGE|
DGB(^D E)GBG|D/D/G BG G,GBG|A2 ~d2 efge|aged [^cg]def||
~g2 ab g ~d3|^cdgd BGGB|AB ~a2 ^gaba|a2 ^gb a=gef|
~g2 ab g~d3|gdgd BGGB|AB ~d2 efge|aged [^cg]def||
~g2 ab gdgd|^cdgd BGGB|A2 ~a2 ^gaba|a2 ^gb a=gef|
~g2 ab g~d3|gdgd BGGB|A2 ~d2 efge|aged BAGE||
DGBG EGBG|DGBG E/E/G BG|A2 eA ^efBg|gc^ga BA =G/F/E|
DGB(^D E)GBG|DGBG F/F/G BG|A2 ~d2 efge|aged BA G/F/E||
D3B E2B2|DGBG E/E/G BG|Ae^eB fc^cg|d^gad BA=GB|
D2 G/G/B EGBG|DGBG G,GBG|A~d3 efge|aged [^cg]def||
g2 ab g~d3|^cdgd BGGB|A2 ~a2 ^gaba|a2 ^gb a=gef|
~g2 ab gdad|ad^cd BGGB|AB ~d2 efge|aged [^cg]def||
~g2 ab g~d3|gdgd BGGB|AB ~a2 ^gaba|~a2 ^gb a=gef|
g2 ab g~d3|g~d3 BGGB|AB ~d2 efge|aged BAB^c||
d2 bd db^cd|bdbd ^cd^dd|e2 c''e ec''ec''|c''ec''c'' ec''c''e|
d2 bd bd^cd|bdbb ^cdbd|^cdbd b^c''ba|g/g/e dB dG E/E/^C||
[d2D2]bd db^cd|bdbd ^cd^dd|e2 c''e c''c''ec''|c''ec''c'' ec''c''e|
d2 bd db^cd|bd^cd bdbd|^cdbd b^c''ba|gedB D3 B||
DGBG EGBG|DG B2 DG B/B/G|AeeA (^de)Ae|eABd ^cA G/F/E|
D2 G/G/B EGBG|DGBG FGBG|AB ~d2 efge|aged BAGE||
D4 E2 B2|DGBG G,GBG|Ae^eB fc^cg|d^gad BA =G/G/B|
DG B/B/B EGBG|D/D/G BG G,GBG|AB ~d2 efge|aged [^cg]def||
~g2 ab g~d3|gdgd BGGB|A2 ~a2 ^gaba|a2 ^gb a=gef|
~g2 ab g~d3|gdgd BGGB|AB ~d2 efge|aged [^cg]def||
~g2 ab g~d3|^cdgd BGGB|A2 ~a2 ^gaba|~a2 ^gb a=gef|
~g2 ab gd B/c/d|gdgd BGGB|A2 ~d2 efge|a^ged BAB^c||
d2 bd db^cd|bdbd ^cd^dd|e2 c''e ec''ec''|c''ec''c'' ec''c''e|
d2 bd db^cd|bdbd ^cdbd|^cdbd b^c''ba|gedB DDB^c||
d2 bd db^cd|bdbd ^cdbd|e2 c''e c''c''ec''|c''ec''c'' ec''ec''|
d2 bd db^cd|bd^cd bdbd|^cdbd b^c''ba|gedB [G4B,4]||(3fga [b2g2] [a2e2] [g2e2]||', 'DGBG EGBG'),
(76, 76, 'Dmaj', '|:fdd cAA|BGG A2G|FAA def|gfg eaa|
fdd cAA|BGG A2G|FAA def|gec d3:|
|:FAA Add|FAA BGG|FAA def|gfg eaa|
fdd cAA|BGG A2G|FAA def|gec d3:|', ''),
(12562, 76, 'Dmaj', 'e|:fdd cAA|BAG A2 G|FGA def|~g3 eag|
fdd cAA|BAG A2 G|FGA def|1 gec d2:|2 gec d2 A||
|:FAA Bcd|FAA BAG|FGA def|ge/f/g eag|
fdd cAA|BAG A2 G|FGA def|1 gec d2 A:|2 gec d2 e||', 'e'),
(398, 398, 'Emin', '|:E2E GFE|DED DED|E2E GFE|ABG AFD|
E2E GFE|DEF DEF|G2E FED|DFD E3:|
|:edB BAF|E2D DEF|edB BAF|AFA d2f|
edB BAF|E2D DEF|G2E FED|DFD E3:|', ''),
(13240, 398, 'Edor', '|:E3 GFE|DB,E DB,D|E3 GFE|ABG AFD|
E2F GFE|DB,E DEF|G2E FED|B,ED E3:|
|:edB BAF|EDB, D3|edB BAF|ABc def|
edB BAF|EDB, DEF|G2E FED|B,ED E3:|', ''),
(89, 89, 'Dmaj', '|:F2F AFF|dFF AFF|G2G ABc|ded cAG|
FEF AFF|dFF AFF|GFG BAG|FDD D3:|
|:d2e fed|ecA ABc|dcd fed|faf gfe|
d2e fed|ecA BAF|GFG BAG|FDD D3:|', ''),
(12626, 89, 'Fmaj', '|:F2F AGF|cAG AGF|G2G A2B|d2d cAG|
F2F AGF|cAG AGF|G2A BAG|AFD D3:|
|:~f3 fcF|FAc fcA|G2G A2B|d2d cAG|
[1 ~f3 fcF|FAc fcA|G2A BAG|AFD D3:|
[2 fef gfg|afd cAF|G2A BAG|AFD D3||
d2e fed|ede A=B^c|d2e fed|g2g gec|
d2e fed|ede A2=B|G2A BAG|AFD D3||
d2e fed|ede A=B^c|d2e fed|afa def|
afd gec|fed cAF|G2A BAG|AFD D3||', ''),
(515, 515, 'Dmaj', '|:F2 E EDE|F2 D DED|F2 E EFA|d2 e fdA|
F2 E EDE|F2 D DED|AFE EFA|B3 d3:|
|:ABd e2 f|d2 cB2 A|ABd e2 f|d2 A B3|
ABd ede|fdB BAF|AFE EFA|B3 d3:|', ''),
(5954, 515, 'Dmaj', '|:A|F2 E EDE F2 D D2 E|F2 E D2 A d2 B B2 A|
F3 EDE F2 D D3|F2 D d2 A B3- B2:|
|:A|F2 d- d2 e f2 e efe|ded cBA d2 B B2 A|
F3 dcd f2 e edc|1 d2 d cBA B2 c cB:|2 dcd cBA B3 B2||', ''),
(399, 399, 'Ador', '|:A2BA (3B^cd ef|gedB AGEF|G2BG dGBG|DEGA BAdB|
A2BA (3B^cd ef|gedB AGEG|B3G A2GE|DEGA BAA2:|
|:eaag a2ga|bgaf gfed|eggf g2ge|dega bgag|
eaag a2ga|bgaf gfed|eg (3gfg edBA|dBgB BAA2:|', ''),
(13245, 399, 'Ador', '|:A2BA Bdef|gedB AGEF|G2BG DGBG|DEGA BddB|
A2BA Bdef|gedB AGEG|AB3 AEGE|DEGA B2AB:|
|:eaag a2ga|(3bag gf gedg|eggf g2ge|dega bgag|
eaag a2ga|(3bag gf gedg|egg2 edBc|dBgB BAA2:|
|:A2BA Bdeg|gedB AGEF|G3B AEE2|DEGA BddB|
A2BA Bdeg|gedB AGEG|AB3 AEGE|DEGA BAA2:|', ''),
(8895, 8895, 'Edor', '|:BE FE|BE G/F/E|D>E FA|DE FA|
BE G/F/E|BE FE|D>E FA|1 FE EF/A/:|2 FE E2||
|:ee/e/ dB|ee/e/ dB|AF dF|AB/c/ df|
ee/e/ dB|ee/e/ dB|AF dF|1 FE gf:|2 FE E2||', ''),
(16296, 8895, 'Ador', 'd|:eA BA|eA BA|G>A Bd|G>A Bd|
eA BA|eA BA|G>A Bd|1 BA Ad:|2 BA Af||
|:a2 gf|a2 gf|dB GA|Bc de|
a2 gf|a2 gf|dB gB|1 BA Af:|2 BA Ad||', 'd'),
(112, 112, 'Emin', '|:EGBE G3 B|A3 B AGFG|EGBE G3 B|AGFG E4:|
|:EGBG c3 A|B3 d AGFG|EGBG c3 A|BAGB A4:|
|:FGBF GBGF|EFGE FGFE|DFAD FADF|AGFG E4:|', ''),
(12697, 112, 'Emin', '|:Bc|~d3e dcBd|c2cA BGGF|EGBG ~c3d|BAGB A2:|
|:GE|DAAG ~A2cA|~B2dB ceGB|DAAG ABcA|BdcB A2:|', ''),
(1849, 2192, 'Gmaj', '|:GA|~B2eB dBAc|~B2GB AGEG|DGGF GA B/c/d|egdB ADGA|
B2ge dBAc|~B2GB AGEG|DGGF GA B/c/d|egdB G2:|
|:zA|BG~G2 gG~G2|gGeg dG~G2|GFGA ~B3d|eaag a2ga|
bgab ge~e2|gdeg dG~G2|~G2EG Dege|dBAB G2:|', ''),
(2192, 2192, 'Gmaj', '|:B2 ge dBGA|B2 GB AGEG|DGGF GABd|egdB ABGA|
B2 ge dBGA|B2 GB AGEG|DGGF GABd|egdB G2 GA:|
|:BG G2 gG G2|g2 eg dBGA|B2 BA Bcdg|eaag a2 ga|
b2 ab agef|g2 eg dB G2|G2 EG DEGe|dBAB G2 GA:|', ''),
(5252, 5252, 'Ador', '|:A2 e2 e2 dB|d2 ef ge a2|A2 e2 e2 dB|eg ed BA GB|
A2 e2 e2 dB|d2 ef ge a2|eg ed e/f/g ed|B2 A2 A2 BG:|
A2 a2 a2 ge|d2 ef ge a2|A2 a2 a2 ge|dg ed BA GB|
A2 a2 a2 ge|d2 ef ge a2|eg ed e/f/g ed|B2 A2 A2 BG:|', ''),
(17495, 5252, 'Ador', '|:A2 e2 e2 dB|d2 ef ge a2|A2 e2 e2 dB|g2 ed B2 AG|
A2 e2 e2 dB|d2 ef ge a2|ge dB e/f/e fd|ef dB A3 G|
A2 e2 e2 dB|d2 ef ge a2|A2 e2 e/f/e dB|g2 ed B/c/B AG|
A2 e2 e2 dB|d2 ef ge a2|ge dB g2 ed|B2 A2 A2||
A2 a2 a2 ge|d2 ef ge a2|A2 a2 a2 ge|dg ed B/c/B A2|
A2 a2 a2 ge|d2 ef ge a2|ge dB g2 ed|B/c/B A2 A2:|
A2 e2 e2 dB|d2 ef ge a2|A2 e2 e2 dB|d2 ed B2 A2|
A2 e2 e2 dB|d2 ef ge a2|ge dB g2 ed|B2 A2 A2 BG|
A2 e2 e2 dB|d2 ef ge a2|A2 e2 e2 dB|g2 ed B2 AG|
A2 e2 e2 dB|d2 ef ge a2|ge dB g2 ed|B2 A2 A2||
A2 a2 a2 ge|d2 ef ge a2|A2 a2 a2 ge|dg ed B/c/B A2|
A2 a2 a2 ge|d2 ef ge a2|ge dB g2 ed|B/c/B A2 A2:|
A2 e2 e2 dB|d2 ef ge a2|A2 e2 e2 dB|g2 ed B2 AG|
A2 e2 e2 dB|d2 ef ge a2|ge dB e2 fd|ef dB A3 G||', ''),
(703, 703, 'Gmin', '|:DGGF DGGF|DFGA B/A/G AF|DGGF DGGF|DCB,C B,A,B,A,|
DGGF DGGF|DFGA B/A/G Ac|dcBc BAGF|1 DGGF G2 G2:|2 DGGF GABc||
dGGc GGBG|GAGG GABc|dFFc FFBF|FAFF GABc|
dEEc EEBE|EAEE GABc|dcBc BAGF|1 DGGF GABc:|2 DCB,C B,A,B,A,||', ''),
(13767, 703, 'Gmin', 'dG Gc G G BG|GA G G G ABc|dF Fc F F BF|FA F F G ABc|
dE Ec E E BE|EA E E G ABc|dc Bc BA GF|DG GF G||', 'dG Gc G G BG'),
(1218, 1218, 'Amix', '|:cdc cBA|cde f2e|cdc cBA|B3 e2d|
cdc cBA|cde f2e|cAc BGB|A3 A3:|
|:a2e f2e|a2e f2e|cdc cBA|BcB B2e|
a2e f2e|a2e f2e|cAc BGB|A3 A3:|', ''),
(14514, 1218, 'Amaj', '|:e/d/|cdc cBA|Ace f2e|cdc cBA|BcB Bed|
cdc cBA|Ace f2e|c2c BcB|A3 A2:|
(3e/f/g/|a2e f2e|a2e f2e|cdc cBA|Bcd efg|
a2e f2e|a2e f2e|c2c BcB|A3 A2:|', ''),
(740, 1662, 'Edor', '|:f|gfe edB|BAB EFG|~F3 DFA|BAc def|
[1 ~g3 edB|BAB d3|B/c/dA FAF|GED E2:|
[2 ~g3 fdB|bag agf|ged e/f/ge|dBG E2||
|:z|efe Beg|bge gfe|1 ded ~d3|Adf afd|
efe Beg|bge gfe|fdB AGF|GED E2:|2 ded [F3d3]||
[E3d3] [D3d3]|efe Beg|bge gfe|fdB AGF|GED E2||', ''),
(1662, 1662, 'Edor', '|:f|~g3 edB|BAB EFG|~F3 DFA|dAF AFD|
~g3 edB|BAB EGA|~B3 AGF|GED E2:|
|:B|ege Beg|bge gfe|~d3 Adf|afd fed|
ege Beg|bge gfe|~B3 AGF|GED E2:|', ''),
(647, 647, 'Amin', '|:AAa2 g<eg2|e>dBA GAB<G|AAa2 g<eg2|e>dBe A2A2:|
|:e>dBA GAB<G|e>dBA B<dd2|e>dBA GAB<G|edB<e A2A2:|', ''),
(13675, 647, 'Ador', '|:(3AAA a2 g<e g2|e<dB>A G>AB<G|(3AAA a2 g<e g2|e>dB>e A2 A2:|
|:e>dB>A G>AB<G|e<dB>A B<d g2|1 e<dB>A G>AB<G|e<dB<e A2 A2:|
[2 e<dB>d g>fg<d|e<dg<B A2 A2||', ''),
(1649, 1649, 'Amaj', '|:af|eAAB c2 BA|e2 A2 Aaaf|eA AB c2 BA|c2 B2 B2 Ac|
eAAB c3 B|ABce a3 f|e3 f ecAc|B2 A2 A2:|
|:ce|a3 a afea|f3 e faaf|e3 f ecAB|c2 B2 B2 ce|
a3 a afea|fece faaf|e3 f ecAc|B2 A2 A2:|', ''),
(9425, 1649, 'Amaj', '|:af|e2A2 c2Bc|e2A2 A2af|e2c2 c2Bc|f2B2 B2cd|
efed c2BA|c2e2 a2c2|d2f2 B2ed|c2A2 A2:|
|:e2|a4 e2fg|a2ed c2BA|a4 efec|d2B2 B2e2|
a4 e2fg|aefd c2BA|d2f2 B2ed|c2A2 A2:|', ''),
(160, 160, 'Edor', 'D|:~E3 GFE|~B3 dBA|BdB BAB|GBG AFD|
~E3 GFE|BAB dBA|BAG FAF|1 GEE E2 D:|2 GEE E2 e||
|:e2 g gfe|g2 b bge|dcd fed|fad fed|
e2 f gfe|dfe dBA|BAG FAF|1 GEE E2 e:|2 GEE E2 D||', 'D'),
(12784, 160, 'Ador', '|:A^GA cBA|e^de ged|e/f/ge edG|Bec dBG|
A^GA cBA|e^de ged|edc BAB|cA^G A2:|
A2 B cBA|c2 d ecA|G2 B dBG|dBG BA^G|
A2 B cBA|GBA G2 D|EDC B,^A,B,|CA,^G, A,2:|', ''),
(5418, 5418, 'Gmaj', '|:g/f/|ed BA|BG E>F|G2 G/A/B/c/|d2 dg/f/|
ed BA|BG E>G|FA DE/F/|G2 G:|
|:z/A/|Bd ef|gd BG|Bd ef|g2 f>^c|
ed BA|BG E>G|FA DE/F/|G2 G:|', ''),
(17576, 5418, 'Gmaj', '|:gf|e2dc B2A2|B2G2 E2D2|G2G2 GABc|d4 B2gf|
e2dc B2A2|B2G2 E2G2|FGA2 D2EF|G4 G2:|
dc|B2 Bcd2ef|g2dcBAG2|Bc d2e2f2|g4 f2gf|
e2dc B2A2|B2G2 E2G2|FGA2 D2EF|G4 G2:|', ''),
(45, 45, 'Dmaj', '|:BAF AFE|FED EFA|BAF AFE|FEE E2A|
BAF AFE|FED FAB|dcB AFE|FDD D2A:|
def d2B|ABA AFA|def d2d|ede fdB|
def edB|dBA ABc|dcB AFE|FDD D2A:|', ''),
(8665, 45, 'Dmaj', '|:d3/2e/f ddB|AFA AFA|def ddA|Be/e/e edB|
d3/2e/f ddB|AFA AFA|gg/f/e fdB|AFD DFA:|
|:BF/F/F AD/D/D|FEF AFD|BF/F/F ADA|AFD EFA|
BF/F/F AD/D/D|FEF AFD|gg/f/e fdB|AFD DFA:|', ''),
(1357, 1357, 'Dmix', '|FG|:Addc AGEF|GEcE dEcE|Addc AGEF|GEcE ED D2:|
|:f2 fd e2 ed|cAAB cdeg|f2 fd e2 ed|eaag edde|
f2 fd e2 ed|cAAB c3 d|eddc AGEF|GEcE ED D2:|', ''),
(12862, 1357, 'Dmix', '|:Addc AGEF|GEcE dEcE|Addc AGEF|GEcE ED D2|
Addc AGEF|(3GGG AB cBcA|ecdB cABG|GEcE ED D2:|
~f3d efed|^cA (3AAA cAGA|~f3d eA (3B^cd|e2ag ed d2|
fd (3ddd efed|^cAAB ~=c3d|e=cdB cABG|GE=cE ED D2:|', ''),
(667, 667, 'Gmaj', '|:BEE GFE|d2d edB|AF{G}F DFF|AFA dAF|
B2E GFE|d2d edB|AFA dAF|FED E3:|
|:Bef gfe|~f2f edB|BAF FEF|DFA BAF|
Bef gfe|~f2f edB|BAB dAF|FED E3:|', ''),
(4472, 667, 'Edor', '|:A|BEE BEE|Bdf edB|BAF FEF|DFA dBA|
BEE BEE|Bdf edB|BAF DAF|FED E2:|A|
Bef gfe|faf edB|BAF FEF|DFA dBA|
Bef gfe|~f3 edB|BAF DAF|FED E2:|', ''),
(1843, 1843, 'Dmix', '|:DFA c2A|dAd efg|fed cAG|FAF GFE|
DFA c2A|dAd efg|fed cAG|Ad^c d2 D:|
|:dfa dfa|dfa afd|ceg ceg|ceg gfe|
fef gfg|agf efg|fed cAG|Ad^c d2 d:|
|:afd d^cd|Adf agf|gec cBc|Gce gfe|
fef gfg|agf efg|fed cAG|Ad^c d2a:|', ''),
(15273, 1843, 'Dmix', '|:FDD c2A|dA/B/d efg|fed ^cAG|F/G/AF GFE|
FDD c2A|dA/B/d efg|fed cAG|1 Ad^c dAG:|2 FAd d2A||
|:dfa dfa|daf g2f|ecg ecg|ecg gfe|
~f3 gfg|~a3 efg|fed cAG|1 Ad^c d2A:|2 Ad^c dfg||
|:afd d^cd|Adf afd|gec cBc|Gce gfe|
fAf gfg|~a3 efg|fed cAG|1 Ad^c dfg:|2 Ad^c dAG||', ''),
(256, 256, 'Ador', '|:G|EAA ABd|e2 A AGE|~G3 GAB|dBA GED|
EAA ABd|e2A AGE|efg dBG|BAG A2:|
a|age a2b|age edB|AGE G2A|BAB GED|
age a2b|age edB|AGE G2A|BAG A3|
age a2b|age edB|AGE G2A|BAB GED|
EDE G2A|BAG ABd|efg dBG|BAG A2||', ''),
(12981, 256, 'Amin', '|:A3 A3|e2 e e>dB|G3 G3|B>AB A>GA|
c3 d3|e>fg B>AG|A>Be d>cB|A3 A3:|
e3 e3|d>eg e>dB|G2 G d2 B|e2 e d>cB|
A3 c3|e>fg B>AG|A>Be d>cB|A3 A3:|', ''),
(1133, 1133, 'Dmaj', '|:F2A G2B|ABc d2A|F2A G2B|AFD E3|
F2A G2B|ABc d2e|f2d g2f|edc d3:|
|:faf d2f|gbg e2g|faf d2f|ecA A2g|
faf d2f|gbg e2g|f2d g2f|edc d3:|', ''),
(14399, 1133, 'Gmaj', '|:F2A G2B|ABc d3|F2A G2B|AGF E3|F2A G2B|ABc d3|gaf g2f|edc d3:|
|:faf d2f|gbg e2g|faf d2f|gec d3|faf d2f|ege c2A|B2c d2B|gec d3:|
A|F2A G2B|ABc d3|F2A G2B|AFD E3|F2A G2B|ABc d2e|f2d g2f|edc d2:|
|:g|f/g/af d2f|g/a/bg e2g|f/g/af d2f|ecA A2g|f/g/af d2f|g/a/bg e2g|f2d g2f|edc d2:|
F2A G2B|ABA [F3d3]|F2A G2B|AGF ~E3|F2A G2B|
ABA [F2d2]e|f2d g2f|edc [F3d3]||(f/g/a)f d2f|(e/f/g)e c2e|
(f/g/a)f d2f|edc [F3d3]|(f/g/a)f d2f|(e/f/g)e c2e|d2g {f/g/}a2f|gec [F3d3]||
A|F2A G2B|ABc d3|F2A G2B|AFD E3|F2A G2B|ABc d2e|f2d g2f|edc d2:|
gbg efg|f2a f2d|ecA A3|gbg efg|fed g2f|edc d3:|
B2d c2e|def g2d|B2d c2e|dcB A3|B2d c2e|def g3|B2G c2B|AGF G3:|
c2e c2A|B2d B2G|A2F D3|
c2e c2A|B2d B2g|A3 G3:|', ''),
(636, 636, 'Bmin', 'e|:fBBA FEFB|(3ABA FB ABde|fBBA FEFA|(3Bcd cA Bcde|
fBBA FEFB|(3ABA FB ABde|faaf effe|1 dBBA ~B3e:|2 dBAF B3c||
d2 fd Adfa|bfaf effe|(3ddd fd Adfa|bfaf egfe|
defd Adfa|bfaf efde|fBBA FEFA|(3Bcd cA B3c|
~d3f a2 fa|(3baf af effe|d2 fd adfa|bfaf effe|
dcdf a2 fa|(3baf af effe|fBBA FEFA|(3Bcd cA ~B3e||', 'e'),
(13663, 636, 'Bmin', 'e|:fBBA FEFB|A3F ABde|fBBA FEFA|BdcA B2 de|
fBBA FEFB|A3F ABde|fbaf efde|1 fBBA B3e:|2 fBBA B3c||
|:d2 fdAd f2|a3f edBc|d2 fdAd f2|a3f egfe|
d2 fdAd f2|a3f efde|fBBA FEFA|1 BdcA B3c:|2 BdcA B3e||', 'e'),
(182, 182, 'Dmaj', 'A|:FA (3AAA BAFA|dfed BddA|FA (3AAA BAFA|dfed (3BdB AG|
FA (3AAA BAFA|dfed Bdef|gage fgfe|1 dfed (3BdB AG:|2 dfed BdAd||
|:fa (3aaa bfaf|gfed Bdde|fa (3aaa bfaf|gfed (3BdB A2|
fa (3aaa bfaf|gfed Bdef|~g3 e ~f3 e|1 dfed BdAd:|2 dfed B2 AG||', 'A'),
(12830, 182, 'Dmaj', '|:eAAG A2(3B=cd|eaaf gedg|ea~a2 ba~a2|ded=c BG(3B=cd|
eAAG A2(3B=cd|eaaf gedg|e~a3 g3z|1 ded=c BG(3B=cd:|2 ded=c BGG2||
a2fa ba~a2|abag fddf|a2fa bafe|dfed BA~A2|
a2fa ba~a2|abag fdef|g3e f3z|efed BAA2:|', ''),
(430, 430, 'Gmaj', 'EAAB GABG|EAAB G2ED|EAA2 GABd|edge dBAG|
EAAB GABG|EAAB G2ED|EAA2 GABd|edge d2ef||
geee gede|geee a2ba|gee2 ged2|efge d2ef|
geee gede|geee a2ga|bgab gabg|efge dBAG||', 'EAAB GABG'),
(13292, 430, 'Gmaj', 'ge~e2 gede|ge~e2 a2ga|bgaf gedg|efge dBAG||
g2fg edBd|ge~e2 a2ga|bgaf gfed|efge dBAG||', 'ge~e2 gede'),
(1251, 1251, 'Ador', '|:A>B cg|de cA|B/c/B/A/ Gd|AB GE|
A>B cg|de cA|B/c/B/A/ Gd|BA A2:|
|:d>e fa|ga fd|g/e/d/c/ Bd/c/|B/A/G B/A/G/B/|
A>B cg|de cA|B/c/B/A/ Gd|BA A2:|
|:e>f2/g2/ f|d e>f2/g2/|fd f/g/f/e/|dc B(d|
d) c/B/ cg|de cA|B/c/B/A/ Gd|BA A2:|', ''),
(14561, 1251, 'Ador', '|:e>f g|d e>f g|fd g>e|dc B(d|
d/) c/B cg|de cA|B/c/B/A/ Gd|BA A2:|', ''),
(321, 321, 'Gmaj', '|:DBBA B2BA|GABd eBdB|(3ABA GB A2(3Bcd|eB(3BAB eBdB|
DBBA B2BA|GABd eBdB|GABG (3ABA GA|BGAG EGD2:|
|:f2fd edBd|edge dABd|f2fd edBd|eaag ea(3aba|
f2fd edBd|g2ge dcBA|GABG (3ABA GA|BGAG EGD2:|', ''),
(13090, 321, 'Gmaj', '|:DGBG cABA|GBdg e2dB|GABG A2(3Bcd|e~A2 eAcA|
DGBG cABA|GBdg e2dB|GABG A2GB|dBAd BGG2:|
|:gfeg fedf|efge dcBA|GABG A2(3Bcd|e~A2 eAcA|
gzeg fedz|efge dcBA|GABG A2 GB|dBAd BGG2:|', ''),
(750, 750, 'Edor', 'G2B E2B BAG|F2A D2A AGF|G2B E2B BAG|B/c/dB AGF DEF|
G2B E2B BAG|F2A D2A AGF|G2B E2B BAG|B/c/dB AGF E3||
g2e g2e edB|f2d dcd fed|g2e g2e edB|dBG GBd e2f|
g2e g2e edB|f2d dcd fed|gfe fed ecA|B/c/dB AGF E2F||', 'G2B E2B BAG'),
(7664, 750, 'Gmin', 'A|B2 d G2 d dcB|A2 c F2 c cBA|B2 d G2 d dcB|dfd cBA G2 A|
B2 d G2 d dcB|A2 c F2 c cBA|B2 d G2 d dcB|dfd cBA G3|
b2 g b2 g gfd|a2 f fgf agf|b2 g b2 g gfd|fdB Bdf g3|
b2 g b2 g gfd|a2 f fgf agf|b2 g a2 f gfd|dfd cBA G2z|', 'A'),
(2772, 2772, 'Amaj', '|:c>c BA|FA AB|cB/c/ BA|B/c/d e>f|
ec BA|FA A>B|c>c ec|BA A2:|
|:a>f ec|ec BA|a>f ec|B/c/d e2|
a>f ec|ec BA|B/c/c ec|BA A2:|', ''),
(3331, 2772, 'Amaj', '|:ce/c/ BA|FA AB|ce/c/ BA|ce f2|
ce/c/ BA|FA AB|cB/c/ ec|BA A2:|
|:a>f ec|ec BA|a>f ec|Bc e2|
a>f ec|ec BA|cB/c/ ec|BA A2:|', ''),
(9, 9, 'Dmix', '|:fed cAG|A2d cAG|F2D DED|FEF GFG|
AGA cAG|AGA cde|fed cAG|Ad^c d3:|
|:f2d d^cd|f2g agf|e2c cBc|e2f gfe|
f2g agf|e2f gfe|fed cAG|Ad^c d3:|
|:f2g e2f|d2e c2d|ABA GAG|F2F GED|
c3 cAG|AGA cde|fed cAG|Ad^c d3:|', ''),
(22361, 9, 'Emix', '|:gfe dBA|B2e dBA|G2E EFE|GFG AGA|
BAB dBA|BAB def|gfe dBA|Be^d e3:|
g2e e^de|g2a bag|f2d dcd|f2g agf|
g2a bag|f2g agf|gfe dBA|Be^d e3:|
g2a f2g|e2f d2e|BcB ABA|G2G AFE|
d3 dBA|BAB def|gfe dBA|Be^d e3:|', ''),
(651, 651, 'Dmaj', '|:FA|BA FA D2 FA|BA (3Bcd e2 de|fa gf eg fe|df ed B2 dB|
BA FA D2 FA|BA (3Bcd e2 de|fa gf eg fe|d2 f2 d2:|
|:fg|af df a2 g2|ef ga b2 ag|fa gf eg fe|df ed B2 dB|
BA FA D2 FA|BA (3Bcd e2 de|fa gf eg fe|d2 f2 d2:|', ''),
(13680, 651, 'Dmaj', '|:A (3EFA|BA FA DE FA|BA Bd e2 de|fa af eg fe|de fd B2 dc|
BA FA DA FA|BA Bd e2 de|fa af eg fe|d2 d2 d2:|
|:fg|af df a2 gf|gf ga b2 ag|fa af eg fe|de fd Bc dc|
BA FA DE FA|BA Bd e2 de|fa af eg fe|d2 d2 d2:|', ''),
(858, 858, 'Gmin', 'G/F/|DGA B2 A/G/|A/B/c/B/A/G/ FGA|BdB d/c/B/A/G/F/|DGG G2 G/F/|
DGA B2 A/G/|A/B/c/B/A/G/ FGA|f3/2e/d d/c/B/A/G/F/|DGG G2 G/A/|
Bdd d2 c/B/|Acc c2 f/e/|dg3/2g/ gab|dg^f g2 g/a/|
bag fed|cA f F2 G/A/|BdB d/c/B/A/G/F/|DGF G2||', 'G/F/'),
(14024, 858, 'Gmin', 'M:6/8
|:G/F/|DBA B2 A/G/|A/B/c/B/A/G/ FGA|BdB cB/A/G/F/|DGG G2:|
|:G/A/|Bdd d2 c/B/|Acc c2 f|d>g^f g>ab|dg^f g2 g/a/|
bag f>ed|d/c/B/A/f FGA|BdB d/c/B/A/G/F/|DGG G2:|', 'M:6/8
'),
(17, 17, 'Amin', '|:"Am"EAA ABc|"G"Bee e2d|"C"cBA ABc|"E"B^GE E2 D|
"Am"EAA ABc|"G"Bee e2d|"Am"cBA "E"B^GE|"Am"A2A A3:|
"C"c3 cdc|"G"Bgg g2^g|"Am"aed cBA|"E"^GBA E^F^G|
"Am"A^GA "Bm"BAB|"C"cde "Dm"fed|"Am"cBA "E"B^GE|"Am"A2A A3:|', ''),
(12387, 17, 'Bmin', '|:FBB Bcd|cff f2 e|dBB Bcd|cAF F2 E|
FBB Bcd|cff f2 e|dcB ^ABc|B3- B2:|
dcd dcB|Aaa a2 ^a|bfe dcB|^ABc F2 F|
B^AB cBc|def gfe|dcB ^ABc|B3- B2:|', ''),
(219, 219, 'Emin', 'GE (3EEE BE (3EEE|GE (3EEE BcBA|GE (3EEE BE (3EEE|AFDF AcBA|
GE (3EEE BE (3EEE|GE (3EEE BcBA|(3GGG GF GBdB|AFDF AcBA||
(3GGG BG dGBG|(3GGG Bd efg2|(3GGG BG dGBG|AFDF AcBA|
(3GGG BG dGBG|(3GGG Bd efg2|afge fded|AFDF AcBA||', 'GE (3EEE BE (3EEE'),
(12900, 219, 'Emin', 'GE ~E2 BE ~E2|GFGA B2BA|GE ~E2 BE ~E2|AFDF AcBA|
GE ~E2 BE ~E2|GFGA B2BA|~G3F GBdB|AFDF AcBA||
G2 BG dGBG|G2 Bd efg2|G2 BG dGBG|AFDF AcBA|
G2 BG dGBG|G2 Bd efg2|afge fded|AFDF AcBA||', 'GE ~E2 BE ~E2'),
(1214, 1214, 'Dmix', '|:AG|FAD DFG|GA{c}A GEA|D{A}D{G}D AGE|FAD DAG|
~F3 ~G3|~A3 cde|dcA GEA|D{A}D{G}D D:|
|:FA|c2A AGF|FG{A}G {A}GFG|AdB cAG|AdA d2e|
fed cAG|EF{A}F GEA|dcA GEA|D{A}D{G}D D:|', ''),
(1778, 1214, 'Dmaj', '|:F2D DAF|GED D2A,|DFA DGE|FDD D2E|
~F3 ~G3|~A3 (3Bcd e|dcA GEA|1 DED D2E:|2 DED D2B||
=c2A AGF|G3 GFG|A2B =cAG|Adc d2e|
fed cAG|FAF GED|dcA GEA|1 DED D2B:|2 DED D2E||', ''),
(1744, 1744, 'Amaj', '|:cAdB efga|A/A/AcA BGEd|cAdB efga|ecdB A2A2:|
afba geag|fdgf ecfe|dBed cAdc|BAGA Bcde|
afba geag|fdgf ecfe|dBed ceaf|ecdB A2z2|', ''),
(15176, 1744, 'Amaj', '|cAdA efga|A/A/A cA BG E/E/E|EAcd efga|ecdB Afed|
~c3d efga|A/A/A cA B~E3|EAcd efga|ecdB Aefg||
afba geag|fdaf eAce|d~B3 ceAc|~B3c defg|
aA A/A/A eAce|aAge fece|d/d/d fd ceaf|ecdB Afed||', ''),
(496, 496, 'Edor', '|:B2AF B2AF|EDEF EDB,D|B2AF B2AF|DFBA FE~E2|
B2AF BFAF|EDEF EDB,A,|B,E~E2 DEFA|dBAF FE~E2:|
|:eB~B2 egfe|d2fd Adfd|eB~B2 egfe|dBAF FE~E2|
eB~B2 egfe|d2fd Adfd|B~B2d efge|dBAF FE~E2:|', ''),
(13408, 496, 'Edor', '|:B2AF BFAF|~E3F EDFA|B2AF BFAF|DFBA FE~E2|
B2AF BFAF|~E3F EDBA|BEEF DEFA|dBAF FE~E2:|', ''),
(974, 974, 'Gmaj', '|:(3cBA|GB,DG BDGB|dGBd gbag|fed^c =cAFD|GBAG (3FED (3cBA|
GB,DG BdGB|dGBd gbag|fed^c =cAFD|(3GGG GF G2:|
|:(3bbb|bB^df bagf|e^def gfg^g|aA^ce agfe|e=dd^c d2ab|
c''afd ^cdef|gfga bgag|fed^c =cAFD|(3GGG GF G2:|', ''),
(14172, 974, 'Gmaj', '|:{A/}B>A|G>BD>G [B,B]>D (3GAB|d>G (3Bcd g>ba>g|f>Ae>d c>FB>A|(3GAG A>G F>D (3cBA|
G>BD>G [B,B]>DG>B|d>G (3Bcd g>ba>g|f>ed>^c =c>FB>A|(3GAG F>A G2:|
|:(3b^ab|b>B^d>f b>ag>f|e>^de>f g>^fg>^g|a>A^c>e a>g (3gfe|(3ded ^c>e d2 a>b|
c''>af>d ^c>de>f|g>^fg>a b2 a>g|f>ed>^c =c>FB>A|(3GAG F>A G2:|', ''),
(1376, 1376, 'Gmaj', 'Bc|:de dB GA BG|EA GE D3 A|BG Bd ge dB|{G}A2 AG A2 Bc|
de dB GA BG|EA GE D3 A|B d2 B AG AB|1 G2 {A}GF G2 Bc:|2 G2 {A}GF G GBd||
e2 ef g2 gf|ed dB d2 (3Bcd|ed Bd ge dB|A2 AG A2 Bc|
de dB GA BG|EA GE D3 A|B d2 B AG AB|1 G2 {A}GF G GBd:|2 G2 {A}GF G2 z2||', 'Bc'),
(14732, 1376, 'Gmaj', '|:B>c|d>ed>B G>AB>G|E2 _E2 D2 G>A|B>d^c>d e>dB>G|A4- A2 B>c|
d>ed>B G>AB>G|E2 _E2 D2 G>A|B>dB>G A>^GA>B|1 G4- G2:|2 G4- G>G||
|:(3Bcd|e2- e>f g2- g>f|e2 d2 d2 G>A|B>d^c>d e>dB>G|A4- A2 B>c|
d>ed>B G>AB>G|E2 _E2 D2 G>A|B>dB>G A>^GA>B|1 G4- G>G:|2 G4- G2||', ''),
(361, 361, 'Amix', '|:AE E2 AEcE|AE E2 GEDE|AE E2 A3 B|cdec d2 cd|
ea a2 agef|gdeg dBGB|AGED EA A2|1 cedB A3 B:|2 cedB ABcd||
|:e2 de cA A2|a3 g efgf|g2 dg Bgdg|gaba gede|
a2 c''a be e2|^ge e2 Be e2|dB B2 GA (3Bcd|1 gedB ABcd:|2 gedB A2 (3Bcd||
|:eA A2 EA A2|ae e2 agef|g2 fa gedB|Ggfa gedB|
cA A2 EA A2|ae e2 agef|g2 fa gedB|1 GBdB A2 (3Bcd:|2 GBdB A3 B||', ''),
(13162, 361, 'Dmix', '|:DA,~A,2 DA,=FA,|DA,~A,2 CA,G,A,|DA,~A,2 DA,DA|FDAF GEFG|
Adde d^cAB|cGAc GECE|CB,A,G, A,D~D2|1 FAGE D3^C:|2 FAGE DEFG||
|:AFGA FD~D2|dedc AGdB|c2Gc EGce|dced cAGE|
~d2fA ~d2fd|^cA~A2 EA^CA|GE~E2 CDEG|cAGE DEFG:|
|:AD~D2 A,D~D2|dA~A2 dcA_B|BcdB cAGE|CcBd cGEG|
FD~D2 A,D~D2|dA~A2 dcA_B|BcdB cAGE|1 CEGE DEFG:|2 CEGE D3^C||', ''),
(3262, 3262, 'Gmaj', '|:G3B d3B|cABG AG (3FED|G3B d2Bd|1 (3efg fa gedB:|2 (3efg fa g2gf||
gabg ag (3fed|efge dB~B2|gabg ag (3fed|egfa g2d2|
gabg ag (3fed|efge dBBA|G3B d2Bd|(3efg fa gedB||', ''),
(6654, 3262, 'Fmaj', 'FGFG Acc2|AGAF GFDC|DFFG Acc2|dfeg fdcA|
FGFG Acc2|AGAF GFDC|DFFG Acc2|dfeg f3||
e|fgaf fdc2|defd cAA2|fgaf fdc2|dfeg f3 e|
fgaf fdc2|defd cAAG|FGFG Ac~c2|dfeg f3||', 'FGFG Acc2'),
(1316, 1316, 'Bmin', '|:fBB2 fgfe|dBAB GBdB|cAAd AAec|afdB ecAc|
dBB2 fgfe|dBAB GBdB|cAdc ecA2|afec B4:|
|:f2dB GBdB|caec dBB2|f2dB GBdB|caec Bcde|
fdd2 fgfe|dBAB GBdB|cAdA eAA2|afec B4:|', ''),
(14652, 1316, 'Bmin', '|:fB~B2 fgfe|dBAB GBdB|cAAd AAeA|Aaec Aceg|
fB~B2 fgfe|dBAB GBdB|cABc def^g|afec B3e:|
|:f2dB GBdB|caec dB~B2|f2dB GBdB|caec Bcde|
fd~d2 fgfe|dBAB GBdB|cABc def^g|afec B3e:|', ''),
(302, 302, 'Gmaj', '|:G3 D E2 DB,|G,A,B,D EGDB,|G,A,B,D GABd|gabg eaaf|
gbag efge|dged B^cde|g2 fa gedB|AcBA GEED:|
|:E2 BE dEBE|Ed^cB AFDF|~E3 F GFGB|AF (3FFF DFAF|
EBBA B3 B|BAGA B^cde|f2 af gfe^c|dBAF GEED:|', ''),
(12073, 302, 'Gmaj', '(3DEF|:G3 F EDB,A,|G,A,B,G, G2 DB,|G,A,B,G, GA (3Bcd|ga (3bag eggf|
ga (3bag efge|dged Bc d2|dggb gbe^c|dBAF GEED:|
E2 BE eE B2|GABG AGFD|E2 eE dE B2|D2 FD A,DFD|
EBBB B3 c|cBAA Bcde|fggf gfe^c|dBAF GEED:|', '(3DEF'),
(2706, 2706, 'Ador', '|:eA A2 BABd|egfd edBd|eA A2 BABc|d2 ed BABd|eA A2 BABd|
egfd edBd|1 g2 ge f2 fe|dfed BABd:|2 gbag faef|dfed Bddf||
|:a2 fa bafa|a2 fd edBd|a2 fa baaf|dfed Bddf|
a2 fa bafa|a2 fd edBd|g2 ge f2 fe|1 dfed Bcdf:|2 dfed BABd||', ''),
(15940, 2706, 'Edor', '|:BE~E2 FEFA|(3Bcd cA BAFA|BE~E2 FEFG|ABAF EDFA|
BEED EFGA|(3Bcd cd BAFA|~d3B ~c3B|1 AcBA FEFA:|2 AcBA FA (3Bcd||
|:e2ce fecf|e2cA BAFA|e2ce fecB|AcBA FAEA|
e2ce fecf|e2cA BAFA|~d3B ~c3B|1 AcBA FA (3Bcd:|2 AcBA FEFA||', ''),
(1709, 1709, 'Amaj', '|:AGF ECE|Ace f2e|acc cBc|dFF F2E|
AGF ECE|Ace f2e|aec BAB|BAG A3:|
|:Ace Ace|Ace dcB|Ace fga|fee efg|
aba gag|faf ecA|dcd Bed|BAG A3:|', ''),
(12187, 1709, 'Gmaj', '|:d|GFG DB,D|GBd e2d|gdB BAB|cBc E2F|
GFG DB,D|GBd e2d|gdB BAB|cEF G2:|
|:D|GBd GBd|GBd cBA|GBd efg|fd^c def|
gbg faf|ece ~d2B|cBc Adc|BGF G2:|', ''),
(1892, 1892, 'Dmaj', '|:D/B,/|A,>B,D {DC}D>ED|EFA B2d|A>FD {EF}E>DE|{DE}FDB, B,2D/B,/|
A,>B,D {DE}D>ED|EFA d2c/B/|A>FD {=C}B,2 A,|B,D>D D2:|
(3A/B/c/|d>fd {cd}ecA|{Bc}B/A/B/c/{Bc}d B/A/G/F/E/D/|{EF}E>DE {DE}F>ED|{D}FDB, B,2 (3A/B/c/|
d>fd {cd}ecA|B/A/B/c/{Bc}d B/A/G/F/E/D/|{EF}E>DE {DE}FDB,|A,<DD [D2A,2] (3A/B/c/|
{e}d>fd ecA|B/A/B/c/{Bc}d B/A/G/F/E/D/|F/D/A/F/d/A/ B/A/G/F/E/D/|{DE}FEE E2D/B,/|
A,B,D D>ED|EFA d2c/B/|A>FD {=C}B,2A,|B,<DD [D2A,2]||', ''),
(741, 741, 'Dmaj', '|:dff cee|def gfe|dff cee|dfe dBA|
dff cee|def ~g3|afd gfe|dfe dBA:|
|:AFA ~A2f|~g3fdB|~A3 AFA|dfe dBA|
AFA BGB|efe efg|afd gfe|dfe dBA:|
|:faa eaa|def gfe|fAA eAA|dfe dBA|
faa eaa|def~g3|afd gfe|dfe dBA:|', ''),
(4582, 741, 'Dmaj', '|:dff cee|def gfe|dff cee|dfe dBA|
dff cee|def ~g3|afd cBA|dfe dBA:|
AFA Adf|gfe fdB|AFA ABc|dfe dcB|
AFA BGB|efe e2 g|f/g/af|dfe dBA:|
fAA fAA|f/g/af gfe|fAA fAA|dfe dBA|
fAA fAA|f/g/af ~g3|afd cBA|dfe dBA:|
AFA AFA|=c/B/AG FGE|D>ED DFA|dfd {f}dB|
{AB}AFA dAF|~G3 EFG|FED DFA|dfd e2 d:|
~f3 ~g3|agf gfe|~f3 ~g3|afd ede|
~f3 ~g3|afd cBA|afd cBA|dfe dBA:|', ''),
(510, 510, 'Amaj', '|:EFE E2 A|FEC E2 e|fec ABc|dcd BAF|
EFE E2 A|FEC E2 e|fec ABc|1 BcB A2 F:|2 BcB Acd||
|:ecB Ace|aff faf|ece fec|cBA Bcd|
ecB Ace|aff faf|ece fec|1 BcB Aee:|2 BcB (3ABA F||', ''),
(3614, 510, 'Amaj', '|:F|ECE E2 A|FEC E2 e|fec ABc|dcd BAF|
ECE E2 A|FEC E2 e|fec ABc|BAG A2:|
|:e|ece Ace|aga fdf|ece fec|BcA Bcd|
ece Ace|aga fdf|ece fec|BAG A2:|', ''),
(5976, 5976, 'Bmin', '|:BffB f2 (3fef gfed|c2 cd ef e2 cedc:|
|:Bz B2 cdBz B2 cd|Bz B2 cded cedc:|', ''),
(7035, 5976, 'Bmin', '|:f|fB f2 ef|gf ed cB|cd ef e2|ce dc B:|
B|fB cd B2|gB cd B2|AB cd ed|ce dc cB|
fB cd B2|gB cd B2|AB cd ed|ce dc B2||', '');

-- Total settings: 300
-- =============================================================================
-- Reset sequences to avoid conflicts with future inserts
-- =============================================================================

SELECT setval('session_session_id_seq', (SELECT MAX(session_id) FROM session));
SELECT setval('person_person_id_seq', (SELECT MAX(person_id) FROM person));
SELECT setval('user_account_user_id_seq', (SELECT MAX(user_id) FROM user_account));
SELECT setval('session_instance_session_instance_id_seq', (SELECT MAX(session_instance_id) FROM session_instance));
SELECT setval('session_instance_tune_session_instance_tune_id_seq', (SELECT MAX(session_instance_tune_id) FROM session_instance_tune));
SELECT setval('session_person_session_person_id_seq', (SELECT MAX(session_person_id) FROM session_person));
SELECT setval('session_instance_person_session_instance_person_id_seq', (SELECT MAX(session_instance_person_id) FROM session_instance_person));
SELECT setval('person_tune_person_tune_id_seq', (SELECT MAX(person_tune_id) FROM person_tune));

-- =============================================================================
-- Seed data complete
-- =============================================================================
