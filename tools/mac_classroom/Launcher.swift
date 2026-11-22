import AppKit
import CryptoKit

private struct Runtime: Decodable {
    let url: URL
    let sha256: String

    static func bundled(in resources: URL) throws -> Runtime {
        let manifest = try Data(contentsOf: resources.appendingPathComponent("runtime.json"))
        let runtimes = try JSONDecoder().decode([String: Runtime].self, from: manifest)
        #if arch(arm64)
        let architecture = "arm64"
        #else
        let architecture = "x86_64"
        #endif
        guard let runtime = runtimes[architecture], runtime.sha256.count == 64,
              runtime.sha256.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else {
            throw SetupError.invalidPackage
        }
        return runtime
    }

    func install(archive: URL, at destination: URL) throws {
        let data = try Data(contentsOf: archive, options: .mappedIfSafe)
        let digest = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        guard digest == sha256 else { throw SetupError.incompleteDownload }

        let files = FileManager.default
        let staging = destination.deletingLastPathComponent().appendingPathComponent(UUID().uuidString)
        try files.createDirectory(at: staging, withIntermediateDirectories: false)
        defer { try? files.removeItem(at: staging) }
        let tar = Process()
        tar.executableURL = URL(fileURLWithPath: "/usr/bin/tar")
        tar.arguments = ["-xzf", archive.path, "-C", staging.path]
        try tar.run()
        tar.waitUntilExit()
        guard tar.terminationStatus == 0, files.isExecutableFile(atPath: Self.python(in: staging).path) else {
            throw SetupError.installationFailed
        }
        do {
            try files.moveItem(at: staging, to: destination)
        } catch {
            if files.isExecutableFile(atPath: Self.python(in: destination).path) { return }
            guard files.fileExists(atPath: destination.path) else { throw error }
            _ = try files.replaceItemAt(destination, withItemAt: staging)
        }
    }

    static func python(in directory: URL) -> URL {
        directory.appendingPathComponent("python/bin/python3")
    }
}

private enum SetupError: LocalizedError {
    case invalidPackage, incompleteDownload, installationFailed, classroomExited

    var errorDescription: String? {
        switch self {
        case .invalidPackage: return "Download a fresh copy of SiMetropolis Edu."
        case .incompleteDownload: return "The download was incomplete or could not be verified."
        case .installationFailed: return "The classroom runtime could not be installed."
        case .classroomExited: return "The classroom could not open in your browser."
        }
    }
}

