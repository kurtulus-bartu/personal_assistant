import SwiftUI

public struct RootTabView: View {
    public init() {}
    public var body: some View {
        TabView {
            HealthDashboardView()
                .tabItem { Label("Sağlık", systemImage: "heart.fill") }
            CalendarPage()
                .tabItem { Label("Takvim", systemImage: "calendar") }
            PomodoroPage()
                .tabItem { Label("Pomodoro", systemImage: "timer") }
            MorePage()
                .tabItem { Label("Diğer", systemImage: "ellipsis.circle") }
        }
        .tint(Theme.accent)
    }
}
