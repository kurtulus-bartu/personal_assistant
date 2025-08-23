import SwiftUI

public struct MorePage: View {
    public init() {}
    public var body: some View {
        ZStack { Theme.primaryBG.ignoresSafeArea()
            List {
                Section("Yakında") {
                    Text("Günlük (Journal)")
                    Text("Planlayıcı / Kanban")
                    Text("Performans Raporları")
                }
            }.scrollContentBackground(.hidden)
        }
    }
}
