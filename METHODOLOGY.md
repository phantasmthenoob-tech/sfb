# Evaluation Methodology

This document records how the simulator and the six-model experiment are evaluated. It is intended to make the assumptions inspectable and to distinguish a useful engineering baseline from evidence of a durable trading edge.

## Research question

The project asks two separate questions:

1. **Engineering:** Can a single-process paper-trading simulator correctly gate data, execute orders, account for fees and borrow, value portfolios and expose a reproducible strategy comparison?
2. **Research:** Do any of the candidate strategies produce better risk-adjusted, after-cost performance than a passive benchmark on unseen chronological data?

The second question is not answered by a high full-period return. It requires out-of-sample evaluation, identical controls and a skeptical treatment of correlated observations.

## Data used

| Item | Value |
| --- | --- |
| Price source | Yahoo Finance daily chart endpoint |
| Experiment history | 10 years, 2,514 sessions |
| Default simulator history | 5 years, 1,255 sessions, 160,640 bars |
| Universe | 120 current-listed US stocks + 8 ETFs |
| ETF treatment | Benchmarks only; agents cannot trade them |
| Headlines | Deterministically generated locally |
| Experiment feature rows | 316,738 |
| Simulated headlines | Generated locally; not an archived historical corpus |

The experiment uses price returns from Yahoo's daily close series. It does not model dividends, independent split normalization, bid/ask spread, market impact, borrow availability or capacity.

The 120 names are current-listed survivors. The data therefore contains survivorship bias and should not be treated as the universe an investor could have selected in 2016.

## Strategy families

The three heuristics are deterministic:

- **Price AI:** 60% SMA5/SMA20 trend + 40% 10-bar momentum.
- **News AI:** five-session simulated headline sentiment, conditioned on the technical trend.
- **Combined AI:** 90% technical score + 10% news score.

The ML experiment adds:

- Random Forest regression.
- Histogram Gradient Boosting regression.
- A two-layer MLP neural network.

All six models output a daily score. The experiment converts scores to cross-sectional percentile ranks and applies the same rule to every model. This is deliberate: a model cannot win because it received a different position size, different leverage or a different exit threshold.

## Features and labels

Each stock/session feature row contains 11 compact features:

1. Technical trend score
2. 10-bar momentum
3. SMA5/SMA20 cross
4. 20-day realized volatility
5. 5-session return
6. 20-session return
7. News component
8. Headline count
9. Price × news interaction
10. Market trend
11. Volume trend

The neural network also receives 15 point-in-time features: RSI(14), 20-day range position, distance from SMA20 and SMA50, 1/3/10-session returns, 5/20-day volatility ratio, market 5/20-day returns, market volatility, relative strength versus the market and sector, market breadth, and one-day news.

The tree models are trained on the raw forward five-session return, clipped to ±25% for robustness. The neural network is trained on the cross-sectional percentile rank of that return. The rank target removes the common market move and improved the network's validation ranking, but applying the same target to the trees reduced their portfolio returns, so RF and GB keep the absolute-return target. Features use only bars, volume and headlines at or before the scoring close.

The **news features are simulated**. A positive result from News AI or Combined AI therefore measures performance on generated sentiment, not real historical journalism.

## Walk-forward validation

The evaluation is the last five years of the 10-year dataset. Training begins with the data before the first validation period and expands by one year at a time.

```text
Fold 1  train: 2016-12-13 .. 2021-11-12   validate: 2021-11-15 .. 2022-11-14
Fold 2  train: 2016-12-13 .. 2022-11-14   validate: 2022-11-15 .. 2023-11-14
Fold 3  train: 2016-12-13 .. 2023-11-14   validate: 2023-11-15 .. 2024-11-13
Fold 4  train: 2016-12-13 .. 2024-11-13   validate: 2024-11-14 .. 2025-11-13
Fold 5  train: 2016-12-13 .. 2025-11-13   validate: 2025-11-14 .. 2026-11-13
```

The first row date is later than the raw data start because the technical features require a warm-up. This is an expanding-window design. Later folds include prior validation years in training, which is standard walk-forward behavior: the model is allowed to learn from history that has already become observed, but never from the validation period it is currently predicting.

### Purge rule

For a training row at offset `t` with horizon `H = 5`, the label uses the close at `t + 5`. A row is excluded when:

```text
t + H >= validation_start
```

The first fold's last training label ends on 2021-11-12 and validation starts on 2021-11-15. This boundary is tested in `backend/tests/test_experiment.py`.

The feature builder is also point-in-time:

- Technical indicators slice bars up to the current offset.
- News sentiment reads only the current and previous five sessions.
- Market trend uses the current and previous closes.
- Standardization statistics are fit on training rows only.
- Early-stopping splits inside RF/GB/MLP use training rows only.

### What this protocol does not prove

Walk-forward validation reduces look-ahead leakage; it does not eliminate overfitting risk. Hyperparameters and features were chosen with knowledge of the dataset, the folds overlap in time, and the final test period is only one path through one market history. A proper stability study would repeat the experiment across seeds, universes, cost assumptions and block-bootstrapped samples.

## Portfolio simulation

The six-model experiment uses one identical portfolio rule:

- Starting capital: $10,000.
- Long-only.
- Rank scores cross-sectionally each session.
- Enter the top ten names above the 82nd percentile.
- Exit below the 50th percentile.
- Target 10% of equity per position.
- Fill at the next open.
- Pay 5 bps per side.
- Mark positions at the close.

