import Foundation
import SwiftUI

public extension Notification.Name {
    static let dataDidSync = Notification.Name("dataDidSync")
    static let tasksDidUpdate = Notification.Name("tasksDidUpdate")
    static let tagsDidUpdate = Notification.Name("tagsDidUpdate")
    static let projectsDidUpdate = Notification.Name("projectsDidUpdate")
    static let eventsDidUpdate = Notification.Name("eventsDidUpdate")
}

public extension ObservableObject {
    func postUpdateNotification(for type: String) {
        DispatchQueue.main.async {
            NotificationCenter.default.post(
                name: Notification.Name("\(type)DidUpdate"),
                object: nil
            )
        }
    }
}

@MainActor
public class SyncStatusManager: ObservableObject {
    @Published public var isRefreshing = false
    @Published public var isBackingUp = false
    @Published public var lastSyncDate: Date?
    @Published public var syncError: String?
    
    public static let shared = SyncStatusManager()
    private init() {}
    
    public func startRefresh() {
        isRefreshing = true
        syncError = nil
    }
    
    public func finishRefresh(error: String? = nil) {
        isRefreshing = false
        if error == nil {
            lastSyncDate = Date()
        }
        syncError = error
        NotificationCenter.default.post(name: .dataDidSync, object: nil)
    }
    
    public func startBackup() {
        isBackingUp = true
        syncError = nil
    }
    
    public func finishBackup(error: String? = nil) {
        isBackingUp = false
        if error == nil {
            lastSyncDate = Date()
        }
        syncError = error
    }
}
