import os, imaplib, email, hashlib, base64, re
from html import unescape
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from pathlib import Path
import httpx
from sqlalchemy import select
from .db import Base, engine, SessionLocal
from .models import Bill, EmailAccount
from .parser import parse_pdf
from .oauth import refresh

STORAGE=Path(os.getenv("STORAGE_DIR","/var/lib/bollette/storage"))
KEYWORDS=("bolletta","fattura","invoice","energia","elettric","gas","luce","acqua","utenza","pagamento","scadenza","enel","plenitude","eni","acea","a2a","hera","tim","vodafone")

def relevant(sender="",subject="",filename=""):
    s=f"{sender} {subject} {filename}".lower()
    return any(k in s for k in KEYWORDS)

def save_pdf(payload,account="",sender="",subject="",mail_date=None):
    h=hashlib.sha256(payload).hexdigest()
    with SessionLocal() as db:
        if db.scalar(select(Bill.id).where(Bill.content_hash==h)): return False
    path=STORAGE/f"mail-{h}.pdf"
    if not path.exists(): path.write_bytes(payload)
    d=parse_pdf(path)
    with SessionLocal() as db:
        db.add(Bill(provider=d["provider"],amount=d["amount"],due_date=d["due_date"],pdf_path=str(path),content_hash=h,source_account=account,email_sender=sender[:500],email_subject=subject[:1000],email_date=mail_date)); db.commit()
    return True

def dec(v):
    try:return str(make_header(decode_header(v or "")))
    except:return v or ""

def message_text(msg):
    chunks=[]
    for part in msg.walk():
        if part.get_content_type() not in ("text/plain","text/html"):
            continue
        raw=part.get_payload(decode=True)
        if not raw:
            continue
        charset=part.get_content_charset() or "utf-8"
        try:
            s=raw.decode(charset,errors="replace")
        except LookupError:
            s=raw.decode("utf-8",errors="replace")
        if part.get_content_type()=="text/html":
            s=re.sub(r"<[^>]+>"," ",s)
            s=unescape(s)
        chunks.append(re.sub(r"\s+"," ",s))
    return " ".join(chunks)

def save_notification(msg,account,sender,subject,mail_date):
    text=message_text(msg)
    hay=f"{sender} {subject} {text}".lower()
    if "bolletta" not in hay and "fattura" not in hay:
        return False

    provider="Da verificare"
    if "plenitude" in hay or "eniplenitude" in hay:
        provider="Eni Plenitude"
    elif "enel" in hay:
        provider="Enel Energia"
    elif "acea" in hay:
        provider="Acea"
    elif "a2a" in hay:
        provider="A2A"
    elif "hera" in hay:
        provider="Hera"

    category="Altro"
    if re.search(r"\b(luce|energia elettrica|elettric)\b",hay):
        category="Luce"
    elif re.search(r"\bgas\b",hay):
        category="Gas"
    elif re.search(r"\bacqua\b",hay):
        category="Acqua"

    due=None
    m=re.search(r"(?:scadenza|scade|entro il)[^0-9]{0,30}(\d{1,2}[/-]\d{1,2}[/-]\d{4})",text,re.I)
    if m:
        for fmt in ("%d/%m/%Y","%d-%m-%Y"):
            try:
                due=datetime.strptime(m.group(1),fmt).date()
                break
            except ValueError:
                pass

    inv=None
    m=re.search(r"(?:bolletta|fattura)(?:\s+(?:n\.?|numero))?\s*([0-9]{5,})",text,re.I)
    if m:
        inv=m.group(1)

    identity=(msg.get("Message-ID") or f"{sender}|{subject}|{mail_date}").encode("utf-8",errors="ignore")
    h=hashlib.sha256(identity).hexdigest()
    with SessionLocal() as db:
        if db.scalar(select(Bill.id).where(Bill.content_hash==h)):
            return False
        db.add(Bill(provider=provider,category=category,due_date=due,invoice_number=inv,content_hash=h,source_account=account,email_sender=sender[:500],email_subject=subject[:1000],email_date=mail_date))
        db.commit()
    return True

