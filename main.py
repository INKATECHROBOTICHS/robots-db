import os
import shutil
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from jinja2 import Environment, FileSystemLoader, select_autoescape

DATABASE_URL = "sqlite:///./robots.db"
UPLOAD_DIR = "./uploads"
ADMIN_TOKEN = "1207135jm"  # <-- cámbiala

os.makedirs(UPLOAD_DIR, exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class RobotDB(Base):
    __tablename__ = "robots"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, index=True)
    modelo = Column(String(100), nullable=False, index=True)
    fabricante = Column(String(100), nullable=True)
    precio = Column(Float, nullable=False, default=0.0)
    descripcion = Column(Text, nullable=True)
    imagen = Column(String(300), nullable=True)
    creado_en = Column(DateTime, nullable=False, default=datetime.utcnow)
    actualizado_en = Column(DateTime, nullable=False, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Robots: Admin + Catálogo")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html", "xml"])
)

def render(template_name: str, **context) -> HTMLResponse:
    return HTMLResponse(env.get_template(template_name).render(**context))

def require_admin(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="No autorizado (token incorrecto)")

@app.get("/", response_class=HTMLResponse)
def public_list():
    with SessionLocal() as db:
        robots = db.query(RobotDB).order_by(RobotDB.id.desc()).all()
    return render("public_list.html", robots=robots)

@app.get("/robot/{robot_id}", response_class=HTMLResponse)
def public_detail(robot_id: int):
    with SessionLocal() as db:
        robot = db.query(RobotDB).filter(RobotDB.id == robot_id).first()
    if not robot:
        raise HTTPException(404, "Robot no encontrado")
    return render("public_detail.html", robot=robot)

@app.get("/admin", response_class=HTMLResponse)
def admin_list(token: str = ""):
    require_admin(token)
    with SessionLocal() as db:
        robots = db.query(RobotDB).order_by(RobotDB.id.desc()).all()
    return render("admin_list.html", robots=robots, token=token)

@app.get("/admin/new", response_class=HTMLResponse)
def admin_new(token: str = ""):
    require_admin(token)
    return render("admin_new.html", token=token)

@app.post("/admin/new")
def admin_create(
    token: str = Form(...),
    nombre: str = Form(...),
    modelo: str = Form(...),
    fabricante: Optional[str] = Form(None),
    precio: float = Form(0.0),
    descripcion: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
):
    require_admin(token)

    filename = None
    if foto and foto.filename:
        ext = os.path.splitext(foto.filename)[1].lower()
        filename = f"robot_{int(datetime.utcnow().timestamp())}{ext}"
        path = os.path.join(UPLOAD_DIR, filename)
        with open(path, "wb") as f:
            shutil.copyfileobj(foto.file, f)

    with SessionLocal() as db:
        robot = RobotDB(
            nombre=nombre,
            modelo=modelo,
            fabricante=fabricante,
            precio=precio,
            descripcion=descripcion,
            imagen=filename,
            creado_en=datetime.utcnow(),
            actualizado_en=datetime.utcnow(),
        )
        db.add(robot)
        db.commit()

    return RedirectResponse(url=f"/admin?token={token}", status_code=303)