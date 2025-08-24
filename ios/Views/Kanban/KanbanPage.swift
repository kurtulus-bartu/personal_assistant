import SwiftUI
import UniformTypeIdentifiers

private struct TaskCard: View {
    var task: PlannerTask
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(task.title)
                    .foregroundColor(Theme.text)
                if let meta = metaText {
                    Text(meta)
                        .font(.footnote)
                        .foregroundColor(Theme.textMuted)
                }
            }
            Spacer()
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.secondaryBG)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
    private var metaText: String? {
        var parts: [String] = []
        if let tag = task.tag { parts.append(tag) }
        if let project = task.project { parts.append(project) }
        return parts.isEmpty ? nil : parts.joined(separator: " > ")
    }
}

private struct KanbanColumn: View {
    var title: String
    var status: String
    var tasks: [PlannerTask]
    var onDropTask: (Int) -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .foregroundColor(Theme.text)
                .font(.headline)
            VStack(alignment: .leading, spacing: 8) {
                ForEach(tasks) { task in
                    TaskCard(task: task)
                        .onDrag { NSItemProvider(object: String(task.id) as NSString) }
                }
            }
            .onDrop(of: [.text], delegate: DropHandler(onDropTask: onDropTask))
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.primaryBG)
    }
    private struct DropHandler: DropDelegate {
        var onDropTask: (Int) -> Void
        func performDrop(info: DropInfo) -> Bool {
            guard let provider = info.itemProviders(for: [.text]).first else { return false }
            provider.loadItem(forTypeIdentifier: UTType.text.identifier, options: nil) { item, _ in
                if let data = item as? Data,
                   let str = String(data: data, encoding: .utf8),
                   let id = Int(str) {
                    DispatchQueue.main.async { onDropTask(id) }
                }
            }
            return true
        }
    }
}

public struct KanbanPage: View {
    @StateObject private var store = TaskStore()
    public init() {}
    public var body: some View {
        VStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    KanbanColumn(title: "Yapılacak", status: "todo",
                                 tasks: filtered(status: "todo"),
                                 onDropTask: { moveTask($0, to: "todo") })
                    KanbanColumn(title: "Yapılıyor", status: "doing",
                                 tasks: filtered(status: "doing"),
                                 onDropTask: { moveTask($0, to: "doing") })
                    KanbanColumn(title: "Bitti", status: "done",
                                 tasks: filtered(status: "done"),
                                 onDropTask: { moveTask($0, to: "done") })
                }
                .padding(.horizontal)
            }
            .scrollIndicators(.hidden)
            .refreshable {
                await store.backupToSupabase()
                await store.syncFromSupabase()
            }

            Button(action: {
                // TODO: Görev ekleme
            }) {
                Text("Görev Ekle")
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Theme.accent)
                    .foregroundColor(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            .padding()
        }
        .task { await store.syncFromSupabase() }
        .background(Theme.primaryBG.ignoresSafeArea())
    }

    private func filtered(status: String) -> [PlannerTask] {
        store.tasks.filter { normalizeStatus($0.status) == status }
    }

    private func moveTask(_ id: Int, to status: String) {
        if let idx = store.tasks.firstIndex(where: { $0.id == id }) {
            store.tasks[idx].status = status
            store.save()
            Task { await store.backupToSupabase() }
        }
    }

    // "todo" / "doing" / "done" normalizasyonu
    private func normalizeStatus(_ raw: String?) -> String {
        let s = raw?.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() ?? ""
        if ["todo","to-do","to do","backlog","open","not started","not_started","new","ns","bekliyor","yapılacak"].contains(s) {
            return "todo"
        }
        if ["doing","in progress","in_progress","progress","wip","çalışılıyor","yapılıyor"].contains(s) {
            return "doing"
        }
        if ["done","completed","complete","finished","bitti","closed","resolved","tamamlandı"].contains(s) {
            return "done"
        }
        return "todo"
    }
}
