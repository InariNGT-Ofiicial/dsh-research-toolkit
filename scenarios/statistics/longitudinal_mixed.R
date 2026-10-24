# Longitudinal analysis of synthetic data. All writes stay inside RB_OUTPUT_DIR.
set.seed(20261024)
input <- Sys.getenv("RB_INPUT_DATA")
output <- Sys.getenv("RB_OUTPUT_DIR")
stopifnot(nzchar(input),nzchar(output))
dir.create(output,recursive=TRUE,showWarnings=FALSE)
raw <- read.csv(input,na.strings=c("","NA"))
vars <- c("score","time","treat_a","treat_b","time_a","time_b","baseline_c","age_c")
stopifnot(all(c("subject","group",vars) %in% names(raw)))
stopifnot(!anyDuplicated(paste(raw$subject,raw$time)))
complete <- raw[complete.cases(raw[,vars]),]
stopifnot(nrow(raw)==576,length(unique(raw$subject))==144,nrow(complete)>450,nrow(complete)<576)
complete$subject <- factor(complete$subject)
complete$group <- factor(complete$group,levels=c("control","active_a","active_b"))
formula <- score ~ time+treat_a+treat_b+time_a+time_b+baseline_c+age_c
fit <- nlme::lme(formula,random=~1|subject,data=complete,method="REML",na.action=na.fail)
tab <- summary(fit)$tTable
write.csv(data.frame(term=rownames(tab),estimate=tab[,1],std_error=tab[,2],df=tab[,3],t=tab[,4],p=tab[,5]),file.path(output,"mixed_coefficients.csv"),row.names=FALSE)
variances <- nlme::VarCorr(fit)
tau2 <- as.numeric(variances[1,"Variance"]); sigma2 <- as.numeric(variances[2,"Variance"])
stopifnot(is.finite(tau2),tau2>0,is.finite(sigma2),sigma2>0)
writeLines(sprintf('{"random_intercept_variance":%.16g,"residual_variance":%.16g,"icc":%.16g,"n_complete":%d,"n_subjects":%d}',tau2,sigma2,tau2/(tau2+sigma2),nrow(complete),length(unique(complete$subject))),file.path(output,"mixed_variances.json"))
# Fit an algebraically equivalent factor model to ask all 12 pairwise questions
# together. by=NULL makes Holm adjustment cover the complete 12-comparison family.
factor_fit <- nlme::lme(score~time*group+baseline_c+age_c,random=~1|subject,data=complete,method="REML",na.action=na.fail)
emm <- emmeans::emmeans(factor_fit,~group|time,at=list(time=0:3))
pairwise <- emmeans::contrast(emm,method="pairwise")
adjusted <- as.data.frame(summary(pairwise,by=NULL,adjust="holm",infer=TRUE))
unadjusted <- as.data.frame(summary(pairwise,by=NULL,adjust="none"))
stopifnot(nrow(adjusted)==12,max(abs(adjusted$p.value-p.adjust(unadjusted$p.value,"holm")))<1e-10)
adjusted$p_raw <- unadjusted$p.value
write.csv(adjusted,file.path(output,"contrasts_holm.csv"),row.names=FALSE)
# Cluster bootstrap resamples subjects with all observed visits, preserving the
# within-subject dependence. This is a sensitivity analysis of the OLS time_b.
ids <- unique(complete$subject)
bootstrap <- function() replicate(200,{
  sampled <- sample(ids,length(ids),replace=TRUE)
  draw <- do.call(rbind,lapply(sampled,function(id) complete[complete$subject==id,]))
  unname(coef(lm(formula,data=draw))["time_b"])
})
first <- bootstrap(); set.seed(20261024); second <- bootstrap()
stopifnot(identical(first,second),all(is.finite(first)))
interval <- quantile(first,c(.025,.975),names=FALSE)
writeLines(sprintf('{"seed":20261024,"replicates":200,"unit":"subject","target":"time_b","mean":%.16g,"ci_lower":%.16g,"ci_upper":%.16g,"repeat_identical":true}',mean(first),interval[1],interval[2]),file.path(output,"bootstrap.json"))
diagnostics <- data.frame(n_rows=nrow(raw),n_complete=nrow(complete),n_excluded=nrow(raw)-nrow(complete),n_subjects=length(ids),min_visits=min(table(complete$subject)),max_visits=max(table(complete$subject)),residual_sd=sd(resid(fit,type="normalized")),max_abs_residual=max(abs(resid(fit,type="normalized"))))
write.csv(diagnostics,file.path(output,"diagnostics.csv"),row.names=FALSE)
capture.output({cat("Synthetic three-arm repeated-measures trial\nComplete-case analysis; no imputation\n");print(summary(fit));print(adjusted);print(diagnostics);sessionInfo()},file=file.path(output,"mixed_report.txt"))
cat("RB_LONGITUDINAL_COMPLETE\n")
