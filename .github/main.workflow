workflow "Test on push" {
  on = "push"
  resolves = [
    "Style check",
    "Pipenv run test",
  ]
}

action "Style check" {
  uses = "bulv1ne/python-style-check@master"
}

action "Pipenv install" {
  uses = "peaceiris/actions-pipenv@3.7"
  args = "sync -d"
}

action "Pipenv run test" {
  uses = "peaceiris/actions-pipenv@3.7"
  needs = ["Pipenv install"]
  args = "run test"
  secrets = ["AWS_ACCESS_KEY_ID", "AWS_DEFAULT_REGION", "AWS_SECRET_ACCESS_KEY", "TC_THIS_BUCKET"]
}
