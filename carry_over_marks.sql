-- Carry the segmenter marks made against the local fixture over to production.
-- One-off: 9 marks on B.D. Riley's 2025-03-27 (session_instance 449).
--
-- Joins on order_position, NOT on session_instance_tune_id: the local fixture
-- uses synthetic ids (44900+) while production has its own (34876+). The
-- order_position strings are identical in both -- that is what makes the local
-- fixture a faithful mirror rather than a lookalike.
--
-- Safe to re-run: an existing mark on the same tune is updated, not duplicated.
-- Aborts rather than half-applying if any mark fails to find its tune.
--
-- Run AFTER schema/049 and after the recording row exists for instance 449.

BEGIN;

CREATE TEMP TABLE _marks (order_position TEXT, start_ms BIGINT, end_ms BIGINT) ON COMMIT DROP;
INSERT INTO _marks (order_position, start_ms, end_ms) VALUES
        ('X', 14950, NULL),
        ('Y', 108450, NULL),
        ('Z', 171050, 267000),
        ('b', 339900, NULL),
        ('c', 413250, NULL),
        ('d', 535650, 616821),
        ('f', 715100, NULL),
        ('g', 813100, NULL),
        ('h', 908808, 1005709);

INSERT INTO recording_tune_segment (recording_id, session_instance_tune_id, start_ms, end_ms)
SELECT r.recording_id, sit.session_instance_tune_id, m.start_ms, m.end_ms
  FROM _marks m
  JOIN session_instance_tune sit
    ON sit.session_instance_id = 449
   AND sit.order_position = m.order_position
   AND sit.record_type = 'tune'
   AND sit.deleted = FALSE
  JOIN recording r
    ON r.session_instance_id = 449 AND r.is_clock_anchor
ON CONFLICT (recording_id, session_instance_tune_id)
DO UPDATE SET start_ms = EXCLUDED.start_ms, end_ms = EXCLUDED.end_ms;

-- Assert every mark landed, and say WHICH precondition failed if not -- the
-- first version just reported "found 0", which is true but useless when the
-- actual cause is that step 3 (creating the recording row) was never run.
DO $$
DECLARE found INT; recs INT; matched INT;
BEGIN
    SELECT count(*) INTO recs FROM recording
     WHERE session_instance_id = 449 AND is_clock_anchor;
    IF recs = 0 THEN
        RAISE EXCEPTION
            'no clock-anchor recording on session_instance 449 -- run the '
            'import_recording.py step first (it creates the row these marks hang off)';
    END IF;

    SELECT count(*) INTO matched
      FROM _marks m
      JOIN session_instance_tune sit
        ON sit.session_instance_id = 449
       AND sit.order_position = m.order_position
       AND sit.record_type = 'tune' AND sit.deleted = FALSE;
    IF matched <> 9 THEN
        RAISE EXCEPTION
            'only % of 9 marks matched a tune by order_position on instance 449 -- '
            'the log has changed since these marks were made', matched;
    END IF;

    SELECT count(*) INTO found
      FROM recording_tune_segment rts
      JOIN recording r ON r.recording_id = rts.recording_id
     WHERE r.session_instance_id = 449;
    IF found <> 9 THEN
        RAISE EXCEPTION 'expected 9 marks on instance 449, found %', found;
    END IF;
    RAISE NOTICE 'OK: 9 marks carried over';
END$$;

COMMIT;

-- Verify: 9 tunes with their resolved ends.
SELECT r.display_name, r.start_ms, r.resolved_end_ms, r.end_is_explicit
  FROM recording_tune_segment_resolved r
  JOIN recording rec ON rec.recording_id = r.recording_id
 WHERE rec.session_instance_id = 449
 ORDER BY r.start_ms;
