# Q141-A13 — non-overlapping lag-2 structural transitions

## Mechanical issue addressed

For a level series X[t], adjacent first differences D[t]=X[t]-X[t-1] and
D[t-1] share X[t-1]. Under IID levels this creates negative lag-1 dependence
without any predictable lottery mechanism. Q141-A12 documented this for
sum and range.

## A13 construction

A13 tests whether D[t-2] predicts D[t]. These two differences use disjoint
level observations: D[t-2] uses X[t-2], X[t-3], while D[t] uses X[t], X[t-1].

To prevent training examples from sharing raw draw rows with each other or
with the target, only prior transition endpoints s congruent to t modulo 4
are used. Each training example consumes rows [s-3,s], examples are spaced
by four rows, and the final training endpoint is at most t-4. The target
block is [t-3,t]. Thus all four-draw blocks are disjoint.

The expanding marginal baseline uses exactly the same phase-matched sample
as the lag-2 transition model. This isolates incremental transition
information, at the cost of using about one quarter of available history.

## Interpretation

The historical walk-forward and IID 5-of-40 simulation are exploratory.
Even a positive result would require a separately frozen prospective test.
A13 predicts only sum/range transition categories; it does not predict
individual numbers or exact tickets.
