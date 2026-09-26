#!/usr/bin/env python
"""Allow the browser to upload recordings straight to S3 (spec 050).

The in-app upload has the browser PUT the audio directly to the bucket rather
than through Flask -- a three-hour master is ~350MB, and pushing that through
the web dyno would pin a worker for the length of the transfer and spool the
whole file to its disk for nothing. The cost of that choice is that S3 now sees
a cross-origin request, so the bucket needs a CORS rule or every upload dies in
the preflight with an error the browser refuses to describe.

    venv/bin/python scripts/configure_s3_cors.py                 # show current
    venv/bin/python scripts/configure_s3_cors.py --apply         # write it

This is a ONE-TIME bucket setting, and it is the only piece of the feature that
lives outside the repo. Nothing else needs it: playback and peaks are same-origin
or plain <audio> loads, which S3 already serves.

**The app's own credentials cannot do this.** `ceol-io-user` is scoped to object
reads and writes, which is the right shape for a key that sits in a web dyno's
environment -- it holds neither s3:GetBucketCORS nor s3:PutBucketCORS. So this
script run with the credentials in .env will print the configuration and then
fail to apply it, which is a correct outcome rather than a broken one: pasting
the JSON into the S3 console (Permissions > Cross-origin resource sharing) as an
admin is the intended path, and --apply is here for whoever does hold bucket
admin. Widening the app user to make --apply work would trade a one-time console
visit for a permanently more powerful key.

Credentials come from the usual AWS_* environment variables (loaded from .env).
Point it at a different bucket with AWS_S3_BUCKET.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Where the admin page is served from. Every origin that will run the upload
# form has to be listed -- S3 matches Origin exactly, so the apex and the www
# host are two different entries, and http/https are two more.
DEFAULT_ORIGINS = [
    "https://ceol.io",
    "https://www.ceol.io",
    "http://localhost:3232",
]


def load_dotenv(path):
    """Minimal .env loader; existing environment variables win."""
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def cors_rules(origins):
    return {
        "CORSRules": [
            {
                "AllowedOrigins": list(origins),
                # PUT is the upload itself. GET/HEAD are here because the
                # segmenter's <audio> element issues range requests against the
                # presigned playback URL, and a browser treats a redirected or
                # crossorigin media fetch as needing the same permission.
                "AllowedMethods": ["PUT", "GET", "HEAD"],
                # The presigned PUT signs Content-Type, so that header must be
                # allowed through the preflight or the upload never starts.
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3000,
            }
        ]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Write the configuration (default is to print it)")
    parser.add_argument(
        "--origin", action="append", dest="origins",
        help="Origin allowed to upload; repeatable. Defaults to the ceol.io hosts plus localhost:3232.",
    )
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, ".env"))

    import recording as rec

    problem = rec.check_configured()
    if problem:
        print(f"ERROR: {problem}", file=sys.stderr)
        return 1

    bucket = rec.get_s3_bucket()
    s3 = rec.get_s3_client()
    origins = args.origins or DEFAULT_ORIGINS

    print(f"Bucket: {bucket}\n")

    try:
        current = s3.get_bucket_cors(Bucket=bucket)
        print("Current CORS configuration:")
        print(json.dumps(current.get("CORSRules", []), indent=2))
    except Exception as exc:
        if "NoSuchCORSConfiguration" in str(exc):
            print("Current CORS configuration: none set.")
        elif "AccessDenied" in str(exc):
            print("Current CORS configuration: unreadable with these credentials "
                  "(the app user has no s3:GetBucketCORS -- expected; see the module docstring).")
        else:
            print(f"Could not read the current CORS configuration: {exc}")

    desired = cors_rules(origins)
    print("\nDesired CORS configuration:")
    print(json.dumps(desired["CORSRules"], indent=2))

    if not args.apply:
        print("\n(--apply not given; nothing written. Re-run with --apply, or paste the "
              "above into the bucket's Permissions > CORS in the S3 console.)")
        return 0

    # This REPLACES the bucket's CORS configuration rather than merging into it.
    # If the bucket already serves another app, fold those rules in by hand
    # instead of running this.
    try:
        s3.put_bucket_cors(Bucket=bucket, CORSConfiguration=desired)
    except Exception as exc:
        if "AccessDenied" not in str(exc):
            raise
        print(
            "\nThese credentials cannot set bucket CORS (no s3:PutBucketCORS) -- expected for the\n"
            "app user, which is deliberately scoped to objects only. Nothing was changed.\n\n"
            "Apply it in the S3 console instead: open the bucket, Permissions >\n"
            f"Cross-origin resource sharing, and paste the JSON above. Bucket: {bucket}.",
            file=sys.stderr,
        )
        return 1
    print(f"\nApplied. {len(origins)} origin(s) may now upload directly to {bucket}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
