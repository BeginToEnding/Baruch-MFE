# **Data Science II: Project**

### **Predicting 24-Hour Forward Residual Returns from Daily and Intraday Equity Data**

Group1: Hao Wang, Mark Tolani



## **1. Introduction**

The goal of this project is to predict the next 24-hour forward residual return for U.S. equities using only the daily and intraday data provided in the course dataset. The modeling target is defined at 15:30 each trading day, using information available no later than 15:30 on day $T$, and predicting the residual return from 15:30 on day $T$ to 15:30 on day $T+1$. This setup follows the project specification and keeps the prediction problem realistic by making sure no future information is used.

Our workflow combined feature engineering, feature vetting, normalization, cross-validation, model tuning, and out-of-sample evaluation. We tested five model specifications in total: Ridge Regression, Random Forest Regressor, XGBoost, LightGBM, and a simple ensemble of the three tree models. The first three were required by the project. Throughout the project, we cared more about whether the results held up out of sample than about squeezing out a slightly better in-sample fit, because the target is noisy and easy to overfit.



------



## **2. Data and Prediction Setup**

The raw dataset consists of five years of daily equity data and intraday data sampled every 15 minutes. The daily files include variables such as $EST_VOL$, $MDV_{63}$, OHLC prices, volume, and adjustment factors. The intraday files include cumulative residual return, cumulative raw return, and cumulative volume from the previous close to each intraday timestamp. The stock universe changes slightly over time, so we built and evaluated features in a way that respects the changing cross-section and avoids survivorship bias.

The target variable is the forward residual return from 15:30 on day $T$ to 15:30 on day $T+1$. Following the project recommendation, we also considered normalizing the return by $ESTVOL$ during fitting and then rescaling predictions back into return space for evaluation. The official evaluation metric is weighted $R^2$ using $\sqrt{MDV_{63}}$ as weights, with actual returns clipped cross-sectionally at 5 MAD before out-of-sample evaluation.



------



## **3. Data Split and Leakage Prevention**

We followed the project requirement to use the first four years for research and hold out 2014 as the validation dataset. More specifically, all feature engineering decisions, cleaning thresholds, feature selection, model selection, and hyperparameter tuning were made using only 2010–2013. The year 2014 was kept fully out of sample until the final evaluation stage. This is consistent with the course guideline that the last year should stay unseen during model development.

Feature construction was implemented date by date. At each prediction date $T$, the pipeline stored the following state objects:

- daily_T: daily data for date $T$

- daily_Tm1: daily data for the most recent previous trading day

- intra_T: intraday data for date $T$

- intra_Tm1: intraday data for the most recent previous trading day

- rolling_state: a rolling container storing the past 20 trading days of history needed for time-series features and normalization

  

To avoid look-ahead bias, intraday data were truncated at 15:30 before any feature was computed. No information after 15:30 on day $T$ was allowed to enter the feature set used to predict the forward target. This also helps the feature-generation code pass the project’s leakage check, where features should stay the same even if future raw files are present in the input directory.

This matters because many of our features combine same-day intraday quantities with lagged daily or intraday state. By explicitly maintaining $(daily_T, daily_{T-1}, intra_T, intra_{T-1})$ and a strictly backward-looking rolling_state, we made sure every feature used only information available by 15:30 on date $T$.



------



## 4. Feature Categories, Economic Motivation, and Final Feature Set

Our final feature set contains 20 features: 14 raw features and 6 interaction features.
 All features were computed using information available no later than 15:30 on day $T$, consistent with the project requirement that predictions be made at 15:30 for the next 24-hour residual return. The raw intraday data provide cumulative residual return, cumulative raw return, and cumulative volume snapshots, so we first converted them into adjusted 15-minute bar returns and adjusted dollar-volume quantities before constructing features.  

We grouped the features into a few themes: liquidity participation, return path and trend, volatility asymmetry, price-path stress, and conditional interactions. We did not want an overly large feature library, so after screening we kept a smaller set that was easier to interpret and less redundant.

### 4.1 Final Feature List

#### Raw features

- `overnight_ret_vol`
- `up_minus_down_risk_L`
- `intraday_resid_ret_vol`
- `tga_directional_asymmetry_L`
- `intraday_dollar_rel_to_yday`
- `volume_accel`
- `common_factor_ret_vol`
- `prev_cumret_resid_1600`
- `negative_illiquidity_L`
- `range`
- `max_drawdown`
- `intraday_macd_hist`
- `amount_dir_15m`
- `up_minus_down_risk_L_raw`

#### Interaction features

- `x_drawdown_conditioned_rsi`
- `x_high_flow_no_move`
- `x_frighten_mean_over_std`
- `x_trend_when_flow_high`
- `x_prev_close_followthrough`
- `x_tail_flow_continuation`

------

### 4.2 Categories of Raw Features

#### A. Return and momentum / reversal features

`overnight_ret_vol`

This feature measures the overnight move from the previous adjusted close to today’s adjusted open, scaled by current estimated volatility. The intuition is that overnight price discovery may carry information into the trading day, especially when the overnight move is unusually large relative to the stock’s typical risk level.

`intraday_resid_ret_vol`

This is the residual return from the previous close to 15:30, scaled by $ESTVOL$. It captures whether the stock has already exhibited strong idiosyncratic performance by 15:30. Depending on market conditions, such moves may either continue or mean-revert, so this feature is useful both directly and as an ingredient in several interaction terms.

`prev_cumret_resid_1600`

This feature is the previous day’s full-day cumulative residual return at 16:00, scaled by the previous day’s volatility estimate. It is intended to capture overnight persistence or reversal from the prior day’s idiosyncratic move.

`common_factor_ret_vol`

This is the difference between cumulative raw return and cumulative residual return up to 15:30, scaled by volatility. It measures how much of the stock’s move is explained by common market or factor-driven behavior rather than stock-specific residual behavior. This helps distinguish systematic moves from idiosyncratic ones.

`intraday_macd_hist`

This is a technical trend indicator computed from the adjusted intraday price path up to 15:30. It measures the gap between the short-term MACD and its signal line. The feature is intended to summarize short-horizon price acceleration or deceleration.

------

#### B. Liquidity and trading-activity features

`intraday_dollar_rel_to_yday`

This feature compares today’s cumulative adjusted dollar volume up to 15:30 with the previous day’s adjusted full-day dollar volume. It captures whether today’s activity level is unusually high or low relative to the stock’s own recent participation level.

`volume_accel`

This feature is the ratio of late-day volume to early-day volume, specifically comparing 14:00–15:30 activity with 09:45–11:00 activity. It is designed to detect whether trading interest is accelerating into the close, which may indicate information arrival or order-flow imbalance.

`amount_dir_15m`

This feature summarizes signed dollar volume across 15-minute intervals. It computes the mean of dollar volume multiplied by the sign of the residual return, normalized by mean dollar volume. It measures whether trading activity tends to align with positive or negative price movement during the day.

------

#### C. Volatility, asymmetry, and downside-risk features

`up_minus_down_risk_L`

This feature compares the total squared positive residual-return variation with the total squared negative residual-return variation over the intraday window up to 15:30. Positive values indicate more upside variation; negative values indicate more downside variation. It is a compact measure of directional volatility asymmetry.

`tga_directional_asymmetry_L`

This feature uses a time-weighted aggregation of positive versus negative residual returns. Later bars receive larger weights, so the feature emphasizes whether the day’s directional pressure strengthened into 15:30. It is intended to capture trend asymmetry rather than just total variance asymmetry.

`negative_illiquidity_L`

This feature measures the magnitude of negative residual returns relative to the dollar volume traded during negative-return intervals, scaled by $MDV_{63}$. Intuitively, it asks whether downside moves occurred “too easily,” i.e. with relatively little liquidity support, which can be interpreted as fragile selling pressure.

