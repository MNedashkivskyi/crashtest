import os


def test_answer_is_42():
    work = os.environ.get("CRASHTEST_WORKDIR", ".")
    path = os.path.join(work, "answer.txt")
    assert os.path.isfile(path), "answer.txt not produced"
    assert open(path).read().strip() == "42"
