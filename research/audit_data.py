from pathlib import Path
import json,hashlib
import pandas as pd
root=Path('repository');df=pd.read_excel(root/'data/PCOS_data_without_infertility.xlsx',sheet_name='Full_new');clinical=df.drop(columns=['Sl. No','Patient File No.','Unnamed: 44']);audit={'local_source_sha256':hashlib.sha256((root/'data/PCOS_data_without_infertility.xlsx').read_bytes()).hexdigest(),'rows':len(df),'columns':len(df.columns),'predictors':41,'labels':df['PCOS (Y/N)'].value_counts().to_dict(),'missing':df.isna().sum()[df.isna().sum()>0].to_dict(),'coerced_missing':df.drop(columns=['Unnamed: 44']).apply(pd.to_numeric,errors='coerce').isna().sum().to_dict(),'duplicate_clinical_rows':int(clinical.duplicated().sum()),'duplicate_patient_ids':int(df['Patient File No.'].duplicated().sum()),'local_second_file_rows':len(pd.read_csv(root/'data/PCOS_infertility.csv')),'outlier_review':{}}
for col in [' Age (yrs)','Weight (Kg)','Height(Cm) ','BMI','AMH(ng/mL)']:
 x=pd.to_numeric(df[col],errors='coerce');q1,q3=x.quantile([.25,.75]);iqr=q3-q1;audit['outlier_review'][col]={'min':float(x.min()),'max':float(x.max()),'outside_1_5_iqr':int(((x<q1-1.5*iqr)|(x>q3+1.5*iqr)).sum())}
(root/'research/local_dataset_audit.json').write_text(json.dumps(audit,indent=2))
print(json.dumps({k:audit[k] for k in ['rows','labels','missing','duplicate_clinical_rows','duplicate_patient_ids','local_second_file_rows']}))
