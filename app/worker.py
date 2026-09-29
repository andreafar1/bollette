import os, imaplib, email, hashlib
from pathlib import Path
from email.header import decode_header
from .db import Base, engine, SessionLocal
from .models import Bill
from .parser import parse_pdf

def run():
    if os.getenv("IMAP_ENABLED","false").lower()!="true": return
    storage=Path(os.getenv("STORAGE_DIR","/var/lib/bollette/storage")); storage.mkdir(parents=True,exist_ok=True)
    m=imaplib.IMAP4_SSL(os.environ["IMAP_HOST"],int(os.getenv("IMAP_PORT","993")))
    m.login(os.environ["IMAP_USER"],os.environ["IMAP_PASSWORD"]); m.select(os.getenv("IMAP_FOLDER","INBOX"))
    _,ids=m.search(None,"UNSEEN")
    Base.metadata.create_all(engine)
    for mid in ids[0].split():
        _,raw=m.fetch(mid,"(RFC822)"); msg=email.message_from_bytes(raw[0][1])
        for part in msg.walk():
            fn=part.get_filename() or ""
            if fn.lower().endswith(".pdf"):
                payload=part.get_payload(decode=True); h=hashlib.sha256(payload).hexdigest(); path=storage/f"mail-{h}.pdf"
                if path.exists(): continue
                path.write_bytes(payload); d=parse_pdf(path)
                with SessionLocal() as db: db.add(Bill(provider=d["provider"],amount=d["amount"],due_date=d["due_date"],pdf_path=str(path))); db.commit()
    m.logout()
if __name__=="__main__": run()
