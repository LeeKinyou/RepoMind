import pytest
from src.service.user_service import UserService
from src.repository.user_repo import UserRepository

def test_get_user_display_name_success():
    repo = UserRepository()
    service = UserService(repo)
    assert service.get_user_display_name(1) == "Alice"

def test_get_user_display_name_fail():
    repo = UserRepository()
    service = UserService(repo)
    # This will raise AttributeError when user_id is 99 because it returns None
    service.get_user_display_name(99)
