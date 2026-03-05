import os
import uuid
from typing import Optional

from fastapi import FastAPI, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.status import HTTP_303_SEE_OTHER

from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from fastapi.templating import Jinja2Templates


# =========================
# CONFIG
# =========================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./robots.db")

# Railway a veces da postgres:// y SQLAlchemy pide postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
STATIC_DIR = os.getenv("STATIC_DIR", "./static")

# Admin login (ponlo en Railway -> Variables)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1207135jm")  # CAMBIA ESTO EN RAILWAY
ADMIN_COOKIE_NAME = os.getenv("ADMIN_COOKIE_NAME", "josephsi5")  # nombre cookie
ADMIN_COOKIE_VALUE = os.getenv("ADMIN_COOKIE_VALUE", "ok")  # valor cookie


# =========================
# DB (SQLAlchemy)
# =========================

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class Robot(Base):
    __tablename__ = "robots"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    modelo = Column(String(200), nullable=False)
    fabricante = Column(String(200), nullable=False, default="INKATECH ROBOTICS")
    precio = Column(Float, nullable=False, default=0.0)
    descripcion = Column(Text, nullable=True)
    imagen = Column(String(500), nullable=True)  # ruta tipo: /uploads/archivo.jpg


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================
# APP + FILES + TEMPLATES
# =========================

app = FastAPI(title="INKATECH ROBOTICS")

# crea carpetas si no existen
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# sirve archivos
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def on_startup():
    init_db()


# =========================
# AUTH (ADMIN)
# =========================

def is_admin(request: Request) -> bool:
    return request.cookies.get(ADMIN_COOKIE_NAME) == ADMIN_COOKIE_VALUE


def require_admin(request: Request):
    if not is_admin(request):
        # lo mandamos a login
        return RedirectResponse(url="/admin/login", status_code=HTTP_303_SEE_OTHER)
    return None


# =========================
# ROUTES (PUBLIC)
# =========================

@app.get("/", response_class=HTMLResponse)
def home():
    return RedirectResponse(url="/robots", status_code=HTTP_303_SEE_OTHER)


@app.get("/robots", response_class=HTMLResponse)
def public_list(request: Request, db: Session = Depends(get_db)):
    robots = db.query(Robot).order_by(Robot.id.desc()).all()
    return templates.TemplateResponse(
        "public_list.html",
        {"request": request, "robots": robots}
    )


@app.get("/robot/{robot_id}", response_class=HTMLResponse)
def public_detail(robot_id: int, request: Request, db: Session = Depends(get_db)):
    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        return HTMLResponse("Robot no encontrado", status_code=404)

    return templates.TemplateResponse(
        "public_detail.html",
        {"request": request, "robot": robot}
    )


# =========================
# ROUTES (ADMIN LOGIN)
# =========================

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_get(request: Request):
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "error": None}
    )


@app.post("/admin/login", response_class=HTMLResponse)
def admin_login_post(
    request: Request,
    password: str = Form(...),
):
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "error": "Contraseña incorrecta"}
        )

    # login ok -> cookie
    resp = RedirectResponse(url="/admin", status_code=HTTP_303_SEE_OTHER)
    resp.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=ADMIN_COOKIE_VALUE,
        httponly=True,
        samesite="lax",
    )
    return resp


@app.get("/admin/logout")
def admin_logout():
    resp = RedirectResponse(url="/robots", status_code=HTTP_303_SEE_OTHER)
    resp.delete_cookie(ADMIN_COOKIE_NAME)
    return resp


# =========================
# ROUTES (ADMIN PANEL)
# =========================

@app.get("/admin", response_class=HTMLResponse)
def admin_list(request: Request, db: Session = Depends(get_db)):
    check = require_admin(request)
    if check:
        return check

    robots = db.query(Robot).order_by(Robot.id.desc()).all()
    return templates.TemplateResponse(
        "admin_list.html",
        {"request": request, "robots": robots}
    )


@app.get("/admin/new", response_class=HTMLResponse)
def admin_new_get(request: Request):
    check = require_admin(request)
    if check:
        return check

    return templates.TemplateResponse(
        "admin_new.html",
        {"request": request, "error": None}
    )


@app.post("/admin/new")
async def admin_new_post(
    request: Request,
    nombre: str = Form(...),
    modelo: str = Form(...),
    fabricante: str = Form("INKATECH ROBOTICS"),
    precio: float = Form(0.0),
    descripcion: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    check = require_admin(request)
    if check:
        return check

    imagen_url = None

    # Si subió foto, la guardamos
    if foto and foto.filename:
        ext = os.path.splitext(foto.filename)[1].lower()  # .jpg .png ...
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)

        content = await foto.read()
        with open(filepath, "wb") as f:
            f.write(content)

        imagen_url = f"/uploads/{filename}"

    robot = Robot(
        nombre=nombre.strip(),
        modelo=modelo.strip(),
        fabricante=fabricante.strip() if fabricante else "INKATECH ROBOTICS",
        precio=float(precio),
        descripcion=descripcion.strip() if descripcion else None,
        imagen=imagen_url,
    )

    db.add(robot)
    db.commit()
    db.refresh(robot)

    return RedirectResponse(url="/admin", status_code=HTTP_303_SEE_OTHER)


@app.post("/admin/delete/{robot_id}")
def admin_delete(robot_id: int, request: Request, db: Session = Depends(get_db)):
    check = require_admin(request)
    if check:
        return check

    robot = db.query(Robot).filter(Robot.id == robot_id).first()
    if not robot:
        return RedirectResponse(url="/admin", status_code=HTTP_303_SEE_OTHER)

    # (opcional) borrar imagen del disco
    if robot.imagen and robot.imagen.startswith("/uploads/"):
        filename = robot.imagen.replace("/uploads/", "")
        filepath = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass

    db.delete(robot)
    db.commit()

    return RedirectResponse(url="/admin", status_code=HTTP_303_SEE_OTHER)

