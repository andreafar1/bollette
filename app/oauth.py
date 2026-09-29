import os, secrets
from urllib.parse import urlencode
import httpx

PROVIDERS={
 "gmail":{
  "authorize":"https://accounts.google.com/o/oauth2/v2/auth",
  "token":"https://oauth2.googleapis.com/token",
  "scope":"openid email https://www.googleapis.com/auth/gmail.readonly",
  "client_id":"GOOGLE_CLIENT_ID","client_secret":"GOOGLE_CLIENT_SECRET"},
 "microsoft":{
  "authorize":"https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
  "token":"https://login.microsoftonline.com/common/oauth2/v2.0/token",
  "scope":"openid email offline_access https://graph.microsoft.com/Mail.Read",
  "client_id":"MICROSOFT_CLIENT_ID","client_secret":"MICROSOFT_CLIENT_SECRET"}
}
def configured(provider):
    p=PROVIDERS[provider]
    return bool(os.getenv(p["client_id"]) and os.getenv(p["client_secret"]))
def callback_url(request,provider):
    base=os.getenv("APP_BASE_URL",str(request.base_url).rstrip("/"))
    return f"{base}/email/oauth/{provider}/callback"
def authorization_url(request,provider,state):
    p=PROVIDERS[provider]
    q={"client_id":os.environ[p["client_id"]],"redirect_uri":callback_url(request,provider),
       "response_type":"code","scope":p["scope"],"state":state}
    if provider=="gmail": q.update({"access_type":"offline","prompt":"consent"})
    return p["authorize"]+"?"+urlencode(q)
def exchange(request,provider,code):
    p=PROVIDERS[provider]
    data={"client_id":os.environ[p["client_id"]],"client_secret":os.environ[p["client_secret"]],
          "code":code,"redirect_uri":callback_url(request,provider),"grant_type":"authorization_code"}
    with httpx.Client(timeout=30) as c:
        r=c.post(p["token"],data=data); r.raise_for_status(); return r.json()
def refresh(provider,refresh_token):
    p=PROVIDERS[provider]
    data={"client_id":os.environ[p["client_id"]],"client_secret":os.environ[p["client_secret"]],
          "refresh_token":refresh_token,"grant_type":"refresh_token"}
    if provider=="microsoft": data["scope"]=p["scope"]
    with httpx.Client(timeout=30) as c:
        r=c.post(p["token"],data=data); r.raise_for_status(); return r.json()
