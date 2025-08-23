import SwiftUI

public struct CalendarPage: View {
    @StateObject private var store = EventStore()
    @State private var selectedDate = Date()
    @State private var showKanban = false
    @State private var mode: Mode = .week

    enum Mode: String, CaseIterable { case day = "Gün", week = "Hafta" }
    public init() {}

    public var body: some View {
        NavigationView {
            VStack {
                Picker("", selection: $mode) {
                    ForEach(Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .padding([.horizontal, .top])

                DatePicker("", selection: $selectedDate, displayedComponents: .date)
                    .datePickerStyle(mode == .week ? .compact : .graphical)
                    .padding(.horizontal)

                List {
                    ForEach(store.events(for: selectedDate)) { ev in
                        VStack(alignment: .leading) {
                            Text(ev.title).font(.headline)
                            Text("\(ev.start.formatted(date: .omitted, time: .shortened)) - \(ev.end.formatted(date: .omitted, time: .shortened))")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .onMove { idx, dest in store.move(from: idx, to: dest, on: selectedDate) }
                }
                .listStyle(.plain)
            }
            .navigationTitle("Takvim")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) { EditButton() }
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Button("Kanban") { showKanban = true }
                    Button("Yedekle") { Task { await store.backupToSupabase() } }
                }
            }
            .sheet(isPresented: $showKanban) { KanbanPage() }
            .task { await store.syncFromSupabase() }
            .background(Theme.primaryBG.ignoresSafeArea())
        }
    }
}
