"""Backend-only email transports. No recipient allowlist or frontend credentials."""
import os,ssl,smtplib,hashlib,json,urllib.request,urllib.error,base64,time
from email.message import EmailMessage
class SendingUncertain(RuntimeError):pass
def configuration():
 provider=os.getenv('EMAIL_PROVIDER', 'gmail' if os.getenv('GMAIL_USERNAME') and os.getenv('GMAIL_APP_PASSWORD') else 'resend').strip().lower()
 required={'resend':['RESEND_API_KEY','EMAIL_FROM','PUBLIC_BASE_URL'],'gmail':['GMAIL_USERNAME','GMAIL_APP_PASSWORD','PUBLIC_BASE_URL'],'gmail_oauth':['GMAIL_USERNAME','GMAIL_OAUTH_CLIENT_ID','GMAIL_OAUTH_CLIENT_SECRET','GMAIL_OAUTH_REFRESH_TOKEN','PUBLIC_BASE_URL']}
 if provider not in required:return {'provider':provider,'configured':False,'missing':['EMAIL_PROVIDER must be gmail, gmail_oauth or resend']}
 missing=[k for k in required[provider] if not os.getenv(k)]
 return {'provider':provider,'configured':not missing,'missing':missing,'auth_mode':{'gmail':'app_password','gmail_oauth':'OAuth refresh token','resend':'API key'}[provider]}
def message(recipient,text,key,link):
 import html
 base=os.getenv('PUBLIC_BASE_URL','http://localhost:5000').rstrip('/');url=base+link
 content=f'<div style="font-family:Arial;background:#faf7f4;padding:28px"><div style="max-width:560px;margin:auto;background:white;border-radius:20px;padding:32px"><h1 style="color:#382344;font-family:Georgia">SheSync</h1><p style="line-height:1.8;color:#71516b">{html.escape(text)}</p><a href="{html.escape(url)}" style="color:#a44c86">Manage this reminder</a><p style="font-size:12px;color:#867282">You requested this SheSync email. You can disable reminders at any time.</p></div></div>'
 return content,text+'\nManage: '+url
_oauth_cache={}

def subject(key,link):
 if '/confirm/' in link:return 'Verify your email · SheSync'
 if key.startswith('direct:'):return 'Your SheSync test reminder'
 return 'Your SheSync update'
def _access_token():
 now=time.time()
 if _oauth_cache.get('expiry',0)>now+60:return _oauth_cache['token']
 import urllib.parse
 payload=urllib.parse.urlencode({'client_id':os.getenv('GMAIL_OAUTH_CLIENT_ID'),'client_secret':os.getenv('GMAIL_OAUTH_CLIENT_SECRET'),'refresh_token':os.getenv('GMAIL_OAUTH_REFRESH_TOKEN'),'grant_type':'refresh_token'}).encode()
 req=urllib.request.Request('https://oauth2.googleapis.com/token',data=payload,headers={'Content-Type':'application/x-www-form-urlencoded','User-Agent':'SheSync/1.2'})
 try:
  with urllib.request.urlopen(req,timeout=20) as res:data=json.load(res)
 except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError):raise RuntimeError('Gmail OAuth refresh failed. Check the authorized refresh token and client configuration; no email was sent.')
 if not data.get('access_token'):raise RuntimeError('Google did not return an access token.')
 _oauth_cache.update(token=data['access_token'],expiry=now+int(data.get('expires_in',3600)));return data['access_token']
