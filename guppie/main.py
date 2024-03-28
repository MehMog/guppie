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
from sqlmodel import Field, Session, SQLModel, create_engine, select

load_dotenv()

class Feature(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(sa_column_kwargs={"default": datetime.now()})
    name: str
    priority: str
    description: str
    rank: int | None = Field(default=1)

class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(sa_column_kwargs={"default": datetime.now()})

class VoteTracker(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(default=None, foreign_key="user.id")
    feature_id: uuid.UUID = Field(default=None, foreign_key="feature.id")
    upvote: bool | None = Field(default=False)
    downvote: bool | None = Field(default=False)


engine = create_engine("mssql+pyodbc:///?odbc_connect=DSN=sqldb;UID="+os.getenv("MSSQL_UID")+";PWD="+os.getenv("MSSQL_PWD"))
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

    with Session(engine) as session:
        if user_cookie is None:
            user_cookie = User()
            session.add(user_cookie)
            session.commit()
            session.refresh(user_cookie)

            user_cookie = user_cookie.id

        statement = select(Feature)  # replace Item with your table class
        results = session.exec(statement)
        if not results:
            features = ['']
        else:
            features = []
            for feature in results:
                features.append(templates.get_template('feature.html').render(request = feature))
        
        response = templates.TemplateResponse("index.html", {"request": request, "features": '\n'.join(features)})
        response.set_cookie(key="user_cookie", value=user_cookie)
        return response

@app.get("/get_form", response_class=HTMLResponse)
async def read_root(request: Request):

    return templates.TemplateResponse("form.html", {"request": request})


@app.get("/feature", response_class=HTMLResponse)
async def submit_feature(id: str):
    with Session(engine) as session:
        feature = session.get(Feature, Feature(id=id).id)
        if not feature:
            raise HTTPException(status_code=404, detail="Feature not found")
        return templates.TemplateResponse("feature.html", {"request": feature.model_dump()})

@app.post("/submit_feature", response_class=HTMLResponse)
async def submit_feature(feature: Feature):
    with Session(engine) as session:
        session.add(feature)
        session.commit()
        session.refresh(feature)
        return templates.TemplateResponse("feature.html", {"request": feature.model_dump()})

@app.put("/increase_rank", response_class=HTMLResponse)
async def increase_rank(feature: Feature):
    with Session(engine) as session:
        feature = session.get(Feature, feature.id)
        if not feature:
            raise HTTPException(status_code=404, detail="Feature not found")
        
        feature.rank += 1
        session.commit()
        session.refresh(feature)
        return '<h2 class="rank-number">'+str(feature.rank)+'</h2>'
    
@app.put("/decrease_rank", response_class=HTMLResponse)
async def increase_rank(feature: Feature):
    with Session(engine) as session:
        feature = session.get(Feature, feature.id)
        if not feature:
            raise HTTPException(status_code=404, detail="Feature not found")
        
        feature.rank = max(feature.rank - 1, 1)
        session.commit()
        session.refresh(feature)
        return '<h2 class="rank-number">'+str(feature.rank)+'</h2>'



