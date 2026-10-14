"""Reproducible baseline-dataset benchmark; originals remain untouched."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.runtime-deps'))
import json,hashlib,platform,time,warnings
import numpy as np,pandas as pd,joblib,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split,StratifiedKFold,RandomizedSearchCV,cross_validate
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier,GradientBoostingClassifier
from sklearn.metrics import accuracy_score,precision_score,recall_score,f1_score,roc_auc_score,confusion_matrix,roc_curve,brier_score_loss
from imblearn.pipeline import Pipeline
from imblearn.over_sampling import SMOTE
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier
SEED=137;OUT=ROOT/'experiments';OUT.mkdir(exist_ok=True)
path=ROOT/'data/PCOS_data_without_infertility.xlsx';df=pd.read_excel(path,sheet_name='Full_new');features=joblib.load(ROOT/'models/feature_names.pkl')
X=df[features].apply(pd.to_numeric,errors='coerce');y=df['PCOS (Y/N)'].astype(int)
# Remove identical clinical feature rows before splitting; conflicting labels are excluded.
hashes=pd.util.hash_pandas_object(X,index=False);groups=pd.DataFrame({'hash':hashes,'label':y});conflicts=groups.groupby('hash').label.nunique();bad=set(conflicts[conflicts>1].index);keep=~hashes.isin(bad)&~hashes.duplicated();duplicates=int((~keep).sum());X=X[keep];y=y[keep]
train,test=train_test_split(np.arange(len(X)),test_size=.2,stratify=y,random_state=SEED)
Xtr,Xte=X.iloc[train],X.iloc[test];ytr,yte=y.iloc[train],y.iloc[test]
cv=StratifiedKFold(3,shuffle=True,random_state=SEED)
scoring={'accuracy':'accuracy','precision':'precision','recall':'recall','f1':'f1','auc':'roc_auc','brier':'neg_brier_score'}
specs={
'Logistic Regression':(LogisticRegression(max_iter=2000,random_state=SEED),{'model__C':[.1,1,10]}),
'Support Vector Machine':(SVC(probability=True,random_state=SEED),{'model__C':[.5,1,5],'model__gamma':['scale',.01]}),
'Random Forest':(RandomForestClassifier(n_estimators=180,random_state=SEED,n_jobs=2),{'model__max_depth':[4,8,None],'model__min_samples_leaf':[1,3,5]}),
'XGBoost':(XGBClassifier(n_estimators=120,random_state=SEED,n_jobs=2,eval_metric='logloss'),{'model__max_depth':[2,3,5],'model__learning_rate':[.03,.1]}),
'LightGBM':(LGBMClassifier(n_estimators=120,random_state=SEED,n_jobs=2,verbosity=-1),{'model__num_leaves':[7,15,31],'model__learning_rate':[.03,.1]}),
'CatBoost':(CatBoostClassifier(iterations=120,random_seed=SEED,verbose=False,thread_count=2,allow_writing_files=False),{'model__depth':[3,5],'model__learning_rate':[.03,.1]}),
'Gradient Boosting':(GradientBoostingClassifier(n_estimators=120,random_state=SEED),{'model__max_depth':[2,3],'model__learning_rate':[.03,.1]})}
results=[];trained={}
for name,(model,params) in specs.items():
 print('Training',name,flush=True)
 pipe=Pipeline([('imputer',SimpleImputer(strategy='median')),('scale',StandardScaler()),('smote',SMOTE(random_state=SEED)),('model',model)])
 search=RandomizedSearchCV(pipe,params,n_iter=3,scoring='f1',cv=cv,random_state=SEED,n_jobs=1,refit=True)
 with warnings.catch_warnings():warnings.simplefilter('ignore');search.fit(Xtr,ytr)
 # This CV is for model selection, not an unbiased estimate after tuning.
 cvscores=cross_validate(search.best_estimator_,Xtr,ytr,cv=cv,scoring=scoring,n_jobs=1)
 trained[name]=search.best_estimator_
 results.append({'name':name,'cv':{k:{'mean':float(cvscores['test_'+k].mean()),'std':float(cvscores['test_'+k].std())} for k in scoring},'parameters':search.best_params_})
# Select exclusively with training CV F1. The holdout is opened once below.
selected=max(results,key=lambda r:r['cv']['f1']['mean'])['name'];print('Selected using CV only:',selected,flush=True)
for r in results:
 p=trained[r['name']].predict_proba(Xte)[:,1];pred=(p>=.5).astype(int);fpr,tpr,_=roc_curve(yte,p)
 r['test']={'accuracy':float(accuracy_score(yte,pred)),'precision':float(precision_score(yte,pred,zero_division=0)),'recall':float(recall_score(yte,pred,zero_division=0)),'f1':float(f1_score(yte,pred,zero_division=0)),'auc':float(roc_auc_score(yte,p)),'brier':float(brier_score_loss(yte,p))}
 r['confusion_matrix']=confusion_matrix(yte,pred).tolist();r['roc']={'fpr':fpr.tolist(),'tpr':tpr.tolist()}
 # Stratified bootstrap keeps both classes present. Conditional on this small split.
 rng=np.random.default_rng(SEED);ya=yte.to_numpy();pos=np.where(ya==1)[0];neg=np.where(ya==0)[0];boot=[]
 for _ in range(500):
  idx=np.r_[rng.choice(pos,len(pos)),rng.choice(neg,len(neg))];boot.append([accuracy_score(ya[idx],pred[idx]),recall_score(ya[idx],pred[idx]),roc_auc_score(ya[idx],p[idx])])
 r['bootstrap_95_ci']={k:np.quantile(np.array(boot)[:,i],[.025,.975]).tolist() for i,k in enumerate(['accuracy','recall','auc'])}
 joblib.dump(trained[r['name']],OUT/(r['name'].lower().replace(' ','_')+'.joblib'))
# Historical split reproduced only for diagnostics: original models already saw the new holdout.
# Do not evaluate these saved models on this new split as if it were an independent holdout.
result={'status':'completed','seed':SEED,'dataset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'dataset_source':'https://www.kaggle.com/datasets/prasoonkottarathil/polycystic-ovary-syndrome-pcos','original_rows':len(df),'rows_used':len(X),'removed_duplicate_or_conflicting_rows':duplicates,'features':len(features),'missing_cells':int(X.isna().sum().sum()),'class_counts':y.value_counts().to_dict(),'train_rows':len(train),'test_rows':len(test),'selection':selected,'promotion':'not promoted; original baseline remains the inference model','baseline_reported':{'accuracy':.834,'precision':.84,'recall':.83,'f1':.727,'auc':.91},'limitations':['Original metrics use a different split; improvements are not a like-for-like reproduction.','Holdout contains only about 109 people from one historical dataset; no external validation.','CV means/std are tuning diagnostics, not nested CV estimates.','SMOTE samples are synthetic training-only points; no patient records were fabricated.','Raw dataset cycle-length column meaning must be confirmed before clinical deployment.','Probabilities are uncalibrated. Brier score is reported; no individual clinical risk guarantee.'],'versions':{'python':platform.python_version(),'sklearn':__import__('sklearn').__version__,'xgboost':__import__('xgboost').__version__},'results':results}
(OUT/'results.json').write_text(json.dumps(result,indent=2));(OUT/'split_manifest.json').write_text(json.dumps({'train_original_rows':Xtr.index.tolist(),'test_original_rows':Xte.index.tolist()}))
fig,axs=plt.subplots(1,2,figsize=(14,5));names=[r['name'] for r in results];axs[0].barh(names,[r['test']['accuracy'] for r in results],color='#a45499');axs[0].set_xlim(0,1);axs[0].set_title('New experiment · held-out accuracy');axs[0].set_xlabel('Accuracy');
for r in results:axs[1].plot(r['roc']['fpr'],r['roc']['tpr'],label=r['name'])
axs[1].plot([0,1],[0,1],'--',color='gray');axs[1].set_title('Held-out ROC curves');axs[1].set_xlabel('False positive rate');axs[1].set_ylabel('True positive rate');axs[1].legend(fontsize=8);fig.tight_layout();fig.savefig(OUT/'comparison.png',dpi=160);plt.close(fig)
# SHAP tree-only explanation of selected model after training-fold preprocessing.
try:
 import shap
 pipe=trained[selected];transformed=pipe.named_steps['scale'].transform(pipe.named_steps['imputer'].transform(Xte));ex=shap.TreeExplainer(pipe.named_steps['model']);sv=ex.shap_values(transformed)
 if isinstance(sv,list):sv=sv[1]
 arr=np.asarray(sv)
 if arr.ndim==3:arr=arr[:,:,1]
 imp=np.abs(arr).mean(axis=0);ranking=sorted(zip(features,imp),key=lambda t:t[1],reverse=True)[:12];result['shap_importance']=[{'feature':f.strip(),'mean_absolute_shap':float(v)} for f,v in ranking];result['shap_status']='Measured on held-out records for selected experimental model'
except Exception as e:result['shap_status']='Unavailable for selected model: '+type(e).__name__
(OUT/'results.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'selected':selected,'metrics':next(r['test'] for r in results if r['name']==selected),'rows':len(X)},indent=2),flush=True)