def send(recipient,text,key,link):
 config=configuration()
 if not config['configured']:raise RuntimeError('Configure '+', '.join(config['missing'])+' in the backend .env and restart backend and worker.')
 content,plain=message(recipient,text,key,link);provider=config['provider']
 if provider=='resend':
  payload={'from':os.getenv('EMAIL_FROM'),'to':[recipient],'subject':subject(key,link),'html':content,'text':plain}
  req=urllib.request.Request('https://api.resend.com/emails',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+os.getenv('RESEND_API_KEY'),'Content-Type':'application/json','User-Agent':'SheSync/1.2 (Resend REST client)','Idempotency-Key':hashlib.sha256(key.encode()).hexdigest()},method='POST')
  try:
   with urllib.request.urlopen(req,timeout=20) as res:result=json.load(res)
  except urllib.error.HTTPError as e:
   reasons={400:'Check sender and recipient format.',401:'API key rejected.',403:'The Resend testing sender is limited to its registered recipient. Select configured Gmail for other recipients.',429:'Provider quota or rate limit reached.'}
   raise RuntimeError(f'Resend rejected the request (HTTP {e.code}). '+reasons.get(e.code,'Inspect the provider dashboard.'))
  except (urllib.error.URLError,TimeoutError):raise RuntimeError('Resend request timed out or failed. A retry uses its provider idempotency key.')
  if not result.get('id'):raise RuntimeError('Resend did not confirm acceptance.')
  return result['id']
 sender=os.getenv('GMAIL_USERNAME').strip();msg=EmailMessage();msg['From']='SheSync <'+sender+'>';msg['To']=recipient;msg['Subject']=subject(key,link);msg['Message-ID']='<'+hashlib.sha256(key.encode()).hexdigest()+'@'+sender.split('@')[-1]+'>';msg.set_content(plain);msg.add_alternative(content,subtype='html')
 if provider=='gmail_oauth':
  raw=base64.urlsafe_b64encode(msg.as_bytes()).decode();req=urllib.request.Request('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',data=json.dumps({'raw':raw}).encode(),headers={'Authorization':'Bearer '+_access_token(),'Content-Type':'application/json','User-Agent':'SheSync/1.2'},method='POST')
  try:
   with urllib.request.urlopen(req,timeout=20) as res:result=json.load(res)
  except urllib.error.HTTPError as e:raise RuntimeError(f'Gmail API rejected the sending request (HTTP {e.code}). Check gmail.send authorization and account quotas.')
  except (urllib.error.URLError,TimeoutError):raise SendingUncertain('Gmail API response was lost. Sending is uncertain; inspect the sender’s Sent folder before any retry.')
  if not result.get('id'):raise SendingUncertain('Gmail API returned no message ID; inspect Sent mail before retrying.')
  return 'gmail_api:'+result['id']
 submitted=False
 try:
  with smtplib.SMTP('smtp.gmail.com',587,timeout=20) as smtp:
   smtp.ehlo();smtp.starttls(context=ssl.create_default_context());smtp.ehlo();smtp.login(sender,os.getenv('GMAIL_APP_PASSWORD').replace(' ',''))
   try:refused=smtp.send_message(msg,from_addr=sender,to_addrs=[recipient])
   except (smtplib.SMTPServerDisconnected,OSError):raise SendingUncertain('SMTP response was lost after submission began. Sending is uncertain; inspect Sent mail before retrying.')
   if refused:raise RuntimeError('Gmail SMTP refused the recipient. Check the address and provider limits.')
   submitted=True
 except smtplib.SMTPAuthenticationError as e:raise RuntimeError(f'Gmail authentication failed (SMTP {e.smtp_code}): '+smtp_detail(e.smtp_error)+' Use a valid app password or reauthorize Gmail OAuth.')
 except (smtplib.SMTPRecipientsRefused,smtplib.SMTPDataError,smtplib.SMTPSenderRefused) as e:
  details=getattr(e,'smtp_error',b'')
  if isinstance(e,smtplib.SMTPRecipientsRefused):details=next(iter(e.recipients.values()),('recipient rejected',b''))
  raise RuntimeError(f'Gmail SMTP rejected the message (SMTP {getattr(e,"smtp_code","recipient rejected")}): '+smtp_detail(details)+'. Check the recipient address, Gmail sending limits and sender account status.')
 except smtplib.SMTPException:
  if not submitted:raise RuntimeError('Gmail SMTP connection or TLS negotiation failed. No success is claimed.')
 except OSError:
  if not submitted:raise RuntimeError('Gmail SMTP could not be reached. Check internet access; no acceptance is claimed.')
 return 'gmail:'+msg['Message-ID'].strip('<>')

def smtp_detail(value):
 if isinstance(value,bytes):value=value.decode('utf-8',errors='replace')
 return ' '.join(str(value).split())[:250]
