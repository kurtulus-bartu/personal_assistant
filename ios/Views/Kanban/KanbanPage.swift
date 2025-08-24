import SwiftUI
import UniformTypeIdentifiers

private struct TaskCard: View {
    var task: PlannerTask
    private static let df: DateFormatter = {
        let d = DateFormatter()
        d.dateStyle = .short
        return d
    }()
    var body: some View {
        HStack {
            HStack(spacing: 0) {
                Text(task.title)
                    .foregroundColor(Theme.text)
                if let meta = metaText {
                    Text(" (\(meta))")
                        .foregroundColor(Theme.textMuted)
                }
            }
            Spacer()
            if let due = task.due {
                Text(Self.df.string(from: due))
                    .font(.footnote)
                    .foregroundColor(Theme.text)
            }
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
        if let parent = task.parent { parts.append(parent) }
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
            HStack {
                Text(title)
                    .foregroundColor(Theme.text)
                    .font(.headline)
                Spacer()
                Text("\(tasks.count)")
                    .foregroundColor(Theme.textMuted)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(Theme.primaryBG)
                    .clipShape(RoundedRectangle(cornerRadius: 4))
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(tasks) { task in
                        TaskCard(task: task)
                            .onDrag { NSItemProvider(object: String(task.id) as NSString) }
                    }
                }
                .padding(8)
            }
            .frame(minHeight: 240)
            .background(Theme.secondaryBG)
            .clipShape(RoundedRectangle(cornerRadius: 8))
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
                let idString: String? =
                    (item as? Data).flatMap { String(data: $0, encoding: .utf8) } ??
                    (item as? String) ??
                    (item as? NSString).map { String($0) }
                if let id = idString.flatMap(Int.init) {
                    DispatchQueue.main.async { onDropTask(id) }
                }
            }
            return true
        }
    }
}

public struct KanbanPage: View {
    @ObservedObject var taskStore: TaskStore
    @ObservedObject var tagStore: TagStore
    @ObservedObject var projectStore: ProjectStore
    @State private var selectedTag: String?
    @State private var selectedProject: String?
    @State private var showingAddTask = false
    @State private var isRefreshing = false
    
    public init(taskStore: TaskStore, tagStore: TagStore, projectStore: ProjectStore) {
        self.taskStore = taskStore
        self.tagStore = tagStore
        self.projectStore = projectStore
    }
    
    public var body: some View {
        VStack {
            // Filtre bölümü
            VStack(spacing: 8) {
                HStack {
                    Picker("Tag", selection: $selectedTag) {
                        Text("Tüm Tagler").tag(String?.none)
                        ForEach(tagStore.tags, id: \.id) { tag in
                            Text(tag.name).tag(String?.some(tag.name))
                        }
                    }
                    .pickerStyle(.menu)
                    
                    Picker("Proje", selection: $selectedProject) {
                        Text("Tüm Projeler").tag(String?.none)
                        ForEach(projectStore.projects, id: \.id) { project in
                            Text(project.name).tag(String?.some(project.name))
                        }
                    }
                    .pickerStyle(.menu)
                    
                    Spacer()
                    
                    Button(action: {
                        Task {
                            isRefreshing = true
                            await refreshData()
                            isRefreshing = false
                        }
                    }) {
                        Image(systemName: isRefreshing ? "arrow.clockwise" : "arrow.down.circle")
                            .rotationEffect(isRefreshing ? .degrees(360) : .degrees(0))
                            .animation(isRefreshing ? Animation.linear(duration: 1).repeatForever(autoreverses: false) : .default, value: isRefreshing)
                    }
                    .disabled(isRefreshing)
                }
                .padding(.horizontal)
                .padding(.top, 8)
                
                if selectedTag != nil || selectedProject != nil {
                    HStack {
                        Text("Aktif filtreler:")
                            .font(.caption)
                            .foregroundColor(Theme.textMuted)
                        if let tag = selectedTag {
                            Text(tag)
                                .font(.caption)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 2)
                                .background(Theme.accent.opacity(0.2))
                                .foregroundColor(Theme.accent)
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                        }
                        if let project = selectedProject {
                            Text(project)
                                .font(.caption)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 2)
                                .background(Theme.accent.opacity(0.2))
                                .foregroundColor(Theme.accent)
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                        }
                        Spacer()
                        Button("Temizle") {
                            selectedTag = nil
                            selectedProject = nil
                        }
                        .font(.caption)
                        .foregroundColor(Theme.accent)
                    }
                    .padding(.horizontal)
                }
            }
            .padding(.bottom, 8)
            .background(Theme.primaryBG)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Theme.secondaryBG, lineWidth: 1)
            )
            .padding(.horizontal)
            
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

            Button(action: {
                showingAddTask = true
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
        .task {
            await refreshData()
        }
        .sheet(isPresented: $showingAddTask) {
            AddTaskSheet(
                taskStore: taskStore,
                tagStore: tagStore,
                projectStore: projectStore,
                preSelectedTag: selectedTag,
                preSelectedProject: selectedProject
            )
        }
        .background(Theme.primaryBG.ignoresSafeArea())
    }

    private func filtered(status: String) -> [PlannerTask] {
        taskStore.tasks.filter { task in
            guard normalizeStatus(task.status) == status else { return false }
            
            if let selectedTag = selectedTag {
                guard task.tag == selectedTag else { return false }
            }
            
            if let selectedProject = selectedProject {
                guard task.project == selectedProject else { return false }
            }
            
            return true
        }
    }

    private func moveTask(_ id: Int, to status: String) {
        if let idx = taskStore.tasks.firstIndex(where: { $0.id == id }) {
            taskStore.tasks[idx].status = status
            taskStore.save()
            Task { await taskStore.backupToSupabase() }
        }
    }
    
    private func refreshData() async {
        await taskStore.syncFromSupabase()
        await tagStore.syncFromSupabase()
        await projectStore.syncFromSupabase()
    }

    private func normalizeStatus(_ raw: String?) -> String {
        let s = raw?.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() ?? ""
        if ["todo","to-do","to do","backlog","open","not started","not_started","new","ns","bekliyor","yapilacak","yapılacak"].contains(s) {
            return "todo"
        }
        if ["doing","in progress","in_progress","progress","wip","calisiyor","çalışıyor","yapiliyor","yapılıyor"].contains(s) {
            return "doing"
        }
        if ["done","completed","complete","finished","bitti","closed","resolved","tamamlandi","tamamlandı"].contains(s) {
            return "done"
        }
        return "todo"
    }
}

