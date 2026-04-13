"""Tests for database model definitions (schema validation, not DB queries)."""
from account_hub.db.base import Base
from account_hub.db.models import LinkedEmail, OAuthState, User


def test_user_table_name():
    assert User.__tablename__ == "users"


def test_linked_email_table_name():
    assert LinkedEmail.__tablename__ == "linked_emails"


def test_oauth_state_table_name():
    assert OAuthState.__tablename__ == "oauth_states"


def test_all_models_registered_on_base():
    table_names = set(Base.metadata.tables.keys())
    assert "users" in table_names
    assert "linked_emails" in table_names
    assert "oauth_states" in table_names


def test_user_columns():
    cols = {c.name for c in User.__table__.columns}
    expected = {"id", "username", "email", "password_hash", "is_active", "created_at", "updated_at"}
    assert expected == cols


def test_linked_email_columns():
    cols = {c.name for c in LinkedEmail.__table__.columns}
    expected = {
        "id", "user_id", "email_address", "provider", "provider_user_id",
        "access_token_enc", "refresh_token_enc", "token_expires_at",
        "scopes", "is_verified", "linked_at", "updated_at",
    }
    assert expected == cols


def test_oauth_state_columns():
    cols = {c.name for c in OAuthState.__table__.columns}
    expected = {"id", "state", "user_id", "provider", "redirect_port", "created_at", "expires_at"}
    assert expected == cols


def test_linked_email_unique_constraint():
    """The (user_id, email_address) pair should have a unique constraint."""
    constraints = LinkedEmail.__table__.constraints
    unique_names = {c.name for c in constraints if hasattr(c, "columns")}
    assert "uq_user_email" in unique_names


def test_linked_email_foreign_key_cascades():
    fks = list(LinkedEmail.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "users"
    assert fks[0].parent.table.name == "linked_emails"


def test_oauth_state_foreign_key():
    fks = list(OAuthState.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "users"
