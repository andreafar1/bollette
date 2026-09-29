import os, imaplib, email, hashlib, base64
from datetime import datetime
from pathlib import Path
import httpx
from sqlalchemy import select
from .db import Base, engine, SessionLocal
from .models import Bill, EmailAccount
from .parser import parse_pdf
from .oauth import refresh

STORAGE=Path(os.getenv("STORAGE_DIR","/var/lib/bollette/storage"))

def save_pdf(payload):
    h=hashlib.sha256(payload).hexdigest(); path=STORAGE/f"mail-{h}.pdf"
    if path.exists(): return
    path.write_bytes(payload); d=parse_pdf(path)
    with SessionLocal() as db: db.add(Bill(provider=d["provider"],amount=d["amount"],due_date=d["due_date"],pdf_path=str(path))); db.commit()

def sync_yahoo(a):
    m=imaplib.IMAP4_SSL("imap.mail.yahoo.com",993); m.login(a.email,a.secret); m.select("INBOX")
    _,ids=m.search(None,"UNSEEN")
    for mid in ids[0].split():
        _,raw=m.fetch(mid,"(RFC822)"); msg=email.message_from_bytes(raw[0][1])
        for part in msg.walk():
            if (part.get_filename() or "").lower().endswith(".pdf"): save_pdf(part.get_payload(decode=True))
    m.logout()

def sync_gmail(a):
    tok=refresh("gmail",a.refresh_token); access=tok["access_token"]
    h={"Authorization":f"Bearer {access}"}
    with httpx.Client(timeout=30,headers=h) as c:
        msgs=c.get("https://gmail.googleapis.com/gmail/v1/users/me/messages",params={"q":"has:attachment filename:pdf","maxResults":50}).json().get("messages",[])
        for item in msgs:
            msg=c.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item['id']}",params={"format":"full"}).json()
            stack=[msg.get("payload",{})]
            while stack:
                p=stack.pop(); stack.extend(p.get("parts",[]))
                fn=p.get("filename",""); aid=p.get("body",{}).get("attachmentId")
                if fn.lower().endswith(".pdf") and aid:
                    d=c.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item['id']}/attachments/{aid}").json().get("data","")
                    if d: save_pdf(base64.urlsafe_b64decode(d+"="*(-len(d)%4)))

def sync_microsoft(a):
    tok=refresh("microsoft",a.refresh_token); access=tok["access_token"]
    h={"Authorization":f"Bearer {access}"}
    with httpx.Client(timeout=30,headers=h) as c:
        url="https://graph.microsoft.com/v1.0/me/messages?$top=50&$filter=hasAttachments eq true"
        for msg in c.get(url).json().get("value",[]):
            for att in c.get(f"https://graph.microsoft.com/v1.0/me/messages/{msg['id']}/attachments").json().get("value",[]):
                if att.get("name","").lower().endswith(".pdf") and att.get("contentBytes"): save_pdf(base64.b64decode(att["contentBytes"]))

def sync_one(account_id):
    STORAGE.mkdir(parents=True,exist_ok=True)
    with SessionLocal() as db:
        a=db.get(EmailAccount,account_id)
        if not a or not a.enabled: return
        try:
            if a.provider=="yahoo": sync_yahoo(a)
            elif a.provider=="gmail": sync_gmail(a)
            elif a.provider=="microsoft": sync_microsoft(a)
            a.last_sync=datetime.utcnow(); a.last_error=None
        except Exception as e:
            a.last_error=str(e)[:1000]
        db.commit()

def run():
    Base.metadata.create_all(engine)
    with SessionLocal() as db: ids=list(db.scalars(select(EmailAccount.id).where(EmailAccount.enabled==True)).all())
    for i in ids: sync_one(i)
if __name__=="__main__": run()