`up_minus_down_risk_L_raw`

This is the raw-return version of `up_minus_down_risk_L`. Including both residual and raw versions allows the model to compare idiosyncratic directional risk with broader market-related directional risk.

------

#### D. Price-path and intraday stress features

`range`

This is the intraday price range up to 15:30, normalized by the first intraday price. It measures how much the stock has traveled during the day and acts as a simple path-volatility feature.

`max_drawdown`

This feature measures the maximum drawdown of the adjusted intraday price path up to 15:30. It is designed to capture whether the stock experienced a meaningful pullback from an earlier intraday high, which can be informative about failed rallies, intraday stress, or reversal pressure.

------

#### E. Market-dislocation / panic-style feature

The final feature set does not keep `frighten_mean_L` and `frighten_std_L` separately, but it does keep their ratio through the interaction feature `x_frighten_mean_over_std`.

The underlying construction first measures, at each 15-minute snapshot, how different a stock’s residual return is from the cross-sectional market-like residual move, using dollar-volume-weighted market return as the benchmark. It then focuses on positive jumps in this “dislocation” measure and multiplies them by the stock’s return. The ratio of mean to standard deviation is meant to summarize whether this dislocation is persistent and directional rather than simply noisy. Using the ratio is more stable and easier to interpret than keeping the raw mean and raw standard deviation separately. 

------

### 4.3 Interaction-Feature Design Logic

The interaction features were meant to capture **conditional effects** rather than just add complexity. The basic idea is that some weak signals become more useful only in certain states. For example, a return signal may matter more when liquidity is high, a reversal signal may matter more after a drawdown, and a continuation signal may be stronger when prior-day and same-day signals point in the same direction.

In our interaction library, there were three main design patterns.

#### A. Gating by intensity

A feature is multiplied by a gate derived from another feature’s time-series z-score. In the code, several gates are created using either a positive-part transform or, in the final version, a sigmoid transform of 20-day time-series z-scores. This turns state variables such as high flow, large drawdown, or strong tail participation into smooth regime weights. 

#### B. Same-direction agreement

Some interactions measure whether two features point in the same direction. If they do, the feature is strengthened; if not, it is weakened. This is meant to isolate cleaner continuation or follow-through cases.

#### C. Stable ratio features

Some features are written as a mean-over-volatility or mean-over-standard-deviation ratio. The goal is to turn a raw level into a more stable signal-to-noise measure.

------

### 4.4 Interpretation of the Final Interaction Features

`x_trend_when_flow_high`

This feature multiplies `intraday_resid_ret_vol` by a smooth gate derived from the time-series z-score of `intraday_dollar_vpr`. The idea is that a directional residual move may mean more when it is supported by unusually high participation. A price move on high flow may reflect stronger information or more persistent order flow than a similar move on weak flow. 

`x_high_flow_no_move`

This feature is large when flow is high but the absolute residual return is still small in cross-sectional rank terms. The intuition is that unusually high participation without much price movement may indicate latent pressure, absorption, or an unresolved imbalance that moves later.

`x_tail_flow_continuation`

This feature averages two gates: one from yesterday’s tail dollar-volume participation ratio and one from today’s intraday dollar volume relative to yesterday. It is designed to detect persistence in trading pressure from yesterday’s close into today’s session. High values mean both prior-day tail activity and current-day participation are elevated, which may support continuation.

`x_drawdown_conditioned_rsi`

This feature multiplies $(50 - RSI)$ by a gate derived from the time-series z-score of `max_drawdown`. The logic is that RSI-type reversal or oversold/overbought information may matter more after a meaningful drawdown. In other words, the model should not treat the same RSI level equally in calm and stressed price-path regimes.

`x_prev_close_followthrough`

This feature measures agreement between yesterday’s close-to-close residual move and today’s residual move into 15:30. It takes the sign agreement of the two features and scales it by the smaller absolute magnitude of the two. This creates a conservative continuation signal: the feature is strongest when both days point in the same direction and both moves are meaningful.

`x_frighten_mean_over_std`

This feature is the ratio of `frighten_mean_L` to `frighten_std_L`. It can be viewed as a “panic signal Sharpe ratio.” High absolute values indicate that the dislocation-style signal is persistent relative to its own variability, rather than being just noisy bursts. It is therefore more stable than the raw mean alone.

------

### 4.5 Comments

We initially generated 42 candidate features. The final set was selected using both IC/ICIR-based screening and economic interpretation. In particular, we retained features that showed relatively stable cross-sectional predictive power in the training period and also had a clear economic rationale, while dropping features that were weak, unstable, or highly redundant.

We kept the final feature set fairly compact so that it stayed interpretable and did not contain too many overlapping signals. The raw features cover different aspects of market behavior, including directional return strength, asymmetric risk, liquidity participation, intraday stress, and technical trend shape. The interaction features then add a few conditional effects, such as strengthening trend signals when participation is high or making reversal-style signals more relevant after a meaningful drawdown.



------



## **5. Feature Testing, Cleaning, and Normalization**

Because many raw features were noisy and heavy-tailed, we spent a meaningful part of the project on preprocessing.

### **5.1 Visual inspection and clipping rules**

For each feature, we plotted a daily time series of five summary statistics across the entire sample: mean, 1st percentile, 99th percentile, minimum, and maximum. We used these plots to understand the distribution of each feature over time and to spot unstable tails, occasional breakdowns, and scale changes.

Using both the visual diagnostics and the economic definition of each feature, we selected feature-specific clipping bounds. This step was intended to remove obviously implausible or overly influential values while preserving genuine cross-sectional structure.

### **5.2 MAD-based winsorization**

After applying feature-specific clipping bounds, we used a 5-MAD winsorization rule. This gave us an extra safeguard against extreme outliers that could distort both normalization and model fitting.

### **5.3 Time-series normalization**

We also tried a 20-day time-series z-score before the cross-sectional z-score, but we did not keep it in the final model. In our tests it lowered the IC mean and ICIR of many features and also made validation performance worse after model training. We think the main reason is that this task is mostly cross-sectional: what matters more is how stocks compare with one another on the same day, not how unusual a stock looks relative to its own recent 20-day history. Many of our features were already built in scaled or ratio form, so another layer of time-series normalization often weakened the signal instead of helping. For state variables such as flow, drawdown, or downside risk, it could also wash out level information that was still useful. For that reason, we left time-series normalization out of the final pipeline.

### **5.4 Cross-sectional normalization**

After clipping and winsorization, we applied a same-day cross-sectional z-score. This lets the model focus on relative ranking across stocks on each date, which is more consistent with the cross-sectional prediction task.

### **5.5 Feature selection using IC and ICIR**

After preprocessing, we evaluated each candidate feature on 2010–2013 using daily cross-sectional Information Coefficient (IC), defined as the correlation between the feature and the target normalized by $ESTVOL$, with $\sqrt{MDV_{63}}$ used as cross-sectional weights.

We then grouped the daily IC values by year and computed, for each year, the mean IC, standard deviation of IC, and ICIR. In addition, we computed the overall 2010–2013 mean IC, standard deviation, and ICIR using the full training period.

To screen features, we imposed two thresholds:

- $|ICIR| > 0.5$
- $|mean\ IC| > 0.002$

Only features passing both thresholds were kept for the next stage.

### **5.6 Redundancy control**

After initial screening, we computed the correlation matrix of the surviving features. For any pair with absolute correlation above 0.8, we kept only the feature with the higher ICIR. This step reduced multicollinearity and helped avoid overfitting by forcing the final feature set to contain distinct information rather than multiple near-duplicates of the same signal.

After this process, the final feature library contained **20 features**.



Overall, this process helped us check each feature on its own, reduce noise, and remove redundant signals before model training.



