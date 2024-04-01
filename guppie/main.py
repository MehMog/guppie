from dotenv import load_dotenv
import os
import uuid
import secrets
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Template
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Field, Session, SQLModel, create_engine, select, func

load_dotenv()

class Feature(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(sa_column_kwargs={"default": datetime.now()})
    name: str
    priority: str
    product: str
    description: str
    rank: int | None = Field(default=1)

class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(sa_column_kwargs={"default": datetime.now()})

class VoteTracker(SQLModel, table=True):
    user_id: uuid.UUID = Field(default=None, foreign_key="user.id", primary_key=True)
    feature_id: uuid.UUID = Field(default=None, foreign_key="feature.id", primary_key=True)
    vote: int = Field(default=0)

map_priority = {"low": "Low", "med":"Medium", "high":"High"}
map_priority_color = {"low": "primary", "med":"warning", "high":"danger"}


engine = create_engine("mssql+pyodbc:///?odbc_connect=DSN=sqldb;UID="+os.getenv("MSSQL_UID")+";PWD="+os.getenv("MSSQL_PWD")).execution_options(schema_translate_map={None: os.getenv("DATABASE_SCHEMA")})
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


# Create an instance of FastAPI
app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()


# Define a route for the root endpoint
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):

    user_cookie = request.cookies.get("user_cookie")

    features = ['']
    feature_votes = 0
    feature_count = 0
    with Session(engine) as session:
        if user_cookie is None:
            user_cookie = User()
            session.add(user_cookie)
            session.commit()
            session.refresh(user_cookie)

            user_cookie = user_cookie.id

        statement = select(Feature).order_by(Feature.rank.desc())  # replace Item with your table class
        results = session.exec(statement)
        if results:
            features = []
            for feature in results:
                feature_votes += feature.rank
                feature_count += 1
                priority_mapped = map_priority.get(feature.priority)
                priority_color_mapped = map_priority_color.get(feature.priority)
                features.append(templates.get_template('feature.html').render(request = feature, priority_mapped=priority_mapped, priority_color=priority_color_mapped))
            
        
        
        response = templates.TemplateResponse("index.html", {"request": request
                                                        , "features": '\n'.join(features)
                                                        , "feature_votes": feature_votes
                                                        , "feature_count": feature_count})
        response.set_cookie(key="user_cookie", value=user_cookie)
        return response


@app.get("/feature", response_class=HTMLResponse)
async def submit_feature(id: str):
    with Session(engine) as session:
        feature = session.get(Feature, Feature(id=id).id)
        priority_mapped = map_priority.get(feature.priority)
        priority_color_mapped = map_priority_color.get(feature.priority)
        print(feature.priority)
        if not feature:
            raise HTTPException(status_code=404, detail="Feature not found")
        return templates.TemplateResponse("feature.html", {"request": feature.model_dump(), "priority_mapped": priority_mapped, "priority_color": priority_color_mapped})

@app.post("/submit_feature", response_class=HTMLResponse)
async def submit_feature(feature: Feature):
    with Session(engine) as session:
        session.add(feature)
        session.commit()
        session.refresh(feature)
        priority_mapped = map_priority.get(feature.priority)
        priority_color_mapped = map_priority_color.get(feature.priority)
        return templates.TemplateResponse("feature.html", {"request": feature.model_dump(), "priority_mapped": priority_mapped, "priority_color": priority_color_mapped})

@app.put("/increase_rank", response_class=HTMLResponse)
async def increase_rank(request: Request, feature: Feature):

    with Session(engine) as session:
        feature = session.get(Feature, feature.id)
        
        if not feature:
            raise HTTPException(status_code=404, detail="Feature not found")
        
        user_cookie = request.cookies.get("user_cookie")
        vote_tracker = session.get(VoteTracker, (user_cookie, feature.id))
        
        if not vote_tracker:
            feature.rank += 1
            session.add(VoteTracker(user_id=user_cookie, feature_id=feature.id, vote=1))
            session.commit()
            session.refresh(feature)
        elif vote_tracker.vote < 1:
            feature.rank += 1
            vote_tracker.vote = vote_tracker.vote + 1
            session.commit()
            session.refresh(feature)

        
        return str(feature.rank)
    
@app.put("/decrease_rank", response_class=HTMLResponse)
async def increase_rank(request: Request, feature: Feature):

    with Session(engine) as session:
        feature = session.get(Feature, feature.id)
        
        if not feature:
            raise HTTPException(status_code=404, detail="Feature not found")
        
        user_cookie = request.cookies.get("user_cookie")
        vote_tracker = session.get(VoteTracker, (user_cookie, feature.id))
        
        if not vote_tracker:
            feature.rank = feature.rank - 1
            session.add(VoteTracker(user_id=user_cookie, feature_id=feature.id, vote=-1))
            session.commit()
            session.refresh(feature)
        elif vote_tracker.vote > -1:
            feature.rank = feature.rank-1 
            vote_tracker.vote = vote_tracker.vote-1
            session.commit()
            session.refresh(feature)
        
        return str(feature.rank)


@app.get("/total_votes", response_class=HTMLResponse)
async def total_votes():
    with Session(engine) as session:
        statement = select(func.sum(Feature.rank))
        result = session.exec(statement).fetchall()[0]
        return str(result)

@app.get("/total_features", response_class=HTMLResponse)
async def total_features():
    with Session(engine) as session:
        statement = select(func.count(Feature.id))
        result = session.exec(statement).fetchall()[0]
        return str(result)