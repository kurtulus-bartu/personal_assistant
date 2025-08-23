import SwiftUI

public struct CalendarPage: View {
    @StateObject private var store = EventStore()
    @State private var selectedDate = Date()
    @State private var showKanban = false
    @State private var mode: Mode = .week
    @State private var selectedTag: String?
    @State private var selectedProject: String?

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
                .padding(.horizontal)

                if mode == .week {
                    WeekView(selectedDate: $selectedDate,
                             events: store.events,
                             tag: selectedTag,
                             project: selectedProject)
                } else {
                    DayTimelineView(date: selectedDate,
                                    events: filteredEvents(for: selectedDate))
                }
            }
            .navigationTitle("Takvim")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) { EditButton() }
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Button("Kanban") { showKanban = true }
                    Button("Yedekle") { Task { await store.backupToSupabase() } }
                }
            }
            .sheet(isPresented: $showKanban) { KanbanPage(store: store) }
            .task { await store.syncFromSupabase() }
            .background(Theme.primaryBG.ignoresSafeArea())
        }
    }
    private func filteredEvents(for day: Date) -> [PlannerEvent] {
        store.events(for: day).filter { ev in
            (selectedTag == nil || ev.tag == selectedTag) &&
            (selectedProject == nil || ev.project == selectedProject)
        }
    }
}

private func weekDates(containing date: Date) -> [Date] {
    let cal = Calendar.current
    let start = cal.date(from: cal.dateComponents([.yearForWeekOfYear, .weekOfYear], from: date))!
    return (0..<7).compactMap { cal.date(byAdding: .day, value: $0, to: start) }
}

private struct DayTimelineView: View {
    var date: Date
    var events: [PlannerEvent]
    var body: some View {
        List {
            ForEach(0..<24, id: \.self) { hr in
                let hourEvents = events.filter { Calendar.current.component(.hour, from: $0.start) == hr }
                Section(header: Text("\(hr):00").foregroundColor(Theme.text)) {
                    ForEach(hourEvents) { ev in
                        VStack(alignment: .leading) {
                            Text(ev.title).foregroundColor(Theme.text).font(.headline)
                            Text("\(ev.start.formatted(date: .omitted, time: .shortened)) - \(ev.end.formatted(date: .omitted, time: .shortened))")
                                .foregroundColor(Theme.textMuted).font(.caption)
                        }
                    }
                }
            }
        }
        .listStyle(.plain)
    }
}

private struct WeekView: View {
    @Binding var selectedDate: Date
    var events: [PlannerEvent]
    var tag: String?
    var project: String?
    var body: some View {
        let week = weekDates(containing: selectedDate)
        let groups = stride(from: 0, to: week.count, by: 3).map { Array(week[$0..<min($0 + 3, week.count)]) }
        TabView {
            ForEach(groups, id: \.self) { group in
                HStack(spacing: 0) {
                    ForEach(group, id: \.self) { day in
                        DayTimelineView(date: day,
                                        events: eventsFor(day: day))
                            .frame(width: UIScreen.main.bounds.width / 3)
                    }
                }
            }
        }
        .tabViewStyle(.page(indexDisplayMode: .automatic))
    }
    private func eventsFor(day: Date) -> [PlannerEvent] {
        let store = EventStore(); store.events = events
        return store.events(for: day).filter { ev in
            (tag == nil || ev.tag == tag) && (project == nil || ev.project == project)
        }
    }
}
