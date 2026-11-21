#!/usr/bin/env python3
"""Verify a Flop Labs proof-of-contribution record.

Reads a JSON record created by generate_contribution_record.py and checks:

  Structural checks (a failure makes the record INVALID):
  - every required field is present and non-empty
    (title, description, url, type, author, did, timestamp, content_hash)
  - the contribution type is one of the five recognised types
  - the DID has the valid Technocore format (did:key:z... Ed25519)
  - the URL is a public http(s) address
  - the timestamp parses as ISO 8601 UTC
  - the stored SHA-256 content hash matches the record fields

  Quality guardrails (a failure also makes the record INVALID, and the
  specific reason is listed in the "quality_warnings" field of the JSON
  report):
  - the URL must point to a specific piece of content, not a homepage or
    a generic feed (twitter.com/home, github.com/explore, a bare profile)
  - the description must be at least 50 characters and must not consist
    only of generic filler words ("test", "hello", "done", ...)
  - the contribution type must be a recognised slug; "thread" and
    "tutorial" are accepted as aliases for "kol-thread" and "content"
    (advisory warning only, the record stays VALID)

Prints VALID or INVALID with reasons. Exit code 0 when valid, 1 when not.
Use --json for a machine-readable report instead of the text output:

    python3 verify_contribution.py --json contribution_record.json

The JSON report contains "status", "problems", and "quality_warnings".

Standard library only. No network access.

Usage:
    python3 verify_contribution.py contribution_record.json
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

VALID_TYPES = {
    "kol-thread",
    "open-source",
    "bug-report",
    "community-help",
    "content",
}

# Aliases for hand-written records, using the names contributors reach
# for most often. The generator only writes canonical slugs; the verifier
# accepts these and nudges the author toward the canonical slug.
TYPE_ALIASES = {
    "thread": "kol-thread",
    "tutorial": "content",
}

REQUIRED_FIELDS = ("title", "description", "url", "type", "author",
                   "did", "timestamp", "content_hash")

DID_PATTERN = re.compile(r"^did:key:z[1-9A-HJ-NP-Za-km-z]+$")
URL_PATTERN = re.compile(r"^https?://\S+$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

MIN_DESCRIPTION_LENGTH = 50

# Words that on their own say nothing about a contribution. A description
# made only of these is filler, not evidence.
GENERIC_WORDS = {
    "test", "testing", "tested", "hello", "hi", "hey", "done",
    "placeholder", "lorem", "ipsum", "asdf", "qwerty", "foo", "bar",
    "baz", "sample", "example", "demo", "xxx", "aaa", "temp",
    "temporary", "todo", "wip", "draft", "abc", "123", "test123",
    "world", "ok", "okay", "yes", "no", "none", "tbd", "blah",
    "stuff", "thing", "things", "contribution", "my", "a", "an",
    "the", "is", "it", "this", "that", "and", "or", "of", "to",
    "for", "in", "on", "with",
}

# First path segment of a URL that points to a feed, a listing, or a
# settings page rather than to a specific piece of content.
GENERIC_PATHS = {
    "home", "feed", "explore", "trending", "search", "notifications",
    "messages", "settings", "discover", "watch", "reels", "live",
    "about", "pricing", "login", "signup", "register", "apps",
    "marketplace", "topics", "collections", "app", "dashboard",
    "inbox", "profile", "account", "help", "support", "blog", "news",
    "events", "groups", "pages", "videos", "photos", "people", "jobs",
    "channels",
}


def compute_hash(record):
    """Recompute the SHA-256 hash exactly as the generator does."""
    payload = {
        "title": record["title"],
        "description": record["description"],
        "url": record["url"],
        "type": record["type"],
        "author": record["author"],
        "did": record["did"],
        "timestamp": record["timestamp"],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def check_url_quality(url):
    """Guardrail: the URL must point to a specific piece of content.

    Returns a list of problems (empty when the URL is specific enough).
    A homepage, a feed, a listing page, or a bare profile is not a
    contribution and is rejected.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or ""
    segments = [seg for seg in path.split("/") if seg]

    def generic_url(reason):
        return [f"URL does not point to a specific contribution ({reason}): "
                f"{url!r} — link the thread, repository, post, or video "
                "itself"]

    if not segments and not parsed.query:
        return generic_url("it is a homepage")

    if host in ("x.com", "twitter.com"):
        if not re.fullmatch(r"/[^/]+/status/\d+/?", path):
            return generic_url("an X/Twitter link must point to a specific "
                               "post (/<user>/status/<id>)")
        return []

    if host in ("github.com", "gitlab.com"):
        if len(segments) < 2 or segments[0] in GENERIC_PATHS:
            return generic_url("a code link must point to a specific "
                               "repository (/<owner>/<repo>) or deeper")
        return []

    if host == "youtube.com":
        if path.startswith(("/shorts/", "/live/", "/embed/")) \
                and len(segments) >= 2:
            return []
        if path == "/watch" and "v=" in (parsed.query or ""):
            return []
        return generic_url("a YouTube link must point to a specific video "
                           "(/watch?v=..., /shorts/<id>, /live/<id>)")

    if host == "youtu.be":
        if len(segments) == 1 and segments[0] not in GENERIC_PATHS:
            return []
        return generic_url("a youtu.be link must point to a specific video "
                           "(<id>)")

    if host == "medium.com":
        if len(segments) < 2:
            return generic_url("a Medium link must point to a specific "
                               "article (/<author>/<slug>)")
        return []

    if host == "linkedin.com":
        if path.startswith(("/posts/", "/pulse/")):
            return []
        return generic_url("a LinkedIn link must point to a specific post "
                           "(/posts/<slug>) or article (/pulse/<slug>)")

    if host == "facebook.com":
        if any(token in path for token in ("/posts/", "/reel/", "/watch/",
                                           "/photo/", "/videos/")):
            return []
        return generic_url("a Facebook link must point to a specific post "
                           "(/posts/<id>, /reel/<id>, ...)")

    if host == "instagram.com":
        if path.startswith(("/p/", "/reel/", "/reels/", "/tv/")):
            return []
        return generic_url("an Instagram link must point to a specific post "
                           "(/p/<id>, /reel/<id>)")

    if host == "tiktok.com":
        if re.fullmatch(r"/@[^/]+/video/\d+/?", path):
            return []
        return generic_url("a TikTok link must point to a specific video "
                           "(/@<user>/video/<id>)")

    if host == "discord.com":
        if re.fullmatch(r"/channels/\d+/\d+/\d+/?", path):
            return []
        return generic_url("a Discord link must point to a specific message "
                           "(/channels/<server>/<channel>/<message>)")

    if host == "t.me":
        if len(segments) >= 2:
            return []
        return generic_url("a Telegram link must point to a specific "
                           "message (/<channel>/<id>)")

    if host.endswith(".substack.com"):
        if path.startswith("/p/"):
            return []
        return generic_url("a Substack link must point to a specific post "
                           "(/p/<slug>)")

    if host == "dev.to":
        if len(segments) >= 2:
            return []
        return generic_url("a dev.to link must point to a specific article "
                           "(/<author>/<slug>)")

    # Any other host: a specific page under a section is fine, but a bare
    # homepage or a single generic section page is not a contribution.
    if len(segments) == 1 and segments[0] in GENERIC_PATHS:
        return generic_url(f"it points to the {segments[0]!r} page, not to "
                           "a specific contribution")
    return []


