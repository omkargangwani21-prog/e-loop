import unittest

from eloop.matching import haversine_km, nearest_collector
from eloop.service import load_collectors


class MatchingTests(unittest.TestCase):
    def test_haversine_known_distance(self) -> None:
        # Connaught Place to Saket is roughly 10 km as the crow flies.
        distance = haversine_km(28.6315, 77.2167, 28.5245, 77.2066)
        self.assertGreater(distance, 9)
        self.assertLess(distance, 14)

    def test_zero_distance(self) -> None:
        self.assertAlmostEqual(haversine_km(28.6, 77.2, 28.6, 77.2), 0.0, places=6)

    def test_nearest_picks_closest_accepting_collector(self) -> None:
        collectors = load_collectors().values()
        collector, km = nearest_collector(collectors, "smartphone", 28.5830, 77.0510, 30)  # type: ignore[misc]
        self.assertEqual(collector.id, "demo-dwarka")
        self.assertLess(km, 2)

    def test_category_filter_skips_collectors_that_do_not_accept(self) -> None:
        collectors = load_collectors().values()
        # Rohini does not accept batteries; from Rohini the nearest accepting point is elsewhere.
        collector, _ = nearest_collector(collectors, "battery_pack", 28.7383, 77.0822, 60)  # type: ignore[misc]
        self.assertNotEqual(collector.id, "demo-rohini")

    def test_out_of_range_returns_none(self) -> None:
        collectors = load_collectors().values()
        self.assertIsNone(nearest_collector(collectors, "laptop", 19.0760, 72.8777, 30))  # Mumbai


if __name__ == "__main__":
    unittest.main()
