workflow "Test on push" {
  on = "push"
  resolves = ["Style check"]
}

action "Style check" {
  uses = "bulv1ne/python-style-check@master"
}
