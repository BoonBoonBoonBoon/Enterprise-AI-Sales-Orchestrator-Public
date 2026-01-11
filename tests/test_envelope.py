import unittest

from agent.utils.envelope import Envelope, make_envelope, validate_envelope


class TestEnvelope(unittest.TestCase):
    def test_from_records_and_validate(self):
        records = [
            {"id": "r1", "email": "a@example.com", "name": "Alice"},
            {"id": "r2", "email": "b@example.com", "name": "Bob"},
        ]
        env = Envelope.from_records("supabase.leads", records, task_id="t1")
        d = env.to_dict()
        self.assertIn("metadata", d)
        self.assertIn("records", d)
        self.assertEqual(d["metadata"]["task_id"], "t1")
        # validate_envelope should accept the produced dict
        self.assertTrue(validate_envelope(d))

    def test_include_raw(self):
        records = [{"id": "r3", "foo": 1}]
        env = Envelope.from_records("supabase.leads", records, task_id="t2", include_raw=True)
        d = env.to_dict()
        self.assertEqual(len(d["records"]), 1)
        prov = d["records"][0].get("provenance", {})
        self.assertIn("raw_row", prov)


if __name__ == "__main__":
    unittest.main()
