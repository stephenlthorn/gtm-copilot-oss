def test_sync_source_type_has_expected_values():
    from app.models.entities import SyncSourceType
    assert SyncSourceType.google_drive.value == "google_drive"
    assert SyncSourceType.chorus.value == "chorus"
    assert SyncSourceType.tidb_docs.value == "tidb_docs"
    assert SyncSourceType.github.value == "github"


def test_sync_status_enum_has_expected_values():
    from app.models.entities import SyncStatusEnum
    assert SyncStatusEnum.idle.value == "idle"
    assert SyncStatusEnum.syncing.value == "syncing"
    assert SyncStatusEnum.error.value == "error"


def test_knowledge_index_can_be_instantiated():
    from app.models.entities import KnowledgeIndex
    ki = KnowledgeIndex(
        source_type="google_drive",
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
    ss = SyncStatus(source_type="google_drive", org_id=1, status=SyncStatusEnum.idle)
    assert ss.org_id == 1


def test_sync_source_type_has_required_active_members():
    from app.models.entities import SyncSourceType
    values = {m.value for m in SyncSourceType}
    assert {"google_drive", "chorus", "tidb_docs", "github"}.issubset(values)


def test_sync_status_status_attribute_is_set():
    from app.models.entities import SyncStatus, SyncStatusEnum
    ss = SyncStatus(source_type="google_drive", org_id=1, status=SyncStatusEnum.syncing)
    assert ss.status == SyncStatusEnum.syncing


def test_kb_config_has_retrieval_cutover():
    from app.models.entities import KBConfig
    config = KBConfig()
    assert hasattr(config, "retrieval_cutover")
    # SA2 mapped_column(default=False) is a column INSERT default, not a Python __init__ default.
    # The attribute is None on a bare instantiation; the DB applies False on INSERT.
    assert config.retrieval_cutover in (False, None)
