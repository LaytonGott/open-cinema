import unittest
from pathlib import Path

import httpx
from comfy_sdk import events

from app.comfy import download_output, submit_and_follow, upload_video
from app.outage import OutageGuard


class StubJob:
    def __init__(self):
        self.result_calls = 0

    def events(self):
        yield events.StatusChange(status="running")
        yield events.Log(level="info", message="ignored")
        yield events.Progress(value=0.5, current_node="n1", step=2, steps=4)

    def result(self):
        self.result_calls += 1


class StubWorkflows:
    def from_json(self, graph):
        return graph


class StubClient:
    def __init__(self, job):
        self.job = job
        self.graphs = []
        self.workflows = StubWorkflows()

    def submit(self, graph):
        self.graphs.append(graph)
        return self.job


class SubmitAndFollowTest(unittest.TestCase):
    def test_follows_events_in_order(self):
        job = StubJob()
        client = StubClient(job)
        got, jobs = [], []
        returned = submit_and_follow(client, {"g": 1}, lambda *a: got.append(a), jobs.append)
        self.assertEqual(got, [
            ("status", "running"),
            ("progress", {"current_node": "n1", "value": 0.5, "step": 2, "steps": 4}),
        ])
        self.assertEqual(client.graphs, [{"g": 1}])
        self.assertEqual(jobs, [job])
        self.assertEqual(job.result_calls, 1)
        self.assertIs(returned, job)

    def test_on_job_optional(self):
        job = StubJob()
        self.assertIs(submit_and_follow(StubClient(job), {}, lambda *a: None), job)

    def test_retry_events(self):
        class FlakyEventsJob(StubJob):
            def __init__(self):
                super().__init__()
                self.event_calls = 0

            def events(self):
                self.event_calls += 1
                if self.event_calls == 1:
                    raise httpx.ConnectError("down")
                yield from super().events()

        job = FlakyEventsJob()
        got = []
        guard = OutageGuard(sleep=lambda s: None)
        submit_and_follow(StubClient(job), {}, lambda *a: got.append(a), guard=guard)
        self.assertEqual(job.event_calls, 2)
        self.assertEqual(got[0], ("status", "running"))
        self.assertEqual(len(got), 2)
        self.assertEqual(job.result_calls, 1)

    def test_retry_result(self):
        class FlakyResultJob(StubJob):
            def result(self):
                super().result()
                if self.result_calls == 1:
                    request = httpx.Request("GET", "http://comfy.test/history")
                    response = httpx.Response(503, request=request)
                    raise httpx.HTTPStatusError("503", request=request, response=response)

        job = FlakyResultJob()
        guard = OutageGuard(sleep=lambda s: None)
        returned = submit_and_follow(StubClient(job), {}, lambda *a: None, guard=guard)
        self.assertIs(returned, job)
        self.assertEqual(job.result_calls, 2)


class StubOutput:
    def __init__(self, node_id, name):
        self.node_id = node_id
        self.name = name
        self.saved = []

    def to_file(self, path):
        self.saved.append(path)
        return path


class StubOutputsJob:
    def __init__(self, outputs):
        self.outputs = outputs


class DownloadOutputTest(unittest.TestCase):
    def test_path_uses_extension_of_name(self):
        other = StubOutput("1", "a.png")
        out = StubOutput("2", "x.webm")
        path = download_output(StubOutputsJob([other, out]), "2", "dest", "before")
        self.assertEqual(path, Path("dest") / "before.webm")
        self.assertEqual(path.name, "before.webm")
        self.assertEqual(out.saved, [path])
        self.assertEqual(other.saved, [])

    def test_default_extension(self):
        out = StubOutput("2", "noext")
        path = download_output(StubOutputsJob([out]), "2", "dest", "after")
        self.assertEqual(path.name, "after.mp4")
        self.assertEqual(out.saved, [path])

    def test_unknown_node_raises(self):
        with self.assertRaises(LookupError):
            download_output(StubOutputsJob([StubOutput("1", "a.mp4")]), "9", "dest", "s")

    def test_retry_download(self):
        class FlakyOutput(StubOutput):
            def to_file(self, path):
                self.saved.append(path)
                if len(self.saved) == 1:
                    request = httpx.Request("GET", "http://comfy/view")
                    response = httpx.Response(503, request=request)
                    raise httpx.HTTPStatusError("503", request=request, response=response)
                return path

        out = FlakyOutput("2", "x.mp4")
        guard = OutageGuard(sleep=lambda s: None)
        path = download_output(StubOutputsJob([out]), "2", "dest", "after", guard)
        self.assertEqual(path, Path("dest") / "after.mp4")
        self.assertEqual(len(out.saved), 2)

    def test_download_lookup_error_propagates(self):
        guard = OutageGuard(sleep=lambda s: None)
        with self.assertRaises(LookupError):
            download_output(StubOutputsJob([StubOutput("1", "a.mp4")]), "9", "dest", "s", guard)


class StubAssets:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def from_file(self, path):
        self.calls.append(path)
        return self.result


class StubAssetsClient:
    def __init__(self, assets):
        self.assets = assets


class UploadVideoTest(unittest.TestCase):
    def test_returns_asset_from_file(self):
        sentinel = object()
        assets = StubAssets(sentinel)
        result = upload_video(StubAssetsClient(assets), "clip.mp4")
        self.assertIs(result, sentinel)
        self.assertEqual(assets.calls, ["clip.mp4"])

    def test_retry_upload(self):
        sentinel = object()

        class FlakyAssets(StubAssets):
            def from_file(self, path):
                self.calls.append(path)
                if len(self.calls) <= 2:
                    raise httpx.ConnectError("down")
                return self.result

        assets = FlakyAssets(sentinel)
        guard = OutageGuard(sleep=lambda s: None)
        result = upload_video(StubAssetsClient(assets), "clip.mp4", guard)
        self.assertIs(result, sentinel)
        self.assertEqual(len(assets.calls), 3)


if __name__ == "__main__":
    unittest.main()
