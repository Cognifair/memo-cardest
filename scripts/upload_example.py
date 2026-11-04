"""Reference integration, not an executable real-account uploader.

Implement an adapter using the current official API documentation. The adapter
owns credentials, request throttling, fresh GETs and field normalization. Its
classify method returns upload_task.WriteResult; never classify a timeout as a
definite rejection. No independent progress counter or notifier is needed.
"""
from upload_task import UploadTask


def upload(journal_path, adapter, *, task_uuid=None, session_id=None):
    """Default: no automatic write retries. A new script must use this flow."""
    with UploadTask.open(journal_path, task_uuid=task_uuid, session_id=session_id,
                         execution=adapter.execution_plan) as task:
        for item in task.snapshot()["items"]:
            key = item["key"]
            if item["status"] == "verified":
                continue
            if item["status"] == "planned":
                result = task.execute_write(key, lambda: adapter.send(item), adapter.classify)
                if result.kind != "confirmed":
                    break  # reject/uncertain is not progress success; no blind resend
            elif item["status"] in ("failed", "skipped"):
                continue  # explicit retry_rejected policy, if authorized, belongs here
            elif item["status"] == "uncertain" and item["bound_card_id"] is None:
                break  # unknown create ID needs separate read-only reconciliation
            current = next(i for i in task.snapshot()["items"] if i["key"] == key)
            # The callback must issue an independent GET, not reuse POST data.
            # If using a chapter endpoint, request card inclusion explicitly and
            # derive chapter membership from the actual response, never expected.
            status = task.verify(key, lambda: adapter.fetch_snapshot(current))
            if status != "verified":
                break
        return task.finish()
