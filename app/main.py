import os, shutil, uuid, secrets
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from .db import Base, engine, SessionLocal
from .models import Bill, EmailAccount
from .parser import parse_pdf
from .oauth import configured, authorization_url, exchange

app=FastAPI(title="Bollette")
templates=Jinja2Templates(directory=str(Path(__file__).parent/"templates"))
STORAGE=Path(os.getenv("STORAGE_DIR","/var/lib/bollette/storage")); STORAGE.mkdir(parents=True,exist_ok=True)
oauth_states={}

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    from .migrations import migrate
    migrate()

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

@app.get("/settings/email",response_class=HTMLResponse)
def email_settings(request:Request,msg:str=""):
    with SessionLocal() as db: accounts=db.scalars(select(EmailAccount).order_by(EmailAccount.id)).all()
    return templates.TemplateResponse(request=request,name="email_settings.html",context={"accounts":accounts,"gmail_ready":configured("gmail"),"microsoft_ready":configured("microsoft"),"msg":msg})

@app.get("/email/connect/{provider}")
def connect_oauth(request:Request,provider:str):
    if provider not in ("gmail","microsoft") or not configured(provider):
        return RedirectResponse("/settings/email?msg=OAuth+non+configurato",303)
    state=secrets.token_urlsafe(24); oauth_states[state]=provider
    return RedirectResponse(authorization_url(request,provider,state),302)

@app.get("/email/oauth/{provider}/callback")
def oauth_callback(request:Request,provider:str,code:str="",state:str=""):
    if not code or oauth_states.pop(state,None)!=provider: return RedirectResponse("/settings/email?msg=Autorizzazione+non+valida",303)
    try:
        tok=exchange(request,provider,code)
        with SessionLocal() as db:
            db.add(EmailAccount(provider=provider,email="",auth_type="oauth",secret=tok.get("access_token"),refresh_token=tok.get("refresh_token"))); db.commit()
        return RedirectResponse("/settings/email?msg=Account+collegato",303)
    except Exception as e:
        return RedirectResponse("/settings/email?msg=Errore+OAuth",303)

@app.post("/email/yahoo")
def add_yahoo(email:str=Form(...),app_password:str=Form(...)):
    with SessionLocal() as db:
        db.add(EmailAccount(provider="yahoo",email=email.strip(),auth_type="app_password",secret=app_password.strip())); db.commit()
    return RedirectResponse("/settings/email?msg=Account+Yahoo+salvato",303)

@app.post("/email/{account_id}/sync")
def sync_account(account_id:int):
    from .worker import sync_one
    try: sync_one(account_id)
    except Exception: pass
    return RedirectResponse("/settings/email",303)

@app.post("/email/{account_id}/delete")
def delete_account(account_id:int):
    with SessionLocal() as db:
        a=db.get(EmailAccount,account_id)
        if a: db.delete(a); db.commit()
    return RedirectResponse("/settings/email",303)

@app.post("/bills")
def add_bill(provider:str=Form(...),category:str=Form("Altro"),amount:Decimal=Form(...),due_date:str=Form(""),status:str=Form("DA_PAGARE")):
    due=datetime.strptime(due_date,"%Y-%m-%d").date() if due_date else None
    with SessionLocal() as db: db.add(Bill(provider=provider,category=category,amount=amount,due_date=due,status=status)); db.commit()
    return RedirectResponse("/",303)

@app.post("/upload")
def upload(file:UploadFile=File(...)):
    if not file.filename.lower().endswith(".pdf"): return RedirectResponse("/",303)
    path=STORAGE/f"{uuid.uuid4().hex}.pdf"
    with path.open("wb") as f: shutil.copyfileobj(file.file,f)
    data=parse_pdf(path)
    with SessionLocal() as db: db.add(Bill(provider=data["provider"],amount=data["amount"],due_date=data["due_date"],pdf_path=str(path))); db.commit()
    return RedirectResponse("/",303)

@app.post("/bills/{bill_id}/paid")
def mark_paid(bill_id:int):
    with SessionLocal() as db:
        b=db.get(Bill,bill_id)
        if b: b.status="PAGATA"; db.commit()
    return RedirectResponse("/",303)

@app.get("/bills/{bill_id}/smart")
def smart_bill(bill_id:int):
    with SessionLocal() as db:
        b=db.get(Bill,bill_id)
        url=b.smart_url if b else None
    if not url or not url.startswith("https://interattiva.eniplenitude.com/"):
        return RedirectResponse("/",303)
    return RedirectResponse(url,302)

@app.get("/bills/{bill_id}/pdf")
def pdf(bill_id:int):
    with SessionLocal() as db: b=db.get(Bill,bill_id)
    if not b or not b.pdf_path: return RedirectResponse("/",303)
    return FileResponse(b.pdf_path,media_type="application/pdf",filename=f"bolletta-{bill_id}.pdf")

@app.get("/health")
def health(): return {"status":"ok"}
