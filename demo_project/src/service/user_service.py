from src.repository.user_repo import UserRepository

class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo
        
    def get_user_display_name(self, user_id: int) -> str:
        user = self.repo.get_user(user_id)
        # Bug: NoneType has no attribute 'name' if user is None
        return user.name
