"""Database boundaries protect snapshot consistency and preserve existing data."""

import copy
import json

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from app.db.database import Base
from app.db.models import User, UserInteraction
from app.services.recommendation_service import load_bundle, verify_snapshot
from src.data_loader import sha256_file
from src.seed_database import seed_database
from src.utils import save_model, write_json_report


def test_snapshot_mismatch_rejected(bundle, session_factory):
    different = copy.deepcopy(bundle)
    different.manifest["dataset"]["dataset_sha256"] = "other"
    with session_factory() as db:
        with pytest.raises(RuntimeError, match="snapshot differs"):
            verify_snapshot(db, different)


def test_seeding_is_idempotent(bundle, session_factory):
    with session_factory() as db:
        before = db.scalar(select(func.count()).select_from(UserInteraction))
        seed_database(db, bundle)
        assert db.scalar(select(func.count()).select_from(UserInteraction)) == before


def test_seed_preserves_unrecognized_database(bundle):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(user_id="DO_NOT_DELETE"))
        db.commit()
        with pytest.raises(RuntimeError, match="other data"):
            seed_database(db, bundle)
        assert db.scalar(select(User.user_id)) == "DO_NOT_DELETE"
    engine.dispose()


def test_artifact_identity_and_checksum_validation(bundle, tmp_path):
    save_model(bundle.model, tmp_path / "recommender.joblib")
    write_json_report(bundle.metrics, tmp_path / "evaluation.json")
    manifest = bundle.manifest | {
        "identity": {"versions": {}},
        "files": {
            name: sha256_file(tmp_path / name)
            for name in ["recommender.joblib", "evaluation.json"]
        },
    }
    write_json_report(manifest, tmp_path / "manifest.json")
    assert load_bundle(tmp_path).model.model_version == "test-model"
    (tmp_path / "evaluation.json").write_text("{}")
    with pytest.raises(RuntimeError, match="checksum"):
        load_bundle(tmp_path)


def test_missing_bundle_is_actionable(tmp_path):
    with pytest.raises(RuntimeError, match="Model missing"):
        load_bundle(tmp_path)


def test_fresh_seed_and_retry_do_not_duplicate_rows(bundle, purchases, tmp_path):
    data = tmp_path / "processed"
    data.mkdir()
    purchases.to_csv(data / "purchases.csv", index=False)
    snapshot = copy.deepcopy(bundle)
    snapshot.manifest["dataset"]["processed_sha256"] = sha256_file(
        data / "purchases.csv"
    )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_database(db, snapshot, tmp_path)
        seed_database(db, snapshot, tmp_path)
        assert db.scalar(select(func.count()).select_from(UserInteraction)) == len(
            purchases
        )
    engine.dispose()


def test_failed_seed_rolls_back_all_rows(bundle, purchases, tmp_path, monkeypatch):
    data = tmp_path / "processed"
    data.mkdir()
    purchases.to_csv(data / "purchases.csv", index=False)
    snapshot = copy.deepcopy(bundle)
    snapshot.manifest["dataset"]["processed_sha256"] = sha256_file(
        data / "purchases.csv"
    )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:

        def broken_commit():
            raise RuntimeError("simulated interrupted seed")

        monkeypatch.setattr(db, "commit", broken_commit)
        with pytest.raises(RuntimeError, match="interrupted"):
            seed_database(db, snapshot, tmp_path)
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert db.scalar(select(func.count()).select_from(UserInteraction)) == 0
    engine.dispose()
