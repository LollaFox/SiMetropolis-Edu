import Darwin

func fail(_ message: String) -> Never {
    fputs(message + "\n", stderr)
    exit(1)
}

if LaunchLifetime.replacesLiveClassWindow(role: .helper, status: 1) {
    fail("A reopen helper's failure replaced the live class window. Only LaunchLifetime.replacesLiveClassWindow for the classroom service may do that.")
}
if !LaunchLifetime.replacesLiveClassWindow(role: .service, status: 1) {
    fail("The classroom service exited with a failure and left the live class window in place.")
}
if LaunchLifetime.closesLauncher(role: .helper, status: 0) {
    fail("A reopen helper's exit closed the launcher. Only LaunchLifetime.closesLauncher for the classroom service may do that.")
}
if !LaunchLifetime.closesLauncher(role: .service, status: 0) {
    fail("The classroom service exited and left the launcher running.")
}
if LaunchLifetime.replacesLiveClassWindow(role: .service, status: 0)
    || LaunchLifetime.closesLauncher(role: .service, status: 1) {
    fail("A normal service exit must close the launcher, and a failed service exit must replace the window.")
}