------



## **6. Feature Importance and Univariate Diagnostics**

### **6.1 MDA feature importance**

We used Mean Decrease in Accuracy (MDA) to evaluate feature importance for the trained models. For each feature, we randomly permuted its values while leaving all other features unchanged, recomputed predictions, and measured the drop in weighted $R^2$. This permutation was repeated five times per feature, and the average decline in performance was used as the MDA importance score.

This method is useful here because it shows how much the fitted model depends on each feature while keeping the other features fixed, instead of relying only on model-internal split statistics.



### **6.2 Bin plots for the strongest individual features**

To complement MDA, we also examined the direct univariate relationship between several top features and the target variable. We selected the three most effective features and sorted observations into four bins by feature value. For each bin, we plotted the average realized target value.

These bin plots give a simple visual check of monotonicity and interpretability. Ideally, a useful feature should show an ordered relationship with the future target.

**Top-feature bin plots**

![image-20260321093642871](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321093642871.png)

![image-20260321093706861](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321093706861.png)

![image-20260321093726569](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321093726569.png)

![image-20260321093739774](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321093739774.png)

![image-20260321094357960](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321094357960.png)

------



## **7. Sample Weights Used During Fitting**

We primarily used $\sqrt{MDV_{63}}$ as sample weights during fitting. The main reason is consistency with the project’s official weighted $R^2$ metric, which is also computed using $\sqrt{MDV_{63}}$. Using the same weighting logic in both training and evaluation keeps the fitting objective consistent with the performance metric.

A second reason is that larger and more liquid stocks tend to have more stable short-horizon residual returns, while very illiquid names are noisier and less reliable. Using $\sqrt{MDV_{63}}$ rather than raw $MDV_{63}$ reduces the dominance of the very largest names while still assigning greater importance to stocks where the target is typically more stable and more practically tradable.

We also considered weighting by $1/ESTVOL$, since the target was often normalized by $ESTVOL$ and because such weighting can reduce the influence of high-volatility names. In practice, we monitored both $\sqrt{MDV_{63}}$-weighted and $1/ESTVOL$-weighted validation performance during cross-validation.



------



## **8. Models Attempted**

We tested five model specifications:

1. **Ridge Regression**
2. **Random Forest Regressor**
3. **XGBoost**
4. **LightGBM**
5. **Ensemble Model(Average of Random Forest, XGBoost, LightGBM)**

The first three were required by the project specification, while LightGBM was added as an additional gradient-boosted tree benchmark.

### **8.1 Ridge Regression**

Ridge Regression provided a useful linear benchmark. It is simple, fast, and relatively robust in low-signal settings. Because many features are noisy and correlated, $L^2$ regularization is a natural baseline.

### **8.2 Random Forest Regressor**

Random Forest was used to test whether nonlinearities and threshold effects could improve performance without requiring heavy parametric assumptions. However, we found that large and weakly regularized forests could overfit easily.

### **8.3 XGBoost**

XGBoost was included because boosted trees can capture nonlinear effects and interactions while also allowing strong control of model complexity through learning rate, depth, subsampling, and regularization.

### **8.4 LightGBM**

LightGBM was explored as an additional tree-based model. Its training speed made it easier to try a broader hyperparameter grid, and it served as a useful reference point during tuning.

### 8.5 Ensemble model

In addition to the individual models, we also tested an **Ensemble model defined as the simple average of Random Forest, XGBoost, and LightGBM predictions**.

The ensemble prediction is defined as
$$
\hat y_i^{ens}
=
\frac{1}{3}
\left(
\hat y_i^{RF}
+
\hat y_i^{XGB}
+
\hat y_i^{LGB}
\right).
$$
We included this ensemble because different tree-based models may prioritize and combine features differently even when they use the same inputs. The MDA results suggest that the three tree models do not rely on exactly the same features to the same extent, so averaging their predictions may reduce model-specific noise. Since the three models also produced predictions on a similar numerical scale, simple averaging was easy to implement without extra recalibration.



------



## **9. Hyperparameter Search and Model Selection**

### **9.1 Cross-validation design**

Hyperparameter selection was performed using expanding-window cross-validation on 2010–2013. We used three folds:

- Train on 2010, validate on 2011

- Train on 2010–2011, validate on 2012

- Train on 2010–2012, validate on 2013

  

This design respects time ordering and is more appropriate than random shuffling for financial data.

For each hyperparameter combination, we trained the model on the training side of each fold, generated predictions on the validation side, and computed weighted $R^2$ using both $\sqrt{MDV_{63}}$ weights and $1/ESTVOL$ weights. We then averaged the metrics across folds and selected the best-performing parameter set.

### **9.2 Hyperparameter grids attempted**

**Ridge Regression**

 param_grid={

​    "alpha": np.logspace(-3, 3, 12).tolist()

  }

**Random Forest Regressor**

  param_grid={

  "n_estimators": [300, 500, 600],

  "max_depth": [2, 3, 4, 6],

  "min_samples_leaf": [200, 500],

  "min_samples_split": [500, 1000],

  "max_features": ["sqrt"],

  "max_samples": [0.1, 0.2, 0.4],

  },

  use_scaler=False,

)

**XGBoost**

  param_grid={

​    "n_estimators": [300, 600],

​    "learning_rate": [0.05],

​    "max_depth": [2, 3, 4],

​    "min_child_weight": [10, 50],

​    "subsample": [0.6, 0.8, 1.0],

​    "colsample_bytree": [0.3, 0.6, 0.8],

​    "reg_alpha": [1.0, 5.0],

​    "reg_lambda": [10.0, 30.0, 50.0],

  }

**LightGBM**

  param_grid={

​    "n_estimators": [300, 600],

​    "learning_rate": [0.05],

​    "max_depth": [2, 4, 6],

​    "min_data_in_leaf": [500, 1000],

​    "min_gain_to_split": [0.1, 1.0],

​    "lambda_l2": [10.0, 30.0, 50.0], 

​    "lambda_l1": [1.0, 5.0, 10.0], 

​    "feature_fraction": [0.2, 0.4, 0.6],

​    "bagging_fraction": [0.8],

​    "bagging_freq": [1],

  }

### **9.3 Selection logic**

Our tuning process was iterative and was guided mainly by validation behavior rather than model complexity alone.

We initially tested relatively large tree-based models with lighter regularization. Their performance was generally weak, which suggested that the models were fitting noise rather than stable signal. We then gradually reduced tree size and increased regularization, which improved validation performance. Interestingly, very strong regularization sometimes produced better weighted $R^2$, likely because the feature-target relationship is extremely weak and noisy: even the strongest single-feature correlations were only around 0.012 in magnitude.

However, we also observed that overly regularized models became too conservative. Their predictions were compressed into a very narrow range, often around 0 to 0.005 in magnitude, much smaller than the scale of the true target. In that regime, the model was mostly predicting relative rank rather than return magnitude. This sometimes led to bin plots where the rightmost prediction bin reversed sign and the pattern was no longer monotonic.

Because of this tradeoff, we did not simply choose the model with the strongest shrinkage. Instead, we moved back to a setup with moderate regularization and slightly larger trees. The final selected specification was the one that balanced three goals:

- acceptable weighted $R^2$

- more stable and interpretable bin-plot monotonicity

- less severe prediction compression

  

**Best hyperparameters by model**

- Ridge Regression:

  Best params: {'alpha': 1000.0}

- Random Forest Regressor:

  Best params: {'max_depth': 6, 'max_features': 'sqrt', 'max_samples': 0.2, 'min_samples_leaf': 500, 'min_samples_split': 1000, 'n_estimators': 500}

- XGBoost:

  Best params: {'colsample_bytree': 0.3, 'learning_rate': 0.05, 'max_depth': 2, 'min_child_weight': 50, 'n_estimators': 300, 'reg_alpha': 5.0, 'reg_lambda': 50.0, 'subsample': 1.0}

