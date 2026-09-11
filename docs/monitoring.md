# Monitoring

The module's error alarms are CloudWatch metric alarms on Lambda's built-in metrics. Whether an alarm can fire at all
depends on two things the module doesn't control: how often the function runs, and how long each run takes. This page
explains how the alarms are evaluated, why a function that runs rarely or for a long time can fail while its alarm stays
green, and how to configure alerting for such functions.

## How Lambda reports errors

- **A datapoint only exists for a minute in which something ran.** Lambda sends metrics when an invocation finishes and
  aggregates them into 1-minute datapoints. A minute with no invocations has no `Invocations` or `Errors` datapoint
  at all. It is missing, not zero.
- **Timeouts are errors.** `Errors` counts exceptions raised by your code and by the runtime, including timeouts.
  Throttled requests count as neither `Invocations` nor `Errors`; the `throttles` alarm covers them.
- **A datapoint is stamped with the minute the invocation started.** In AWS's words, "the timestamp on an error metric
  reflects when the function was invoked, not when the error occurred." The datapoint is published when the invocation
  ends, so a run that fails 12 minutes in produces a datapoint that is already 12 minutes old when it appears.

Source: [Types of metrics for Lambda functions](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html).

## How CloudWatch evaluates an alarm

Each error alarm is defined by four settings:

| Setting | Meaning | `errors_immediate` | `errors_threshold` |
|---|---|---|---|
| Period | Time span of one datapoint | 60 s | `error_rate_period` (default 60 s) |
| Evaluation periods (N) | How many recent datapoints are judged | `ceil(timeout / 60) + 5` | `error_rate_evaluation_periods` (default 2) |
| Datapoints to alarm (M) | How many of those must breach | 1 | `error_rate_datapoints_to_alarm` (default 2) |
| Missing data | How a period without a datapoint counts | Not breaching | Not breaching |

A datapoint breaches when `Errors > 0` for `errors_immediate`, and when `errors / invocations * 100` exceeds
`error_rate_threshold` for `errors_threshold`.

Each time CloudWatch evaluates an alarm, it retrieves datapoints over an *evaluation range* that is somewhat longer
than N periods, and then:

1. Takes the N most recent **real** datapoints in the range, reaching back past missing periods if needed.
2. If the range holds fewer than N real datapoints, fills the shortfall with missing periods. This module counts those
   as not breaching.
3. Goes to `ALARM` if at least M of the N datapoints breach.

Two consequences matter for Lambda:

- **A datapoint outside the evaluation range is never judged.** If it arrives after its minute has left the range, the
  alarm ignores it, however bad it is.
- **The range is longer than N periods, and AWS doesn't publish its size.** Measured with 60-second periods
  (backdated custom metrics, September 2026, `tests/tools/probe_alarm_range.py`): CloudWatch used datapoints up to
  **6 minutes old** and ignored anything older, both for a 1-of-1 alarm and for a 2-of-2 one. That matches what this module sees in practice, where a
  single-period alarm caught errors reported 1 to 3 minutes late and missed errors reported 12 minutes late. Treat the
  number as an observation, not a contract: size periods so the alarm doesn't depend on it.

