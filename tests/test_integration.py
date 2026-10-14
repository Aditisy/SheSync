import os,sys,tempfile,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.runtime-deps'))
os.environ['SHESYNC_DB']=str(ROOT/'instance/test.sqlite3')
os.environ['SECRET_KEY']='test-only-secret-not-for-deployment'
os.environ['EMAIL_PROVIDER']='resend'
import backend_api as api
os.environ['EMAIL_PROVIDER']='resend'
from datetime import date,datetime,timedelta
class Integration(unittest.TestCase):
 def setUp(self):
  with api.db() as c:c.execute('DELETE FROM rate_events')
 @classmethod
 def setUpClass(cls):
  cls.client=api.app.test_client();cls.headers={'X-SheSync-Client':'web','Origin':'http://localhost:5000'}
  with api.db() as c:
   for t in ['users','periods','logs','reminders','outbox','settings','wearable','appointments','rate_events','email_actions']:c.execute('DELETE FROM '+t)
  r=cls.client.post('/api/auth/signup',json={'name':'Test User','email':'integration@example.test','password':'test-only-strong-password','stage':'Adult'},headers=cls.headers);assert r.status_code==200,r.json
 def call(self,path,data):return self.client.post(path,json=data,headers=self.headers)
 def test_01_cycle_exact_dates(self):
  for start,end in [('2026-09-18','2026-09-22'),('2026-10-13',None)]:
   r=self.call('/api/periods',{'start':start,'end':end});self.assertEqual(r.status_code,200,r.json)
  self.assertEqual(r.json['average'],25);self.assertEqual(r.json['next_period'],'2026-11-07');self.assertEqual(r.json['lengths'],[25]);self.assertEqual(r.json['day'],(datetime.now(api.TZ).date()-date(2026,10,13)).days+1)
  r=self.call('/api/periods',{'start':'2026-10-13'});self.assertEqual(r.status_code,400)
  self.assertEqual(self.call('/api/periods',{'start':(datetime.now(api.TZ).date()+timedelta(days=1)).isoformat()}).status_code,400)
  self.assertEqual(self.call('/api/periods',{'start':'2026-09-20','end':'2026-09-19'}).status_code,400)
  self.assertEqual(self.client.get('/api/periods').json['next_period'],'2026-11-07')
 def test_02_auth_and_logs(self):
  anon=api.app.test_client();self.assertEqual(anon.get('/api/periods').status_code,401)
  with api.db() as c:row=c.execute('SELECT password_hash FROM users').fetchone()
  self.assertNotIn('test-only-strong-password',row[0]);self.assertTrue(row[0].startswith('scrypt:'))
  for mood in ['Okay','Happy']:
   r=self.call('/api/daily-log',{'date':'2026-10-13','mood':mood,'notes':'<script>alert(1)</script>'});self.assertEqual(r.status_code,200)
  logs=self.client.get('/api/daily-log').json;self.assertEqual(len(logs),1);self.assertEqual(logs[0]['mood'],'Happy')
 def test_03_real_model_and_schema(self):
  data=__import__('pandas').read_excel(ROOT/'data/PCOS_data_without_infertility.xlsx',sheet_name='Full_new')[api.features].apply(__import__('pandas').to_numeric,errors='coerce').dropna().iloc[0].to_dict()
  r=self.call('/api/pcos-risk',{'features':data});self.assertEqual(r.status_code,200,r.json);self.assertEqual(set(r.json['models']),{'xgboost','random_forest'});self.assertTrue(0<=r.json['models']['xgboost']['probability']<=1);self.assertEqual(len(r.json['shap']),10)
  self.assertEqual(self.call('/api/pcos-risk',{'features':{'BMI':20}}).status_code,422)
  data[' Age (yrs)']=-1;self.assertEqual(self.call('/api/pcos-risk',{'features':data}).status_code,400)
  self.assertEqual(self.call('/api/pcos-demo',{}).status_code,200)
 def test_04_reminder_scheduler_mocked_provider(self):
  self.assertEqual(self.call('/api/reminders',{'email':'invalid','consent':True}).status_code,400)
  prefs={'daily':True,'upcoming':True,'prediction_update':True,'days_before':3,'hour':9}
  self.assertEqual(self.call('/api/reminders',{'email':'integration@example.test','consent':True,'prefs':prefs}).status_code,200)
  self.assertEqual(self.call('/api/reminders/test',{}).status_code,400)
  with api.db() as c:r=c.execute('SELECT * FROM reminders').fetchone()
  self.assertEqual(self.client.get('/api/reminders/confirm/'+r['verify_token']).status_code,200)
  original=api.send_email;calls=[]
  original_env={k:os.getenv(k) for k in ['RESEND_API_KEY','EMAIL_FROM','PUBLIC_BASE_URL']}
  os.environ.update(RESEND_API_KEY='test-key-never-transmitted',EMAIL_FROM='SheSync <test@example.test>',PUBLIC_BASE_URL='http://localhost:5000')
  def fake(*args):calls.append(args);return 'mock-provider-id'
  api.send_email=fake
  try:
   now=datetime(2026,11,4,9,0,tzinfo=api.TZ)
   api.schedule_due(now);api.schedule_due(now);api.process_outbox();api.process_outbox();self.assertEqual(len(calls),2)
   logs=self.client.get('/api/reminders').json['delivery_logs'];self.assertTrue(all(l['status']=='accepted' for l in logs))
   self.client.get('/api/reminders/unsubscribe/'+r['unsubscribe_token']);api.schedule_due(datetime(2026,11,5,9,tzinfo=api.TZ));api.process_outbox();self.assertEqual(len(calls),2)
  finally:
   api.send_email=original
   for k,v in original_env.items():
    if v is None:os.environ.pop(k,None)
    else:os.environ[k]=v
 def test_05_wearable(self):
  os.environ['WEARABLE_INGEST_KEY']='test-device-key'
  payload={'device_id':'test-device','source':'live','heart_rate':70,'temperature':36.5,'timestamp':'2026-10-13T09:00:00+05:30'}
  self.assertEqual(self.client.post('/api/wearable',json=payload).status_code,401)
  r=self.client.post('/api/wearable',json=payload,headers={'X-Device-Key':'test-device-key'});self.assertEqual(r.status_code,200);self.assertFalse(r.json['used_for_pcos'])
  payload['temperature']=100;self.assertEqual(self.client.post('/api/wearable',json=payload,headers={'X-Device-Key':'test-device-key'}).status_code,400)
 def test_06_edit_delete(self):
  r=self.call('/api/periods',{'start':'2026-09-17','end':'2026-09-22','original_start':'2026-09-18'});self.assertEqual(r.json['average'],26)
  r=self.client.delete('/api/periods/2026-09-17',headers=self.headers);self.assertEqual(r.status_code,200);self.assertIn('default estimate',r.json['basis'])
 def test_07_configuration_does_not_consume_attempts(self):
  uid=self.client.get('/api/auth/me').json
  with api.db() as c:user_id=c.execute('SELECT id FROM users WHERE email=?',(uid['email'],)).fetchone()[0]
  previous=os.environ.pop('RESEND_API_KEY',None)
  try:
   api.enqueue(user_id,'test','test-no-credentials','Test only')
   api.process_outbox('test-no-credentials')
   with api.db() as c:r=c.execute("SELECT status,attempts FROM outbox WHERE key='test-no-credentials'").fetchone()
   self.assertEqual(r['status'],'blocked_configuration');self.assertEqual(r['attempts'],0)
  finally:
   if previous is not None:os.environ['RESEND_API_KEY']=previous
 def test_08_historical_examples(self):
  examples=self.client.get('/api/pcos-examples').json['examples'];self.assertEqual(len(examples),4)
  self.assertEqual({e['recorded_label'] for e in examples},{0,1})
  for example in examples:
   self.assertEqual(set(example['features']),set(api.features));r=self.call('/api/pcos-demo',{'example_id':example['id']});self.assertEqual(r.status_code,200,r.json);self.assertEqual(r.json['example']['id'],example['id']);self.assertEqual(len(r.json['shap']),10)
   for model in r.json['models'].values():self.assertIn(model['classification'],['PCOS','Non-PCOS'])
  self.assertEqual(self.call('/api/pcos-demo',{'example_id':'invented-record'}).status_code,400)
 def test_09_complete_email_workflow_mocked_http(self):
  from unittest.mock import patch
  previous={k:os.getenv(k) for k in ['RESEND_API_KEY','EMAIL_FROM','PUBLIC_BASE_URL']}
  os.environ.update(RESEND_API_KEY='fake-resend-key-not-transmitted',EMAIL_FROM='SheSync <test@example.test>',PUBLIC_BASE_URL='http://localhost:5000')
  requests=[]
  class Response:
   def __init__(self,payload):self.payload=payload
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return json.dumps(self.payload).encode()
  def provider(req,timeout=0):
   requests.append(req)
   if req.get_method()=='GET':return Response({'last_event':'delivered'})
   self.assertEqual(req.full_url,'https://api.resend.com/emails');self.assertTrue(req.get_header('Authorization').startswith('Bearer '));self.assertTrue(req.get_header('Idempotency-key'));payload=json.loads(req.data);self.assertEqual(payload['to'],['integration@example.test']);return Response({'id':'test-provider-'+str(len(requests))})
  try:
   prefs={'upcoming':True,'daily':True,'days_before':3,'hour':9}
   self.assertEqual(self.call('/api/reminders',{'email':'integration@example.test','consent':True,'prefs':prefs}).status_code,200)
   with api.db() as c:
    uid=c.execute('SELECT user_id FROM reminders').fetchone()[0];c.execute('DELETE FROM outbox WHERE user_id=?',(uid,));c.execute("UPDATE reminders SET verified=0,verify_token='test-confirmation-token'")
   with patch('backend_api.urllib.request.urlopen',side_effect=provider):
    confirmation=self.call('/api/reminders/verify',{});self.assertEqual(confirmation.status_code,200);self.assertEqual(confirmation.json['status'],'accepted');self.assertIn('/api/reminders/confirm/',json.loads(requests[0].data)['html'])
    
    with api.db() as c:token=c.execute('SELECT verify_token FROM reminders WHERE user_id=?',(uid,)).fetchone()[0]
    self.assertEqual(self.client.get('/api/reminders/confirm/'+token).status_code,200)
    
    with api.db() as c:c.execute('DELETE FROM rate_events')
    sent=self.call('/api/reminders/test',{'email':'integration@example.test','consent':True,'prefs':prefs});self.assertEqual(sent.status_code,200);self.assertEqual(sent.json['status'],'accepted')
    delivery=self.client.get('/api/reminders/delivery/'+sent.json['provider_id']);self.assertEqual(delivery.json['provider_event'],'delivered');self.assertTrue(delivery.json['provider_reports_delivery'])
    now=datetime(2026,11,8,9,tzinfo=api.TZ);api.schedule_due(now);api.process_outbox();n=len(requests);api.schedule_due(now);api.process_outbox();self.assertEqual(len(requests),n)
   self.assertEqual(self.client.get('/api/reminders').json['settings']['verified'],1)
  finally:
   for k,v in previous.items():
    if v is None:os.environ.pop(k,None)
    else:os.environ[k]=v
 def test_10_dynamic_gmail_and_private_requests(self):
  from unittest.mock import patch
  sent=[]
  class SMTP:
   def __init__(self,*a,**kw):pass
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def ehlo(self):pass
   def starttls(self,**kw):pass
   def login(self,*a):pass
   def send_message(self,message,**kw):sent.append((str(message['To']),message.get_body(preferencelist=('plain',)).get_content()));return {}
  users=[]
  with patch.dict(os.environ,{'EMAIL_PROVIDER':'gmail','GMAIL_USERNAME':'sender@example.test','GMAIL_APP_PASSWORD':'mock-password-not-transmitted'}),patch('email_providers.smtplib.SMTP',SMTP):
   for i,address in enumerate(['first@gmail.com','second@outlook.com']):
    client=api.app.test_client();users.append(client)
    self.assertEqual(client.post('/api/auth/signup',json={'name':'Mock user '+str(i),'email':address,'password':'mock-strong-password'},headers=self.headers).status_code,200)
    self.assertEqual(client.post('/api/reminders',json={'email':address,'consent':True,'prefs':{'daily':True,'hour':9}},headers=self.headers).status_code,200)
    with api.db() as c:c.execute('DELETE FROM rate_events')
    self.assertEqual(client.post('/api/reminders/verify',json={},headers=self.headers).json['status'],'accepted')
    with api.db() as c:r=c.execute('SELECT * FROM reminders WHERE email=?',(address,)).fetchone()
    self.assertEqual(client.get('/api/reminders/confirm/'+r['verify_token']).status_code,200)
    with api.db() as c:c.execute('DELETE FROM rate_events')
    response=client.post('/api/reminders/test',json={'email':address,'consent':True,'prefs':{'daily':True,'hour':9}},headers=self.headers)
    self.assertEqual(response.json['status'],'accepted');self.assertEqual(response.json['provider'],'gmail')
    self.assertEqual(client.post('/api/reminders/test',json={'email':address,'consent':True,'prefs':{'daily':True,'hour':9}},headers=self.headers).status_code,200)
   self.assertEqual([r[0] for r in sent],['first@gmail.com','first@gmail.com','first@gmail.com','second@outlook.com','second@outlook.com','second@outlook.com'])
   with api.db() as c:
    c.execute('DELETE FROM rate_events');c.execute("UPDATE reminders SET consent=0 WHERE email='integration@example.test'")
   api.schedule_due(datetime(2026,12,1,10,tzinfo=api.TZ));api.process_outbox();before=len(sent);api.schedule_due(datetime(2026,12,1,10,tzinfo=api.TZ));api.process_outbox();self.assertEqual(len(sent),before);self.assertEqual([r[0] for r in sent[-2:]],['first@gmail.com','second@outlook.com'])
   # These are explicitly mocked clinic snapshots, never shipped as real doctors.
   clinic={'id':'mock_place_12345','name':'Mock clinic','address':'Mock address','website':'https://example.test','phone':'+910000000000'}
   record=users[0].post('/api/appointments',json={'clinic':clinic,'day':(datetime.now(api.TZ).date()+timedelta(days=2)).isoformat(),'time':'10:30','reason':'Mock clinical consultation','contact_name':'Mock User','contact_phone':'+910000000000','status':'confirmed'},headers=self.headers)
   self.assertEqual(record.status_code,201);self.assertEqual(record.json['status'],'request_prepared')
   self.assertEqual(len(users[0].get('/api/appointments').json),1);self.assertEqual(users[1].get('/api/appointments').json,[])
   self.assertEqual(users[1].delete('/api/appointments/'+str(record.json['id']),headers=self.headers).status_code,404)
   self.assertEqual(users[0].post('/api/appointments',json={'clinic':clinic,'day':(datetime.now(api.TZ).date()-timedelta(days=1)).isoformat(),'time':'10:30','reason':'Past date','contact_name':'Mock User','contact_phone':'+910000000000'},headers=self.headers).status_code,400)
   self.assertEqual(users[0].post('/api/appointments',json={'clinic':clinic,'day':(datetime.now(api.TZ).date()+timedelta(days=2)).isoformat(),'time':'10:30','reason':'','contact_name':'Mock User','contact_phone':'+910000000000'},headers=self.headers).status_code,400)
   self.assertEqual(users[1].get('/api/reminders').json['settings']['email'],'second@outlook.com')
   # Changing a recipient invalidates ownership, cancels old pending snapshots.
   with api.db() as c:r=c.execute("SELECT * FROM reminders WHERE email='first@gmail.com'").fetchone()
   api.enqueue(r['user_id'],'daily','mock-old-recipient','Server controlled reminder')
   users[0].post('/api/reminders',json={'email':'new@yahoo.com','consent':True,'prefs':{}},headers=self.headers)
   api.process_outbox('mock-old-recipient')
   with api.db() as c:self.assertEqual(c.execute("SELECT status FROM outbox WHERE key='mock-old-recipient'").fetchone()[0],'cancelled')
   with api.db() as c:c.execute('DELETE FROM rate_events')
   self.assertEqual(users[0].post('/api/reminders/test',json={},headers=self.headers).status_code,400)
   self.assertEqual(users[1].get('/api/reminders/unsubscribe/'+users[1].get('/api/reminders').json['settings'].get('unsubscribe_token','missing')).status_code,400)
   with api.db() as c:r=c.execute("SELECT * FROM reminders WHERE email='second@outlook.com'").fetchone()
   self.assertEqual(users[1].get('/api/reminders/unsubscribe/'+r['unsubscribe_token']).status_code,200)
   with api.db() as c:c.execute('DELETE FROM rate_events')
   self.assertEqual(users[1].post('/api/reminders/test',json={},headers=self.headers).status_code,400)
 def test_11_uncertain_submission_never_retries(self):
  from unittest.mock import patch
  with api.db() as c:r=c.execute("SELECT * FROM reminders WHERE email='second@outlook.com'").fetchone();c.execute('UPDATE reminders SET consent=1 WHERE user_id=?',(r['user_id'],))
  api.enqueue(r['user_id'],'test','mock-uncertain','Server test')
  with patch('backend_api.send_email',side_effect=api.email_providers.SendingUncertain('Mock lost response')) as sender:
   api.process_outbox('mock-uncertain');api.process_outbox('mock-uncertain');self.assertEqual(sender.call_count,1)
  with api.db() as c:self.assertEqual(c.execute("SELECT status FROM outbox WHERE key='mock-uncertain'").fetchone()[0],'review_required')

 def test_12_validation_expiry_and_transport_errors(self):
  from unittest.mock import patch,MagicMock
  import smtplib
  for address in ['a@example.com\r\nBcc: victim@example.com','a..b@gmail.com','a@example.com,other@example.com','x@y']:
   self.assertFalse(api.email_valid(address))
  for address in ['user@gmail.com','user@outlook.com','user@yahoo.com','student+project@college.ac.in']:self.assertTrue(api.email_valid(address))
  anonymous=api.app.test_client();self.assertEqual(anonymous.get('/api/appointments').status_code,401)
  self.assertIsNone(self.client.get('/api/clinic-booking/nonexistent-place').json['booking_url'])
  with api.db() as c:
   r=c.execute("SELECT * FROM reminders WHERE email='second@outlook.com'").fetchone();c.execute('UPDATE reminders SET verified=0,verify_token=?,updated=? WHERE user_id=?',('expired-test-token',(datetime.now(__import__('datetime').timezone.utc)-timedelta(days=2)).isoformat(),r['user_id']))
  self.assertEqual(self.client.get('/api/reminders/confirm/expired-test-token').status_code,400)
  with patch.dict(os.environ,{'EMAIL_PROVIDER':'gmail','GMAIL_USERNAME':'sender@example.test','GMAIL_APP_PASSWORD':'mock-secret'}):
   smtp=MagicMock();smtp.__enter__.return_value=smtp;smtp.login.side_effect=smtplib.SMTPAuthenticationError(535,b'mock rejected')
   with patch('email_providers.smtplib.SMTP',return_value=smtp),self.assertRaisesRegex(RuntimeError,'authentication failed'):api.email_providers.send('dynamic@yahoo.com','Server text','mock-auth','/api/test')
   smtp.login.side_effect=None;smtp.send_message.side_effect=smtplib.SMTPServerDisconnected('mock lost response')
   with patch('email_providers.smtplib.SMTP',return_value=smtp),self.assertRaises(api.email_providers.SendingUncertain):api.email_providers.send('dynamic@yahoo.com','Server text','mock-uncertain-transport','/api/test')

 def test_13_direct_send_current_form_and_idempotency(self):
  from unittest.mock import patch
  client=api.app.test_client();self.assertEqual(client.post('/api/auth/signup',json={'name':'Direct send test','email':'direct-account@example.test','password':'test-only-strong-password'},headers=self.headers).status_code,200)
  sent=[]
  def provider(recipient,text,*args):sent.append((recipient,text));return 'gmail:mock-direct-'+str(len(sent))
  payload={'email':'dynamic@outlook.com','consent':True,'prefs':{'daily':True,'hour':23},'request_id':'direct-request-verify-001'}
  with patch.dict(os.environ,{'EMAIL_PROVIDER':'gmail','GMAIL_USERNAME':'sender@example.test','GMAIL_APP_PASSWORD':'mock-only'}),patch('backend_api.send_email',side_effect=provider):
   first=client.post('/api/reminders/test',json=payload,headers=self.headers);self.assertEqual(first.status_code,200);self.assertTrue(first.json['verification_required']);self.assertFalse(first.json['scheduled'])
   with api.db() as c:r=c.execute("SELECT * FROM reminders WHERE email='dynamic@outlook.com'").fetchone();self.assertEqual(c.execute('SELECT COUNT(*) FROM outbox WHERE user_id=?',(r['user_id'],)).fetchone()[0],0)
   self.assertEqual(client.get('/api/reminders/confirm/'+r['verify_token']).status_code,200)
   payload['request_id']='direct-request-test-001';test=client.post('/api/reminders/test',json=payload,headers=self.headers);self.assertEqual(test.status_code,200,test.json);self.assertEqual(test.json['kind'],'test')
   duplicate=client.post('/api/reminders/test',json=payload,headers=self.headers);self.assertTrue(duplicate.json['duplicate']);self.assertEqual(len(sent),2)
   self.assertIn('Daily symptom check-in at 23:00 India time',sent[0][1]);self.assertNotIn('Upcoming-period reminder',sent[0][1])
   payload.update(email='changed@yahoo.com',request_id='direct-request-changed-001');changed=client.post('/api/reminders/test',json=payload,headers=self.headers)
   self.assertEqual(changed.status_code,200,changed.json);self.assertTrue(changed.json['verification_required']);self.assertEqual(sent[-1][0],'changed@yahoo.com')
   with api.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outbox WHERE user_id=?',(r['user_id'],)).fetchone()[0],0)

 def test_14_appointment_database_failure_is_reported(self):
  """A save acknowledgement must never be returned when SQLite rejects it."""
  import sqlite3
  from unittest.mock import patch
  payload={
   'clinic':{'name':'Presentation clinic','specialty':'Gynecology','source':'manual'},
   'day':(datetime.now(api.TZ).date()+timedelta(days=2)).isoformat(),
   'time':'11:30','reason':'Routine consultation','contact_name':'Test User',
   'contact_phone':'+910000000000'
  }
  with patch('backend_api.db',side_effect=sqlite3.OperationalError('forced database failure')):
   response=self.call('/api/appointments',payload)
  self.assertEqual(response.status_code,500)
  self.assertIn('error',response.json)

 def test_15_open_data_clinic_result_is_not_fabricated(self):
  from unittest.mock import patch
  nominatim=[{'lat':'12.9716','lon':'77.5946'}]
  overpass={'elements':[{'type':'node','id':123,'lat':12.9717,'lon':77.5947,'tags':{'name':'Source supplied clinic','amenity':'clinic','addr:street':'Source Street','addr:city':'Bengaluru','phone':'+91 80 1234 5678','website':'https://clinic.example.test'}}]}
  with patch('backend_api.public_json',side_effect=[nominatim,overpass]):
   response=self.call('/api/clinics/search',{'city':'Bengaluru','area':'','specialty':'Gynecologist'})
  self.assertEqual(response.status_code,200,response.json)
  self.assertEqual(response.json['source'],'OpenStreetMap public listings')
  clinic=response.json['clinics'][0]
  self.assertEqual(clinic['name'],'Source supplied clinic')
  self.assertEqual(clinic['phone'],'+91 80 1234 5678')
  self.assertEqual(clinic['website'],'https://clinic.example.test')
  self.assertIn('Source Street',clinic['address'])

 def test_16_clinic_failover_handles_missing_map_tags(self):
  from unittest.mock import patch
  fallback=[
   RuntimeError('overpass timeout'),
   {'address':{'city':'Bengaluru'}},
   [{'osm_type':'node','osm_id':99,'display_name':'Source Hospital, Bengaluru','namedetails':None,'extratags':None}]
  ]
  with patch('backend_api.public_json',side_effect=fallback):
   response=self.call('/api/clinics/search',{'latitude':12.97,'longitude':77.59,'specialty':'Gynecologist'})
  self.assertEqual(response.status_code,200,response.json)
  self.assertEqual(response.json['source'],'OpenStreetMap public listings via Nominatim')
  self.assertEqual(response.json['clinics'][0]['name'],'Source Hospital')

 def test_17_test_reminder_has_html_and_plain_body(self):
  content,plain=api.email_providers.message('reader@example.test','Your SheSync test reminder is ready.\nTake a moment to check in with yourself today.','direct:1:body-check','/api/reminders/unsubscribe/test-token')
  self.assertIn('Your SheSync test reminder',content)
  self.assertIn('Take a moment to check in with yourself today.',content)
  self.assertIn('Manage reminder settings',content)
  self.assertIn('Hi there,',plain)
  self.assertIn('Manage reminder settings:',plain)

 def test_18_password_reset_replaces_password_without_losing_account(self):
  from unittest.mock import patch
  client=api.app.test_client();headers=self.headers
  email='reset-'+str(int(__import__('time').time()*1000000))+'@example.test'
  self.assertEqual(client.post('/api/auth/signup',json={'name':'Reset User','email':email,'password':'old-password-123','stage':'Adult'},headers=headers).status_code,200)
  with patch('backend_api.send_email',return_value='gmail:mock-reset'):
   response=client.post('/api/auth/password-reset/request',json={'email':email},headers=headers)
  self.assertEqual(response.status_code,200,response.json)
  with api.db() as c:token_hash=c.execute('SELECT token_hash FROM password_resets ORDER BY created DESC LIMIT 1').fetchone()[0]
  # The one-time token cannot be recovered from its stored hash; use a direct seeded reset record to test POST semantics.
  token='test-reset-token-'+str(int(__import__('time').time()*1000000));hashed=__import__('hashlib').sha256(token.encode()).hexdigest()
  with api.db() as c:c.execute('INSERT INTO password_resets(token_hash,user_id,created,used) SELECT ?,id,?,0 FROM users WHERE email=?',(hashed,datetime.now(__import__('datetime').timezone.utc).isoformat(),email))
  self.assertEqual(client.post('/api/auth/password-reset/'+token,data={'password':'new-password-456'}).status_code,200)
  self.assertEqual(client.post('/api/auth/login',json={'email':email,'password':'new-password-456'},headers=headers).status_code,200)

if __name__=='__main__':unittest.main(verbosity=2)