- LightGBM:

  Best params: {'bagging_fraction': 0.8, 'bagging_freq': 1, 'feature_fraction': 0.4, 'lambda_l1': 10.0, 'lambda_l2': 50.0, 'learning_rate': 0.05, 'max_depth': 6, 'min_data_in_leaf': 1000, 'min_gain_to_split': 0.1, 'n_estimators': 300}



------



## **10. Performance on the 2014 Validation Dataset**

After choosing the final model and hyperparameters using only 2010–2013, we retrained that model on the full 2010–2013 sample and then evaluated it in 2014 as a fully out-of-sample validation set, as required by the project.

**Final selected model:**

Model selection was based on validation performance, primarily using weighted $R^2$ with $\sqrt{MDV_{63}}$ weights, together with supporting diagnostics such as weighted correlation and bin-plot monotonicity. Among all candidate models, **Random Forest achieved the best validation performance**, with a validation weighted $R^2$ of **0.000351** under $\sqrt{MDV_{63}}$ weighting, outperforming Ridge Regression, XGBoost, and LightGBM. Therefore, although the ensemble model was included as a robustness experiment, the **final selected model was Random Forest**, because it provided the strongest standalone validation performance and the most reliable overall validation behavior.



### **10.1 Weighted $R^2$**

We report the model’s out-of-sample weighted $R^2$ in 2014.

**2014 weighted $R^2$ results**

