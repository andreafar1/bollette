import os, shutil, uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from .db import Base, engine, SessionLocal
from .models import Bill
from .parser import parse_pdf

app=FastAPI(title="Bollette")
templates=Jinja2Templates(directory=str(Path(__file__).parent/"templates"))
STORAGE=Path(os.getenv("STORAGE_DIR","/var/lib/bollette/storage"))
STORAGE.mkdir(parents=True,exist_ok=True)

@app.on_event("startup")
def startup(): Base.metadata.create_all(engine)

def derived_status(b):
    if b.status=="PAGATA": return "PAGATA"
    if b.due_date and b.due_date < date.today(): return "SCADUTA"
    return "DA_PAGARE"

@app.get("/",response_class=HTMLResponse)
def home(request:Request):
    with SessionLocal() as db:
        bills=db.scalars(select(Bill).order_by(Bill.due_date.desc().nullslast(),Bill.id.desc())).all()
        for b in bills: b.display_status=derived_status(b)
        paid=sum((b.amount or 0) for b in bills if b.display_status=="PAGATA")
        due=sum((b.amount or 0) for b in bills if b.display_status in ("DA_PAGARE","SCADUTA"))
    return templates.TemplateResponse(request=request,name="index.html",context={"bills":bills,"paid":paid,"due":due})

@app.post("/bills")
def add_bill(provider:str=Form(...),category:str=Form("Altro"),amount:Decimal=Form(...),due_date:str=Form(""),status:str=Form("DA_PAGARE")):
    due=datetime.strptime(due_date,"%Y-%m-%d").date() if due_date else None
    with SessionLocal() as db:
        db.add(Bill(provider=provider,category=category,amount=amount,due_date=due,status=status)); db.commit()
    return RedirectResponse("/",303)

@app.post("/upload")
def upload(file:UploadFile=File(...)):
    if not file.filename.lower().endswith(".pdf"): return RedirectResponse("/",303)
    path=STORAGE/f"{uuid.uuid4().hex}.pdf"
    with path.open("wb") as f: shutil.copyfileobj(file.file,f)
    data=parse_pdf(path)
    with SessionLocal() as db:
        db.add(Bill(provider=data["provider"],amount=data["amount"],due_date=data["due_date"],pdf_path=str(path))); db.commit()
    return RedirectResponse("/",303)

@app.post("/bills/{bill_id}/paid")
def mark_paid(bill_id:int):
    with SessionLocal() as db:
        b=db.get(Bill,bill_id)
        if b: b.status="PAGATA"; db.commit()
    return RedirectResponse("/",303)

@app.get("/bills/{bill_id}/pdf")
def pdf(bill_id:int):
    with SessionLocal() as db: b=db.get(Bill,bill_id)
    if not b or not b.pdf_path: return RedirectResponse("/",303)
    return FileResponse(b.pdf_path,media_type="application/pdf",filename=f"bolletta-{bill_id}.pdf")

@app.get("/health")
def health(): return {"status":"ok"}
