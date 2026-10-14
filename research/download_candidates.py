from pathlib import Path
import urllib.request,zipfile,io,json
folder=Path('repository/research');refs=['samikshadalvi/pcos-diagnosis-dataset','prasadbobby/pcosdata']
for ref in refs:
 try:
  url='https://www.kaggle.com/api/v1/datasets/download/'+ref
  data=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'SheSync academic audit'}),timeout=30).read()
  dest=folder/'candidate-downloads'/ref.split('/')[0];dest.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   for item in z.infolist():
    if item.filename.lower().endswith(('.csv','.xlsx')):
     target=dest/Path(item.filename).name;target.write_bytes(z.read(item));print(ref,target.name,len(z.read(item)))
 except Exception as e:print(ref,type(e).__name__)
