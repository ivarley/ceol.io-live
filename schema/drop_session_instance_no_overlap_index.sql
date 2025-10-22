-- Drop the unique index that prevents overlapping session instances
-- This allows support for festival-type sessions where overlapping instances are valid

DROP INDEX IF EXISTS idx_session_instance_no_overlap;

-- Add comment to document the change
COMMENT ON TABLE session_instance IS 'Session instances can now overlap (e.g., for festival sessions). The idx_session_instance_no_overlap constraint has been removed.';
