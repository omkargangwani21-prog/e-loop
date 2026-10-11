import unittest

from eloop.ledger import GENESIS_HASH, build_event, verify_chain


def chain() -> list:
    first = build_event(None, type_="requested", actor="citizen", data={"category": "laptop", "quantity": 1}, at="2026-10-11T05:00:00Z")
    second = build_event(first, type_="confirmed", actor="collector:a", data={"collector_id": "a"}, at="2026-10-11T05:01:00Z")
    third = build_event(second, type_="collected", actor="collector:a", data={"weight_g": 2300}, at="2026-10-11T05:02:00Z")
    return [first, second, third]


class LedgerTests(unittest.TestCase):
    def test_first_event_links_to_genesis(self) -> None:
        self.assertEqual(chain()[0].prev_hash, GENESIS_HASH)
        self.assertEqual([e.seq for e in chain()], [1, 2, 3])

    def test_valid_chain_verifies(self) -> None:
        self.assertTrue(verify_chain(chain()))

    def test_tampering_with_data_is_detected(self) -> None:
        events = chain()
        events[2] = events[2].model_copy(update={"data": {"weight_g": 9999}})
        self.assertFalse(verify_chain(events))

    def test_removing_a_middle_event_is_detected(self) -> None:
        events = chain()
        self.assertFalse(verify_chain([events[0], events[2]]))

    def test_reordered_input_still_verifies_by_sequence(self) -> None:
        events = chain()
        self.assertTrue(verify_chain([events[2], events[0], events[1]]))

    def test_floats_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            build_event(None, type_="collected", actor="x", data={"weight_kg": 2.3}, at="2026-10-11T05:00:00Z")

    def test_hash_is_deterministic(self) -> None:
        self.assertEqual(chain()[2].hash, chain()[2].hash)


if __name__ == "__main__":
    unittest.main()
