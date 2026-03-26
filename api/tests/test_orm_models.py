def test_sync_source_type_has_expected_values():
    from app.models.entities import SyncSourceType
    assert SyncSourceType.feishu.value == "feishu"
    assert SyncSourceType.google_drive.value == "google_drive"
    assert SyncSourceType.tidb_docs.value == "tidb_docs"


def test_sync_status_enum_has_expected_values():
    from app.models.entities import SyncStatusEnum
    assert SyncStatusEnum.idle.value == "idle"
    assert SyncStatusEnum.syncing.value == "syncing"
    assert SyncStatusEnum.error.value == "error"


def test_knowledge_index_can_be_instantiated():
    from app.models.entities import KnowledgeIndex
    ki = KnowledgeIndex(
        source_type="feishu",
        source_ref="ABC123",
        title="Test Doc",
        chunk_text="hello world",
        chunk_index=0,
        org_id=1,
    )
    assert ki.source_ref == "ABC123"
    assert ki.org_id == 1


def test_sync_status_can_be_instantiated():
    from app.models.entities import SyncStatus, SyncStatusEnum
    ss = SyncStatus(source_type="feishu", org_id=1, status=SyncStatusEnum.idle)
    assert ss.org_id == 1


def test_sync_source_type_has_all_five_members():
    from app.models.entities import SyncSourceType
    values = {m.value for m in SyncSourceType}
    assert values == {"feishu", "google_drive", "chorus", "tidb_docs", "github"}


def test_sync_status_status_attribute_is_set():
    from app.models.entities import SyncStatus, SyncStatusEnum
    ss = SyncStatus(source_type="feishu", org_id=1, status=SyncStatusEnum.syncing)
    assert ss.status == SyncStatusEnum.syncing
