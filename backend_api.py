"""SheSync API: authenticated accounts, real inference, persistent reminders.
Run: python backend_api.py; scheduler: python reminder_worker.py
"""
from pathlib import Path
import os, sys
ROOT=Path(__file__).resolve().parent
# Prefer the active virtual environment.  The optional local package cache is
# a last resort and must not shadow installed packages (notably python-dotenv).
sys.path.append(str(ROOT/'.runtime-deps'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env',override=True)
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, json, secrets, time, hashlib, math, re, html
from functools import wraps
from contextlib import contextmanager
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import urllib.request, urllib.error
import urllib.parse
import email_providers
import joblib, numpy as np, pandas as pd
DB=str(Path(os.getenv('SHESYNC_DB',str(ROOT/'instance'/'shesync.sqlite3'))).expanduser());DB=str((ROOT/DB).resolve()) if not Path(DB).is_absolute() else DB
Path(DB).parent.mkdir(parents=True,exist_ok=True)
TZ=ZoneInfo('Asia/Kolkata')
app=Flask(__name__)
secret=os.getenv('SECRET_KEY')
if secret and secret.startswith('replace-'):secret=None
if not secret:
 keyfile=Path(DB).parent/'session.key'
 if not keyfile.exists():keyfile.write_text(secrets.token_hex(32))
 secret=keyfile.read_text().strip()
app.config.update(SECRET_KEY=secret,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','false')=='true',MAX_CONTENT_LENGTH=100_000)
CORS(app,origins=os.getenv('ALLOWED_ORIGINS','http://localhost:5000,http://127.0.0.1:5000').split(','),supports_credentials=True)
@contextmanager
def db():
 c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row
 try:
  yield c
  c.commit()
 except Exception:
  c.rollback();raise
 finally:c.close()
with db() as c:
 c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password_hash TEXT NOT NULL,stage TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS periods(user_id INTEGER,start TEXT,end TEXT,PRIMARY KEY(user_id,start));
 CREATE TABLE IF NOT EXISTS logs(user_id INTEGER,day TEXT,data TEXT,PRIMARY KEY(user_id,day));
 CREATE TABLE IF NOT EXISTS reminders(user_id INTEGER PRIMARY KEY,email TEXT,consent INTEGER,verified INTEGER DEFAULT 0,prefs TEXT,verify_token TEXT,unsubscribe_token TEXT,updated TEXT);
 CREATE TABLE IF NOT EXISTS outbox(key TEXT PRIMARY KEY,user_id INTEGER,kind TEXT,body TEXT,status TEXT DEFAULT 'pending',provider_id TEXT,error TEXT,created TEXT,attempts INTEGER DEFAULT 0);
 CREATE TABLE IF NOT EXISTS wearable(id INTEGER PRIMARY KEY,device_id TEXT,recorded TEXT,source TEXT,data TEXT);
 CREATE TABLE IF NOT EXISTS settings(user_id INTEGER PRIMARY KEY,cycle_length INTEGER DEFAULT 29);
 CREATE TABLE IF NOT EXISTS worker_status(name TEXT PRIMARY KEY,last_seen TEXT);
 CREATE TABLE IF NOT EXISTS password_resets(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,created TEXT NOT NULL,used INTEGER NOT NULL DEFAULT 0);
 ''')
with db() as c:
 c.execute('BEGIN IMMEDIATE')
 existing={r[1] for r in c.execute('PRAGMA table_info(outbox)')}
 for name,kind in [('recipient','TEXT'),('action_path','TEXT'),('last_attempt','TEXT'),('delivery_event','TEXT'),('provider','TEXT')]:
  if name not in existing:c.execute(f'ALTER TABLE outbox ADD COLUMN {name} {kind}')
with db() as c:
 c.execute("UPDATE outbox SET status='blocked_configuration',attempts=0,last_attempt=NULL WHERE provider_id IS NULL AND (error LIKE 'Email service is not configured%' OR error LIKE 'Missing provider configuration%')")
features=joblib.load(ROOT/'models/feature_names.pkl')
models={};model_errors={}
for name,file in [('xgboost','pcos_xgb_model.pkl'),('random_forest','pcos_rf_model.pkl')]:
 try:models[name]=joblib.load(ROOT/'models'/file)
 except Exception as e:model_errors[name]=type(e).__name__
def authenticated(fn):
 @wraps(fn)
 def wrapped(*args,**kwargs):
  if not session.get('user_id'):return jsonify(error='Sign in to use this feature.'),401
  return fn(*args,**kwargs)
 return wrapped
@app.before_request
def protect_mutations():
 # Password-reset POSTs arrive from the emailed one-time-token page, not from
 # browser JavaScript. The unguessable, expiring, single-use token is its CSRF proof.
 if request.method in ('POST','PUT','DELETE','PATCH') and not request.path.startswith(('/api/wearable','/api/auth/password-reset/')):
  if request.headers.get('X-SheSync-Client')!='web':return jsonify(error='Missing application request header.'),403
  origin=request.headers.get('Origin')
  allowed=set(os.getenv('ALLOWED_ORIGINS','http://localhost:5000,http://127.0.0.1:5000').split(','))
  if origin and origin not in allowed:return jsonify(error='Origin is not allowed.'),403
@app.errorhandler(ValueError)
def bad_value(e):return jsonify(error=str(e)),400
@app.errorhandler(404)
def not_found(e):return jsonify(error='Not found.'),404
@app.errorhandler(500)
def server_error(e):return jsonify(error='The service could not complete this request. Please try again.'),500
def body():
 x=request.get_json(silent=True)
 if not isinstance(x,dict):raise ValueError('A JSON object is required.')
 return x
def email_valid(e):
 if not isinstance(e,str) or len(e)>254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}",e) or '..' in e:return False
 local,domain=e.rsplit('@',1)
 return not local.startswith('.') and not local.endswith('.') and all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',label) for label in domain.split('.'))

with db() as c:
 c.executescript('''CREATE TABLE IF NOT EXISTS rate_events(scope TEXT,stamp REAL);
 CREATE INDEX IF NOT EXISTS rate_events_lookup ON rate_events(scope,stamp);
 CREATE TABLE IF NOT EXISTS email_actions(key TEXT PRIMARY KEY,user_id INTEGER NOT NULL,kind TEXT,recipient TEXT,action_path TEXT,status TEXT,provider TEXT,provider_id TEXT,error TEXT,created TEXT);
 CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,clinic TEXT NOT NULL,day TEXT NOT NULL,time TEXT NOT NULL,notes TEXT,status TEXT NOT NULL DEFAULT 'request_prepared',created TEXT NOT NULL,reason TEXT DEFAULT '',contact_name TEXT DEFAULT '',contact_phone TEXT DEFAULT '',updated TEXT DEFAULT '');''')
 appointment_columns={r[1] for r in c.execute('PRAGMA table_info(appointments)')}
 for column in ('reason','contact_name','contact_phone','updated'):
  if column not in appointment_columns:c.execute(f"ALTER TABLE appointments ADD COLUMN {column} TEXT DEFAULT ''")

def reserve_limits(scopes):
 now=time.time();wait=0
 with db() as c:
  c.execute('BEGIN IMMEDIATE');c.execute('DELETE FROM rate_events WHERE stamp<?',(now-86400,))
  for scope,limit,window in scopes:
   stamps=[r[0] for r in c.execute('SELECT stamp FROM rate_events WHERE scope=? AND stamp>? ORDER BY stamp',(scope,now-window))]
   if len(stamps)>=limit:wait=max(wait,math.ceil(stamps[len(stamps)-limit]+window-now))
  if wait:return wait
  for scope,limit,window in scopes:c.execute('INSERT INTO rate_events VALUES(?,?)',(scope,now))
 return 0

def limit_requests(scopes):return reserve_limits(scopes)==0

# OpenStreetMap is used only as a no-key discovery fallback.  It is not an
# appointment provider: returned fields are verbatim public map tags and can
# be incomplete or stale, so the UI always attributes and asks users to verify.
CLINIC_CACHE={}
def public_json(url,method='GET',data=None,content_type=None):
 headers={'User-Agent':'SheSync student project/1.0','Accept':'application/json'}
 if content_type:headers['Content-Type']=content_type
 req=urllib.request.Request(url,data=data,method=method,headers=headers)
 try:
  with urllib.request.urlopen(req,timeout=12) as response:return json.loads(response.read().decode('utf-8'))
 except (urllib.error.URLError,urllib.error.HTTPError,TimeoutError,json.JSONDecodeError) as error:
  raise RuntimeError('Live clinic search is temporarily unavailable. Use the Google Maps link or enter a clinic you can verify.') from error
def clinic_address(tags):
 parts=[tags.get(k,'').strip() for k in ('addr:housenumber','addr:street','addr:suburb','addr:city','addr:postcode')]
 return ', '.join(x for x in parts if x)
def clinic_search_key(latitude,longitude,city,area,specialty):
 return '|'.join((f'{latitude:.3f}' if latitude is not None else '',f'{longitude:.3f}' if longitude is not None else '',city.casefold(),area.casefold(),specialty.casefold()))
def nominatim_clinics(city,area,latitude,longitude,specialty):
 """Return only fields supplied by Nominatim when Overpass is busy."""
 locality=' '.join(x for x in (area,city) if x).strip()
 if not locality and latitude is not None:
  reverse=public_json('https://nominatim.openstreetmap.org/reverse?'+urllib.parse.urlencode({'lat':latitude,'lon':longitude,'format':'jsonv2'}))
  address=reverse.get('address',{})
  locality=str(address.get('city') or address.get('town') or address.get('village') or address.get('county') or '').strip()
 if not locality:raise RuntimeError('No city or locality was available for a public clinic search. Use Google Maps or enter a city.')
 rows=public_json('https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode({'q':'hospital '+locality,'format':'jsonv2','limit':'20','namedetails':'1','extratags':'1'}))
 clinics=[];seen=set()
 for row in rows:
  identifier='nominatim_'+str(row.get('osm_type',''))+'_'+str(row.get('osm_id',''))
  if identifier in seen:continue
  seen.add(identifier);details=row.get('namedetails') or {};extra=row.get('extratags') or {}
  name=str(details.get('name') or row.get('name') or str(row.get('display_name','')).split(',')[0]).strip()
  if not name:continue
  phone=str(extra.get('phone') or extra.get('contact:phone') or '').strip()[:80];website=str(extra.get('website') or extra.get('contact:website') or '').strip()[:500]
  if website and not re.fullmatch(r'https?://[^\s]+',website):website=''
  address=str(row.get('display_name','')).strip()[:500];destination=address or name
  clinics.append({'id':identifier,'name':name[:160],'specialty':'Public healthcare listing','address':address,'phone':phone,'website':website,'source':'OpenStreetMap public listing via Nominatim','directions':'https://www.google.com/maps/dir/?api=1&destination='+urllib.parse.quote(destination)})
 return clinics
@app.post('/api/clinics/search')
@authenticated
def clinics_search():
 d=body();city=str(d.get('city','')).strip()[:120];area=str(d.get('area','')).strip()[:120];specialty=str(d.get('specialty','Gynecologist')).strip()[:80]
 latitude=d.get('latitude');longitude=d.get('longitude')
 try:
  latitude=float(latitude) if latitude not in (None,'') else None;longitude=float(longitude) if longitude not in (None,'') else None
 except (TypeError,ValueError):raise ValueError('Location coordinates are invalid.')
 if latitude is not None and not (-90<=latitude<=90 and longitude is not None and -180<=longitude<=180):raise ValueError('Location coordinates are invalid.')
 if latitude is None and not (city or area):raise ValueError('Enter a city or area, or allow location access.')
 if specialty not in ('Gynecologist','Obstetrician',"Women's health clinic",'Fertility specialist'):raise ValueError('Choose a listed specialty.')
 wait=reserve_limits([('clinic-search:user:'+str(session['user_id']),10,60)])
 if wait:return jsonify(error='Please wait '+str(wait)+' seconds before another live clinic search.',retry_after_seconds=wait),429
 key=clinic_search_key(latitude,longitude,city,area,specialty);cached=CLINIC_CACHE.get(key)
 if cached and time.time()-cached[0]<600:return jsonify(**cached[1],cached=True)
 try:
  if latitude is None:
   place=public_json('https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode({'q':' '.join(x for x in (area,city) if x),'format':'jsonv2','limit':'1'}))
   if not place:raise RuntimeError('No map location was found for that city or area. Try the Google Maps link.')
   latitude=float(place[0]['lat']);longitude=float(place[0]['lon'])
  # A compact radius keeps the public service responsive in dense cities.
  radius=3000
  query='[out:json][timeout:8];nwr["amenity"~"^(clinic|doctors|hospital)$"]["name"](around:%d,%.6f,%.6f);out center tags 20;'%(radius,latitude,longitude)
  try:raw=public_json('https://overpass-api.de/api/interpreter','POST',urllib.parse.urlencode({'data':query}).encode('utf-8'),'application/x-www-form-urlencoded')
  except RuntimeError:
   clinics=nominatim_clinics(city,area,latitude,longitude,specialty)
   result={'clinics':clinics,'source':'OpenStreetMap public listings via Nominatim','location':{'latitude':latitude,'longitude':longitude},'notice':'Public map listings are temporarily using Nominatim. Details can be incomplete; verify specialty, contact details and availability with the clinic.'}
   CLINIC_CACHE[key]=(time.time(),result);return jsonify(**result,cached=False)
  seen=set();clinics=[]
  for item in raw.get('elements',[]):
   tags=item.get('tags',{});name=str(tags.get('name','')).strip();identifier=str(item.get('type',''))+'/'+str(item.get('id',''))
   if not name or identifier in seen:continue
   seen.add(identifier);phone=str(tags.get('contact:phone') or tags.get('phone') or '').strip()[:80];website=str(tags.get('contact:website') or tags.get('website') or '').strip()[:500]
   if website and not re.fullmatch(r'https?://[^\s]+',website):website=''
   item_lat=item.get('lat',item.get('center',{}).get('lat'));item_lon=item.get('lon',item.get('center',{}).get('lon'))
   address=clinic_address(tags)
   if not address:address=str(tags.get('addr:full') or tags.get('description') or '').strip()[:500]
   if not address and item_lat is not None:address=f'{float(item_lat):.5f}, {float(item_lon):.5f}'
   clinic_specialty=str(tags.get('healthcare:speciality') or tags.get('healthcare') or tags.get('amenity') or specialty).replace('_',' ').title()[:120]
   clinics.append({'id':'osm_'+identifier.replace('/','_'),'name':name[:160],'specialty':clinic_specialty,'address':address[:500],'phone':phone,'website':website,'source':'OpenStreetMap public listing','directions':'https://www.google.com/maps/dir/?api=1&destination='+urllib.parse.quote(address or name)})
  result={'clinics':clinics,'source':'OpenStreetMap public listings','location':{'latitude':latitude,'longitude':longitude},'notice':'Details come from public OpenStreetMap tags and may be incomplete. Verify specialty, contact details and availability with the clinic.'}
  CLINIC_CACHE[key]=(time.time(),result);return jsonify(**result,cached=False)
 except RuntimeError as error:
  app.logger.warning('Open-data clinic lookup unavailable: %s',error.__cause__ or error)
  return jsonify(error=str(error),fallback='google_maps'),503

@app.before_request
def email_abuse_guard():
 if request.method=='POST' and request.path=='/api/auth/signup':
  ip=hashlib.sha256((request.remote_addr or '').encode()).hexdigest()
  if not limit_requests([('signup:'+ip,8,3600)]):return jsonify(error='Registration limit reached. Try again later.'),429

@app.get('/api/appointments')
@authenticated
def appointments_list():
 with db() as c:rows=c.execute('SELECT * FROM appointments WHERE user_id=? ORDER BY day,time',(session['user_id'],)).fetchall()
 return jsonify([{**dict(r),'clinic':json.loads(r['clinic'])} for r in rows])

@app.get('/api/clinic-booking/<place_id>')
def clinic_booking(place_id):
 # Only an operator-verified clinic booking destination can create a Book action.
 # Google Places websiteURI alone does not establish a booking integration.
 path=ROOT/'instance'/'verified_booking_links.json'
 try:record=json.loads(path.read_text()).get(place_id,{}) if path.exists() else {}
 except (ValueError,OSError):record={}
 url=record.get('url','')
 if record.get('verified') is not True or not record.get('verified_at') or not record.get('evidence') or not re.fullmatch(r'https://[^\s]+',url):return jsonify(booking_url=None)
 return jsonify(booking_url=url,verified_at=record['verified_at'])

@app.post('/api/appointments')
@authenticated
def appointment_save():
 d=body();clinic=d.get('clinic',{});day=parse_day(d.get('day'));preferred=str(d.get('time',''));notes=str(d.get('notes','')).strip();reason=str(d.get('reason','')).strip();contact_name=str(d.get('contact_name','')).strip();contact_phone=str(d.get('contact_phone','')).strip()
 if not isinstance(clinic,dict) or not str(clinic.get('name','')).strip():raise ValueError('Enter a clinic or hospital name.')
 if day<datetime.now(TZ).date() or day>datetime.now(TZ).date()+timedelta(days=365) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',preferred):raise ValueError('Choose a preferred date within the next year and a valid time.')
 if not reason:raise ValueError('Tell the clinic why you would like an appointment.')
 if not contact_name or not re.fullmatch(r'[0-9+() .-]{7,30}',contact_phone):raise ValueError('Enter your name and a valid phone number so you can contact the clinic.')
 if len(notes)>1000 or len(reason)>500 or len(contact_name)>120:raise ValueError('Keep request details within the allowed length.')
 safe={k:str(clinic.get(k,'')).strip()[:500] for k in ['id','name','address','phone','website','specialty','source']}
 safe['id']=safe['id'] if re.fullmatch(r'[A-Za-z0-9_-]{5,200}',safe['id']) else 'manual_'+secrets.token_urlsafe(12)
 if safe['website'] and not re.fullmatch(r'https?://[^\s]+',safe['website']):raise ValueError('Invalid clinic website.')
 safe['directions']='https://www.google.com/maps/dir/?api=1&destination='+__import__('urllib.parse',fromlist=['quote']).quote(safe['address'] or safe['name'])
 with db() as c:
  if c.execute("SELECT COUNT(*) FROM appointments WHERE user_id=? AND status='request_prepared'",(session['user_id'],)).fetchone()[0]>=30:return jsonify(error='You already have 30 prepared requests. Remove an old request first.'),429
  now=datetime.now(timezone.utc).isoformat()
  cur=c.execute('INSERT INTO appointments(user_id,clinic,day,time,notes,reason,contact_name,contact_phone,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',(session['user_id'],json.dumps(safe),day.isoformat(),preferred,notes,reason,contact_name,contact_phone,now,now))
 return jsonify(id=cur.lastrowid,status='request_prepared',message='Request prepared and saved. Contact the clinic to arrange and confirm a booking.',timezone='Asia/Kolkata'),201

@app.put('/api/appointments/<int:identifier>')
@authenticated
def appointment_edit(identifier):
 d=body();day=parse_day(d.get('day'));preferred=str(d.get('time',''));reason=str(d.get('reason','')).strip();notes=str(d.get('notes','')).strip();contact_name=str(d.get('contact_name','')).strip();contact_phone=str(d.get('contact_phone','')).strip()
 if day<datetime.now(TZ).date() or day>datetime.now(TZ).date()+timedelta(days=365) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',preferred):raise ValueError('Choose a preferred date within the next year and a valid time.')
 if not reason or not contact_name or not re.fullmatch(r'[0-9+() .-]{7,30}',contact_phone):raise ValueError('Enter a reason, your name and a valid phone number.')
 if len(notes)>1000 or len(reason)>500 or len(contact_name)>120:raise ValueError('Keep request details within the allowed length.')
 with db() as c:changed=c.execute("UPDATE appointments SET day=?,time=?,reason=?,notes=?,contact_name=?,contact_phone=?,updated=? WHERE id=? AND user_id=? AND status IN ('request_prepared','awaiting_clinic_confirmation')",(day.isoformat(),preferred,reason,notes,contact_name,contact_phone,datetime.now(timezone.utc).isoformat(),identifier,session['user_id'])).rowcount
 if not changed:return jsonify(error='Only your unconfirmed request can be edited.'),404
 return jsonify(success=True,status='request_prepared',message='Request updated. It is still awaiting clinic confirmation.')

@app.delete('/api/appointments/<int:identifier>')
@authenticated
def appointment_delete(identifier):
 with db() as c:changed=c.execute("UPDATE appointments SET status='cancelled',updated=? WHERE id=? AND user_id=? AND status!='confirmed'",(datetime.now(timezone.utc).isoformat(),identifier,session['user_id'])).rowcount
 return (jsonify(success=True,status='cancelled',message='Request cancelled.'),200) if changed else (jsonify(error='Only your unconfirmed request can be cancelled.'),404)
def parse_day(s):
 try:d=date.fromisoformat(s)
 except (ValueError,TypeError):raise ValueError('Use a valid date in YYYY-MM-DD format.')
 return d
@app.get('/favicon.ico')
def favicon():return '',204
@app.get('/')
def website():return send_from_directory(ROOT,'SheSync_Website.html')
@app.get('/api/health')
def health():return jsonify(status='running',models_loaded=list(models),model_errors=model_errors,email_configured=email_configuration()['configured'],maps_configured=bool(os.getenv('GOOGLE_MAPS_BROWSER_KEY')),timezone='Asia/Kolkata')
def email_configuration():return email_providers.configuration()
@app.get('/api/config')
def config():return jsonify(maps_browser_key=os.getenv('GOOGLE_MAPS_BROWSER_KEY',''),email_configured=email_configuration()['configured'],email_setup=email_configuration(),maps_apis=['Maps JavaScript API','Places API (New)'])
@app.post('/api/auth/signup')
def signup():
 d=body();email=str(d.get('email','')).strip().lower();name=str(d.get('name','')).strip();pwd=d.get('password','')
 if not email_valid(email) or not 1<=len(name)<=100 or not isinstance(pwd,str) or not 8<=len(pwd)<=128:raise ValueError('Enter a name, valid email and password of 8–128 characters.')
 try:
  with db() as c:
   cur=c.execute('INSERT INTO users(email,name,password_hash,stage) VALUES(?,?,?,?)',(email,name,generate_password_hash(pwd),str(d.get('stage','Adult'))[:100]));uid=cur.lastrowid
 except sqlite3.IntegrityError:return jsonify(error='An account with this email already exists.'),409
 session.clear();session['user_id']=uid
 return jsonify(email=email,name=name,stage=d.get('stage','Adult'))
login_attempts={}
@app.post('/api/auth/login')
def login():
 d=body();email=str(d.get('email','')).strip().lower();key=(request.remote_addr,email);now=time.time();times=[x for x in login_attempts.get(key,[]) if now-x<300];login_attempts[key]=times
 if len(times)>=10:return jsonify(error='Too many attempts. Try again in five minutes.'),429
 with db() as c:u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
 if not u or not check_password_hash(u['password_hash'],str(d.get('password',''))):times.append(now);return jsonify(error='Incorrect email or password.'),401
 login_attempts.pop(key,None);session.clear();session['user_id']=u['id'];return jsonify(email=u['email'],name=u['name'],stage=u['stage'])
@app.post('/api/auth/password-reset/request')
def password_reset_request():
 d=body();email=str(d.get('email','')).strip().lower()
 if not email_valid(email):raise ValueError('Enter a valid email address.')
 ip=hashlib.sha256((request.remote_addr or '').encode()).hexdigest();wait=reserve_limits([('password-reset-ip:'+ip,5,3600),('password-reset-email:'+hashlib.sha256(email.encode()).hexdigest(),3,3600)])
 if wait:return jsonify(error=f'Please wait {wait} seconds before another reset request.',retry_after_seconds=wait),429
 with db() as c:u=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
 # Do not disclose account existence. The email remains the ownership proof.
 if not u:return jsonify(message='If this email has a SheSync account, a password-reset link was requested.'),200
 config=email_configuration()
 if not config['configured']:return jsonify(error='Email sending is not configured. Start the backend with its configured .env file.'),503
 token=secrets.token_urlsafe(32);token_hash=hashlib.sha256(token.encode()).hexdigest();now=datetime.now(timezone.utc).isoformat()
 with db() as c:
  c.execute('UPDATE password_resets SET used=1 WHERE user_id=? AND used=0',(u['id'],))
  c.execute('INSERT INTO password_resets(token_hash,user_id,created,used) VALUES(?,?,?,0)',(token_hash,u['id'],now))
 try:send_email(email,'Use the secure link in this email to set a new SheSync password. The link expires in 30 minutes. If you did not request it, you can ignore this email.','password-reset:'+str(u['id'])+':'+token,'/api/auth/password-reset/'+token)
 except Exception as e:
  with db() as c:c.execute('UPDATE password_resets SET used=1 WHERE token_hash=?',(token_hash,))
  return jsonify(error='Password-reset email could not be accepted for sending: '+str(e)[:300]),502
 return jsonify(message='If this email has a SheSync account, a password-reset link was sent.'),200
@app.route('/api/auth/password-reset/<token>',methods=['GET','POST'])
def password_reset(token):
 token_hash=hashlib.sha256(token.encode()).hexdigest()
 with db() as c:r=c.execute('SELECT * FROM password_resets WHERE token_hash=?',(token_hash,)).fetchone()
 if not r or r['used'] or datetime.now(timezone.utc)-datetime.fromisoformat(r['created'])>timedelta(minutes=30):return 'This password-reset link is invalid or expired. Request a new link in SheSync.',400
 if request.method=='GET':return '''<!doctype html><title>Reset SheSync password</title><style>body{font-family:Arial;background:#faf7f4;color:#382344;max-width:460px;margin:60px auto;padding:28px}.card{background:white;padding:32px;border-radius:18px}input,button{width:100%;box-sizing:border-box;padding:13px;margin:10px 0;border-radius:9px;border:1px solid #e5c9dc}button{background:#a94380;color:white;border:0;font-weight:bold;cursor:pointer}</style><div class="card"><h1>Set a new password</h1><p>Choose at least 8 characters for your SheSync account.</p><form method="post"><input type="password" name="password" minlength="8" maxlength="128" required autocomplete="new-password" placeholder="New password"><button type="submit">Save new password</button></form></div>'''
 password=request.form.get('password','')
 if not 8<=len(password)<=128:return 'Password must be 8–128 characters.',400
 with db() as c:
  changed=c.execute('UPDATE password_resets SET used=1 WHERE token_hash=? AND used=0',(token_hash,)).rowcount
  if not changed:return 'This password-reset link was already used.',400
  c.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(password),r['user_id']))
 return '<h1>SheSync</h1><p>Password updated. Return to the app and sign in with your new password.</p>'
@app.post('/api/auth/logout')
def logout():session.clear();return jsonify(success=True)
@app.get('/api/auth/me')
@authenticated
def me():
 with db() as c:u=c.execute('SELECT email,name,stage FROM users WHERE id=?',(session['user_id'],)).fetchone()
 return jsonify(dict(u))
@app.put('/api/profile')
@authenticated
def profile():
 d=body();name=str(d.get('name','')).strip()
 if not 1<=len(name)<=100:raise ValueError('Enter a name of 1–100 characters.')
 with db() as c:c.execute('UPDATE users SET name=?,stage=? WHERE id=?',(name,str(d.get('stage','Adult'))[:100],session['user_id']))
 return jsonify(success=True)
def predict_cycle(records,default=29,today=None):
 today=today or datetime.now(TZ).date();records=sorted(records,key=lambda r:r['start']);starts=[parse_day(r['start']) for r in records]
 lengths=[(b-a).days for a,b in zip(starts,starts[1:])]
 avg=round(sum(lengths)/len(lengths)) if lengths else int(default)
 if not lengths and not 15<=avg<=180:raise ValueError('Default estimate must be between 15 and 180 days.')
 if lengths and avg<1:raise ValueError('Period start dates must be distinct.')
 if not starts:return {'average':avg,'basis':'default estimate','history':records,'lengths':[],'next_period':None,'phase':'Not set up','variation':None}
 last=starts[-1];next_day=last+timedelta(days=avg);elapsed=(today-last).days;lastrec=records[-1];duration=(parse_day(lastrec['end'])-last).days+1 if lastrec.get('end') else 5
 phase='Menstrual' if elapsed<duration else 'Follicular' if today<next_day-timedelta(days=16) else 'Ovulation estimate' if today<=next_day-timedelta(days=12) else 'Luteal'
 if elapsed>=avg:phase='Prediction due or overdue'
 return {'average':avg,'basis':f'{len(lengths)} observed cycle'+('s' if len(lengths)!=1 else '') if lengths else 'default estimate — record a second start date','history':records,'lengths':lengths,'next_period':next_day.isoformat(),'last':last.isoformat(),'day':elapsed+1,'days_remaining':(next_day-today).days,'phase':phase,'fertile_start':(next_day-timedelta(days=19)).isoformat(),'fertile_end':(next_day-timedelta(days=12)).isoformat(),'ovulation':(next_day-timedelta(days=14)).isoformat(),'variation':max(lengths)-min(lengths) if lengths else None,'period_duration':duration,'irregular':len(lengths)>1 and max(lengths)-min(lengths)>7,'note':'Calendar estimates only; not contraception or confirmation of ovulation.'}
def user_cycle(uid):
 with db() as c:
  rec=[dict(r) for r in c.execute('SELECT start,end FROM periods WHERE user_id=? ORDER BY start',(uid,))];setting=c.execute('SELECT cycle_length FROM settings WHERE user_id=?',(uid,)).fetchone()
 result=predict_cycle(rec,setting[0] if setting else 29);result['default_length']=setting[0] if setting else 29;return result
@app.put('/api/cycle-settings')
@authenticated
def cycle_settings():
 value=int(body().get('default_length',29))
 if not 15<=value<=180:raise ValueError('Default estimate must be 15–180 days.')
 with db() as c:c.execute('INSERT OR REPLACE INTO settings(user_id,cycle_length) VALUES(?,?)',(session['user_id'],value))
 return jsonify(user_cycle(session['user_id']))
@app.get('/api/periods')
@authenticated
def get_periods():return jsonify(user_cycle(session['user_id']))
@app.post('/api/periods')
@authenticated
def save_period():
 d=body();start=parse_day(d.get('start'));end=parse_day(d['end']) if d.get('end') else None;today=datetime.now(TZ).date()
 if start>today or (end and (end<start or end>today)):raise ValueError('Period dates cannot be in the future; end must follow start.')
 if end and (end-start).days>60:raise ValueError('Check the period end date; duration is over 60 days.')
 uid=session['user_id'];old=d.get('original_start')
 with db() as c:
  rows=c.execute('SELECT start,end FROM periods WHERE user_id=? AND start<>?',(uid,old or '')).fetchall()
  for r in rows:
   a=parse_day(r['start']);b=parse_day(r['end']) if r['end'] else a
   if start==a or (start<=b and (end or start)>=a):raise ValueError('A duplicate or overlapping period already exists. Edit its record instead.')
  if old:
   if not c.execute('SELECT 1 FROM periods WHERE user_id=? AND start=?',(uid,old)).fetchone():raise ValueError('Period record not found.')
   c.execute('DELETE FROM periods WHERE user_id=? AND start=?',(uid,old))
  c.execute('INSERT INTO periods VALUES(?,?,?)',(uid,start.isoformat(),end.isoformat() if end else None))
 result=user_cycle(uid);queue_prediction_update(uid,result);return jsonify(result)
@app.delete('/api/periods/<start>')
@authenticated
def delete_period(start):
 parse_day(start)
 with db() as c:c.execute('DELETE FROM periods WHERE user_id=? AND start=?',(session['user_id'],start))
 result=user_cycle(session['user_id']);queue_prediction_update(session['user_id'],result);return jsonify(result)
@app.post('/api/cycle-predict')
def cycle_predict():
 d=body();default=int(d.get('cycle_length',29));records=d.get('history') or ([{'start':d['last_period'],'end':None}] if d.get('last_period') else [])
 return jsonify(predict_cycle(records,default))
@app.get('/api/phase/<last>/<int:length>')
def phase(last,length):return jsonify(predict_cycle([{'start':last,'end':None}],length))
@app.post('/api/daily-log')
@authenticated
def daily_log():
 d=body();day=parse_day(d.get('date'))
 if day>datetime.now(TZ).date():raise ValueError('Logs cannot be dated in the future.')
 allowed={k:d.get(k) for k in ['period','flow','pain','mood','sleep','symptoms','notes']};allowed['date']=day.isoformat()
 if len(str(allowed.get('notes') or ''))>2000:raise ValueError('Notes must be under 2000 characters.')
 with db() as c:c.execute('INSERT OR REPLACE INTO logs VALUES(?,?,?)',(session['user_id'],day.isoformat(),json.dumps(allowed)))
 return jsonify(success=True)
@app.get('/api/daily-log')
@authenticated
def read_logs():
 with db() as c:logs=[json.loads(r[0]) for r in c.execute('SELECT data FROM logs WHERE user_id=? ORDER BY day',(session['user_id'],))]
 return jsonify(logs)
@app.post('/api/pcos-risk')
@authenticated
def risk():
 return infer_models(body().get('features'))
def infer_models(vals):
 if not isinstance(vals,dict):raise ValueError('Provide clinical features using the model input form.')
 unknown=set(vals)-set(features)
 if unknown:raise ValueError('Unknown model feature names.')
 missing=[f for f in features if f not in vals or vals[f] is None]
 if missing:return jsonify(error='All baseline model features are required. No clinical values are invented.',missing=missing),422
 numbers={}
 for f in features:
  try:v=float(vals[f])
  except (ValueError,TypeError):raise ValueError('Each feature must be a number.')
  if not math.isfinite(v) or abs(v)>1e6:raise ValueError('Feature value outside supported numeric range.')
  if v<0:raise ValueError('Clinical measurements cannot be negative.')
  numbers[f]=v
 limits={' Age (yrs)':(8,100),'Weight (Kg)':(15,350),'Height(Cm) ':(80,230),'BMI':(5,100),'Pulse rate(bpm) ':(20,250),'RR (breaths/min)':(5,80),'BP _Systolic (mmHg)':(50,260),'BP _Diastolic (mmHg)':(20,160),'Follicle No. (L)':(0,100),'Follicle No. (R)':(0,100),'Endometrium (mm)':(0,80)}
 for f,(lo,hi) in limits.items():
  if not lo<=numbers[f]<=hi:raise ValueError('Please check the measurement for '+f.strip())
 binary=[f for f in features if '(Y/N)' in f]
 if any(numbers[f] not in (0,1) for f in binary):raise ValueError('Yes/no inputs must be 0 or 1.')
 for f in [' Age (yrs)','Weight (Kg)','Height(Cm) ']:
  if numbers[f]<=0:raise ValueError('Age, weight and height must be positive.')
 if numbers['Cycle(R/I)'] not in (2,4):raise ValueError('Cycle type must be 2 (regular) or 4 (irregular).')
 if numbers['Blood Group'] not in range(11,19):raise ValueError('Blood group code must be 11–18.')
 frame=pd.DataFrame([numbers],columns=features);result={}
 for name,model in models.items():
  prob=float(model.predict_proba(frame)[0,1]);result[name]={'probability':prob,'prediction':int(model.predict(frame)[0]),'classification':'PCOS' if int(model.predict(frame)[0]) else 'Non-PCOS'}
 if not result:return jsonify(error='Baseline models could not be loaded.'),503
 explanation=[];shap_status='not available'
 try:
  import shap
  explainer=shap.TreeExplainer(models['xgboost']);sv=np.asarray(explainer.shap_values(frame)).reshape(-1)
  explanation=sorted([{'feature':f.strip(),'value':numbers[f],'contribution':float(v)} for f,v in zip(features,sv)],key=lambda x:abs(x['contribution']),reverse=True)[:10];shap_status='XGBoost SHAP contributions in log-odds'
 except Exception:shap_status='SHAP could not be computed for this installed model/runtime.'
 return jsonify(feature_count=len(features),feature_order_validated=True,models=result,model_version='original-2026-baseline',shap=explanation,shap_status=shap_status,calibrated=False,disclaimer='Research screening support only, not a diagnosis. Model probability is uncalibrated and is not an individual clinical risk percentage.')
def historical_examples():
 data=pd.read_excel(ROOT/'data/PCOS_data_without_infertility.xlsx',sheet_name='Full_new')
 numeric=data[features].apply(pd.to_numeric,errors='coerce')
 candidates=numeric.dropna()
 examples=[]
 for diagnosis in [0,1]:
  subset=candidates.loc[data.loc[candidates.index,'PCOS (Y/N)']==diagnosis]
  for idx,row in subset.head(2).iterrows():
   examples.append({'id':f'historical-{int(idx)+1}','name':f'Historical record {int(idx)+1} · recorded label '+('PCOS' if diagnosis else 'Non-PCOS'),'record_number':int(idx)+1,'recorded_label':diagnosis,'features':{f:float(row[f]) for f in features}})
 return examples
@app.get('/api/pcos-examples')
def demo_examples():
 return jsonify(examples=historical_examples(),source={'name':'Kottarathil historical PCOS dataset','url':'https://www.kaggle.com/datasets/prasoonkottarathil/polycystic-ovary-syndrome-pcos','file':'data/PCOS_data_without_infertility.xlsx','sheet':'Full_new','sha256':hashlib.sha256((ROOT/'data/PCOS_data_without_infertility.xlsx').read_bytes()).hexdigest()},note='Existing complete historical records, not live measurements or fabricated patient data.')
@app.post('/api/pcos-demo')
def demo_inference():
 selected=body().get('example_id')
 examples=historical_examples();sample=next((e for e in examples if e['id']==selected),None) if selected else examples[0]
 if not sample:raise ValueError('Select a documented historical example from the list.')
 result=infer_models(sample['features'])
 if isinstance(result,tuple):return result
 data=result.get_json();data['example']={k:v for k,v in sample.items() if k!='features'};data['source']='Historical dataset research demo';return jsonify(data)
@app.get('/api/model-schema')
def schema():return jsonify(features=features,model_version='original-2026-baseline')
@app.get('/api/experiments')
def experiments():
 path=ROOT/'experiments/results.json'
 return jsonify(json.loads(path.read_text()) if path.exists() else {'status':'No completed experiments yet.'})
def enqueue(uid,kind,key,text):
 with db() as c:
  reminder=c.execute('SELECT * FROM reminders WHERE user_id=?',(uid,)).fetchone()
  recipient=reminder['email'] if reminder else None
  path=('/api/reminders/confirm/'+reminder['verify_token'] if kind=='verify' else '/api/reminders/unsubscribe/'+reminder['unsubscribe_token']) if reminder else None
  c.execute('INSERT OR IGNORE INTO outbox(key,user_id,kind,body,created,recipient,action_path) VALUES(?,?,?,?,?,?,?)',(key,uid,kind,text,datetime.now(timezone.utc).isoformat(),recipient,path))
  c.execute("UPDATE outbox SET recipient=?,action_path=?,status='pending',error=NULL WHERE key=? AND attempts=0 AND provider_id IS NULL AND status IN ('blocked_configuration','cancelled')",(recipient,path,key))
def queue_prediction_update(uid,cycle):
 with db() as c:r=c.execute('SELECT * FROM reminders WHERE user_id=?',(uid,)).fetchone()
 if r and r['consent'] and r['verified'] and json.loads(r['prefs']).get('prediction_update') and cycle.get('next_period'):
  enqueue(uid,'prediction_update',f'prediction:{uid}:{cycle.get("last")}:{cycle["next_period"]}',f'Your saved calendar estimate has been updated. Next estimated period: {cycle["next_period"]}. Calendar predictions are estimates.')
def send_email(recipient,text,key,unsubscribe):return email_providers.send(recipient,text,key,unsubscribe)
@app.get('/api/reminders')
@authenticated
def get_reminders():
 with db() as c:
  r=c.execute('SELECT email,consent,verified,prefs FROM reminders WHERE user_id=?',(session['user_id'],)).fetchone()
  logs=[dict(x) for x in c.execute('SELECT kind,status,provider_id,error,created,delivery_event,provider FROM outbox WHERE user_id=? ORDER BY created DESC LIMIT 15',(session['user_id'],))]
  logs += [dict(x) for x in c.execute('SELECT kind,status,provider_id,error,created,NULL AS delivery_event,provider FROM email_actions WHERE user_id=? ORDER BY created DESC LIMIT 15',(session['user_id'],))]
  logs=sorted(logs,key=lambda x:x['created'],reverse=True)[:20]
 with db() as c:w=c.execute("SELECT last_seen FROM worker_status WHERE name='reminder_worker'").fetchone()
 last_seen=w[0] if w else None
 active=bool(last_seen and datetime.now(timezone.utc)-datetime.fromisoformat(last_seen)<timedelta(minutes=3))
 return jsonify(settings={**dict(r),'prefs':json.loads(r['prefs'])} if r else None,delivery_logs=logs,configured=email_configuration()['configured'],configuration=email_configuration(),worker={'active':active,'last_seen':last_seen,'timezone':'Asia/Kolkata'})
@app.get('/api/reminders/delivery/<provider_id>')
@authenticated
def delivery_status(provider_id):
 with db() as c:row=c.execute('SELECT key,provider,status FROM outbox WHERE provider_id=? AND user_id=?',(provider_id,session['user_id'])).fetchone()
 if not row:
  with db() as c:row=c.execute('SELECT key,provider,status FROM email_actions WHERE provider_id=? AND user_id=?',(provider_id,session['user_id'])).fetchone()
 if not row:return jsonify(error='No sending request with that ID belongs to this account.'),404
 if row['provider'] in ('gmail','gmail_oauth') or provider_id.startswith(('gmail:','gmail_api:')):return jsonify(provider_id=provider_id,provider_event='smtp_accepted' if row['provider']=='gmail' else 'gmail_api_accepted',provider_reports_delivery=False,note='Gmail accepted submission. SMTP/API acceptance does not establish inbox delivery; check the sender and recipient mailboxes.')
 if not os.getenv('RESEND_API_KEY'):return jsonify(error='Resend configuration is required to retrieve this earlier Resend message.'),503
 if not re.fullmatch(r'[A-Za-z0-9-]{1,100}',provider_id):raise ValueError('Invalid provider message ID.')
 req=urllib.request.Request('https://api.resend.com/emails/'+provider_id,headers={'Authorization':'Bearer '+os.getenv('RESEND_API_KEY'),'Accept':'application/json','User-Agent':'SheSync/1.1 (Resend REST client)'})
 try:
  with urllib.request.urlopen(req,timeout=15) as res:data=json.load(res)
 except urllib.error.HTTPError as e:return jsonify(error=f'Resend delivery lookup was rejected (HTTP {e.code}). The key may not permit reading emails; inspect the Resend dashboard.'),502
 except (urllib.error.URLError,TimeoutError):return jsonify(error='Resend delivery status could not be reached. No delivery confirmation is claimed.'),502
 event=str(data.get('last_event','unknown'))[:80]
 with db() as c:c.execute('UPDATE outbox SET delivery_event=? WHERE key=?',(event,row['key']))
 return jsonify(provider_id=provider_id,provider_event=event,provider_reports_delivery=event=='delivered',note='Delivered means the recipient mail server accepted the email; it does not establish inbox placement or that it was read.')
@app.post('/api/reminders')
@authenticated
def reminders():
 verified=save_reminder_preferences(body(),session['user_id'])
 return jsonify(success=True,verified=verified,configuration=email_configuration(),message='Preferences saved.' if verified else 'Preferences saved. Confirm your email before automatic reminders can start.')

def save_reminder_preferences(d,uid):
 email=str(d.get('email','')).strip();consent=d.get('consent') is True;prefs=d.get('prefs',{})
 if not email_valid(email):raise ValueError('Enter a valid email address.')
 if not isinstance(prefs,dict):raise ValueError('Invalid reminder preferences.')
 days=int(prefs.get('days_before',3));hour=int(prefs.get('hour',9))
 if not 0<=days<=14 or not 0<=hour<=23:raise ValueError('Lead time must be 0–14 days; hour must be 0–23.')
 safe={k:bool(prefs.get(k)) for k in ['upcoming','daily','prediction_update','wellness']};safe.update(days_before=days,hour=hour)
 token=secrets.token_urlsafe(32);unsub=secrets.token_urlsafe(32)
 with db() as c:
  old=c.execute('SELECT * FROM reminders WHERE user_id=?',(uid,)).fetchone();verified=bool(old and old['email']==email and old['verified']);token=old['verify_token'] if old and old['email']==email else token;unsub=old['unsubscribe_token'] if old else unsub
  c.execute('INSERT OR REPLACE INTO reminders VALUES(?,?,?,?,?,?,?,?)',(uid,email,int(consent),int(verified),json.dumps(safe),token,unsub,datetime.now(timezone.utc).isoformat()))
 return verified
def direct_email_action(action):
 d=body();uid=session['user_id']
 # Browser supplies the current form, including its consent and recipient.
 # Legacy confirmation calls may omit preferences; tests require a current address.
 if 'email' in d:
  if d.get('consent') is not True:raise ValueError('Check the email consent box before sending.')
  save_reminder_preferences(d,uid)
 elif action=='test':raise ValueError('Enter the current recipient address and consent before sending.')
 with db() as c:r=c.execute('SELECT * FROM reminders WHERE user_id=?',(uid,)).fetchone()
 if not r or not r['consent']:raise ValueError('Enter your email and opt in first.')
 if action=='verify' and r['verified']:return jsonify(status='already_confirmed',message='This address is already verified. Click Send Test Email.'),200
 kind='test' if action=='test' and r['verified'] else 'verify'
 configuration=email_configuration()
 if not configuration['configured']:return jsonify(error='Configure '+', '.join(configuration['missing'])+' in the backend .env and restart both processes.',configuration=configuration),503
 # An explicit Resend selection is retained for existing integrations; the active
 # configured deployment uses Gmail. Never silently fall back to a different sender.
 request_id=str(d.get('request_id') or secrets.token_urlsafe(24))
 if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',request_id):raise ValueError('Invalid email request ID.')
 key=f'direct:{uid}:{request_id}'
 with db() as c:previous=c.execute('SELECT * FROM email_actions WHERE key=?',(key,)).fetchone()
 if previous:
  if previous['recipient']!=r['email'] or previous['kind']!=kind:return jsonify(error='This request ID belongs to a different recipient or action. Start a new request.'),409
  return direct_action_response(previous,duplicate=True)
 ip=hashlib.sha256((request.remote_addr or '').encode()).hexdigest();recipient=hashlib.sha256(r['email'].encode()).hexdigest()
 scopes=[('email-action:'+kind+':'+str(uid),1,300 if kind=='verify' else 60),('email-user-day:'+str(uid),8,86400),('email-recipient:'+recipient,8,86400),('email-ip:'+ip,20,3600),('provider-budget',int(os.getenv('EMAIL_DAILY_LIMIT','100')),86400),('provider-minute',10,60),('delivery-user:'+str(uid),10,86400),('delivery-recipient:'+recipient,20,86400)]
 wait=reserve_limits(scopes)
 if wait:
  response=jsonify(error=f'Application email cooldown: retry in {wait} seconds. No sending request was made.',retry_after_seconds=wait,cooldown_until=(datetime.now(timezone.utc)+timedelta(seconds=wait)).isoformat(),provider=configuration['provider'])
  response.headers['Retry-After']=str(wait);return response,429
 if kind=='verify':
  # A fresh link for each permitted verification send has a clear 24-hour lifetime.
  with db() as c:
   c.execute('UPDATE reminders SET verify_token=? WHERE user_id=?',(secrets.token_urlsafe(32),uid));r=c.execute('SELECT * FROM reminders WHERE user_id=?',(uid,)).fetchone()
 link='/api/reminders/'+('confirm/'+r['verify_token'] if kind=='verify' else 'unsubscribe/'+r['unsubscribe_token'])
 created=datetime.now(timezone.utc).isoformat()
 with db() as c:
  claimed=c.execute("INSERT OR IGNORE INTO email_actions(key,user_id,kind,recipient,action_path,status,provider,created) VALUES(?,?,?,?,?,'sending',?,?)",(key,uid,kind,r['email'],link,configuration['provider'],created)).rowcount
  if not claimed:return direct_action_response(c.execute('SELECT * FROM email_actions WHERE key=?',(key,)).fetchone(),duplicate=True)
 text='Confirm ownership of this email address to enable your requested SheSync reminders. After confirming, return to SheSync and click Send Test Email.' if kind=='verify' else 'Your SheSync test reminder is ready. This is an immediate test of your verified email preferences, separate from your automatic reminder schedule. Take a moment to check in with yourself today.'
 try:
  provider_id=send_email(r['email'],text,key,link)
  with db() as c:c.execute("UPDATE email_actions SET status='accepted',provider_id=? WHERE key=?",(provider_id,key))
 except email_providers.SendingUncertain as e:
  with db() as c:c.execute("UPDATE email_actions SET status='review_required',error=? WHERE key=?",(str(e)[:500],key))
 except Exception as e:
  with db() as c:c.execute("UPDATE email_actions SET status='failed',error=? WHERE key=?",(str(e)[:500],key))
 with db() as c:row=c.execute('SELECT * FROM email_actions WHERE key=?',(key,)).fetchone()
 return direct_action_response(row)

def direct_action_response(row,duplicate=False):
 result={k:row[k] for k in ['kind','status','provider','provider_id','error','recipient']};result.update(verification_required=row['kind']=='verify',duplicate=duplicate,scheduled=False)
 if row['status']=='accepted':
  result['message']='Verification email accepted for sending. Open its link, then click Send Test Email.' if row['kind']=='verify' else 'Email accepted for sending. Inbox delivery has not been independently verified.'
  result['retry_after_seconds']=max(0,math.ceil((datetime.fromisoformat(row['created'])+timedelta(seconds=300 if row['kind']=='verify' else 60)-datetime.now(timezone.utc)).total_seconds()))
  return jsonify(result),200
 if row['status']=='sending':result['error']='This request is still sending. Refresh status; do not submit another request.';return jsonify(result),202
 return jsonify(result),502

@app.post('/api/reminders/verify')
@authenticated
def verify_request():return direct_email_action('verify')

@app.get('/api/reminders/confirm/<token>')
def confirm_email(token):
 with db() as c:
  r=c.execute('SELECT user_id,updated FROM reminders WHERE verify_token=?',(token,)).fetchone()
  if not r:return 'Invalid confirmation link.',400
  issued=c.execute("SELECT created FROM email_actions WHERE user_id=? AND action_path=? AND status='accepted' ORDER BY created DESC LIMIT 1",(r['user_id'],'/api/reminders/confirm/'+token)).fetchone()
  if not issued:issued=c.execute('SELECT created FROM outbox WHERE key=?',(f'verify:{r["user_id"]}:{token}',)).fetchone()
  if datetime.now(timezone.utc)-datetime.fromisoformat(issued['created'] if issued else r['updated'])>timedelta(hours=24):return 'This confirmation link expired. Request a new confirmation email in SheSync.',400
  c.execute('UPDATE reminders SET verified=1 WHERE user_id=?',(r['user_id'],))
 return '<h1>SheSync</h1><p>Email confirmed. Your opted-in reminders are enabled. Return to the app to continue.</p>'
@app.get('/api/reminders/unsubscribe/<token>')
def unsubscribe(token):
 with db() as c:
  changed=c.execute('UPDATE reminders SET consent=0 WHERE unsubscribe_token=?',(token,)).rowcount
 if not changed:return 'Invalid unsubscribe link.',400
 return '<h1>SheSync</h1><p>Automatic reminders are disabled.</p>'
@app.post('/api/reminders/test')
@authenticated
def test_email():return direct_email_action('test')

def schedule_due(now=None):
 now=now or datetime.now(TZ)
 with db() as c:rows=c.execute('SELECT * FROM reminders WHERE consent=1 AND verified=1').fetchall()
 for r in rows:
  prefs=json.loads(r['prefs']);uid=r['user_id'];cy=user_cycle(uid)
  if now.hour<prefs['hour']:continue
  today=now.date().isoformat()
  if prefs.get('daily'):enqueue(uid,'daily',f'daily:{uid}:{today}','A small moment for yourself: your daily check-in is ready.')
  if prefs.get('wellness') and now.weekday()==0:enqueue(uid,'wellness',f'wellness:{uid}:{today}','Your weekly wellbeing check-in is ready. Take a moment to reflect on how you feel.')
  if prefs.get('upcoming') and cy.get('next_period') and (parse_day(cy['next_period'])-now.date()).days==prefs['days_before']:enqueue(uid,'upcoming',f'upcoming:{uid}:{cy["next_period"]}',f'Your next calendar estimate is {cy["next_period"]}. Take a moment to prepare if helpful. This is an estimate.')
def process_outbox(only_key=None):
 if only_key is None:
  with db() as c:c.execute("UPDATE outbox SET status='cancelled',error='Historical manual action retired. Use the immediate email button to make a new request.' WHERE kind IN ('test','verify') AND status IN ('pending','failed','blocked_configuration')")
 # Missing credentials are configuration failures, not provider attempts.
 if not email_configuration()['configured']:
  with db() as c:c.execute("UPDATE outbox SET status='blocked_configuration',error='Missing provider configuration; no sending request was made.' WHERE status IN ('pending','failed','blocked_configuration')"+(' AND key=?' if only_key else ''),(only_key,) if only_key else ())
  return
 with db() as c:
  rows=c.execute("SELECT * FROM outbox WHERE status IN ('pending','failed','blocked_configuration') AND attempts<3"+(' AND key=?' if only_key else ''),(only_key,) if only_key else ()).fetchall()
 for row in rows:
  with db() as c:
   r=c.execute('SELECT * FROM reminders WHERE user_id=?',(row['user_id'],)).fetchone()
   if not r or not r['consent'] or (row['kind']!='verify' and not r['verified']):c.execute("UPDATE outbox SET status='cancelled' WHERE key=?",(row['key'],));continue
   if row['recipient'] and row['recipient']!=r['email']:c.execute("UPDATE outbox SET status='cancelled',error='Recipient changed; old queued email cancelled.' WHERE key=?",(row['key'],));continue
   if row['kind']=='verify' and row['action_path'] and row['action_path']!='/api/reminders/confirm/'+r['verify_token']:c.execute("UPDATE outbox SET status='cancelled' WHERE key=?",(row['key'],));continue
   if row['attempts'] and datetime.now(timezone.utc)-datetime.fromisoformat(row['created'])>timedelta(hours=23):c.execute("UPDATE outbox SET status='review_required' WHERE key=?",(row['key'],));continue
   if row['last_attempt'] and datetime.now(timezone.utc)-datetime.fromisoformat(row['last_attempt'])<timedelta(minutes=1) and row['status']=='failed':continue
   claimed=c.execute("UPDATE outbox SET status='sending',attempts=attempts+1,last_attempt=? WHERE key=? AND status IN ('pending','failed','blocked_configuration')",(datetime.now(timezone.utc).isoformat(),row['key'])).rowcount
  if not claimed:continue
  if not limit_requests([('provider-budget',int(os.getenv('EMAIL_DAILY_LIMIT','100')),86400),('provider-minute',10,60),('delivery-user:'+str(row['user_id']),10,86400),('delivery-recipient:'+hashlib.sha256(r['email'].encode()).hexdigest(),20,86400)]):
   with db() as c:c.execute("UPDATE outbox SET status='pending',attempts=attempts-1,error='Application sending budget reached; deferred to the worker.' WHERE key=?",(row['key'],))
   continue
  try:
   link=row['action_path'] or ('/api/reminders/confirm/'+r['verify_token'] if row['kind']=='verify' else '/api/reminders/unsubscribe/'+r['unsubscribe_token']);pid=send_email(row['recipient'] or r['email'],row['body'],row['key'],link)
   with db() as c:c.execute("UPDATE outbox SET status='accepted',provider_id=?,provider=?,error=NULL WHERE key=?",(pid,email_configuration()['provider'],row['key']))
  except email_providers.SendingUncertain as e:
   with db() as c:c.execute("UPDATE outbox SET status='review_required',error=? WHERE key=?",(str(e)[:300],row['key']))
  except Exception as e:
   with db() as c:c.execute("UPDATE outbox SET status='failed',error=? WHERE key=?",(str(e)[:300],row['key']))
@app.post('/api/wearable')
def ingest():
 expected=os.getenv('WEARABLE_INGEST_KEY')
 if not expected or not secrets.compare_digest(request.headers.get('X-Device-Key',''),expected):return jsonify(error='Device authentication required.'),401
 d=body();dev=str(d.get('device_id',''))
 if not dev or len(dev)>80:raise ValueError('Device identifier is required.')
 source=d.get('source','live')
 if source not in ['live','demo']:raise ValueError('Source must be live or demo.')
 ranges={'heart_rate':(20,250),'temperature':(20,45),'gsr':(0,100),'steps':(0,200000),'motion':(0,1000),'ecg':(-10000,10000),'estradiol':(0,100000)};values={}
 for k,(lo,hi) in ranges.items():
  if k in d:
   v=float(d[k])
   if not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid sensor value for '+k)
   values[k]=v
 if not values:raise ValueError('At least one recognized sensor reading is required.')
 timestamp=d.get('timestamp')
 if timestamp:
  try:parsed=datetime.fromisoformat(timestamp.replace('Z','+00:00'))
  except ValueError:raise ValueError('Timestamp must be ISO 8601.')
  if parsed.tzinfo is None:raise ValueError('Sensor timestamp needs a timezone offset.')
 else:timestamp=datetime.now(timezone.utc).isoformat()
 with db() as c:c.execute('INSERT INTO wearable(device_id,recorded,source,data) VALUES(?,?,?,?)',(dev,timestamp,source,json.dumps(values)))
 return jsonify(success=True,source=source,used_for_pcos=False,message='Reading stored. Sensor measurements are not inputs to the clinical baseline model.')
@app.delete('/api/data')
@authenticated
def clear_health():
 uid=session['user_id']
 with db() as c:
  for table in ['periods','logs','reminders','outbox','settings','appointments','email_actions']:c.execute(f'DELETE FROM {table} WHERE user_id=?',(uid,))
 return jsonify(success=True)
if __name__=='__main__':app.run(host='127.0.0.1',port=int(os.getenv('PORT',5000)),debug=False)