def sync_yahoo(a):
    m=imaplib.IMAP4_SSL("imap.mail.yahoo.com",993); m.login(a.email,a.secret); m.select("INBOX")
    _,ids=m.search(None,"ALL")
    for mid in ids[0].split()[-200:]:
        _,raw=m.fetch(mid,"(RFC822)"); msg=email.message_from_bytes(raw[0][1])
        sender=dec(msg.get("From")); subject=dec(msg.get("Subject"))
        try: dt=parsedate_to_datetime(msg.get("Date")).replace(tzinfo=None)
        except: dt=None
        save_notification(msg,a.email,sender,subject,dt)
        for part in msg.walk():
            fn=dec(part.get_filename())
            if fn.lower().endswith(".pdf") and relevant(sender,subject,fn):
                payload=part.get_payload(decode=True)
                if payload: save_pdf(payload,a.email,sender,subject,dt)
    m.logout()

def sync_gmail(a):
    tok=refresh("gmail",a.refresh_token); access=tok["access_token"]; h={"Authorization":f"Bearer {access}"}
    with httpx.Client(timeout=30,headers=h) as c:
        msgs=c.get("https://gmail.googleapis.com/gmail/v1/users/me/messages",params={"q":"has:attachment filename:pdf","maxResults":100}).json().get("messages",[])
        for item in msgs:
            msg=c.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item['id']}",params={"format":"full"}).json()
            headers={x["name"].lower():x["value"] for x in msg.get("payload",{}).get("headers",[])}
            sender=headers.get("from",""); subject=headers.get("subject","")
            try: dt=datetime.fromtimestamp(int(msg.get("internalDate","0"))/1000)
            except: dt=None
            stack=[msg.get("payload",{})]
            while stack:
                p=stack.pop(); stack.extend(p.get("parts",[])); fn=p.get("filename",""); aid=p.get("body",{}).get("attachmentId")
                if fn.lower().endswith(".pdf") and aid and relevant(sender,subject,fn):
                    d=c.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item['id']}/attachments/{aid}").json().get("data","")
                    if d: save_pdf(base64.urlsafe_b64decode(d+"="*(-len(d)%4)),a.email or "Gmail",sender,subject,dt)

def sync_microsoft(a):
    tok=refresh("microsoft",a.refresh_token); access=tok["access_token"]; h={"Authorization":f"Bearer {access}"}
    with httpx.Client(timeout=30,headers=h) as c:
        url="https://graph.microsoft.com/v1.0/me/messages?$top=100&$filter=hasAttachments eq true&$select=id,subject,from,receivedDateTime,hasAttachments"
        for msg in c.get(url).json().get("value",[]):
            sender=msg.get("from",{}).get("emailAddress",{}).get("address",""); subject=msg.get("subject","")
            try: dt=datetime.fromisoformat(msg.get("receivedDateTime","").replace("Z","+00:00")).replace(tzinfo=None)
            except: dt=None
            for att in c.get(f"https://graph.microsoft.com/v1.0/me/messages/{msg['id']}/attachments").json().get("value",[]):
                fn=att.get("name","")
                if fn.lower().endswith(".pdf") and att.get("contentBytes") and relevant(sender,subject,fn):
                    save_pdf(base64.b64decode(att["contentBytes"]),a.email or "Microsoft",sender,subject,dt)

def sync_one(account_id):
    STORAGE.mkdir(parents=True,exist_ok=True)
    with SessionLocal() as db:
        a=db.get(EmailAccount,account_id)
        if not a or not a.enabled:return
        try:
            if a.provider=="yahoo":sync_yahoo(a)
            elif a.provider=="gmail":sync_gmail(a)
            elif a.provider=="microsoft":sync_microsoft(a)
            a.last_sync=datetime.utcnow();a.last_error=None
        except Exception as e:a.last_error=str(e)[:1000]
        db.commit()

def run():
    Base.metadata.create_all(engine)
    from .migrations import migrate
    migrate()
    with SessionLocal() as db:ids=list(db.scalars(select(EmailAccount.id).where(EmailAccount.enabled==True)).all())
    for i in ids:sync_one(i)
if __name__=="__main__":run()
