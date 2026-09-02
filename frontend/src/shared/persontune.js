// Facts about a person_tune row that the CLIENT has to predict, because it draws the
// row optimistically before the server has written it (the offline op-queue). Each one
// mirrors a server-side default — keep them in step or a queued add renders as one
// thing and syncs as another.

/**
 * What heard_count a brand-new person_tune starts at. Mirrors
 * PersonTune.DEFAULT_HEARD_COUNT (models/person_tune.py): putting a tune on your list
 * is itself evidence you heard it, so a new row starts at one. Zero then means what it
 * says — on the list, not heard since.
 */
export const DEFAULT_HEARD_COUNT = 1
