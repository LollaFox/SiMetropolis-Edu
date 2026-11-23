import Foundation

@main
struct LaunchLifetimeCheck {
    enum WindowAction: Equatable {
        case showFailure, closeLauncher
    }

    @MainActor
    static func check(_ role: ClassroomProcessRole, status: Int32, expecting expected: [WindowAction]) throws {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: status == 0 ? "/usr/bin/true" : "/usr/bin/false")
        var handled = false
        var actions: [WindowAction] = []
        try Launcher.runClassroomProcess(process, role: role, didFinish: { finished in
            precondition(finished === process && finished.terminationStatus == status)
            handled = true
        }, showClassroomFailure: {
            actions.append(.showFailure)
        }, closeLauncher: {
            actions.append(.closeLauncher)
        })

        let deadline = Date().addingTimeInterval(5)
        while !handled && Date() < deadline {
            RunLoop.main.run(until: Date().addingTimeInterval(0.01))
        }
        guard handled, actions == expected else {
            fputs("\(role) exit \(status): expected \(expected), recorded \(actions), handled=\(handled)\n", stderr)
            exit(1)
        }
    }

    @MainActor
    static func main() throws {
        try check(.helper, status: 0, expecting: [])
        try check(.helper, status: 1, expecting: [])
        try check(.service, status: 0, expecting: [.closeLauncher])
        try check(.service, status: 1, expecting: [.showFailure])
    }
}