Source: [How alarm state is evaluated when data is missing](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/alarms-and-missing-data.html#alarms-evaluating-missing-data).

## Sparse invocations

A function is *sparse* when the gap between its invocations is longer than its alarm period: scheduled jobs, deploy
hooks, anything triggered a few times an hour or a day.

### Why the threshold alarm stays green

Take a function scheduled every 30 minutes that fails on every run, with `alert_strategy = "threshold"` and the default
settings: a 60-second period, N = 2 and M = 2. Each run produces one breaching datapoint, followed by 29 minutes with no
datapoints:

```text
minute        :00  :01  :02  ...  :29  :30  :31  :32  ...
datapoint      X    -    -   ...   -    X    -    -   ...

X  breaching (error rate 100 %)
-  missing (no invocation)
```

Whenever the alarm evaluates, its range holds at most one real datapoint, because the previous run is 30 minutes back.
CloudWatch fills the second datapoint it needs with a not-breaching value, so only 1 of 2 breaches and the alarm stays
`OK`. It stays `OK` for as long as the function keeps failing
([#25](https://github.com/infrahouse/terraform-aws-lambda-monitored/issues/25)).

A shorter schedule only hides the problem. With the measured 6-minute range, the default period pairs up failures less
than about 7 minutes apart and gives up beyond that, so a function scheduled every 5 minutes alarms today and the same
function moved to a 10-minute schedule silently stops alarming.

### The rule: every period must contain a run

The threshold alarm works when each `error_rate_period` contains at least one invocation. Every period then has a real
datapoint, the missing-data setting never applies, and N and M count periods that each include a run. Set:

```text
error_rate_period >= longest normal gap between invocations
```

### Configuring a sparse function

**Every run should succeed: use `immediate`.** A single breaching datapoint is enough, so any failed run alarms,
however rarely the function runs. This is the simplest choice for scheduled jobs.

```hcl
alert_strategy = "immediate"
```

**Some failed runs are acceptable: use `threshold` with a period that spans the schedule.** For a job that runs every
30 minutes and should alarm after two failed runs in a row:

```hcl
alert_strategy                 = "threshold"
error_rate_period              = 1800 # each 30-minute period contains one run
error_rate_threshold           = 0    # a period breaches if any run in it failed
error_rate_evaluation_periods  = 2
error_rate_datapoints_to_alarm = 2    # two failing periods in a row
```

With one run per period, the error rate is either 0 % or 100 %, so N and M do the work. For "2 failed runs out of the
last 4", set `error_rate_evaluation_periods = 4` and `error_rate_datapoints_to_alarm = 2`. Expect the alarm within
roughly M × `error_rate_period` of the first failed run.

**Rare or irregular invocations: use `immediate`.** If the gap between invocations ranges from minutes to days, no
single period fits, and a period long enough to span the longest gap would average errors over hours.

## Long-running invocations

Because a datapoint carries its invocation's start minute, a run that lasts close to `timeout` reports its result
roughly `timeout` late. The alarm catches it only if that minute is still inside the evaluation range when the datapoint
arrives.

**`errors_immediate` sizes its window from `timeout`.** It evaluates `ceil(timeout / 60) + 5` one-minute periods: enough
for a run that ends at `timeout`, plus the offset within the start minute, publishing lag and evaluation delay
([#33](https://github.com/infrahouse/terraform-aws-lambda-monitored/issues/33)). An error still alarms as soon as its
datapoint exists. The trade-off: after a single error the alarm stays in `ALARM` until that minute leaves the window,
about 6 minutes at the default 60-second timeout and 20 minutes at 900 seconds, and further errors in that time don't
send a new notification.

**`errors_threshold` needs `error_rate_period` of at least `timeout`.** With 1-minute periods, a run longer than the
6-minute range reports after its minute has dropped out of it, so its errors are never judged, however many runs fail.
A period at least as long as `timeout` keeps each run's datapoint inside the alarm's window: the window covers the last
N × `error_rate_period` before each evaluation, and a run reports at most `timeout` plus a minute or so after the minute
it is stamped with. Measured with a 540-second period: a datapoint 18 minutes old, two periods back, still counted
towards the alarm. Combined with the sparse rule:

```text
error_rate_period >= max(longest normal gap between invocations, timeout)
```

## Choosing settings

| How the function runs | Strategy | Settings |
|---|---|---|
| Steady traffic (at least one invocation a minute), `timeout` ≤ 60 s | `threshold` or `immediate` | Defaults |
| Any pattern, every run must succeed | `immediate` | Defaults |
| Scheduled, some failed runs are acceptable | `threshold` | `error_rate_period` ≥ schedule interval and ≥ `timeout` |
| Steady traffic, long runs, some failures acceptable | `threshold` | `error_rate_period` ≥ `timeout` |
| Rare or irregular | `immediate` | Defaults |

## What the alarms don't catch

**A function that stops running.** No invocations means no datapoints, and missing data counts as not breaching, so
every alarm stays `OK`. Detecting a missed scheduled run needs a separate alarm on `Invocations` that treats an empty
period as a failure. The module doesn't create one.
