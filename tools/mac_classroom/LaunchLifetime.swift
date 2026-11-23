enum ClassroomProcessRole {
    case service
    case helper
}

enum LaunchLifetime {
    static func replacesLiveClassWindow(role: ClassroomProcessRole, status: Int32) -> Bool {
        role == .service && status != 0
    }

    static func closesLauncher(role: ClassroomProcessRole, status: Int32) -> Bool {
        role == .service && status == 0
    }
}
