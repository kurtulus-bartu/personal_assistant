import SwiftUI

private struct KanbanColumn: View {
    var title: String
    var tasks: [PlannerTask]
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .foregroundColor(Theme.text)
                .font(.headline)
            ScrollView {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(tasks) { task in
                        Text(task.title)
                            .padding(8)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Theme.secondaryBG)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .foregroundColor(Theme.text)
                    }
                }
            }
            .scrollIndicators(.hidden)
            .frame(maxHeight: 200)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.primaryBG)
    }
}

public struct KanbanPage: View {
    @StateObject private var store = TaskStore()
    @State private var selectedTag: String?
    @State private var selectedProject: String?
    public init() {}
    public var body: some View {
        VStack {
            HStack {
                Picker("Tag", selection: $selectedTag) {
                    Text("Tümü").tag(String?.none)
                    ForEach(Array(Set(store.tasks.compactMap { $0.tag })), id: \.self) { t in
                        Text(t).tag(String?.some(t))
                    }
                }
                Picker("Proje", selection: $selectedProject) {
                    Text("Tümü").tag(String?.none)
                    ForEach(Array(Set(store.tasks.compactMap { $0.project })), id: \.self) { p in
                        Text(p).tag(String?.some(p))
                    }
        }
    }
            .padding()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    KanbanColumn(title: "Yapılacak", tasks: filtered(status: "todo"))
                    KanbanColumn(title: "Yapılıyor", tasks: filtered(status: "doing"))
                    KanbanColumn(title: "Bitti", tasks: filtered(status: "done"))
                }
                .padding(.horizontal)
            }
            .scrollIndicators(.hidden)
            .refreshable { await store.syncFromSupabase() }
        }
        .task { await store.syncFromSupabase() }
        .background(Theme.primaryBG.ignoresSafeArea())
    }
    private func filtered(status: String) -> [PlannerTask] {
        store.tasks.filter { task in
            let st = normalizeStatus(task.status)
            return st == status &&
                (selectedTag == nil || task.tag == selectedTag) &&
                (selectedProject == nil || task.project == selectedProject)
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