private struct AddTaskSheet: View {
    @ObservedObject var taskStore: TaskStore
    @ObservedObject var tagStore: TagStore
    @ObservedObject var projectStore: ProjectStore
    
    @State private var title = ""
    @State private var notes = ""
    @State private var selectedStatus = "todo"
    @State private var selectedTag: String?
    @State private var selectedProject: String?
    @State private var hasDueDate = false
    @State private var dueDate = Date()
    
    var preSelectedTag: String?
    var preSelectedProject: String?
    
    @Environment(\.dismiss) private var dismiss
    
    private let statusOptions = [
        ("todo", "Yapılacak"),
        ("doing", "Yapılıyor"),
        ("done", "Bitti")
    ]
    
    var body: some View {
        NavigationView {
            Form {
                Section("Görev Bilgileri") {
                    TextField("Görev başlığı", text: $title)
                    TextField("Notlar (isteğe bağlı)", text: $notes, axis: .vertical)
                        .lineLimit(3...6)
                }
                
                Section("Kategori") {
                    Picker("Durum", selection: $selectedStatus) {
                        ForEach(statusOptions, id: \.0) { status, label in
                            Text(label).tag(status)
                        }
                    }
                    
                    Picker("Tag", selection: $selectedTag) {
                        Text("Tag Seçilmedi").tag(String?.none)
                        ForEach(tagStore.tags, id: \.id) { tag in
                            Text(tag.name).tag(String?.some(tag.name))
                        }
                    }
                    
                    Picker("Proje", selection: $selectedProject) {
                        Text("Proje Seçilmedi").tag(String?.none)
                        ForEach(projectStore.projects, id: \.id) { project in
                            Text(project.name).tag(String?.some(project.name))
                        }
                    }
                }
                
                Section("Zaman") {
                    Toggle("Bitiş tarihi ekle", isOn: $hasDueDate)
                    if hasDueDate {
                        DatePicker("Bitiş tarihi", selection: $dueDate, displayedComponents: .date)
                    }
                }
            }
            .navigationTitle("Yeni Görev")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("İptal") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Kaydet") {
                        saveTask()
                    }
                    .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .onAppear {
                selectedTag = preSelectedTag
                selectedProject = preSelectedProject
            }
        }
    }
    
    private func saveTask() {
        let tagId = selectedTag.flatMap { tagName in
            tagStore.tags.first { $0.name == tagName }?.id
        }
        
        let projectId = selectedProject.flatMap { projectName in
            projectStore.projects.first { $0.name == projectName }?.id
        }
        
        let newTask = PlannerTask(
            title: title.trimmingCharacters(in: .whitespacesAndNewlines),
            notes: notes.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : notes.trimmingCharacters(in: .whitespacesAndNewlines),
            status: selectedStatus,
            tagId: tagId,
            tag: selectedTag,
            projectId: projectId,
            project: selectedProject,
            due: hasDueDate ? dueDate : nil,
            hasTime: false
        )
        
        taskStore.tasks.append(newTask)
        taskStore.save()
        
        Task {
            await taskStore.backupToSupabase()
        }
        
        dismiss()
    }
}
