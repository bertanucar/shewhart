# Contributing

Thanks for looking. shewhart is small on purpose, and it is meant to stay
correct, so a few rules shape what gets merged.

## Setup

```bash
git clone https://github.com/bertanucar/shewhart
cd shewhart
pip install -e .
pip install pytest
python -m pytest
```

The suite runs in a few seconds and must stay green on Python 3.10 through
3.12.

## The grammar is frozen

The public surface on the [API page](docs/reference/api.md) is a covenant.
From 0.1 on, no public name, function signature, default value, or string
alias is removed or changes meaning within a major version. The reason is
boring and non-negotiable: changed defaults change numbers, and people run
this in audits and cron jobs. Names planned for later versions are already
listed on that page and will appear exactly as written.

New analyses are welcome. New ways to spell an existing one, or a default
that shifts a result, are not.

## Numbers get validated, not asserted

Every statistic shewhart reports is checked against an external reference:
a NIST-certified value, a published worked example, or a hand-derived case
with the derivation in the test. A pull request that adds a computation
without a reference anchor will be asked for one. If a reference value comes
from a copyrighted source, cite it and reproduce the input independently
rather than copying the table.

See [Validation](docs/reference/validation.md) for the existing anchors and
the policy.

## Style

* Errors teach. Every exception ends with a corrected, runnable example.
* Comments explain the non-obvious math or a constraint, nothing else.
* Statistics and presentation stay separate: computation returns a `Result`,
  rendering lives in `plot()` and the report functions.
* Match the surrounding code. It is terse and declarative; keep it that way.

## Reporting bugs

Open an [issue](https://github.com/bertanucar/shewhart/issues) with a
minimal example, the result you got, and the result you expected. A wrong
number with a reproduction is the most useful report there is.

## License

By contributing you agree that your contribution is licensed under the MIT
license, the same as the project.
