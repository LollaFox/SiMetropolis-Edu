import AppKit

let application = NSApplication.shared
private let launcher = Launcher()
application.delegate = launcher
application.setActivationPolicy(.regular)
application.run()
