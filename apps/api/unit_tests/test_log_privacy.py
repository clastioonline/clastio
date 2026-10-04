"""Credential and teacher-data redaction at the central structured logging boundary."""
import json
import logging
import sys

from app.core.logging import JsonFormatter, redact_sentry_event


def formatted(message, fields=None, exc_info=None):
    record = logging.LogRecord("audit", logging.ERROR, __file__, 1, message, (), exc_info)
    record.extra_fields = fields or {}
    return json.loads(JsonFormatter().format(record))


def test_nested_secret_fields_and_teacher_prompts_are_redacted():
    output = formatted("provider_failed", {
        "details": {"headers": {"Authorization": "Bearer private", "Set-Cookie": "session=private"},
                    "attempts": [{"api-key": "private", "prompt": "Teacher's private source material"}],
                    "ok": False}, "latency_ms": 50})
    assert output["details"]["headers"] == {"Authorization": "[redacted]", "Set-Cookie": "[redacted]"}
    assert output["details"]["attempts"] == [{"api-key": "[redacted]", "prompt": "[redacted]"}]
    assert output["details"]["ok"] is False and output["latency_ms"] == 50
    assert "private" not in json.dumps(output).lower()


def test_exception_strings_and_log_messages_do_not_expose_keys_or_connection_passwords():
    examples = ["sk-proj-" + "x" * 24, "sk_live_" + "x" * 24, "re_" + "x" * 24,
                "cfat_" + "x" * 24, "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature"]
    output = formatted("failed " + " ".join(examples), {
        "error": "postgresql+asyncpg://admin:password%40value@db.example.com/database "
                 "Bearer credential-value", "status": 401})
    serialized = json.dumps(output)
    assert all(secret not in serialized for secret in examples)
    assert "password%40value" not in serialized and "credential-value" not in serialized
    assert "db.example.com/database" in serialized and output["status"] == 401


def test_sql_parameters_are_removed_but_error_type_and_traceback_remain():
    try:
        raise RuntimeError("ForeignKeyViolation: missing plan\n[SQL: INSERT INTO subscriptions]\n"
                           "[parameters: ('teacher@example.com',\n 'password-hash', 'private lesson')]\n"
                           "(More information)")
    except RuntimeError:
        output = formatted("unhandled_error", {"error_type": "RuntimeError"}, sys.exc_info())
    assert "ForeignKeyViolation" in output["exc"] and "Traceback" in output["exc"]
    assert "INSERT INTO subscriptions" in output["exc"]
    assert "teacher@example.com" not in output["exc"]
    assert "password-hash" not in output["exc"] and "private lesson" not in output["exc"]


def test_private_key_blocks_are_removed_from_exception_details():
    key = "-----BEGIN PRIVATE KEY-----\nprivate encoded key\n-----END PRIVATE KEY-----"
    output = formatted("key parsing failed", {"error": key})
    assert output["error"] == "[redacted private key]"


def test_push_capability_urls_and_subscription_keys_are_redacted():
    endpoint = "https://fcm.googleapis.com/fcm/send/private-device-capability"
    output = formatted("push failed at " + endpoint, {"subscription": {"endpoint": endpoint,
        "keys": {"auth": "private-auth", "p256dh": "private-public-key"}}, "vapid_private_key": "private-signing-key"})
    serialized = json.dumps(output)
    assert endpoint not in serialized
    assert "private-device-capability" not in serialized and "private-auth" not in serialized
    assert "private-public-key" not in serialized and "private-signing-key" not in serialized


def test_external_error_reporting_excludes_payloads_locals_and_nested_credentials():
    event = {"request": {"url": "https://app.example.com/api/v1/auth/clerk",
                         "data": {"unusual_field": "Teacher material"}, "cookies": "private cookie",
                         "headers": {"Authorization": "private token", "Content-Type": "application/json"}},
             "exception": {"values": [{"type": "ValueError", "value": "Validation failed",
                                        "stacktrace": {"frames": [{"filename": "jobs.py", "lineno": 5,
                                                                   "vars": {"unusual_name": "private file"}}]}}]},
             "contexts": {"trace": {"data": {"gen_ai.request.messages": ["Teacher prompt"], "http.status": 500}}}}
    output = redact_sentry_event(event, {})
    assert "data" not in output["request"] and "cookies" not in output["request"]
    assert output["request"]["headers"]["Authorization"] == "[redacted]"
    frame = output["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert frame == {"filename": "jobs.py", "lineno": 5}
    assert output["contexts"]["trace"]["data"]["gen_ai.request.messages"] == "[redacted]"
    assert output["contexts"]["trace"]["data"]["http.status"] == 500
    assert "Teacher" not in json.dumps(output) and "private" not in json.dumps(output)
    # Redaction must not mutate the SDK's original event or accidentally delete useful diagnostics.
    assert "data" in event["request"] and "vars" in event["exception"]["values"][0]["stacktrace"]["frames"][0]


def test_installed_sentry_sdk_accepts_privacy_options_without_a_network_transport():
    from sentry_sdk import Client

    client = Client(dsn=None, default_integrations=False, send_default_pii=False,
                    max_request_body_size="never", include_local_variables=False,
                    before_send=redact_sentry_event, before_send_transaction=redact_sentry_event)
    assert client.options["max_request_body_size"] == "never"
    assert client.options["include_local_variables"] is False
    assert client.options["before_send"] is redact_sentry_event
    assert client.options["before_send_transaction"] is redact_sentry_event
    client.close()
