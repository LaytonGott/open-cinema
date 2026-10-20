import unittest

from comfy_sdk import events

from app.comfy import submit_and_follow


class StubJob:
    def __init__(self):
        self.result_calls = 0

    def events(self):
        yield events.StatusChange(status="running")
        yield events.Log(level="info", message="ignored")
        yield events.Progress(value=0.5, current_node="n1", step=2, steps=4)

    def result(self):
        self.result_calls += 1


class StubClient:
    def __init__(self, job):
        self.job = job
        self.graphs = []

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


if __name__ == "__main__":
    unittest.main()
