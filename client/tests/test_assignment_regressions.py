import itertools
import random
import unittest

from app.detection.tracker import Tracker


class AssignmentRegressionTests(unittest.TestCase):
    def test_assignment_matches_exhaustive_objective(self):
        # Verify unmatched/new-ID costs too; simple nearest-neighbor tests
        # would not detect an incorrect rectangular assignment formulation.
        rng = random.Random(44)
        for _ in range(30):
            tracker = Tracker()
            tracker.tracks = {i: dict(hits=1, missing=3) for i in range(4)}
            costs = [[rng.choice([None, -100, 20, 100, 200, 400]) for _ in range(3)]
                     for _ in range(4)]
            indices = {id(track): index for index, track in tracker.tracks.items()}
            tracker._candidate_cost = lambda track, detection: costs[indices[id(track)]][detection]
            assignments, suppressed = tracker._assign_detections([0, 1, 2])
            self.assertFalse(suppressed)

            def objective(choices):
                chosen = [i for i in choices if i is not None]
                if len(chosen) != len(set(chosen)):
                    return float('inf')
                total = 35 * (4 - len(chosen))
                for detection, track in enumerate(choices):
                    if track is None:
                        total += 150
                    elif costs[track][detection] is None:
                        return float('inf')
                    else:
                        total += costs[track][detection]
                return total

            optimal = min(objective(choice) for choice in itertools.product([None, 0, 1, 2, 3], repeat=3))
            self.assertEqual(objective([assignments.get(i) for i in range(3)]), optimal)

    def test_expired_track_cannot_be_reassigned(self):
        tracker = Tracker(max_missing=1)
        detection = dict(x1=10, y1=10, x2=30, y2=50, point=(20, 15))
        old = tracker.update([detection])[0]['id']
        tracker.update([])
        new = tracker.update([detection])[0]['id']
        self.assertNotEqual(old, new)
