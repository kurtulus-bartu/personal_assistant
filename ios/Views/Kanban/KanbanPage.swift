import SwiftUI

private struct KanbanColumn: View {
    var title: String
    var events: [PlannerEvent]
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .foregroundColor(Theme.text)
                .font(.headline)
            ForEach(events) { ev in
                Text(ev.title)
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.secondaryBG)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .foregroundColor(Theme.text)
            }
            Spacer()
        }
        .padding()
        .frame(width: 200)
        .background(Theme.primaryBG)
    }
}

public struct KanbanPage: View {
    @ObservedObject var store: EventStore
    public init(store: EventStore) { self.store = store }
    public var body: some View {
        ScrollView(.horizontal) {
            HStack(alignment: .top, spacing: 12) {
                KanbanColumn(title: "Yapılacak", events: store.events.filter { $0.status == "todo" || $0.status == nil })
                KanbanColumn(title: "Yapılıyor", events: store.events.filter { $0.status == "doing" })
                KanbanColumn(title: "Bitti", events: store.events.filter { $0.status == "done" })
            }
            .padding()
        }
        .background(Theme.primaryBG.ignoresSafeArea())
    }
}