def check_description_quality(description):
    """Guardrail: the description must say something real.

    Returns a list of problems (empty when the description is fine).
    """
    issues = []
    text = description.strip()
    if len(text) < MIN_DESCRIPTION_LENGTH:
        issues.append(
            f"description is too short ({len(text)} characters; at least "
            f"{MIN_DESCRIPTION_LENGTH} required) — describe what the "
            "contribution is and why it is useful")
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if tokens and all(token in GENERIC_WORDS for token in tokens):
        issues.append(
            "description contains only generic filler words (e.g. 'test', "
            "'hello', 'done') — describe the actual contribution")
    return issues


def check_type_quality(type_value):
    """Return (problems, warnings) for the contribution type."""
    if type_value in VALID_TYPES:
        return [], []
    if type_value in TYPE_ALIASES:
        canonical = TYPE_ALIASES[type_value]
        return [], [f"contribution type {type_value!r} is an alias; use the "
                    f"canonical slug {canonical!r} "
                    "(see references/contribution-types.md)"]
    return [f"unknown contribution type: {type_value!r} "
            f"(expected one of: {', '.join(sorted(VALID_TYPES))})"], []


def check_record(record):
    """Return (problems, quality_warnings) found in the record."""
    problems = []
    quality_warnings = []

    if not isinstance(record, dict):
        return ["record is not a JSON object"], []

    for field in REQUIRED_FIELDS:
        if field not in record:
            problems.append(f"missing required field: {field}")
        elif isinstance(record[field], str) and not record[field].strip():
            problems.append(f"required field is empty: {field}")
        elif record[field] is None:
            problems.append(f"required field is empty: {field}")
    if problems:
        return problems, quality_warnings

    type_problems, type_warnings = check_type_quality(record["type"])
    problems.extend(type_problems)
    quality_warnings.extend(type_warnings)

    if not DID_PATTERN.match(record["did"]):
        problems.append(
            f"invalid DID format: {record['did']!r} "
            "(expected did:key:z... Ed25519 public identity)")

    if not URL_PATTERN.match(record["url"]):
        problems.append(
            f"invalid URL: {record['url']!r} "
            "(expected a public http(s) address)")
    else:
        url_issues = check_url_quality(record["url"])
        problems.extend(url_issues)
        quality_warnings.extend(url_issues)

    timestamp = record["timestamp"]
    try:
        datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        problems.append(
            f"invalid timestamp: {timestamp!r} "
            "(expected ISO 8601 UTC, e.g. 2026-11-22T01:00:00Z)")

    description_issues = check_description_quality(record["description"])
    problems.extend(description_issues)
    quality_warnings.extend(description_issues)

    stored_hash = record["content_hash"]
    if not HASH_PATTERN.match(stored_hash or ""):
        problems.append("content_hash is not a 64-character hex digest")
    elif stored_hash != compute_hash(record):
        problems.append("content_hash does not match the record fields "
                        "(the record was altered after generation)")

    return problems, quality_warnings


