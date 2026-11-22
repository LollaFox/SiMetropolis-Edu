import AppKit
import ApplicationServices

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

func waitFor(_ description: String, until ready: () -> Bool) {
    let deadline = Date().addingTimeInterval(12)
    while !ready() {
        guard Date() < deadline else { fail("Timed out waiting for " + description) }
        RunLoop.current.run(until: Date().addingTimeInterval(0.1))
    }
}

func attribute(_ element: AXUIElement, _ key: String) -> CFTypeRef? {
    var value: CFTypeRef?
    AXUIElementCopyAttributeValue(element, key as CFString, &value)
    return value
}

func retryButton(in element: AXUIElement) -> AXUIElement? {
    if attribute(element, kAXRoleAttribute) as? String == kAXButtonRole,
       attribute(element, kAXTitleAttribute) as? String == "Retry",
       attribute(element, kAXEnabledAttribute) as? Bool == true {
        return element
    }
    for child in attribute(element, kAXChildrenAttribute) as? [AXUIElement] ?? [] {
        if let button = retryButton(in: child) { return button }
    }
    return nil
}

let action = CommandLine.arguments[1]
let bundle = URL(fileURLWithPath: CommandLine.arguments[2]).resolvingSymlinksInPath()
guard let identifier = Bundle(url: bundle)?.bundleIdentifier,
      let app = NSRunningApplication.runningApplications(withBundleIdentifier: identifier).first(where: {
          $0.bundleURL?.resolvingSymlinksInPath().path == bundle.path
      }) else { fail("Test launcher is not running at " + bundle.path) }

switch action {
case "quit":
    guard app.terminate() else { fail("macOS declined the test launcher's Quit request") }
    waitFor("the test launcher to quit") { app.isTerminated }
case "wait-for-retry", "retry":
    guard AXIsProcessTrusted() else { exit(77) } // EX_NOPERM. Do not prompt for Accessibility access.
    let target = AXUIElementCreateApplication(app.processIdentifier)
    waitFor("the enabled Retry button") {
        let windows = attribute(target, kAXWindowsAttribute) as? [AXUIElement] ?? []
        for window in windows {
            if let button = retryButton(in: window) {
                return action == "wait-for-retry" || AXUIElementPerformAction(button, kAXPressAction as CFString) == .success
            }
        }
        return false
    }
default:
    fail("Unknown test action: " + action)
}
