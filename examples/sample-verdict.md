# Verdict: "Proven 5-Minute Forex Scalping Strategy for XAUUSD/GOLD"

> Real output of VS Video Reader on a public YouTube video, lightly tidied for the README.
> The extractor ran on an M-series Mac: 5:49 of video → 62 transcript lines + 33 chart frames in about 30 s
> (local Whisper took 7 s). Claude Code then read `index.md` and wrote this file.

**Source:** YouTube · uploaded 2022-12-02 · 5:49 · https://www.youtube.com/watch?v=fSp-jMvNOhE
**Read:** 2026-10-27 · words: local Whisper large-v3-turbo (en) · 33 frames

## One line

A top-down 20/50 MA trend-following short on gold (monthly → weekly → daily → 4H → 5M), entered on a 5M bearish
engulfing of both MAs with a fixed 750-tick stop and 1500-tick target. One hand-picked example, shown after the fact;
the video explains the method well but proves nothing about its edge.

## The strategy, literally

| Part | What the presenter does |
|---|---|
| Indicators | Two simple moving averages, 20 and 50, on every timeframe; Stochastic RSI (default) as a last check |
| Bias | Monthly double top broken, close below the 50 MA → bearish. Weekly: MAs above price. Daily: pullback, "MAs already broke on the higher TFs". 4H: break below the 50 MA, head-and-shoulders neckline broken |
| Target zone | A 4H support area below ("where the 4H candles are heading") |
| Entry | 5M: price breaks both MAs to the downside, a bearish engulfing candle swallows the previous bullish one near the MAs → sell |
| Filter | Stochastic RSI above the 50 line = "overbought, likely to dip" |
| SL | 750 ticks = $7.50 on XAUUSD, "a little space above the MAs" because gold spikes |
| TP | 1500 ticks = $15.00, placed at the 4H support (2:1) |
| Management | At half the target close 50 % of the lot, move SL to entry or halve it, let the rest run |

## Chart vs speech

| Time | Said | The chart showed |
|---|---|---|
| 04:11 | "750 ticks should be sufficient … a 2 to 1 risk to reward" | The position tool on screen reads **Stop 4.67 (467 ticks), Risk/Reward 3.21**. He had just dragged the stop to "just below the moving averages" to show the tighter alternative; the words and the picture are two different trades |
| 05:04 | "we nearly reached our take profit … 1333 ticks instead of 1500, that's totally okay" | Replay tool reads Stop 7.50 · Target 15.00 · ratio 2 and the target was **not** hit. Shown as a win because partials would have been taken; no partial is marked on the chart |
| 01:21 | "on the daily we're on a pullback although the MAs are below the candles" | Correct on the frame: daily price is above both MAs. A strict reading of his own rule says the daily is not bearish yet; he overrides it with the monthly/weekly |

## Strong points to catch

1. **Top-down alignment with a visible, mechanical rule.** Every timeframe is judged by the same two things:
   price vs the 50 MA, and a structure break. Easy to code, easy to audit.
2. **Target at a higher-timeframe level, not a fixed R.** The 4H support decides the TP; the stop is sized to make it
   at least 2:1. That ordering (target first, then check the stop fits) is sound.
3. **The 5M engulfing of both MAs** as the trigger is a clean, testable entry definition.
4. **A spike cushion on gold.** Leaving the stop above the MAs rather than at them is a real gold-specific point.

## Weak points and what the video doesn't show

- One example, chosen after the fact, on a 2022 chart. No count of trades, no losers, no win rate, no drawdown.
- The "proven" in the title is never backed by a number.
- The stop shown (4.67) and the stop said (7.50) differ by 60 %; a viewer copying the screen gets a different trade
  from one copying the words.
- The Stochastic RSI reading at 04:27 is called "overbought" while above the 50 line; that is "above mid", not overbought
  (overbought on this indicator is 80+).
- Management is described (partials, break-even) but never applied in the example.

## Verdict per trading style

| Style | What it gives | Evidence / next test |
|---|---|---|
| **Swing** | The monthly/weekly/daily bias half is usable as a direction filter for multi-day gold trades | Not measured. Test: daily close vs 50 MA as the only bias rule, last 6 months |
| **Intraday** | The whole system as shown: 4H bias + 5M engulfing of both MAs, SL $7.50, TP at the 4H level ≥ 2:1 | Not measured. Test: count every 5M engulfing-of-both-MAs in 4H-bias direction, fixed $7.50 stop |
| **Scalping** | Only the trigger candle. A $7.50 stop and a $15 target are not scalping sizes on gold | Not measured. Test: same trigger with a $3 stop, 1:1, time-boxed exit |

**Next step if you want it:** backtest the intraday version on your own data before any live trade. Nothing here is
financial advice.
