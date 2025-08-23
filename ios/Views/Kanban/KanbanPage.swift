import SwiftUI

private struct KanbanColumn: View {
    var title: String
    var events: [PlannerEvent]
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .foregroundColor(Theme.text)
                .font(.headline)
            ScrollView {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(events) { ev in
                        Text(ev.title)
                            .padding(8)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Theme.secondaryBG)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .foregroundColor(Theme.text)
                    }
                }
            }
            .frame(maxHeight: 200)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.primaryBG)
    }
}

public struct KanbanPage: View {
    @ObservedObject var store: EventStore
    @State private var selectedTag: String?
    @State private var selectedProject: String?
    public init(store: EventStore) { self.store = store }
    public var body: some View {
        VStack {
            HStack {
                Picker("Tag", selection: $selectedTag) {
                    Text("Tümü").tag(String?.none)
                    ForEach(Array(Set(store.events.compactMap { $0.tag })), id: \.self) { t in
                        Text(t).tag(String?.some(t))
                    }
                }
                Picker("Proje", selection: $selectedProject) {
                    Text("Tümü").tag(String?.none)
                    ForEach(Array(Set(store.events.compactMap { $0.project })), id: \.self) { p in
                        Text(p).tag(String?.some(p))
                    }
                }
            }
            .padding()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    KanbanColumn(title: "Yapılacak", events: filtered(status: "todo"))
                    KanbanColumn(title: "Yapılıyor", events: filtered(status: "doing"))
                    KanbanColumn(title: "Bitti", events: filtered(status: "done"))
                }
                .padding(.horizontal)
            }
        }
        .background(Theme.primaryBG.ignoresSafeArea())
    }
    private func filtered(status: String) -> [PlannerEvent] {
        store.events.filter { ev in
            let st = ev.status ?? "todo"
            return st == status &&
                (selectedTag == nil || ev.tag == selectedTag) &&
                (selectedProject == nil || ev.project == selectedProject) &&
                ev.title != ev.tag && ev.title != ev.project
        }
    }
}
