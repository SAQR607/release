"""YouTube publishing tests: metadata, error classification, oauth, upload/verify, snapshots.

No network: services are fakes, `_upload`/`_notify` are monkeypatched,
google credentials are constructed offline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.youtube import channel as ch
from app.youtube import oauth, publish
from app.youtube.errors import QuotaExceeded, YouTubeError, classify
from app.youtube.metadata import long_body, short_body
from app.youtube.oauth import YouTubeCredentialsError
from app.state import load_registry
from qc_fixtures import qc_cfg


# --- metadata ---------------------------------------------------------------


def test_long_body_fields():
    pkg = {"title": "T", "metadata": {"title": "Nice Title | Fernwood Friends S1E01",
                                      "description": "Desc.", "tags": ["kids", "stories"]}}
    body = long_body(pkg, private=False)
    assert body["snippet"]["title"] == "Nice Title | Fernwood Friends S1E01"
    assert body["snippet"]["tags"] == ["kids", "stories"]
    assert body["snippet"]["categoryId"] == "1"
    assert body["status"]["privacyStatus"] == "public"
    assert body["status"]["selfDeclaredMadeForKids"] is True


def test_long_body_private_and_title_clip():
    pkg = {"metadata": {"title": "x" * 200, "description": "d", "tags": ["t"] * 40}}
    body = long_body(pkg, private=True, category_id="24")
    assert len(body["snippet"]["title"]) <= 100
    assert body["status"]["privacyStatus"] == "private"
    assert body["snippet"]["categoryId"] == "24"
    assert len(body["snippet"]["tags"]) <= 30


def test_short_body_has_cross_link_and_hashshorts():
    doc = {"title": "Big Splash"}
    body = short_body(doc, private=True, long_title="The Smallest Light | Fernwood Friends S1E01")
    assert body["snippet"]["title"].startswith("Big Splash")
    assert "| Fernwood Friends" in body["snippet"]["title"]
    assert "#shorts" in body["snippet"]["description"]
    assert "The Smallest Light" in body["snippet"]["description"]
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["selfDeclaredMadeForKids"] is True


# --- error classification ---------------------------------------------------


class _Resp:
    def __init__(self, status):
        self.status = status


class _Http(Exception):
    def __init__(self, status, content=b""):
        self.resp = _Resp(status)
        self.content = content


def test_classify_quota():
    body = json.dumps({"error": {"errors": [{"reason": "quotaExceeded"}]}}).encode()
    assert classify(_Http(403, body)) == "quota"
    assert classify(_Http(429)) == "quota"
    assert classify(QuotaExceeded("x")) == "quota"


def test_classify_transient_and_fatal():
    assert classify(_Http(503)) == "transient"
    assert classify(ConnectionError("reset")) == "transient"
    assert classify(TimeoutError()) == "transient"
    assert classify(_Http(400, json.dumps({"error": {"errors": [{"reason": "badRequest"}]}}).encode())) == "fatal"
    assert classify(RuntimeError("bug")) == "fatal"


# --- oauth ------------------------------------------------------------------


def test_credentials_missing_env(monkeypatch):
    for key in oauth.ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(YouTubeCredentialsError, match="youtube-oauth"):
        oauth.require_env()


def test_credentials_placeholder_rejected(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "REPLACE_ME")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "s")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "r")
    with pytest.raises(YouTubeCredentialsError):
        oauth.require_env()


def test_credentials_builds_offline(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "1//refresh")
    creds = oauth.credentials()
    assert creds.refresh_token == "1//refresh"
    assert creds.client_id == "cid.apps.googleusercontent.com"
    assert "youtube.upload" in " ".join(creds.scopes)


# --- verify -----------------------------------------------------------------


class FakeVideos:
    def __init__(self, responses=None, insert_raises=None):
        self.responses = list(responses or [])
        self.i = 0
        self.insert_kwargs = None
        self.insert_raises = insert_raises

    def list(self, **kw):
        self.list_kwargs = kw
        return self

    def execute(self):
        r = self.responses[min(self.i, len(self.responses) - 1)] if self.responses else {}
        self.i += 1
        return r

    def insert(self, **kw):
        self.insert_kwargs = kw
        if self.insert_raises:
            raise self.insert_raises
        return self

    def next_chunk(self):  # pragma: no cover - only used if _upload isn't mocked
        return None, {"id": "from-insert"}


class FakeThumbnails:
    def __init__(self):
        self.calls = []

    def set(self, **kw):
        self.calls.append(kw)
        return self

    def execute(self):
        return {}


class FakeService:
    def __init__(self, responses=None):
        self._videos = FakeVideos(responses)
        self.thumbs = FakeThumbnails()

    def videos(self):
        return self._videos

    def thumbnails(self):
        return self.thumbs


def test_verify_waits_until_processed():
    svc = FakeService([
        {"items": [{"status": {"uploadStatus": "uploaded"}}]},
        {"items": [{"status": {"uploadStatus": "processed"}, "snippet": {"title": "t"}}]},
    ])
    sleeps = []
    item = publish._verify(svc, "vid1", tries=5, delay=3.0, sleep=sleeps.append)
    assert item["snippet"]["title"] == "t"
    assert sleeps == [3.0]


def test_verify_processing_failed():
    svc = FakeService([{"items": [{"status": {"uploadStatus": "failed", "failureReason": "transcode"}}]}])
    with pytest.raises(YouTubeError, match="processing FAILED"):
        publish._verify(svc, "vid1", tries=2, delay=0, sleep=lambda s: None)


def test_verify_budget_exhausted():
    svc = FakeService([{"items": [{"status": {"uploadStatus": "processing"}}]}])
    with pytest.raises(YouTubeError, match="not processed"):
        publish._verify(svc, "vid1", tries=3, delay=0, sleep=lambda s: None)


def test_verify_video_disappeared():
    svc = FakeService([{"items": []}])
    with pytest.raises(YouTubeError, match="not found"):
        publish._verify(svc, "vid1", tries=1, delay=0, sleep=lambda s: None)


# --- stage: publish_long ----------------------------------------------------


def _long_setup(tmp_path):
    state = tmp_path / "state"
    reg = load_registry(state)
    ep_id = reg.episode_id_for_slot("slot")
    base = state / "episodes" / ep_id
    (base / "render").mkdir(parents=True, exist_ok=True)
    video = base / "render" / "long.mp4"
    video.write_bytes(b"\x00" * 4096)
    thumb = base / "render" / "thumb.jpg"
    thumb.write_bytes(b"\xff\xd8\xff" + b"\x00" * 20000)
    (base / "package.json").write_text(json.dumps({
        "title": "The Smallest Light",
        "metadata": {"title": "The Smallest Light | Fernwood Friends S1E01",
                     "description": "Gentle story.", "tags": ["kids stories"]},
    }), encoding="utf-8")
    entry = reg.get(ep_id)
    entry["video_path"] = str(video)
    entry["thumbnail_path"] = str(thumb)
    reg.save()
    return qc_cfg(state), reg, ep_id, base


def test_publish_long_happy_path(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _long_setup(tmp_path)
    svc = FakeService([{"items": [{"status": {"uploadStatus": "processed",
                                              "privacyStatus": "public"}}]}])
    uploads = {}
    notifies = []

    def fake_upload(service, path, body, *, label):
        uploads["body"] = body
        uploads["path"] = path
        return "vid123"

    monkeypatch.setattr(publish, "build_service", lambda: svc)
    monkeypatch.setattr(publish, "_upload", fake_upload)
    monkeypatch.setattr(publish, "_notify", notifies.append)

    publish.publish_long(cfg, reg, ep_id, {})

    entry = reg.get(ep_id)
    assert entry["youtube_video_id"] == "vid123"
    assert entry["youtube_verified"] is True
    assert entry["youtube_privacy"] == "public"
    assert entry["published_at"]
    assert uploads["body"]["status"]["privacyStatus"] == "public"
    assert svc.thumbs.calls and svc.thumbs.calls[0]["videoId"] == "vid123"
    assert notifies and notifies[0].startswith("SUCCESS long")


def test_publish_long_private_test(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _long_setup(tmp_path)
    svc = FakeService([{"items": [{"status": {"uploadStatus": "processed",
                                              "privacyStatus": "private"}}]}])
    bodies = []
    monkeypatch.setattr(publish, "build_service", lambda: svc)
    monkeypatch.setattr(publish, "_upload",
                        lambda service, path, body, *, label: (bodies.append(body), "vidP")[1])
    monkeypatch.setattr(publish, "_notify", lambda t: None)

    publish.publish_long(cfg, reg, ep_id, {"private_test": True})
    assert bodies[0]["status"]["privacyStatus"] == "private"
    assert reg.get(ep_id)["youtube_privacy"] == "private"


def test_publish_long_idempotent_when_verified(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _long_setup(tmp_path)
    entry = reg.get(ep_id)
    entry["youtube_video_id"] = "vidOld"
    entry["youtube_verified"] = True
    reg.save()
    monkeypatch.setattr(publish, "build_service",
                        lambda: pytest.fail("must not touch the API when already verified"))
    publish.publish_long(cfg, reg, ep_id, {})  # no raise


def test_publish_long_dry_run_skips_api(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _long_setup(tmp_path)
    monkeypatch.setattr(publish, "build_service",
                        lambda: pytest.fail("dry run must not build a service"))
    publish.publish_long(cfg, reg, ep_id, {"dry_run": True})
    entry = reg.get(ep_id)
    assert not entry.get("youtube_video_id")


def test_publish_long_missing_video_fails(tmp_path):
    cfg, reg, ep_id, base = _long_setup(tmp_path)
    reg.get(ep_id)["video_path"] = str(tmp_path / "gone.mp4")
    reg.save()
    with pytest.raises(YouTubeError, match="missing"):
        publish.publish_long(cfg, reg, ep_id, {})


def test_publish_long_quota_not_recorded(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _long_setup(tmp_path)
    monkeypatch.setattr(publish, "build_service", lambda: FakeService())
    monkeypatch.setattr(publish, "_upload",
                        lambda *a, **k: (_ for _ in ()).throw(QuotaExceeded("quota")))
    with pytest.raises(QuotaExceeded):
        publish.publish_long(cfg, reg, ep_id, {})
    assert not reg.get(ep_id).get("youtube_video_id")


def test_publish_long_resume_verifies_without_reupload(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _long_setup(tmp_path)
    entry = reg.get(ep_id)
    entry["youtube_video_id"] = "vidResume"
    reg.save()
    svc = FakeService([{"items": [{"status": {"uploadStatus": "processed",
                                              "privacyStatus": "public"}}]}])
    monkeypatch.setattr(publish, "build_service", lambda: svc)
    monkeypatch.setattr(publish, "_upload",
                        lambda *a, **k: pytest.fail("must not re-upload a known video id"))
    monkeypatch.setattr(publish, "_notify", lambda t: None)

    publish.publish_long(cfg, reg, ep_id, {})
    assert reg.get(ep_id)["youtube_verified"] is True
    assert svc._videos.list_kwargs["id"] == "vidResume"


# --- stage: publish_shorts --------------------------------------------------


def _shorts_setup(tmp_path, statuses=("rendered", "rendered")):
    cfg, reg, ep_id, base = _long_setup(tmp_path)
    shorts_dir = base / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)
    shorts = {}
    for i, status in enumerate(statuses, 1):
        sid = f"short_{i}"
        doc = shorts_dir / f"short_{i}.json"
        doc.write_text(json.dumps({"short_id": sid, "title": f"Title {i}", "kind": "funny"}),
                       encoding="utf-8")
        video = base / "render" / f"short_{i}.mp4"
        video.write_bytes(b"\x00" * 4096)
        shorts[sid] = {"status": status, "file": str(doc), "video_path": str(video),
                       "title": f"Title {i}", "kind": "funny"}
    entry = reg.get(ep_id)
    entry["shorts"] = shorts
    reg.save()
    return cfg, reg, ep_id, base


def test_publish_shorts_all(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _shorts_setup(tmp_path)
    svc = FakeService([{"items": [{"status": {"uploadStatus": "processed"}}]}])
    calls, notifies = [], []
    counter = {"n": 0}

    def fake_upload(service, path, body, *, label):
        counter["n"] += 1
        calls.append(label)
        return f"vidS{counter['n']}"

    monkeypatch.setattr(publish, "build_service", lambda: svc)
    monkeypatch.setattr(publish, "_upload", fake_upload)
    monkeypatch.setattr(publish, "_notify", notifies.append)

    publish.publish_shorts(cfg, reg, ep_id, {})

    shorts = reg.get(ep_id)["shorts"]
    assert all(shorts[s]["status"] == "uploaded" for s in shorts)
    assert shorts["short_1"]["youtube_video_id"] == "vidS1"
    assert len(calls) == 2
    assert notifies and notifies[0].startswith("SUCCESS shorts")


def test_publish_shorts_partial_failure_resumes(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _shorts_setup(tmp_path)
    svc = FakeService([{"items": [{"status": {"uploadStatus": "processed"}}]}])
    monkeypatch.setattr(publish, "build_service", lambda: svc)
    monkeypatch.setattr(publish, "_notify", lambda t: None)

    def flaky_upload(service, path, body, *, label):
        if label.endswith("short_2"):
            raise QuotaExceeded("quota")
        return "vidS1"

    monkeypatch.setattr(publish, "_upload", flaky_upload)
    with pytest.raises(QuotaExceeded):
        publish.publish_shorts(cfg, reg, ep_id, {})

    shorts = reg.get(ep_id)["shorts"]
    assert shorts["short_1"]["status"] == "uploaded"
    assert shorts["short_2"]["status"] == "upload_failed"
    assert "quota" in shorts["short_2"]["error"]

    # resume: only the failed short is attempted
    attempts = []

    def retry_upload(service, path, body, *, label):
        attempts.append(label)
        return "vidS2"

    monkeypatch.setattr(publish, "_upload", retry_upload)
    publish.publish_shorts(cfg, reg, ep_id, {})
    assert attempts == [f"{ep_id}/short_2"]
    shorts = reg.get(ep_id)["shorts"]
    assert shorts["short_2"]["status"] == "uploaded"
    assert shorts["short_2"]["youtube_video_id"] == "vidS2"


def test_publish_shorts_dry_run_skips(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _shorts_setup(tmp_path)
    monkeypatch.setattr(publish, "_upload",
                        lambda *a, **k: pytest.fail("dry run must not upload"))
    publish.publish_shorts(cfg, reg, ep_id, {"dry_run": True})
    assert reg.get(ep_id)["shorts"]["short_1"]["status"] == "rendered"


def test_publish_shorts_nothing_pending(tmp_path, monkeypatch):
    cfg, reg, ep_id, base = _shorts_setup(tmp_path, statuses=("uploaded", "uploaded"))
    monkeypatch.setattr(publish, "build_service",
                        lambda: pytest.fail("no pending work must not build a service"))
    publish.publish_shorts(cfg, reg, ep_id, {})


# --- channel snapshot -------------------------------------------------------


class FakeChannels:
    def __init__(self, resp):
        self.resp = resp

    def list(self, **kw):
        self.kw = kw
        return self

    def execute(self):
        return self.resp


class FakeChannelService:
    def __init__(self, resp):
        self._ch = FakeChannels(resp)

    def channels(self):
        return self._ch


def test_channel_stats_parses_and_formats():
    svc = FakeChannelService({"items": [{
        "id": "UC123",
        "snippet": {"title": "Fernwood Friends", "customUrl": "@fernwoodfriends"},
        "statistics": {"subscriberCount": "1234", "videoCount": "9", "viewCount": "56789",
                       "hiddenSubscriberCount": False},
    }]})
    stats = ch.channel_stats(svc)
    assert stats["subscribers"] == 1234
    assert stats["videos"] == 9
    assert stats["views"] == 56789
    assert stats["handle"] == "@fernwoodfriends"
    text = ch.format_snapshot(stats)
    assert "1,234" in text and "@fernwoodfriends" in text


def test_channel_stats_no_channel_raises():
    svc = FakeChannelService({"items": []})
    with pytest.raises(YouTubeError, match="no channel"):
        ch.channel_stats(svc)
