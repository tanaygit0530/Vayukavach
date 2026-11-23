from run import main


def test_no_args_prints_usage(capsys):
    assert main(["run.py"]) == 0
    assert "usage" in capsys.readouterr().out


def test_unknown_job_fails():
    assert main(["run.py", "does-not-exist"]) == 1
