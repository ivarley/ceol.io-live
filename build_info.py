"""Which build of Ceol this process is running.

One string, fixed for the life of the process. On Render it is the deployed
commit; anywhere else it is the moment the process started, so a local restart
also reads as a new build. The live logger compares the id its page was served
with against `GET /api/build` whenever its tab comes back, and offers a reload
when they differ (a page left open through a deploy would otherwise run the old
bundle all night).
"""

import os
import time

BUILD_ID = os.environ.get("RENDER_GIT_COMMIT", "")[:8] or f"local-{int(time.time())}"
