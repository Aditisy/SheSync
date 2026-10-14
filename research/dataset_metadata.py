import urllib.request,json
from pathlib import Path
refs=['prasoonkottarathil/polycystic-ovary-syndrome-pcos','lucass0s0/polycystic-ovary-syndrome-pcos','samikshadalvi/pcos-diagnosis-dataset','prasadbobby/pcosdata']
Path('repository/research').mkdir(exist_ok=True)
allmeta=[]
for ref in refs:
 try:
  req=urllib.request.Request('https://www.kaggle.com/api/v1/datasets/view/'+ref,headers={'User-Agent':'SheSync academic audit'})
  data=json.load(urllib.request.urlopen(req,timeout=20));Path('repository/research/'+ref.split('/')[0]+'-metadata.json').write_text(json.dumps(data,indent=2))
  print(ref, json.dumps({k:data.get(k) for k in ['description','licenseName','totalBytes','files']})[:2500])
 except Exception as e:print(ref,type(e).__name__)
