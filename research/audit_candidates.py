from pathlib import Path
import pandas as pd,json
root=Path('repository');base=pd.read_excel(root/'data/PCOS_data_without_infertility.xlsx',sheet_name='Full_new');base.columns=base.columns.str.strip();out=[]
for path in (root/'research/candidate-downloads').rglob('*.csv'):
 d=pd.read_csv(path);d.columns=d.columns.str.strip();shared=[c for c in d.columns if c in base and c not in ['Sl. No','Patient File No.','Unnamed: 44']];matches=None
 if len(shared)>10:
  a=base[shared].apply(pd.to_numeric,errors='coerce').round(8);b=d[shared].apply(pd.to_numeric,errors='coerce').round(8);ah=set(pd.util.hash_pandas_object(a,index=False));matches=int(pd.util.hash_pandas_object(b,index=False).isin(ah).sum())
 row={'file':str(path.relative_to(root)),'rows':len(d),'columns':len(d.columns),'names':d.columns.tolist(),'missing':d.isna().sum()[d.isna().sum()>0].to_dict(),'shared_columns_with_baseline':len(shared),'matching_baseline_rows':matches}
 out.append(row);print(json.dumps(row))
(root/'research/candidate_audit.json').write_text(json.dumps(out,indent=2))
