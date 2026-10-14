# Competition-day model selection review

Reviewed 14 October 2026 using the already completed experiment results. No extra training was run to delay application fixes, and no model was selected using final-test scores.

| Experimental model | CV recall | CV F1 | CV ROC-AUC | Previously opened test accuracy | Previously opened test recall |
|---|---|---|---|---|---|
| Logistic Regression | 0.851 | 0.819 | 0.932 | 0.881 | 0.833 |
| Support Vector Machine | 0.752 | 0.793 | 0.936 | 0.844 | 0.667 |
| Random Forest | 0.816 | 0.849 | 0.954 | 0.908 | 0.833 |
| XGBoost | 0.837 | 0.846 | 0.945 | 0.908 | 0.833 |
| LightGBM | 0.844 | 0.856 | 0.947 | 0.872 | 0.750 |
| CatBoost | 0.837 | 0.849 | 0.949 | 0.908 | 0.833 |
| Gradient Boosting | 0.858 | 0.849 | 0.951 | 0.881 | 0.750 |

The prior experiment selected LightGBM by training CV F1 (0.856), with CV recall 0.844 and CV ROC-AUC 0.947. It is the highest-CV-F1 candidate. Gradient Boosting has the highest CV recall (0.858); Random Forest has the highest CV ROC-AUC (0.954). These CV estimates follow hyperparameter tuning and are selection diagnostics, not unbiased nested-CV estimates.

The selected LightGBM scored 87.2% on the previously evaluated 109-person test split, but its recall was 0.750. The user-reported baseline recall is 0.83. Other models measured 90.8% test accuracy, but replacing the selection with one of them after seeing test scores would contaminate model choice. Therefore no experimental pipeline is promoted for competition-day inference. Original RF/XGBoost remain active and fallback behavior is unchanged.

The original report's 83.4% accuracy is from a different split and is not a matched benchmark. The existing experiment holdout has already been inspected; it must not be called an untouched new final test set. Clinical promotion requires a preregistered selection rule (including sensitivity/calibration), nested training validation and an independent untouched cohort. The original notebook fitted median imputation before splitting; the new experiment fitted preprocessing within training folds. Numeric category interpolation by ordinary SMOTE remains a limitation; a future SMOTENC/encoding study should be evaluated independently.

Original cohort: 541 records, no duplicate patient IDs found. No new patient data was invented. The candidate audit identified substantial republication of the same 541-patient cohort; synthetic data was excluded; another 1,000-row source lacked demonstrated clinical collection provenance. Ultrasound-frame and metabolomics datasets are separate modalities, not compatible rows to concatenate. See research/DATASET_REPORT.md and saved source metadata for links, licenses and sample audits. No new compatible independently validated clinical cohort became available in this repair run.
