-- 066 A blog post emailed to the update subscribers (blog.py): the email_message
-- row that recorded the send names the post, so it cannot go out twice and the
-- post's page can say when it went.
ALTER TABLE email_message ADD COLUMN IF NOT EXISTS blog_slug TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_message_blog_slug
    ON email_message (blog_slug) WHERE blog_slug IS NOT NULL;
