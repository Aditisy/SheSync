"""Persistent India-time reminder worker. Keep this process running."""
import time
from backend_api import schedule_due, process_outbox, db
from datetime import datetime,timezone
if __name__=='__main__':
 # Requests interrupted while sending need operator reconciliation, not blind resending.
 with db() as c:c.execute("UPDATE outbox SET status='review_required',error='Interrupted send: inspect provider logs before retrying.' WHERE status='sending'")
 while True:
  try:
   with db() as c:c.execute("INSERT OR REPLACE INTO worker_status VALUES('reminder_worker',?)",(datetime.now(timezone.utc).isoformat(),))
   schedule_due();process_outbox()
  except Exception:print('Reminder processing failed; retrying on next tick.')
  time.sleep(60)
