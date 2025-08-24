import SwiftUI

@main
struct PersonalAssistantApp: App {
    @StateObject private var taskStore = TaskStore()
    @StateObject private var tagStore = TagStore()
    @StateObject private var projectStore = ProjectStore()

    var body: some Scene {
        WindowGroup {
            RootTabView()
                .environmentObject(taskStore)
                .environmentObject(tagStore)
                .environmentObject(projectStore)
        }
    }
}
