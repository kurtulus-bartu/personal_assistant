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
                    .padding(.horizontal)
                    .environmentObject(store)
                } else {
                    DayTimelineView(date: selectedDate,
                                    events: filteredEvents(for: selectedDate))
                    .padding(.horizontal)
                    .environmentObject(store)
                }

                Button("Kanban") { showKanban = true }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Theme.secondaryBG)
                    .foregroundColor(Theme.text)
                    .padding([.horizontal, .bottom])
            }
            .navigationTitle("Takvim")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { Task { await store.syncFromSupabase() } }) {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
            .sheet(isPresented: $showKanban) { KanbanPage() }
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

private struct DayColumn: View {
    @EnvironmentObject var store: EventStore
    let day: Date
    let events: [PlannerEvent]
    let rowHeight: CGFloat
    var body: some View {
        GeometryReader { geo in
            let dayWidth = geo.size.width
            ZStack(alignment: .topLeading) {
                VStack(spacing: 0) {
                    ForEach(0..<24, id: \.self) { _ in
                        Rectangle()
                            .fill(Color.gray.opacity(0.3))
                            .frame(height: 0.5)
                            .offset(y: rowHeight - 0.5)
                            .frame(height: rowHeight)
                    }
                }
                ForEach(events) { ev in
                    let y = yOffset(for: ev.start, rowHeight: rowHeight)
                    let h = height(for: ev, rowHeight: rowHeight)
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Theme.secondaryBG)
                        .overlay(
                            VStack(alignment: .leading, spacing: 2) {
                                Text(ev.title).font(.caption).foregroundColor(Theme.text)
                                Text(timeRange(ev)).font(.system(size: 10)).foregroundColor(Theme.textMuted)
                            }
                            .padding(6)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        )
                        .frame(height: h)
                        .offset(y: y)
                        .gesture(dragGesture(for: ev, day: day, rowHeight: rowHeight, dayWidth: dayWidth))
                }
            }
            .frame(minHeight: rowHeight * 24, alignment: .top)
        }
    }
    private func yOffset(for start: Date, rowHeight: CGFloat) -> CGFloat {
        let comps = Calendar.current.dateComponents([.hour, .minute], from: start)
        let h = CGFloat(comps.hour ?? 0)
        let m = CGFloat(comps.minute ?? 0) / 60
        return (h + m) * rowHeight
    }
    private func height(for ev: PlannerEvent, rowHeight: CGFloat) -> CGFloat {
        let dur = ev.end.timeIntervalSince(ev.start) / 3600
        return CGFloat(dur) * rowHeight
    }
    private func timeRange(_ ev: PlannerEvent) -> String {
        "\(ev.start.formatted(date: .omitted, time: .shortened)) - \(ev.end.formatted(date: .omitted, time: .shortened))"
    }
    private func dragGesture(for ev: PlannerEvent, day: Date, rowHeight: CGFloat, dayWidth: CGFloat) -> some Gesture {
        DragGesture()
            .onEnded { value in
                let minuteDelta = Int((value.translation.height / rowHeight) * 60)
                let dayDelta = Int((value.translation.width / dayWidth).rounded())
                let cal = Calendar.current
                var newStart = cal.date(byAdding: .minute, value: minuteDelta, to: ev.start) ?? ev.start
                var newEnd = cal.date(byAdding: .minute, value: minuteDelta, to: ev.end) ?? ev.end
                if dayDelta != 0 {
                    newStart = cal.date(byAdding: .day, value: dayDelta, to: newStart) ?? newStart
                    newEnd = cal.date(byAdding: .day, value: dayDelta, to: newEnd) ?? newEnd
                }
                if let idx = store.events.firstIndex(where: { $0.id == ev.id }) {
                    store.events[idx].start = newStart
                    store.events[idx].end = newEnd
                    store.save()
                    Task { await store.backupToSupabase() }
                }
            }
    }
}

private struct DayTimelineView: View {
    @EnvironmentObject var store: EventStore
    var date: Date
    var events: [PlannerEvent]
    let rowHeight: CGFloat = 60
    var body: some View {
        ScrollView {
            HStack(alignment: .top, spacing: 0) {
                VStack(spacing: 0) {
                    ForEach(0..<24, id: \.self) { hr in
                        Text("\(hr):00")
                            .frame(width: 40, height: rowHeight, alignment: .topLeading)
                            .foregroundColor(Theme.text)
                            .font(.caption)
                    }
                }
                DayColumn(day: date, events: events, rowHeight: rowHeight)
                    .frame(maxWidth: .infinity)
            }
        }
    }
}

private struct WeekView: View {
    @EnvironmentObject var store: EventStore
    @Binding var selectedDate: Date
    var events: [PlannerEvent]
    var tag: String?
    var project: String?
    @State private var page = 0
    let rowHeight: CGFloat = 60
    private let dayFormatter: DateFormatter = {
        let f = DateFormatter(); f.dateFormat = "E dd"; return f
    }()
    var body: some View {
        let week = weekDates(containing: selectedDate)
        let groups = grouped(week)
        TabView(selection: $page) {
            ForEach(groups.indices, id: \.self) { idx in
                let days = groups[idx]
                VStack(spacing: 0) {
                    HStack(spacing: 0) {
                        Text("")
                            .frame(width: 40)
                        ForEach(days, id: \.self) { day in
                            Text(dayFormatter.string(from: day))
                                .frame(maxWidth: .infinity)
                                .foregroundColor(Theme.text)
                        }
                    }
                    .padding(.vertical, 4)
                    ScrollView {
                        HStack(alignment: .top, spacing: 0) {
                            VStack(spacing: 0) {
                                ForEach(0..<24, id: \.self) { hr in
                                    Text("\(hr):00")
                                        .frame(width: 40, height: rowHeight, alignment: .topLeading)
                                        .foregroundColor(Theme.text)
                                        .font(.caption)
                                }
                            }
                            ForEach(days, id: \.self) { day in
                                DayColumn(day: day,
                                          events: eventsFor(day: day),
                                          rowHeight: rowHeight)
                                    .frame(width: 100)
                            }
                        }
                    }
                }
                .tag(idx)
            }
        }
        .tabViewStyle(.page(indexDisplayMode: .automatic))
        .onAppear {
            if let idx = groups.firstIndex(where: { $0.contains(selectedDate) }) { page = idx }
        }
    }
    private func eventsFor(day: Date) -> [PlannerEvent] {
        events.filter { ev in
            Calendar.current.isDate(ev.start, inSameDayAs: day) &&
            (tag == nil || ev.tag == tag) &&
            (project == nil || ev.project == project)
        }
    }
    private func grouped(_ days: [Date]) -> [[Date]] {
        var result: [[Date]] = []
        var index = 0
        while index < days.count {
            let end = min(index + 3, days.count)
            result.append(Array(days[index..<end]))
            index += 3
        }
        return result
    }
}