def build_report(path, record, problems, quality_warnings):
    """Build the machine-readable JSON report for --json."""
    report = {
        "status": "INVALID" if problems else "VALID",
        "record_file": str(path),
        "problems": problems,
        "quality_warnings": quality_warnings,
    }
    if isinstance(record, dict):
        for field in ("title", "type", "author", "did", "url", "timestamp"):
            if field in record:
                report[field] = record[field]
    return report


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Verify a Flop Labs proof-of-contribution record.")
    parser.add_argument("record_file",
                        help="Path to the contribution record JSON file.")
    parser.add_argument("--json", action="store_true",
                        help="Print a machine-readable JSON report "
                             "(with a quality_warnings field) instead of "
                             "the text output.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    path = Path(args.record_file)

    if not path.is_file():
        report = {"status": "INVALID", "record_file": str(path),
                  "problems": [f"file not found: {path}"],
                  "quality_warnings": []}
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(f"INVALID: file not found: {path}")
        return 1

    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        report = {"status": "INVALID", "record_file": str(path),
                  "problems": [f"file is not valid JSON: {exc}"],
                  "quality_warnings": []}
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(f"INVALID: file is not valid JSON: {exc}")
        return 1

    problems, quality_warnings = check_record(record)

    if args.json:
        print(json.dumps(build_report(path, record, problems,
                                      quality_warnings), indent=2,
                         ensure_ascii=False))
        return 1 if problems else 0

    if problems:
        print("INVALID")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("VALID")
        print(f"  Title: {record['title']}")
        print(f"  Type: {record['type']}")
        print(f"  Author: {record['author']}")
        print(f"  URL: {record['url']}")
        print(f"  DID: {record['did']}")
        print(f"  Timestamp: {record['timestamp']}")

    # In text mode, show only warnings not already listed as problems.
    extra_warnings = [w for w in quality_warnings if w not in problems]
    if extra_warnings:
        print("Quality warnings:")
        for warning in extra_warnings:
            print(f"  - {warning}")

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
