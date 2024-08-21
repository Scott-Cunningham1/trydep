from fastapi import FastAPI
from mangum import Mangum
import os
from psycopg_pool import ConnectionPool
from fastapi.middleware.cors import CORSMiddleware
from jwtdown_fastapi.authentication import Authenticator
from pydantic import BaseModel
from datetime import date, timedelta
from jwtdown_fastapi.authentication import Token

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status
)

from typing import (
    List,
    Optional,
    Union
)


app = FastAPI()

DATABASE_URL = "postgresql://cfp:runitback66@cfpgame.cdiou22ye712.us-east-2.rds.amazonaws.com:5432/cfpgame"
pool = ConnectionPool(conninfo=DATABASE_URL)
router = APIRouter()


    
from datetime import timedelta

class DuplicateUserError(ValueError):
    pass


class Error(BaseModel):
    message: str


class UserIn(BaseModel):
    username: str
    password: str
    verified_password: str


class UserOut(BaseModel):
    id: int
    username: str


class UserOutWithHashedPassword(UserOut):
    hashed_password: str


class UsersOut(BaseModel):
    username: str | None
    rank: int | None
    losses: int | None
    points: int | None


class TeamForm(BaseModel):
    name: str | None
    rank: int | None
    wins: int | None
    losses: int | None
    web_id: int | None
    user_id: int | None


class TeamOut(TeamForm):
    id: int


class RankingsIn(BaseModel):
    school: str


class RankingsOut(RankingsIn):
    id: int


class AccountForm(BaseModel):
    username: str
    password: str


class AccountToken(Token):
    user: UserOut


class HttpError(BaseModel):
    detail: str





class TeamsQueries:
    def create(
            self,
            team: TeamForm,
    ):
        with pool.connection() as conn:
            with conn.cursor() as db:
                result = db.execute(
                    """
                    INSERT INTO teams
                        (name,
                        rank,
                        wins,
                        losses,
                        web_id,
                        user_id)
                    VALUES
                        (
                        %s,%s,%s,%s,
                        %s,%s
                        )
                    RETURNING id, *;
                    """,
                    [
                        team.name,
                        team.rank,
                        team.wins,
                        team.losses,
                        team.web_id,
                        team.user_id,
                    ]
                )
                new_team = {}
                new_team["id"] = result.fetchone()[0]
                new_team = TeamOut(**new_team, **team.dict())
                return new_team

    def update(
            self,
            id: int,
            team: TeamForm,
    ):
        with pool.connection() as conn:
            with conn.cursor() as db:
                result = db.execute(
                    """
                    UPDATE teams
                    SET user_id = %s
                    WHERE id = %s
                    RETURNING *;
                    """,
                    [
           
                        team.user_id,
                        id
                    ]
                )
                updated_team = result.fetchone()
                updated_team = TeamOut(**dict(zip(["id", "name", "rank", "wins", "losses", "web_id", "user_id"], updated_team)))
                return updated_team
    
    def get_all_teams(self) -> Union[Error, List[TeamOut]]:
        try:
            with pool.connection() as conn:
                with conn.cursor() as db:
                    db.execute(
                        """
                        SELECT *
                        FROM teams
                        ORDER BY rank desc;
                        """
                    )
                    teams_list = []
                    for record in db.fetchall():
                        team = TeamOut(
                            id=record[0],
                            name=record[1],
                            rank=record[2],
                            wins=record[3],
                            losses=record[4],
                            web_id=record[5],
                            user_id=record[6],
                        )
                        teams_list.append(team)
                    return teams_list
        except Exception as e:
            # Log the exception or print it for debugging
            print(f"Error in get_all_teams: {e}")
            return Error(message="Internal Server Error")
    

    def get_team(self, id) -> Union[Error, List[TeamOut]]:
        try:
            with pool.connection() as conn:
                with conn.cursor() as db:
                    db.execute(
                        """
                        SELECT *
                        FROM teams
                        WHERE id = %s;
                        """,
                        [id]
                    )
                    record = db.fetchone()
                    if record:
                        team = TeamOut(
                            id=record[0],
                            name=record[1],
                            rank=record[2],
                            wins=record[3],
                            losses=record[4],
                            web_id=record[5],
                            user_id=record[6],
                        )
                        return team
                    else:
                        return Error(message="Team not found")
        except Exception as e:
            # Log the exception or print it for debugging
            print(f"Error in get_all_teams: {e}")
            return Error(message="Internal Server Error")