private final class Launcher: NSObject, NSApplicationDelegate {
    private let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 440, height: 192),
                                  styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
    private let heading = NSTextField(labelWithString: "SiMetropolis Edu")
    private let status = NSTextField(wrappingLabelWithString: "Preparing Long Valley…")
    private let progress = NSProgressIndicator()
    private lazy var action = NSButton(title: "Retry", target: self, action: #selector(setupAction))
    private var classroomProcesses = Set<Process>()
    private var download: URLSessionDownloadTask?
    private var progressTimer: Timer?
    private var quitAfterSetup = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let item = NSMenuItem()
        item.submenu = NSMenu()
        item.submenu?.addItem(withTitle: "Quit SiMetropolis Edu", action: #selector(NSApplication.terminate(_:)),
                              keyEquivalent: "q")
        menu.addItem(item)
        NSApp.mainMenu = menu

        window.title = "Open SiMetropolis Edu"
        window.isReleasedWhenClosed = false
        heading.font = .systemFont(ofSize: 22, weight: .semibold)
        progress.minValue = 0
        progress.maxValue = 1
        progress.setAccessibilityLabel("Classroom runtime download progress")
        progress.isHidden = true
        action.bezelStyle = .rounded
        action.isHidden = true
        let content = NSStackView(views: [heading, status, progress, action])
        content.orientation = .vertical
        content.alignment = .leading
        content.spacing = 12
        content.translatesAutoresizingMaskIntoConstraints = false
        let body = NSView()
        body.addSubview(content)
        NSLayoutConstraint.activate([
            content.leadingAnchor.constraint(equalTo: body.leadingAnchor, constant: 24),
            content.trailingAnchor.constraint(equalTo: body.trailingAnchor, constant: -24),
            content.topAnchor.constraint(equalTo: body.topAnchor, constant: 24),
            status.widthAnchor.constraint(equalTo: content.widthAnchor),
            progress.widthAnchor.constraint(equalTo: content.widthAnchor),
        ])
        window.contentView = body
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        openClassroom()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if classroomProcesses.contains(where: \.isRunning) {
            openClassroom()
        }
        return true
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let download else { return .terminateNow }
        quitAfterSetup = true
        download.cancel()
        return .terminateLater
    }

    func applicationWillTerminate(_ notification: Notification) {
        for process in classroomProcesses where process.isRunning { process.interrupt() }
    }

    @objc private func setupAction() {
        action.isEnabled = false
        if let download {
            download.cancel()
        } else {
            openClassroom()
        }
    }

    private func openClassroom() {
        action.isHidden = true
        status.stringValue = "Preparing Long Valley…"
        do {
            guard let resources = Bundle.main.resourceURL, let id = Bundle.main.bundleIdentifier else {
                throw SetupError.invalidPackage
            }
            let files = FileManager.default
            let support = try files.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                        appropriateFor: nil, create: true).appendingPathComponent(id)
            try files.createDirectory(at: support, withIntermediateDirectories: true,
                                      attributes: [.posixPermissions: 0o700])
            let runtime = try Runtime.bundled(in: resources)
            let destination = support.appendingPathComponent("runtime-\(runtime.sha256)")
            if files.isExecutableFile(atPath: Runtime.python(in: destination).path) {
                try startClassroom(runtimeAt: destination, resources: resources)
            } else {
                downloadRuntime(runtime, to: destination, resources: resources)
            }
        } catch {
            showFailure(error)
        }
    }

    private func downloadRuntime(_ runtime: Runtime, to destination: URL, resources: URL) {
        status.stringValue = "Downloading the classroom runtime…"
        progress.isHidden = false
        progress.isIndeterminate = true
        progress.doubleValue = 0
        progress.startAnimation(nil)
        action.title = "Cancel download"
        action.isHidden = false
        action.isEnabled = true
        action.keyEquivalent = ""
        var request = URLRequest(url: runtime.url, cachePolicy: .reloadIgnoringLocalCacheData)
        request.timeoutInterval = 20
        let task = URLSession.shared.downloadTask(with: request) { archive, response, error in
            let outcome = Result {
                if let error { throw error }
                guard let archive, let response = response as? HTTPURLResponse, response.statusCode == 200 else {
                    throw SetupError.incompleteDownload
                }
                DispatchQueue.main.async {
                    self.action.isHidden = true
                    self.status.stringValue = "Installing the classroom runtime…"
                    self.progress.isIndeterminate = true
                    self.progress.startAnimation(nil)
                }
                try runtime.install(archive: archive, at: destination)
            }
            DispatchQueue.main.async {
                self.download = nil
                self.progressTimer?.invalidate()
                self.progress.isHidden = true
                self.progress.stopAnimation(nil)
                if self.quitAfterSetup {
                    NSApp.reply(toApplicationShouldTerminate: true)
                    return
                }
                do {
                    try outcome.get()
                    try self.startClassroom(runtimeAt: destination, resources: resources)
                } catch {
                    self.showFailure(error)
                }
            }
        }
        download = task
        progressTimer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { [weak self] _ in
            guard let self, task.state == .running, task.countOfBytesExpectedToReceive > 0 else { return }
            let fraction = min(1, Double(task.countOfBytesReceived) / Double(task.countOfBytesExpectedToReceive))
            self.progress.isIndeterminate = false
            self.progress.doubleValue = fraction
            self.status.stringValue = "Downloading the classroom runtime… \(Int(fraction * 100))%"
        }
        task.resume()
    }

    private func startClassroom(runtimeAt destination: URL, resources: URL) throws {
        let lesson = resources.appendingPathComponent("lesson")
        let process = Process()
        process.executableURL = Runtime.python(in: destination)
        process.currentDirectoryURL = destination.deletingLastPathComponent()
        process.arguments = ["-I", "-B", "-c",
                             "import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module('classroom', run_name='__main__', alter_sys=True)",
                             lesson.path, "launch"]
        var environment = ProcessInfo.processInfo.environment
        // Use Launch Services to open the default browser without Apple Events automation permissions.
        if environment["BROWSER"] == nil { environment["BROWSER"] = "/usr/bin/open %s" }
        process.environment = environment
        process.terminationHandler = { finished in
            DispatchQueue.main.async {
                self.classroomProcesses.remove(finished)
                if finished.terminationStatus != 0 {
                    self.showFailure(SetupError.classroomExited)
                } else if self.classroomProcesses.isEmpty {
                    NSApp.terminate(nil)
                }
            }
        }
        try process.run()
        classroomProcesses.insert(process)
        action.isHidden = true
        status.stringValue = "Continue in your browser. Keep this window open while using the classroom."
    }

    private func showFailure(_ error: Error) {
        NSLog("Classroom setup: %@", error.localizedDescription)
        let failure = error as NSError
        if failure.domain == NSURLErrorDomain {
            status.stringValue = failure.code == NSURLErrorCancelled
                ? "Download paused. Select Retry to restart setup."
                : "Download interrupted. Check your internet connection, then select Retry."
        } else {
            status.stringValue = error.localizedDescription
        }
        action.title = "Retry"
        action.isHidden = false
        action.isEnabled = true
        action.keyEquivalent = "\r"
    }
}

let application = NSApplication.shared
private let launcher = Launcher()
application.delegate = launcher
application.setActivationPolicy(.regular)
application.run()
