import os
from fastapi import Depends
from datetime import timedelta
from jwtdown_fastapi.authentication import Authenticator
from queries.users import UsersQueries
from models.models import UserOutWithHashedPassword, UserOut


class BalancebeamAuthenticator(Authenticator):
    async def get_account_data(
        self,
        username: str,
        users: UsersQueries = Depends(),
    ):
        return users.get_user(username)

    def get_account_getter(
        self,
        users: UsersQueries = Depends(),
    ):
        return users

    def get_hashed_password(self, user: UserOutWithHashedPassword):
        return user.hashed_password

    def get_account_data_for_cookie(self, user: UserOut):
        return user.username, UserOut(**user.dict())


three_hours = timedelta(hours=3)
authenticator = BalancebeamAuthenticator(
    os.environ["SIGNING_KEY"],
    exp=three_hours
)