This rule is intentionally simple and common across models. It is not a claim that the top-ten ranking is optimal; it isolates the signal from portfolio-construction differences. The entry, exit, position-size and position-count settings were selected from a small grid, so the five-year result is in-sample for that parameter choice and is not independent confirmation.

## Metrics

| Metric | Definition |
| --- | --- |
| Total return | Final equity / starting equity − 1 |
| CAGR | Compounded annual growth from the evaluation length |
| Maximum drawdown | Largest peak-to-trough decline in marked equity |
| Sharpe ratio | Annualized mean daily return / annualized daily volatility; zero risk-free rate |
| Volatility | Standard deviation of daily returns, annualized |
| Win rate | Share of closed trades with positive realized P&L |
| Calmar ratio | Annualized return / maximum drawdown |
| Turnover | Traded notional / average equity |
| Exposure | Average marked position value / equity |
| Regime return | Compounded return on days classified by SPY's position versus its 200-day average |
| Correlation | Average pairwise and same-sector/cross-sector return correlation |

A high return with an unacceptable drawdown is not treated as a better result. Sharpe, drawdown, Calmar and turnover are reported alongside return. The live simulator's agents use separate thresholds; the experiment applies one common portfolio rule so the models can be compared directly.

## Results

After 5 bps per side, over the five-year evaluation:

| Model | Return | CAGR | Volatility | Sharpe | Max DD | Trades | Final |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Price AI | +101.45% | 15.10% | 16.81% | 0.92 | 17.49% | 3,983 | $20,145 |
| News AI | +22.57% | 4.17% | 14.40% | 0.36 | 28.37% | 6,473 | $12,257 |
| Combined AI | +133.46% | 18.56% | 16.00% | 1.15 | 16.40% | 4,101 | $23,346 |
| Random Forest | +80.61% | 12.60% | 19.31% | 0.71 | 20.39% | 3,873 | $18,061 |
| Gradient Boosting | +94.84% | 14.33% | 17.43% | 0.86 | 19.96% | 7,136 | $19,484 |
| Neural Network | +64.48% | 10.51% | 16.78% | 0.68 | 25.80% | 8,208 | $16,448 |
| SPY buy-and-hold | +61.29% | — | — | — | — | — | — |

### Verdict against the target

- The **$20,000 target was met** by Price AI at $20,145 and Combined AI at $23,346.
- No model met the “two 100%+ validation folds” criterion; the best fold was +46.63%.
- Price AI, Combined AI, Random Forest, Gradient Boosting and Neural Network beat SPY after costs.
- Price AI, Combined AI, Random Forest and Gradient Boosting stayed below 25% maximum drawdown.
- Gradient Boosting was the strongest ML model at +94.84%; the neural network improved to +64.48% but remained weaker on drawdown.

### Regime observation

The bear subset was much less forgiving than the bull subset. Price AI returned +108.15% in bull-regime days with Sharpe 1.40, but −3.22% in bear-regime days with a slightly negative Sharpe. Combined AI returned +168.16% in the bull subset and −12.94% in the bear subset. These subset totals are not continuous portfolio returns; they show that headline performance is regime-dependent.

### Cost and turnover

Price AI traded 3,983 times with turnover of about 129× average equity; Combined AI traded 4,101 times at about 127×. Gradient Boosting and the neural network traded considerably more and still trailed Combined AI after costs. The experiment charges 5 bps per side, but does not model a separate spread or market impact. A 20 bps sensitivity run still left Combined AI positive (+56.1%), but the return is path-sensitive and should not be read as a precise forecast.

### Preliminary logistic result

A separate dependency-free logistic model reached about **53.04%** directional accuracy. Its held-out return was about **+94.2%**, below the Combined heuristic at **+106.1%** on the same research path. This is a preliminary baseline, not a validated production model.

## Reproducibility

The experiment fixes:

- Random seeds.
- Feature definitions.
- Fold boundaries.
- Model hyperparameters.
- Portfolio rule.
- Fee assumption.

The result JSON records the data range, Python version, NumPy version, scikit-learn version, fold boundaries, training row counts and model metrics.

One full 10-year pass was completed. I have not measured run-to-run variance with a second full pass. Yahoo's dataset may change between downloads, so “reproducible” currently means reproducible from the same saved data and code, not necessarily reproducible from a live re-download at a future date.

## Known limitations

1. Survivorship bias from current-listed constituents.
2. Simulated rather than archived historical news.
3. Correlated ticker observations and no block-bootstrap significance test.
4. One historical path; no guarantee across regimes.
5. No separate spread, impact or capacity model.
6. No dividend reinvestment or independent split normalization.
7. The offline ML results are research artifacts. The separate live Neural AI is trained only from simulator history up to its cutoff and is not the same walk-forward experiment; its live returns are not evidence for the offline numbers.
8. Full daily equity curves are not exported by the current experiment script.
9. Deployment of the latest `main` commit has not been verified on Render.

## Next experiments

In priority order:

1. Save and plot daily equity curves for every model.
2. Add block-aware resampling or another uncertainty estimate.
3. Re-run the full experiment with multiple seeds and cost assumptions.
4. Replace the survivor universe with point-in-time constituents.
5. Replace simulated headlines with an archived news source.
6. Validate the results through an independent implementation of the accounting and scoring path.

The full machine-readable output is [artifacts/experiments/results.json](artifacts/experiments/results.json). The implementation is [backend/tools/experiment.py](backend/tools/experiment.py).
