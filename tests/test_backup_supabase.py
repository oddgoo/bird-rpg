import json
import os

import pytest

from scripts import backup_supabase as bk


class FakeQuery:
    def __init__(self, rows, fail=False):
        self.rows = rows
        self.fail = fail
        self._range = (0, len(rows))

    def select(self, *_):
        return self

    def order(self, *_):
        return self

    def range(self, start, end):
        self._range = (start, end + 1)
        return self

    def execute(self):
        if self.fail:
            raise RuntimeError("boom")

        class Res:
            pass

        r = Res()
        r.data = self.rows[self._range[0]:self._range[1]]
        return r


class FakeBucket:
    def __init__(self, tree, files):
        self.tree = tree  # prefix -> list of entries
        self.files = files  # path -> bytes

    def list(self, prefix, options):
        entries = self.tree.get(prefix, [])
        off, lim = options["offset"], options["limit"]
        return entries[off:off + lim]

    def download(self, path):
        return self.files[path]


class FakeStorage:
    def __init__(self, bucket):
        self.bucket = bucket

    def from_(self, _name):
        return self.bucket


class FakeClient:
    def __init__(self, tables, bucket, failing=()):
        self.tables = tables
        self.failing = set(failing)
        self.storage = FakeStorage(bucket)

    def table(self, name):
        return FakeQuery(self.tables.get(name, []), fail=name in self.failing)


def test_fetch_all_rows_pages_past_limit(monkeypatch):
    monkeypatch.setattr(bk, "PAGE_SIZE", 3)
    rows = [{"id": i} for i in range(7)]
    sb = FakeClient({"players": rows}, FakeBucket({}, {}))
    assert bk.fetch_all_rows(sb, "players", "id") == rows


def test_list_bucket_files_recurses_into_folders():
    bucket = FakeBucket(
        {
            "": [{"name": "u1", "id": None}, {"name": "top.jpg", "id": "a"}],
            "u1": [{"name": "x.jpg", "id": "b"}, {"name": ".emptyFolderPlaceholder", "id": "c"}],
        },
        {},
    )
    assert sorted(bk.list_bucket_files(bucket)) == ["top.jpg", "u1/x.jpg"]


def test_safe_local_path_rejects_escape(tmp_path):
    with pytest.raises(ValueError):
        bk.safe_local_path(str(tmp_path), "../evil.jpg")


def test_run_backup_writes_tables_images_and_manifest(tmp_path):
    sightings = [{"id": 1, "storage_path": "u1/x.jpg", "image_url": "http://x"}]
    bucket = FakeBucket(
        {"": [{"name": "u1", "id": None}], "u1": [{"name": "x.jpg", "id": "b"}]},
        {"u1/x.jpg": b"jpegdata"},
    )
    sb = FakeClient(
        {"players": [{"user_id": "u1"}], "birdwatch_sightings": sightings},
        bucket,
        failing={"memoirs"},
    )
    out = tmp_path / "bk"
    manifest = bk.run_backup(sb, str(out))

    assert json.loads((out / "tables" / "players.json").read_text()) == [{"user_id": "u1"}]
    assert (out / "storage" / "birdwatch-images" / "u1" / "x.jpg").read_bytes() == b"jpegdata"
    assert manifest["storage"]["birdwatch-images"] == {"found": 1, "downloaded": 1}
    assert manifest["tables"]["players"] == 1
    assert "memoirs" not in manifest["tables"]
    assert any("memoirs" in e for e in manifest["errors"])
    assert os.path.exists(out / "manifest.json")
    assert os.path.exists(out / "schema.sql")


class FakeProc:
    def __init__(self, returncode, stderr=""):
        self.returncode = returncode
        self.stderr = stderr


def test_run_pg_dump_writes_both_formats(tmp_path):
    calls = []

    def runner(cmd, **_):
        calls.append(cmd)
        dest = cmd[cmd.index("-f") + 1]
        with open(dest, "w") as f:
            f.write("dump")
        return FakeProc(0)

    manifest = {"errors": []}
    url = "postgresql://postgres:s3cret@db.x.supabase.co:5432/postgres"
    bk.run_pg_dump(url, str(tmp_path), manifest, runner=runner, pg_dump_path="pg_dump")

    assert manifest["errors"] == []
    assert manifest["pg_dump"] == {"database.dump": 4, "database.sql": 4}
    assert all("--schema=public" in c and url in c for c in calls)


def test_run_pg_dump_failure_redacts_password(tmp_path):
    url = "postgresql://postgres:s3cret@db.x.supabase.co:5432/postgres"

    def runner(cmd, **_):
        return FakeProc(1, stderr="password authentication failed: s3cret")

    manifest = {"errors": []}
    bk.run_pg_dump(url, str(tmp_path), manifest, runner=runner, pg_dump_path="pg_dump")

    assert manifest["pg_dump"]["database.dump"] == "failed"
    assert len(manifest["errors"]) == 2
    assert all("s3cret" not in e for e in manifest["errors"])


def test_run_backup_marks_pg_dump_skipped_without_url(tmp_path):
    sb = FakeClient({}, FakeBucket({}, {}))
    manifest = bk.run_backup(sb, str(tmp_path / "bk"), skip_images=True)
    assert manifest["pg_dump"] == "skipped"