class UsersQueries:
    def create(
        self, user: UserIn, hashed_password: str
    ) -> UserOutWithHashedPassword | Error:
        username_exists = self.get_user(user.username)
        if isinstance(username_exists, UserOutWithHashedPassword):
            raise DuplicateUserError(
                "Cannot create user from provided inputs."
            )
        # connect to the database
        with pool.connection() as conn:
            with conn.cursor() as db:
                result = db.execute(
                    """
                    INSERT INTO users
                    (username, password)
                    VALUES
                        (%s, %s)
                    RETURNING id, username, password;
                    """,
                    [user.username, hashed_password],
                )
                new_user = result.fetchone()
                if not new_user:
                    return Error(message="Could not create user.")
                id = new_user[0]
                username = new_user[1]
                hashed_password = new_user[2]
                return UserOutWithHashedPassword(
                    id=id, username=username, hashed_password=hashed_password
                )

    def get_user(self, username: str) -> UserOutWithHashedPassword | None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as db:
                    result = db.execute(
                        """
                        SELECT
                        id,
                        username,
                        password
                        FROM users
                        WHERE username = %s
                        """,
                        [username],
                    )
                    record = result.fetchone()
                    if not record:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Could not find a user with this username.",
                        )
                    id = record[0]
                    username = record[1]
                    hashed_password = record[2]
                    return UserOutWithHashedPassword(
                        id=id,
                        username=username,
                        hashed_password=hashed_password,
                    )
        except Exception:
            return None

    def get_users(self) -> Union[Error, List[UsersOut]]:
        with pool.connection() as conn:
            with conn.cursor() as db:
                db.execute(
                    """
                    SELECT username as username, COALESCE(SUM(teams.rank), 0) AS rank,
                        COALESCE(SUM(teams.losses), 0) AS losses, 
                        COALESCE(SUM(teams.losses), 0) * 5 AS points
                    FROM users
                    LEFT JOIN teams on users.id = teams.user_id
                    GROUP by users.username
                    ORDER BY rank asc
                    """
                )
                users = []
                for record in db:
                    user = UsersOut(
                       username=record[0],
                       rank=record[1],
                       losses=record[2],
                       points=record[3]
                    )
                    users.append(user)
                return users


    def get_for_login(self, username: str) -> UserOutWithHashedPassword | None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as db:
                    result = db.execute(
                        """
                        SELECT
                        id,
                        username,
                        password
                        FROM users
                        WHERE username = %s
                        """,
                        [username],
                    )
                    record = result.fetchone()
                    if not record:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Could not find a user with this username.",
                        )
                    id = record[0]
                    username = record[1]
                    hashed_password = record[2]
                    return UserOutWithHashedPassword(
                        id=id,
                        username=username,
                        hashed_password=hashed_password,
                    )
        except Exception:
            return None
        
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


logout_hours = timedelta(hours=168)
authenticator = BalancebeamAuthenticator(
    os.environ["SIGNING_KEY"],
    exp=logout_hours
)

@app.post("/api/teams", response_model=Union[TeamOut, Error])
def create_team(
    team_form: TeamForm,
    request: Request,
    response: Response,
    repo: TeamsQueries = Depends(),
    user_data: Optional[dict] = Depends(
        authenticator.get_current_account_data
    ),
):
    team = TeamForm(
        **team_form.dict()
    )
    try:
        new_team = repo.create(team)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a team with provided info: " + str(e),
        )
    return new_team


@app.get("/api/teams", response_model=Union[Error, List[TeamOut]])
def get_teams(
    repo: TeamsQueries = Depends(),
    user_data: Optional[dict] = Depends(authenticator.get_current_account_data)
):
    return repo.get_all_teams()


@app.get("/api/teams/{id}", response_model=Union[Error, TeamOut])
def get_team(
    id: int,
    repo: TeamsQueries = Depends(),
    user_data: Optional[dict] = Depends(authenticator.get_current_account_data)
):
    team = repo.get_team(id)
    if team:
        return team


@app.put(
    "/api/teams/{id}",
    response_model=Union[TeamOut, Error]
)
def update_team(
    id: int,
    team_form: TeamForm,
    repo: TeamsQueries = Depends(),
    user_data: Optional[dict] = Depends(authenticator.get_current_account_data)
):

    user_id = user_data["id"]

    updated_team= TeamForm(
    name=team_form.name,
    rank=team_form.rank,
    wins=team_form.wins,
    losses=team_form.losses,
    web_id=team_form.web_id,
    user_id=user_id

)

    try:
        updated_team = repo.update(id, updated_team)
      
        return updated_team
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update team with provided info: " + str(e),
        )


@app.get("/token", response_model=AccountToken | None)
async def get_token(
    request: Request,
    user: UserOut = Depends(authenticator.try_get_current_account_data),
) -> AccountToken | None:
    if user and authenticator.cookie_name in request.cookies:
        return AccountToken(
            access_token=request.cookies[authenticator.cookie_name],
            token_type="Bearer",
            user=user
            )


@app.get("/api/users/{username}", response_model=UserOut | Error)
def get_user(
    username: str,
    repo: UsersQueries = Depends(),
    user_data: Optional[dict] = Depends(authenticator.get_current_account_data)
) -> UserOut | Error:
    try:
        user = repo.get_user(username)
        if user:
            return user
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    

@app.post("/api/users", response_model=Union[AccountToken, Error])
async def create_user(
    info: UserIn,
    request: Request,
    response: Response,
    repo: UsersQueries = Depends(),
):
    if info.verified_password != info.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords no not match:",
        )
    hashed_password = authenticator.hash_password(info.password)
    try:
        newuser = repo.create(info, hashed_password)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if not isinstance(newuser, UserOutWithHashedPassword):
        return Error(message="Could not create user.")

    form = AccountForm(username=info.username, password=info.password)
    token = await authenticator.login(response, request, form, repo)
    return AccountToken(user=newuser, **token.dict())


@app.get("/api/users", response_model=Union[List[UsersOut], Error])
async def get_users(
    repo: UsersQueries = Depends(),
    user_data: Optional[dict] = Depends(
        authenticator.get_current_account_data)
):
    return repo.get_users()





# from fastapi import FastAPI
# from mangum import Mangum
# from fastapi.middleware.cors import CORSMiddleware
# from routers import users, teams
# from authenticator import authenticator


# app = FastAPI()
# handler = Mangum(app)


# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# app.include_router(authenticator.router, tags=["auth"])
# app.include_router(users.router, tags=["users"])
# app.include_router(teams.router, tags=["teams"])
