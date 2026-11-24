import os


def test_answer_exists():
    work = os.environ.get("CRASHTEST_WORKDIR", ".")
    assert os.path.isfile(os.path.join(work, "answer.txt"))
