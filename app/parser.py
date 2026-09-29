import re
from datetime import datetime
from decimal import Decimal
from pypdf import PdfReader

PROVIDERS={"enel":"Enel Energia","plenitude":"Eni Plenitude","eni":"Eni Plenitude","acea":"Acea","a2a":"A2A","hera":"Hera","tim":"TIM","vodafone":"Vodafone"}

def parse_pdf(path):
    text="\n".join((p.extract_text() or "") for p in PdfReader(path).pages[:5])
    low=text.lower()
    provider=next((v for k,v in PROVIDERS.items() if k in low),"Da verificare")
    amount=None
    for pat in [r"(?:totale|importo)[^\d]{0,30}(\d{1,5}[.,]\d{2})\s*€?",r"€\s*(\d{1,5}[.,]\d{2})"]:
        m=re.search(pat,text,re.I)
        if m:
            amount=Decimal(m.group(1).replace(".","").replace(",","."))
            break
    due=None
    m=re.search(r"(?:scadenza|entro il)[^\d]{0,20}(\d{1,2}[/-]\d{1,2}[/-]\d{4})",text,re.I)
    if m:
        for fmt in ("%d/%m/%Y","%d-%m-%Y"):
            try: due=datetime.strptime(m.group(1),fmt).date(); break
            except ValueError: pass
    return {"provider":provider,"amount":amount,"due_date":due}
