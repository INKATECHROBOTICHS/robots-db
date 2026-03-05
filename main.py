import os
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base, Session

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# ===============================
# CONFIG
# ===============================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./robots.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1207135m")
ADMIN_COOKIE_NAME = "admin_session"

# ===============================
# DATABASE
# ===============================

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


class Robot(Base):
    __tablename__ = "robots"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    modelo = Column(String)
    fabricante = Column(String)
    precio = Column(Float)
    descripcion = Column(String)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===============================
# STATIC FILES
# ===============================

app.mount("/static", StaticFiles(directory="static"), name="static")


# ===============================
# PUBLIC
# ===============================

@app.get("/")
def home():
    return RedirectResponse("/robots")


@app.get("/robots")
def public_list(request: Request, db: Session = Depends(get_db)):
    robots = db.query(Robot).all()
    return templates.TemplateResponse(
        "public_list.html",
        {"request": request, "robots": robots}
    )


@app.get("/robot/{robot_id}")
def robot_detail(robot_id: int, request: Request, db: Session = Depends(get_db)):
    robot = db.query(Robot).filter(Robot.id == robot_id).first()

    return templates.TemplateResponse(
        "public_detail.html",
        {"request": request, "robot": robot}
    )


# ===============================
# LOGIN ADMIN
# ===============================

@app.get("/admin/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "error": ""}
    )


@app.post("/admin/login")
def login(password: str = Form(...)):

    if password != ADMIN_PASSWORD:
        return RedirectResponse("/admin/login", status_code=303)

    response = RedirectResponse("/admin", status_code=303)

    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value="ok",
        httponly=True
    )

    return response


# ===============================
# ADMIN PANEL
# ===============================

def check_admin(request: Request):
    return request.cookies.get(ADMIN_COOKIE_NAME) == "ok"


@app.get("/admin")
def admin_panel(request: Request, db: Session = Depends(get_db)):

    if not check_admin(request):
        return RedirectResponse("/admin/login")

    robots = db.query(Robot).all()

    return templates.TemplateResponse(
        "admin_list.html",
        {"request": request, "robots": robots}
    )


@app.get("/admin/new")
def new_robot_page(request: Request):

    if not check_admin(request):
        return RedirectResponse("/admin/login")

    return templates.TemplateResponse(
        "admin_new.html",
        {"request": request}
    )


@app.post("/admin/new")
def create_robot(
    request: Request,
    nombre: str = Form(...),
    modelo: str = Form(...),
    fabricante: str = Form(...),
    precio: float = Form(...),
    descripcion: str = Form(...),
    db: Session = Depends(get_db)
):

    if not check_admin(request):
        return RedirectResponse("/admin/login")

    robot = Robot(
        nombre=nombre,
        modelo=modelo,
        fabricante=fabricante,
        precio=precio,
        descripcion=descripcion
    )

    db.add(robot)
    db.commit()

    return RedirectResponse("/admin", status_code=303)
