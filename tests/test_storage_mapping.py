from __future__ import annotations

import os
import tempfile
import unittest

from app.db.session import create_engine_and_session, create_tables
from app.services.storage import Storage


class StorageMappingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        engine, factory = create_engine_and_session(self.db_path)
        create_tables(engine)
        self.storage = Storage(factory)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_save_mapping(self) -> None:
        self.storage.save_admin_relay_mapping(admin_message_id=101, target_user_id=5001)
        resolved = self.storage.resolve_user_id_by_admin_message_id(101)
        self.assertEqual(resolved, 5001)

    def test_resolve_user_by_admin_message_id(self) -> None:
        self.storage.save_admin_relay_mapping(admin_message_id=202, target_user_id=7002)
        found = self.storage.resolve_user_id_by_admin_message_id(202)
        missing = self.storage.resolve_user_id_by_admin_message_id(9999)
        self.assertEqual(found, 7002)
        self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
