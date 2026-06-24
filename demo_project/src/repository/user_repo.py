class User:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name

class UserRepository:
    def get_user(self, user_id: int) -> User | None:
        if user_id == 1:
            return User(1, "Alice")
        return None
