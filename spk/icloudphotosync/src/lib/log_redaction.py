"""Central log-redaction helpers.

Vendored pyicloud_ipd exceptions can embed raw Apple API response bodies
(see vendor/pyicloud_ipd/base.py: `raise PyiCloudAPIResponseException(
response.text, str(response.status_code))` on a failed SRP login init)
and Apple ID emails (vendor/pyicloud_ipd/exceptions.py:
PyiCloud2SARequiredException embeds `apple_id` directly in its message).
Any code that logs an exception's message or traceback must go through
this module first — CLAUDE.md forbids passwords, 2FA codes, cookies,
tokens, and personal email addresses in logs, and forbids ad-hoc
per-line redaction in favor of central functions.
"""
import re
import traceback

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

_SENSITIVE_JSON_KEYS = (
    "password", "sessiontoken", "session_token", "trusttoken", "trust_token",
    "scnt", "sessionid", "session_id", "dswebauthtoken", "authtoken",
    "searchpartytoken",
)
_JSON_VALUE_RE = re.compile(
    r'"(%s)"\s*:\s*"[^"]*"' % "|".join(_SENSITIVE_JSON_KEYS),
    re.IGNORECASE,
)

_HEADER_RE = re.compile(
    r"(?im)^(cookie|set-cookie|authorization|x-apple-[\w-]*(?:session|token)[\w-]*)\s*:\s*.*$"
)


def mask_email(email):
    """Partially mask an email address: 'k***@example.invalid'.

    Matches the exact display format CLAUDE.md specifies for logged
    Apple IDs — first character of the local part, then '***@', then
    the domain unchanged.
    """
    if not email or "@" not in email:
        return "[REDACTED]"
    local, _, domain = email.partition("@")
    if not local:
        return "***@" + domain
    return local[0] + "***@" + domain


def redact_text(text):
    """Redact known-sensitive patterns from arbitrary log text (exception
    messages, tracebacks). This is a best-effort net for the specific
    patterns vendored pyicloud_ipd is known to embed in exception text
    (see module docstring) — not a guarantee against every possible leak
    shape.
    """
    if not text:
        return text
    text = _JSON_VALUE_RE.sub(lambda m: '"%s": "[REDACTED]"' % m.group(1), text)
    text = _HEADER_RE.sub(lambda m: "%s: [REDACTED]" % m.group(1), text)
    text = _EMAIL_RE.sub(lambda m: mask_email(m.group(0)), text)
    return text


def safe_log_exception(log, level, msg, *args):
    """Log `msg % args` at `level`, plus the currently-handled exception's
    redacted traceback. Must be called from inside an `except:` block.

    Replaces bare `logger.exception(...)` / `logger.warning(...,
    exc_info=True)` calls. Deliberately does NOT pass `exc_info=` to the
    underlying logger call: Python's stdlib `logging` formats `exc_info`
    internally at emit time, which would bypass any redaction applied
    here. Instead this captures and redacts the traceback itself first,
    then logs it as a plain string argument.

    Callers are responsible for pre-masking any sensitive values they
    pass in `args` (e.g. `mask_email(apple_id)`) — this function only
    guarantees the appended traceback is redacted.
    """
    tb = redact_text(traceback.format_exc())
    log.log(level, msg + "\n%s", *(tuple(args) + (tb,)))
