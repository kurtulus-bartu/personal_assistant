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
                    DatePicker("", selection: $selectedDate, displayedComponents: .date)
                        .labelsHidden()
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
        ScrollView {
            LazyVStack(spacing: 0) {
                ForEach(0..<24, id: \.self) { hr in
                    let hourEvents = events.filter { Calendar.current.component(.hour, from: $0.start) == hr }
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(hr):00")
                            .foregroundColor(Theme.text)
                            .font(.caption)
                        ForEach(hourEvents) { ev in
                            VStack(alignment: .leading) {
                                Text(ev.title).foregroundColor(Theme.text).font(.headline)
                                Text("\(ev.start.formatted(date: .omitted, time: .shortened)) - \(ev.end.formatted(date: .omitted, time: .shortened))")
                                    .foregroundColor(Theme.textMuted).font(.caption)
                            }
                        }
                        Spacer()
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(4)
                    .frame(height: 60, alignment: .top)
                    .border(Color.gray.opacity(0.3), width: 0.5)
                }
            }
        }
    }
}

private struct WeekView: View {
    @Binding var selectedDate: Date
    var events: [PlannerEvent]
    var tag: String?
    var project: String?
    private let dayFormatter: DateFormatter = {
        let f = DateFormatter(); f.dateFormat = "E dd"; return f
    }()
    var body: some View {
        let week = weekDates(containing: selectedDate)
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                ForEach(week, id: \.self) { day in
                    Text(dayFormatter.string(from: day))
                        .frame(maxWidth: .infinity)
                        .foregroundColor(Theme.text)
                }
            }
            .padding(.vertical, 4)
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(0..<24, id: \.self) { hr in
                        HStack(spacing: 0) {
                            ForEach(week, id: \.self) { day in
                                let evs = eventsFor(day: day, hour: hr)
                                VStack(alignment: .leading, spacing: 2) {
                                    ForEach(evs) { ev in
                                        Text(ev.title)
                                            .font(.caption)
                                            .foregroundColor(Theme.text)
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                    }
                                    Spacer()
                                }
                                .frame(maxWidth: .infinity, alignment: .topLeading)
                                .padding(4)
                                .border(Color.gray.opacity(0.3), width: 0.5)
                                .frame(height: 60)
                            }
                        }
                    }
                }
            }
        }
    }
    private func eventsFor(day: Date, hour: Int) -> [PlannerEvent] {
        let cal = Calendar.current
        return events.filter { ev in
            cal.isDate(ev.start, inSameDayAs: day) && cal.component(.hour, from: ev.start) == hour &&
            (tag == nil || ev.tag == tag) && (project == nil || ev.project == project)
        }
    }
}
