from ezvals import eval, EvalResult


@eval(dataset="fixture_dataset", labels=["test", "fixture"])
def test_fixture_function():
    return EvalResult(
        input="fixture_input",
        output="fixture_output",
        scores={"key": "accuracy", "value": 1.0}
    )


@eval(dataset="another_dataset", labels=["production"])
async def async_fixture_function():
    return EvalResult(
        input="async_input",
        output="async_output"
    )


@eval()
def test_no_params():
    return [
        EvalResult(input="1", output="a"),
        EvalResult(input="2", output="b")
    ]


# This function should not be discovered
def not_an_eval_function():
    return "not eval"
