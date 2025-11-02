# 007 Unified Search

We're going to create a unified tune search experience from all the places that look up tunes by name in the system (not including the javascript search-to-filter-current-list functionality, which is a pure text search over the contents of the current view, shown in several places).

To start with, do an analysis of the 3 key places that tune search happens now:
- On my_tunes, when you click "Add", it brings up a modal to search by name in the tune table and, if that has no results, directly against thesession.org
- On session_detail, when your on-screen filter turns up no results, it works the same way as my-tunes
- On session_instance_detail, when you type a tune name into the log and hit return / tab, it attempts to match to a single tune, and if it does, it puts it as "matched" in blue; if there are multiple possible tunes based on your input it turns it red and the context menu shows you which tunes you can choose from; and if nothing matches it shows as unmatched in grey.

I'm looking to combine the back-end API calls for all of these in a unified way, with configurable behavior, such that you get consistent results from a given search string wherever you input it.

First, let's extract the shared modal from the first two cases and make it reusable:

  1. Extract shared autocomplete component from my_tunes_add.html and session_tune_add.html
  2. Create single template/partial for the search UI (they're ~90% identical)
  3. Share JavaScript search logic - currently duplicated across both pages