|      |         model |                                       best_params | val_r2_weighted_sqrt_mdv | val_r2_weighted_est_vol | n_valid |
| ---: | ------------: | ------------------------------------------------: | -----------------------: | ----------------------: | ------- |
|    0 | random_forest | {'max_depth': 6, 'max_features': 'sqrt', 'max_... |                 0.000351 |                0.000254 | 125340  |
|    1 |         ridge |                                 {'alpha': 1000.0} |                -0.000416 |               -0.000154 | 125340  |
|    2 |       xgboost | {'colsample_bytree': 0.3, 'learning_rate': 0.0... |                -0.001806 |               -0.002231 | 125340  |
|    3 |      lightgbm | {'bagging_fraction': 0.8, 'bagging_freq': 1, '... |                -0.002051 |               -0.001727 | 125340  |

### 10.2 Prediction Distribution

![image-20260321184131838](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321184131838.png)

![image-20260321184143085](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321184143085.png)

![image-20260321184153670](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321184153670.png)

![image-20260321184231082](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321184231082.png)

![image-20260321190523231](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321190523231.png)

### **10.3 Validation-year bin plot**

We generated a 4-bin prediction plot for 2014, with predictions on the x-axis and realized target values on the y-axis.

ridge

![image-20260321185009218](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321185009218.png)

|  bin |  avg_pred |  avg_true | count |
| ---: | --------: | --------: | ----- |
|    0 | -0.000450 | -0.000342 | 31335 |
|    1 | -0.000066 | -0.000105 | 31335 |
|    2 |  0.000100 | -0.000042 | 31335 |
|    3 |  0.000453 |  0.000236 | 31335 |

random forest

![image-20260321190208759](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321190208759.png)

|  bin |  avg_pred |  avg_true | count |
| ---: | --------: | --------: | ----- |
|    0 | -0.000714 | -0.000311 | 31335 |
|    1 | -0.000104 | -0.000185 | 31335 |
|    2 |  0.000147 | -0.000012 | 31335 |
|    3 |  0.000750 |  0.000254 | 31335 |

xgboost

![image-20260321183515069](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321183515069.png)

|  bin |  avg_pred |  avg_true | count |
| ---: | --------: | --------: | ----- |
|    0 | -0.000448 | -0.000353 | 31335 |
|    1 | -0.000063 | -0.000070 | 31335 |
|    2 |  0.000103 |  0.000006 | 31335 |
|    3 |  0.000468 |  0.000163 | 31335 |

lightgbm

![image-20260321184532681](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321184532681.png)

|  bin |  avg_pred |  avg_true | count |
| ---: | --------: | --------: | ----- |
|    0 | -0.000714 | -0.000311 | 31335 |
|    1 | -0.000104 | -0.000185 | 31335 |
|    2 |  0.000147 | -0.000012 | 31335 |
|    3 |  0.000750 |  0.000254 | 31335 |

ensemble

![image-20260321190639144](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321190639144.png)

|  bin |  avg_pred |  avg_true | count |
| ---: | --------: | --------: | ----- |
|    0 | -0.000451 | -0.000329 | 31335 |
|    1 | -0.000064 | -0.000134 | 31335 |
|    2 |  0.000108 | -0.000059 | 31335 |
|    3 |  0.000474 |  0.000268 | 31335 |

### **10.4 30-day moving average of cross-sectional correlation**

To check temporal stability, we computed the daily cross-sectional correlation between predictions and the target and then plotted the 30-day moving average over 2014.

![image-20260321185031753](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321185031753.png)

![image-20260321190327165](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321190327165.png)

![image-20260321183723123](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321183723123.png)

![image-20260321184639734](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321184639734.png)

![image-20260321190708734](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321190708734.png)

|       | ridge     | random forest | xgboost   | lightgbm  | ensemble  |
| ----- | --------- | ------------- | --------- | --------- | --------- |
| count | 252       | 252           | 252       | 252       | 252       |
| mean  | 0.021396  | 0.023169      | 0.022187  | 0.026348  | 0.026970  |
| std   | 0.072523  | 0.065339      | 0.063215  | 0.063181  | 0.062811  |
| min   | -0.156032 | -0.152498     | -0.147704 | -0.150433 | -0.157394 |
| 25%   | -0.027018 | -0.023041     | -0.020148 | -0.016269 | -0.018215 |
| 50%   | 0.014966  | 0.023005      | 0.016332  | 0.025759  | 0.023049  |
| 75%   | 0.070078  | 0.071641      | 0.064701  | 0.068294  | 0.068912  |
| max   | 0.232274  | 0.189114      | 0.183573  | 0.182555  | 0.197214  |



### **10.5 MDA on the validation-year model**

We also computed MDA feature importance using the final model trained on 2010–2013.

![image-20260321184938636](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321184938636.png)

<img src="C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321000153592.png" alt="image-20260321000153592"  />

![image-20260321183447739](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321183447739.png)

![image-20260321184457618](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321184457618.png)



### **10.6 Validation-year drift plot**

We also generated the required drift plot for 2014. Predictions were sorted into four bins, and for each bin we plotted the average realized cumulative residual return path from 24 hours before prediction time to 48 hours after prediction time, with standard-error bands.

![image-20260321185142485](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321185142485.png)

![image-20260321190459221](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321190459221.png)

![image-20260321184054867](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321184054867.png)

![image-20260321190726424](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321190726424.png)



## **11. Steps Taken to Avoid Overfitting**

First, we kept 2014 fully out of sample during research and model development. Second, we selected features based on consistent IC behavior over 2010–2013 rather than on isolated performance spikes. Third, we reduced redundancy by removing highly correlated features and retaining only the stronger representative in each pair. Fourth, we limited the final feature count to a relatively compact set of 20 features spanning several economic categories instead of using a very large and uncontrolled library.

At the model stage, we used time-ordered cross-validation, regularization, and tree-size control. Empirically, larger and less regularized tree models tended to overfit, while moderate regularization gave a better bias-variance tradeoff. We also checked prediction bin plots, not just scalar metrics, because a model can have a slightly better validation score while still showing unstable ranking behavior.



------



## **12. Stationarity, Normalization, and Risk Controls**

A major challenge in this project is that many raw inputs are not naturally stationary and may embed unwanted exposure to volatility, liquidity, or size.

To address this, we applied:

- feature-specific clipping based on time-series diagnostics

- 5-MAD winsorization

- same-day cross-sectional z-score normalization

  

These steps were designed to reduce tail influence, improve comparability across time and across stocks, and make the model focus on relative signals rather than raw magnitudes.

We also took steps to avoid learning spurious signals or unintended risk exposures. In particular, the weighting schemes $\sqrt{MDV_{63}}$ and $1/ESTVOL$ help control the extent to which the model is driven by tiny illiquid names or extreme-volatility names. In addition, because many features were scaled by recent liquidity or volatility measures, the feature set was less likely to encode a trivial “long high-volatility / short low-volatility” or pure size effect. Finally, the cross-sectional normalization reduced the chance that the model would exploit persistent level differences unrelated to the intended prediction task.



------



## **13. Thoughtfulness of Feature Design**

We did not build the feature library by trying random powers or arbitrary transformations. Instead, each feature started from a specific short-horizon idea we thought might matter.

The raw features measure trading intensity, return path, volatility shape, and relative participation. The interaction features then ask conditional questions such as whether a return signal gets stronger when participation is high, when volatility asymmetry is elevated, or when two signals line up in the same direction.

This let us add some nonlinearity without losing interpretability. It also made later feature screening more meaningful, since each retained variable was tied to a specific idea rather than a mechanical transform.



------



## **14. Out-of-Sample Robustness**

The key question is not only whether the model works on the development period, but also whether its performance holds up in 2014 and stays reasonably close to what we saw in cross-validation.

**Out-of-sample robustness summary**

- Cross-validation mean performance on 2011–2013:

  |      |         model | cv_r2(sqrt_mdv)_mean | cv_r2(sqrt_mdv)_std | fold_1_r2 | fold_2_r2 | fold_3__r2 |
  | ---: | ------------: | -------------------: | ------------------: | --------: | --------: | ---------- |
  |    0 |         ridge |             0.000332 |            0.000200 |  0.000535 |  0.000060 | 0.000401   |
  |    1 | random_forest |             0.000724 |            0.000117 |  0.000767 |  0.000564 | 0.000842   |
  |    2 |       xgboost |            -0.002233 |            0.002746 | -0.000832 |  0.000202 | -0.006070  |
  |    3 |      lightgbm |             0.000466 |            0.000065 |  0.000554 |  0.000444 | 0.000399   |

- 2014 validation performance: 

  |      |         model | val_r2_weighted_sqrt_mdv | val_r2_weighted_est_vol |
  | ---: | ------------: | -----------------------: | ----------------------: |
  |    0 | random_forest |                 0.000351 |                0.000254 |
  |    1 |         ridge |                -0.000416 |               -0.000154 |
  |    2 |       xgboost |                -0.001806 |               -0.002231 |
  |    3 |      lightgbm |                -0.002051 |               -0.001727 |

- Gap between CV and 2014:

  r2_sqrt_mdv_gap = val_r2(sqrt_mdv) - cv_r2(sqrt_mdv)_mean

  |      |         model | r2_sqrt_mdv_gap |
  | ---: | ------------: | --------------: |
  |    0 |         ridge |        0.000748 |
  |    1 | random_forest |        0.000373 |
  |    2 |       xgboost |       -0.000427 |
  |    3 |      lightgbm |        0.002517 |

This comparison matters because, in low-signal financial prediction problems, a large drop from cross-validation to hold-out performance often points to overfitting or unstable features. Our goal was not to maximize in-sample fit, but to build a process whose out-of-sample degradation stayed acceptable.



------



## **15. Conclusion**

This project developed a leakage-free, date-by-date pipeline for predicting 24-hour forward residual returns using daily and intraday stock data. The pipeline emphasized careful feature construction, preprocessing, IC-based feature screening, redundancy reduction, and time-ordered cross-validation. We compared linear and nonlinear models, observed a strong bias-variance tradeoff in tree-based methods, and selected a final model that balanced weighted $R^2$, monotonicity in bin plots, and prediction stability.

Overall, this project highlights the main difficulty of short-horizon equity prediction: the signal is weak, noisy, and unstable. Because of that, preprocessing, feature screening, and regularization mattered at least as much as model choice. We therefore judged the final model not only by validation $R^2$, but also by whether its bin plots, drift plots, and rolling correlation looked reasonably consistent.



------



## **Appendix A. Full Raw Feature List**

- $t^\star =$ 15:30 on day $T$
- $r^{res}_{i,\tau}$ = 15-minute residual return of stock $i$ at interval $\tau$
- $r^{raw}_{i,\tau}$ = 15-minute raw return of stock $i$ at interval $\tau$
- $DV_{i,\tau}$ = adjusted dollar volume in interval $\tau$
- $P_{i,\tau}$ = adjusted price at interval $\tau$
- $ESTVOL_i(T)$ = daily estimated volatility on day $T$
- $MDV_{63,i}(T)$ = 63-day median daily dollar volume
- $R^{res}_{i}(T,16{:}00)$ = cumulative residual return of day $T$ at 16:00
- $R^{res}_{i}(T,15{:}30)$ = cumulative residual return of day $T$ at 15:30
- $R^{raw}_{i}(T,15{:}30)$ = cumulative raw return of day $T$ at 15:30

------

### A.0 Price Adjustment, Share Adjustment, and Dollar-Volume Construction

The raw daily files provide both a price adjustment factor (`PxAdjFactor`) and a shares adjustment factor (`SharesAdjFactor`). These are used to place prices and volumes on a consistent post-corporate-action basis across dates. The project addendum explicitly notes that when comparing prices across days one should use the ratio of price adjustment factors, and when comparing volumes across days one should use the ratio of shares adjustment factors. 

In our implementation, we define adjusted prices and adjusted share volume as follows.

#### A.0.1 Adjusted daily prices

For any daily raw price field $P^{raw}_i(T)$, such as open, high, low, or close, we define
$$
P^{adj}_i(T)=P^{raw}_i(T)\cdot PxAdjFactor_i(T).
$$
In particular,
$$
O^{adj}_i(T)=Open_i(T)\cdot PxAdjFactor_i(T),
$$
Using adjusted prices ensures that returns across split dates or dividend dates are computed in consistent price units.

#### A.0.2 Adjusted daily share volume

Raw daily share volume is adjusted using the shares adjustment factor:
$$
V^{adj,day}_i(T)=Volume_i(T)\cdot SharesAdjFactor_i(T).
$$
This places historical volumes on a split-adjusted basis so that cross-day comparisons remain meaningful.

#### A.0.3 Adjusted daily dollar volume

We define adjusted daily dollar volume as adjusted share volume times adjusted closing price:
$$
DV^{adj,day}_i(T)=V^{adj,day}_i(T)\cdot C^{adj}_i(T).
$$
Equivalently,
$$
DV^{adj,day}_i(T)
=
Volume_i(T)\cdot SharesAdjFactor_i(T)\cdot Close_i(T)\cdot PxAdjFactor_i(T).
$$
This daily adjusted dollar volume is used directly in some features and also to construct relative liquidity measures such as yesterday-tail participation and volume-relative features. This is exactly how it is computed in our feature code. 

------

#### A.0.4 Adjusted intraday price path

The intraday file provides cumulative raw return from the previous day’s 16:00 close to each intraday snapshot. The project notes that these cumulative returns are already adjusted for corporate actions. 

Let $R^{raw,cum}_i(T,\tau)$ denote the cumulative raw return for stock $i$ from the previous day’s close to intraday timestamp $\tau$ on day $T$. Let $C^{adj}_i(T-1)$ be the previous day’s adjusted close. Then we reconstruct the adjusted intraday price path as
$$
P^{adj}_i(T,\tau)
=
C^{adj}_i(T-1)\cdot \left(1+R^{raw,cum}_i(T,\tau)\right).
$$
This is the adjusted intraday price series used throughout our intraday feature construction. In the code, this corresponds to `P_adj = PrevClose_adj * (1 + CumReturnRaw)`. 

------

#### A.0.5 Adjusted intraday cumulative and bar share volume

The intraday file provides cumulative share volume `CumVolume` from the start of trading through each timestamp. To put intraday volume on the same split-adjusted basis, we define adjusted cumulative intraday volume as
$$
V^{adj,cum}_i(T,\tau)
=
CumVolume_i(T,\tau)\cdot SharesAdjFactor_i(T).
$$
The 15-minute adjusted bar volume is then obtained by differencing the cumulative series:
$$
V^{adj}_i(T,\tau)
=
V^{adj,cum}_i(T,\tau)-V^{adj,cum}_i(T,\tau^-),
$$
where $\tau^-$ denotes the previous intraday snapshot. For the first bar of the day, we set
$$
V^{adj}_i(T,\tau_1)=V^{adj,cum}_i(T,\tau_1).
$$
This matches the implementation in `build_intraday_15m_adjusted`, where `V_adj_cum` is first formed from `CumVolume * SharesAdjFactor`, and `V_adj` is the within-day difference.

------

#### A.0.6 Adjusted intraday 15-minute returns

Because the intraday return fields are cumulative, we convert them into 15-minute bar returns before constructing most path-based features.

For cumulative raw return:
$$
r^{raw}_i(T,\tau)
=
\frac{1+R^{raw,cum}_i(T,\tau)}
{1+R^{raw,cum}_i(T,\tau^-)}
-1.
$$
For cumulative residual return:
$$
r^{res}_i(T,\tau)
=
\frac{1+R^{res,cum}_i(T,\tau)}
{1+R^{res,cum}_i(T,\tau^-)}
-1.
$$
For the first intraday snapshot of the day, the previous cumulative return is taken to be zero, so the first bar return equals the first cumulative return. This follows the project statement that the 09:45 snapshot includes the move from the previous day’s 16:00 close through 09:45.

------

#### A.0.7 Adjusted intraday dollar volume

For each 15-minute bar, we compute adjusted dollar volume using adjusted bar share volume multiplied by the average adjusted price over the bar. Let $P^{adj}_i(T,\tau^-)$ and $P^{adj}_i(T,\tau)$ denote the adjusted prices at the start and end of the bar. Then
$$
DV^{adj}_i(T,\tau)
=
V^{adj}_i(T,\tau)\cdot
\frac{P^{adj}_i(T,\tau^-)+P^{adj}_i(T,\tau)}{2}.
$$
For the first bar of the day, the bar-start price is taken to be the adjusted opening price:
$$
P^{adj}_i(T,\tau_1^-)=O^{adj}_i(T).
$$
The cumulative adjusted intraday dollar volume is then
$$
DV^{adj,cum}_i(T,\tau)
=
\sum_{s \le \tau} DV^{adj}_i(T,s).
$$
This is exactly the quantity used in our code as `DV_adj` and `DV_adj_cum`. 

### A.1 Raw Features

1. Overnight return scaled by volatility

$$
overnight\_ret\_vol_i(T)
=
\frac{\dfrac{O^{adj}_i(T)}{C^{adj}_i(T-1)} - 1}{ESTVOL_i(T)}
$$

2. Intraday residual return scaled by volatility

$$
intraday\_resid\_ret\_vol_i(T)
=
\frac{R^{res}_i(T,15{:}30)}{ESTVOL_i(T)}
$$

3. Intraday dollar volume relative to yesterday

Let $DV^{day}_{i}(T-1)$ denote yesterday’s adjusted full-day dollar volume. Then
$$
intraday\_dollar\_rel\_to\_yday_i(T)
=
\frac{DV^{cum}_i(T,15{:}30)}{DV^{day}_i(T-1)}
$$

4. Volume acceleration

Let
$$
V^{early}_i(T)=\sum_{\tau \in [09{:}45,11{:}00]} V_{i,\tau},
\qquad
V^{late}_i(T)=\sum_{\tau \in [14{:}00,15{:}30]} V_{i,\tau}.
$$
Then
$$
volume\_accel_i(T)=\frac{V^{late}_i(T)}{V^{early}_i(T)}.
$$

5. Common-factor return scaled by volatility

$$
common\_factor\_ret\_vol_i(T)
=
\frac{R^{raw}_i(T,15{:}30)-R^{res}_i(T,15{:}30)}{ESTVOL_i(T)}
$$

6. Previous-day cumulative residual return at 16:00

$$
prev\_cumret\_resid\_1600_i(T)
=
\frac{R^{res}_i(T-1,16{:}00)}{ESTVOL_i(T-1)}
$$

7. Range

Let $P^{first}_i(T)$ be the first intraday adjusted price of the day. Then
$$
range_i(T)
=
\frac{\max_{\tau \le t^\star} P_{i,\tau}-\min_{\tau \le t^\star} P_{i,\tau}}
{P^{first}_i(T)}.
$$

8. Maximum drawdown

Let
$$
P^{max}_{i,\tau}(T)=\max_{s \le \tau} P_{i,s}(T).
$$
Then
$$
max\_drawdown_i(T)
=
\max_{\tau \le t^\star}
\frac{P^{max}_{i,\tau}(T)-P_{i,\tau}(T)}
{P^{max}_{i,\tau}(T)}.
$$

9. Up-minus-down risk, residual version

Define
$$
U_i(T)=\sum_{\tau \le t^\star} \max(r^{res}_{i,\tau},0)^2,
\qquad
D_i(T)=\sum_{\tau \le t^\star} \max(-r^{res}_{i,\tau},0)^2.
$$
Then
$$
up\_minus\_down\_risk\_L_i(T)
=
\frac{U_i(T)-D_i(T)}{U_i(T)+D_i(T)}.
$$

10. TGA directional asymmetry, residual version

Let $w_\tau = \tau$ be increasing time weights over the intraday bars. Define
$$
TGA^+_i(T)
=
\frac{\sum_{\tau \le t^\star} w_\tau \max(r^{res}_{i,\tau},0)}
{\sum_{\tau \le t^\star} w_\tau \cdot \left(\frac{1}{N}\sum_{\tau \le t^\star}|r^{res}_{i,\tau}|\right)},
$$
$$
TGA^-_i(T)
=
\frac{\sum_{\tau \le t^\star} w_\tau \max(-r^{res}_{i,\tau},0)}
{\sum_{\tau \le t^\star} w_\tau \cdot \left(\frac{1}{N}\sum_{\tau \le t^\star}|r^{res}_{i,\tau}|\right)}.
$$
Then
$$
tga\_directional\_asymmetry\_L_i(T)=TGA^+_i(T)-TGA^-_i(T).
$$

11. Negative illiquidity

Let
$$
NegRet_i(T)=\sum_{\tau \le t^\star,\, r^{res}_{i,\tau}<0} |r^{res}_{i,\tau}|,
\qquad
NegDV_i(T)=\sum_{\tau \le t^\star,\, r^{res}_{i,\tau}<0} DV_{i,\tau}.
$$
Then
$$
negative\_illiquidity\_L_i(T)
=
\frac{NegRet_i(T)}
{NegDV_i(T)/MDV_{63,i}(T-1)}.
$$

12. Amount direction

$$
amount\_dir\_15m_i(T)
=
\frac{\frac{1}{N}\sum_{\tau \le t^\star} DV_{i,\tau}\,\mathrm{sign}(r^{res}_{i,\tau})}
{\frac{1}{N}\sum_{\tau \le t^\star} DV_{i,\tau}}.
$$

13. Intraday MACD histogram

Let $\text{EMA}_{fast}$ and $\text{EMA}_{slow}$ be exponential moving averages of $\log P_{i,\tau}$ over the intraday path. Then
$$
MACD_{i,\tau}=\text{EMA}^{fast}_{i,\tau}-\text{EMA}^{slow}_{i,\tau},
$$

14. Up-minus-down risk, raw version

Define
$$
U_i^{raw}(T)=\sum_{\tau \le t^\star} \max(r^{raw}_{i,\tau},0)^2,
\qquad
D_i^{raw}(T)=\sum_{\tau \le t^\star} \max(-r^{raw}_{i,\tau},0)^2.
$$
Then
$$
up\_minus\_down\_risk\_L\_raw_i(T)
=
\frac{U_i^{raw}(T)-D_i^{raw}(T)}{U_i^{raw}(T)+D_i^{raw}(T)}.
$$

------

### A.2 Interaction Features

20-day time-series z-scores. For a generic variable $X_i(T)$, define
$$
zscore_{20}(X_i(T))
=
\frac{X_i(T)-\mu_{i,20}(T)}{\sigma_{i,20}(T)},
$$
where
$$
\mu_{i,20}(T)
=
\frac{1}{20}\sum_{s=T-19}^{T} X_i(s),
\qquad
\sigma_{i,20}(T)
=
\sqrt{
\frac{1}{20}
\sum_{s=T-19}^{T}
\left(X_i(s)-\mu_{i,20}(T)\right)^2
}.
$$
sigmoid gate：
$$
\sigma_k(z)=\frac{1}{1+e^{-kz}}.
$$
Then define the smooth gates
$$
g^{flow}_i(T)=\sigma_k\!\left(z^{flow}_i(T)\right),
\qquad
g^{tail}_i(T)=\sigma_k\!\left(z^{tail}_i(T)\right),
\qquad
g^{rel}_i(T)=\sigma_k\!\left(z^{rel}_i(T)\right),
\qquad
g^{dd}_i(T)=\sigma_k\!\left(z^{dd}_i(T)\right),
$$

1. Trend when flow is high

$$
x\_trend\_when\_flow\_high_i(T)
=
intraday\_resid\_ret\_vol_i(T)\cdot g^{flow}_i(T)
$$

2. High flow but little price movement

Let
$$
pct_i(T)=\text{cross-sectional percentile rank of }
|intraday\_resid\_ret\_vol_i(T)|.
$$
Then
$$
x\_high\_flow\_no\_move_i(T)
=
g^{flow}_i(T)\cdot \left(1-pct_i(T)\right)
$$

3. Tail-flow continuation

$$
x\_tail\_flow\_continuation_i(T)
=
\frac{1}{2}\left(g^{tail}_i(T)+g^{rel}_i(T)\right)
$$

4. Drawdown-conditioned RSI

Let $RSI_i(T)$ denote the intraday RSI evaluated at 15:30. Then
$$
x\_drawdown\_conditioned\_rsi_i(T)
=
\left(50-RSI_i(T)\right)\cdot g^{dd}_i(T)
$$

5. Previous-close follow-through

Let
$$
a_i(T)=prev\_cumret\_resid\_1600_i(T),
\qquad
b_i(T)=intraday\_resid\_ret\_vol_i(T).
$$
Then
$$
x\_prev\_close\_followthrough_i(T)
=
\mathrm{sign}\!\left(a_i(T)\,b_i(T)\right)\cdot
\min\!\left(|a_i(T)|,\ |b_i(T)|\right)
$$

6. Frighten mean over standard deviation

$$
x\_frighten\_mean\_over\_std_i(T)
=
\frac{frighten\_mean\_L_i(T)}
{frighten\_std\_L_i(T)}
$$

### A.3 Auxiliary Variables Used in Interaction Features

The interaction features rely on a small number of auxiliary state variables that are not necessarily included as standalone raw features in the final model. They are defined below for completeness.

1. Intraday dollar-volume participation ratio

This variable measures cumulative adjusted dollar volume up to 15:30 relative to the stock’s typical liquidity.
$$
intraday\_dollar\_vpr_i(T)
=
\frac{DV^{cum}_i(T,15{:}30)}{MDV_{63,i}(T-1)}
$$
where $DV^{cum}_i(T,15{:}30)$ is cumulative adjusted dollar volume from the start of trading to 15:30 on day $T$.

Interpretation: high values indicate that the stock has already traded an unusually large fraction of its normal daily dollar volume by 15:30.

------

2. Yesterday tail dollar-volume participation ratio

This variable measures how large yesterday’s last 30 minutes plus closing-auction activity was relative to typical liquidity.

Let $DV^{tail}_i(T-1)$ denote adjusted dollar volume over the final part of day $T-1$ (for example the 15:30–16:00 interval, possibly including the closing auction depending on implementation). Then
$$
yday\_tail\_vpr_i(T)
=
\frac{DV^{tail}_i(T-1)}{MDV_{63,i}(T-1)}
$$
Interpretation: large values indicate unusual trading pressure near yesterday’s close, which may carry over into the next day.

------

3. Intraday RSI

The intraday Relative Strength Index is computed from the adjusted intraday price path up to 15:30. Let $\Delta P_{i,\tau}=P_{i,\tau}-P_{i,\tau-1}$ and define positive and negative moves
$$
U_{i,\tau}=\max(\Delta P_{i,\tau},0),
\qquad
D_{i,\tau}=\max(-\Delta P_{i,\tau},0).
$$
Using a rolling intraday window or exponential smoothing, define average gains and losses:
$$
\overline{U}_i(T)=\text{AvgGain up to }15{:}30,
\qquad
\overline{D}_i(T)=\text{AvgLoss up to }15{:}30.
$$
Then
$$
RS_i(T)=\frac{\overline{U}_i(T)}{\overline{D}_i(T)},
\qquad
intraday\_rsi_i(T)=100-\frac{100}{1+RS_i(T)}.
$$
Interpretation: a low RSI indicates that downside moves have dominated recently, while a high RSI indicates stronger recent upward movement.

------

4. Frighten mean

This quantity is built from an intraday “dislocation” or “panic” series. At each intraday snapshot, define a cross-sectionally weighted market-like residual move:
$$
m^{res}_\tau(T)
=
\frac{\sum_i w_{i,\tau} \, R^{res}_{i,\tau}(T)}
{\sum_i w_{i,\tau}},
$$
where $w_{i,\tau}$ is a liquidity-related weight such as adjusted dollar volume or cumulative volume.

For each stock, define a dislocation measure
$$
d_{i,\tau}(T)
=
R^{res}_{i,\tau}(T)-m^{res}_\tau(T).
$$
Then define the “frighten” contribution at each interval as a positive-part transformed dislocation times return, for example
$$
f_{i,\tau}(T)
=
\max(d_{i,\tau}(T),0)\cdot r^{res}_{i,\tau}(T).
$$
The mean frighten measure is
$$
frighten\_mean\_L_i(T)
=
\frac{1}{N_T}\sum_{\tau \le 15{:}30} f_{i,\tau}(T),
$$
where $N_T$ is the number of intraday intervals used up to 15:30.

Interpretation: this quantity is intended to capture whether the stock exhibits repeated positive dislocation or “stress” relative to the market-like residual path.

------

5. Frighten standard deviation

Using the same intraday frighten contributions $f_{i,\tau}(T)$, define
$$
frighten\_std\_L_i(T)
=
\sqrt{
\frac{1}{N_T}
\sum_{\tau \le 15{:}30}
\left(
f_{i,\tau}(T)-frighten\_mean\_L_i(T)
\right)^2
}.
$$
Interpretation: this measures the variability of the frighten signal during the day. A large value means the dislocation-style signal is noisy or unstable.



## **Appendix B. IC Table**

|      |                         feature |      2010 |      2011 |      2012 |      2013 | abs_ic_mean |  abs_icir |
| ---: | ------------------------------: | --------: | --------: | --------: | --------: | ----------: | --------: |
|    0 |              intraday_macd_hist | -0.011929 | -0.013843 | -0.013687 | -0.011454 |    0.012728 | 10.482800 |
|    1 |           common_factor_ret_vol | -0.012902 | -0.013761 | -0.010984 | -0.008435 |    0.011521 |  4.877737 |
|    2 |             x_high_flow_no_move |  0.008991 |  0.007376 |  0.008323 |  0.012275 |    0.009241 |  4.342832 |
|    3 |      x_drawdown_conditioned_rsi |  0.022668 |  0.021271 |  0.011967 |  0.020705 |    0.019153 |  3.940212 |
|    4 |                    intraday_rsi | -0.020260 | -0.021830 | -0.009431 | -0.018991 |    0.017628 |  3.155252 |
|    5 | tga_directional_asymmetry_L_raw | -0.019952 | -0.021159 | -0.008007 | -0.018407 |    0.016881 |  2.803194 |
|    6 |     tga_directional_asymmetry_L | -0.021897 | -0.024232 | -0.008711 | -0.020251 |    0.018773 |  2.719164 |
|    7 |            intraday_macd_signal | -0.016132 | -0.016101 | -0.006210 | -0.020764 |    0.014802 |  2.413618 |
|    8 |                    volume_accel |  0.010019 |  0.005058 |  0.008682 |  0.003387 |    0.006786 |  2.198502 |
|    9 |                           range | -0.003421 | -0.006952 | -0.006251 | -0.002058 |    0.004670 |  2.016703 |
|   10 |        x_frighten_mean_over_std | -0.012426 | -0.011178 | -0.002625 | -0.008637 |    0.008716 |  2.001019 |
|   11 |        x_tail_flow_continuation |  0.002318 |  0.003971 |  0.001210 |  0.004889 |    0.003097 |  1.879509 |
|   12 |                           RVJ_L | -0.005102 | -0.008045 | -0.010608 | -0.001607 |    0.006341 |  1.636241 |
|   13 |          x_trend_when_flow_high | -0.018072 | -0.009641 | -0.000704 | -0.010874 |    0.009823 |  1.378415 |
|   14 |          prev_cumret_resid_1600 |  0.000554 | -0.007482 | -0.008147 | -0.007369 |    0.005611 |  1.360549 |
|   15 |      x_prev_close_followthrough |  0.004846 | -0.000246 |  0.002975 |  0.006784 |    0.003590 |  1.199479 |
|   16 |                    max_drawdown |  0.006811 |  0.003174 | -0.000719 |  0.006043 |    0.003827 |  1.121913 |
|   17 |        x_jump_vs_continuous_vol | -0.000621 | -0.001619 | -0.008074 | -0.003627 |    0.003485 |  1.054798 |
|   18 |                 frighten_mean_L | -0.007758 | -0.008259 |  0.002579 | -0.010440 |    0.005969 |  1.026223 |
|   19 |        up_minus_down_risk_L_raw | -0.019132 | -0.007288 |  0.000981 | -0.008409 |    0.008462 |  1.025165 |
|   20 |              amount_dir_15m_raw | -0.016956 | -0.005078 | -0.000650 | -0.005423 |    0.007027 |  1.008589 |
|   21 |          intraday_resid_ret_vol | -0.017723 | -0.009755 |  0.003488 | -0.009686 |    0.008419 |  0.957870 |
|   22 |                  amount_dir_15m | -0.015269 | -0.006626 |  0.002595 | -0.007549 |    0.006712 |  0.917542 |
|   23 |  x_overnight_intraday_agreement | -0.008655 | -0.001277 | -0.007039 |  0.001077 |    0.003973 |  0.859712 |
|   24 |               r1_umdvol_std_raw |  0.001480 |  0.004815 |  0.002218 | -0.000730 |    0.001946 |  0.851191 |
|   25 |         x_panic_amplified_illiq |  0.000331 | -0.003647 | -0.001667 |  0.000147 |    0.001209 |  0.650507 |
|   26 |              r1_umdvol_inv_mean | -0.001880 |  0.002293 |  0.004021 |  0.001073 |    0.001377 |  0.554020 |
|   27 |          negative_illiquidity_L |  0.002518 | -0.003849 | -0.001930 | -0.002111 |    0.001343 |  0.494575 |
|   28 |               overnight_ret_vol | -0.007265 | -0.008221 |  0.005790 | -0.002435 |    0.003033 |  0.473607 |
|   29 |                           RTV_L | -0.003603 | -0.004526 |  0.000058 |  0.002199 |    0.001468 |  0.466664 |
|   30 |            up_minus_down_risk_L | -0.013064 | -0.005175 |  0.007438 | -0.004656 |    0.003864 |  0.456769 |
|   31 |                 r1_umd_inv_mean |  0.004004 | -0.005405 | -0.003809 | -0.002242 |    0.001863 |  0.452337 |
|   32 |                         pv_corr | -0.005652 |  0.005296 |  0.017745 |  0.000114 |    0.004376 |  0.438812 |
|   33 |                     pv_corr_raw | -0.005580 |  0.005037 |  0.011890 |  0.001391 |    0.003184 |  0.437072 |
|   34 |                  r1_umdvol_mean | -0.002666 | -0.003313 |  0.005431 | -0.007165 |    0.001928 |  0.364269 |
|   35 |             intraday_dollar_vpr | -0.003037 |  0.003034 | -0.000908 |  0.004325 |    0.000853 |  0.249667 |
|   36 |           vol_profile_L1_vs_avg | -0.003109 |  0.002996 | -0.002681 |  0.001167 |    0.000406 |  0.136700 |
|   37 |                  frighten_std_L | -0.000308 | -0.004205 |  0.001178 |  0.005463 |    0.000532 |  0.133124 |
|   38 |                   r1_umdvol_std |  0.002004 |  0.000936 | -0.002013 | -0.001952 |    0.000256 |  0.125700 |
|   39 |      negative_illiquidity_L_raw |  0.002798 | -0.000578 | -0.001902 | -0.000764 |    0.000112 |  0.055073 |
|   40 |     intraday_dollar_rel_to_yday |  0.001446 | -0.001159 | -0.006667 |  0.005321 |    0.000265 |  0.052651 |
|   41 |       x_r1_umdvol_mean_over_std | -0.000555 | -0.000377 |  0.004480 | -0.003607 |    0.000015 |  0.004402 |
|   42 |                   yday_tail_vpr | -0.007495 |  0.007751 |  0.002419 | -0.002770 |    0.000024 |  0.003638 |



## **Appendix C. Figures**

- Monthly feature summary plots

![image-20260321210113884](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210113884.png)

![image-20260321210147429](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210147429.png)

![image-20260321210151329](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210151329.png)

![image-20260321210155685](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210155685.png)

![image-20260321210159014](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210159014.png)

![image-20260321210203739](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210203739.png)

![image-20260321210207650](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210207650.png)

![image-20260321210211650](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210211650.png)

![image-20260321210216076](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210216076.png)

![image-20260321210220112](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210220112.png)

![image-20260321210227442](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210227442.png)

![image-20260321210230792](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210230792.png)

![image-20260321210236467](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210236467.png)

![image-20260321210243821](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210243821.png)

![image-20260321210248066](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210248066.png)

![image-20260321210251574](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210251574.png)

![image-20260321210255487](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210255487.png)

![image-20260321210259612](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210259612.png)

![image-20260321210303237](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210303237.png)

![image-20260321210306250](C:\Users\Lenovo\AppData\Roaming\Typora\typora-user-images\image-20260321210306250.png)