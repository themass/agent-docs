"""后台任务（O §2）与上传（O §5）的规则和执行。"""

import asyncio
import io
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from PIL import Image

from companion.adapters.storage.images import normalize_image
from companion.adapters.storage.memory import InMemoryObjectStore
from companion.adapters.storage.tos import TosNotConfigured, TosObjectStore
from companion.app.jobs.handlers import audit_trim, confirmation_expire
from companion.app.jobs.worker import JobWorker
from companion.app.uploads.service import UploadService
from companion.domain.jobs.policy import after_failure, retry_delay
from companion.domain.uploads.policy import UploadRejected, detect_type
from companion.ports.jobs import JobRecord

NOW = datetime(2026, 11, 9, 10, 0)


class JobStore:
    def __init__(self, jobs):
        self.jobs = jobs
        self.log = []

    async def claim(self, *, owner, now, lease_until, limit):
        out, self.jobs = self.jobs[:limit], self.jobs[limit:]
        return out

    async def renew(self, *, job_id, owner, lease_until):
        return True

    async def complete(self, *, job_id, owner):
        self.log.append(("done", job_id))
        return True

    async def fail(self, *, job_id, owner, status, run_after, error):
        self.log.append(("fail", job_id, status, error))
        return True


def test_backoff_schedule_and_dead_letter():
    assert [retry_delay(i).total_seconds() / 60 for i in (1, 2, 3, 4)] == [1, 4, 16, 64]
    assert after_failure(1, 5, NOW) == ("queued", NOW + timedelta(minutes=1))
    assert after_failure(5, 5, NOW) == ("dead", None)


async def test_worker_completes_retries_and_kills_correctly_without_leaking_error_text():
    async def ok(payload):
        return None

    async def boom(payload):
        raise ValueError("user text must not leak")

    store = JobStore([JobRecord(1, "ok", {}, 1, 5, None), JobRecord(2, "boom", {}, 1, 5, None),
                      JobRecord(3, "unknown", {}, 1, 5, None), JobRecord(4, "boom", {}, 5, 5, None)])
    await JobWorker(store=store, handlers={"ok": ok, "boom": boom}, owner="w", clock=lambda: NOW).run_once()
    assert ("done", 1) in store.log
    assert ("fail", 2, "queued", "ValueError") in store.log
    assert ("fail", 3, "dead", "unknown job kind: unknown") in store.log
    assert ("fail", 4, "dead", "ValueError") in store.log
    assert all("leak" not in str(entry) for entry in store.log)


async def test_confirmation_expiry_and_audit_trim_use_their_cutoffs():
    class Confirm:
        async def expire_due(self, *, now):
            self.now = now
            return 1

    class Audit:
        async def trim_before(self, *, cutoff):
            self.cutoff = cutoff
            return 0

    confirm, audit = Confirm(), Audit()
    await confirmation_expire(confirm, clock=lambda: NOW)({})
    await audit_trim(audit, clock=lambda: NOW)({})
    assert confirm.now == NOW
    assert audit.cutoff == NOW - timedelta(days=90)


def _png(size=(3000, 1500), gps=True):
    img = Image.new("RGB", size, (200, 50, 50))
    buf = io.BytesIO()
    exif = Image.Exif()
    if gps:
        exif[0x8825] = {1: "N", 2: (31.0, 14.0, 0.0)}
    img.save(buf, format="PNG", exif=exif)
    return buf.getvalue()


def test_type_is_detected_by_magic_bytes_not_by_name():
    assert detect_type(_png()[:16]) == "image/png"
    assert detect_type(b"<html>") is None


def test_images_are_reencoded_scaled_and_stripped_of_exif():
    out = normalize_image(_png())
    assert max(out.width, out.height) == 2048
    decoded = Image.open(io.BytesIO(out.data))
    assert decoded.format == "JPEG"
    assert not decoded.getexif()


def test_bad_images_are_rejected_with_user_safe_message():
    with pytest.raises(UploadRejected):
        normalize_image(b"\x89PNG\r\n\x1a\nGARBAGE")


class Records:
    def __init__(self):
        self.rows = {}

    async def create(self, r):
        self.rows[r.id] = r

    async def get_owned(self, *, owner_id, upload_id):
        r = self.rows.get(upload_id)
        return r if r and r.owner_id == owner_id else None


async def test_upload_is_private_and_url_is_signed_for_owner_only():
    svc = UploadService(objects=InMemoryObjectStore(), records=Records(), normalize=normalize_image)
    rec = await svc.accept(owner_id=7, data=_png(size=(800, 600), gps=False))
    assert await svc.read_url(owner_id=7, upload_id=rec.id) is not None
    assert await svc.read_url(owner_id=8, upload_id=rec.id) is None
    with pytest.raises(UploadRejected):
        await svc.accept(owner_id=7, data=b"")


def test_tos_adapter_refuses_to_run_unconfigured():
    with pytest.raises(TosNotConfigured):
        TosObjectStore(endpoint="", bucket="", access_key="", secret_key="")


def test_tos_adapter_puts_deletes_and_signs_with_stubbed_s3():
    import boto3
    from botocore.config import Config
    from botocore.stub import Stubber

    client = boto3.client("s3", endpoint_url="https://tos-s3-cn-beijing.volces.com", aws_access_key_id="AK",
                          aws_secret_access_key="SK", region_name="cn-beijing",
                          config=Config(s3={"addressing_style": "virtual"}))
    stub = Stubber(client)
    stub.add_response("put_object", {}, {"Bucket": "b", "Key": "uploads/7/x.jpg", "Body": b"d",
                                         "ContentType": "image/jpeg"})
    stub.add_response("delete_object", {}, {"Bucket": "b", "Key": "uploads/7/x.jpg"})
    stub.activate()
    store = TosObjectStore(endpoint="https://tos-s3-cn-beijing.volces.com", bucket="b",
                           access_key="AK", secret_key="SK", client=client)

    async def run():
        await store.put(key="uploads/7/x.jpg", data=b"d", content_type="image/jpeg")
        await store.delete(key="uploads/7/x.jpg")
        return await store.signed_url(key="uploads/7/x.jpg", ttl_seconds=300)

    url = asyncio.run(run())
    stub.assert_no_pending_responses()
    assert "/uploads/7/x.jpg" in url and "X-Amz-Expires=300" in url
