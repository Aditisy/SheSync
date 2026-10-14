"""Private local fixture access for an explicitly authorized live browser test."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path('repository').resolve()))
import backend_api as a
with a.db() as c:
 uid=c.execute("SELECT id FROM users WHERE email LIKE 'immediate-button-%@example.test' ORDER BY id DESC LIMIT 1").fetchone()[0]
 if '--link' in sys.argv:
  token=c.execute('SELECT verify_token FROM reminders WHERE user_id=?',(uid,)).fetchone()[0]
  print(json.dumps({'url':'http://localhost:5000/api/reminders/confirm/'+token}))
 else:
  queued=c.execute("SELECT COUNT(*) FROM outbox WHERE user_id=? AND kind IN ('test','verify')",(uid,)).fetchone()[0]
  sent=c.execute("SELECT COUNT(*) FROM email_actions WHERE user_id=? AND status='accepted'",(uid,)).fetchone()[0]
  print(json.dumps({'scheduledTestJobs':queued,'directAccepted':sent}))
