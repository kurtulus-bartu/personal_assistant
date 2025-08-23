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

                let H: CGFloat = 16
                if mode == .week {
                    WeekView(selectedDate: $selectedDate,
                             events: store.events,
                             tag: selectedTag,
                             project: selectedProject)
                    .padding(.horizontal, H)
                    .environmentObject(store)
                } else {
                    DayTimelineView(date: selectedDate,
                                    events: filteredEvents(for: selectedDate))
                    .padding(.horizontal, H)
                    .environmentObject(store)
                }

                Button("Kanban") { showKanban = true }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Theme.secondaryBG)
                    .foregroundColor(Theme.text)
                    .padding([.horizontal, .bottom])
            }
            .toolbar {
                ToolbarItem(placement: .principal) {
                    HStack(spacing: 8) {
                        Text("Takvim").font(.headline)
                        Spacer()
                        Button(action: { Task { await store.syncFromSupabase() } }) {
                            Image(systemName: "arrow.clockwise")
                        }
                    }
                    .frame(maxWidth: .infinity)
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
                    let durMin = Int(ev.end.timeIntervalSince(ev.start) / 60)
                    let isSmall = durMin <= 45
                    RoundedRectangle(cornerRadius: 8)
                        .fill(isSmall ? Theme.accentBG : Theme.secondaryBG)
                        .overlay(
                            VStack(alignment: .leading, spacing: 2) {
                                Text(ev.title).font(.caption).bold().foregroundColor(Theme.text)
                                if let tag = ev.tag, let pr = ev.project {
                                    Text("\(tag) > \(pr)").font(.system(size: 10)).foregroundColor(Theme.textMuted)
                                } else if let tag = ev.tag {
                                    Text(tag).font(.system(size: 10)).foregroundColor(Theme.textMuted)
                                } else if let pr = ev.project {
                                    Text(pr).font(.system(size: 10)).foregroundColor(Theme.textMuted)
                                }
                            }
                            .padding(6)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        )
                        .frame(height: h)
                        .offset(y: y)
                        .zIndex(isSmall ? 1 : 0)
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
    private func snapped(_ date: Date, by minutesDelta: CGFloat) -> Date {
        let m = Int(minutesDelta.rounded())
        let snap = (m / 15) * 15
        return Calendar.current.date(byAdding: .minute, value: snap, to: date)!
    }
    private func dragGesture(for ev: PlannerEvent, day: Date, rowHeight: CGFloat, dayWidth: CGFloat) -> some Gesture {
        DragGesture()
            .onEnded { value in
                let minutes = (value.translation.height / rowHeight) * 60.0
                let dayShift = Int((value.translation.width / dayWidth).rounded())
                var newStart = snapped(ev.start, by: minutes)
                var newEnd = snapped(ev.end, by: minutes)
                if dayShift != 0 {
                    newStart = Calendar.current.date(byAdding: .day, value: dayShift, to: newStart) ?? newStart
                    newEnd = Calendar.current.date(byAdding: .day, value: dayShift, to: newEnd) ?? newEnd
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
    @State private var selection = 0
    let rowHeight: CGFloat = 60
    private let refDate = Calendar.current.date(from: DateComponents(year: 2000, month: 1, day: 1))!
    private let dayFormatter: DateFormatter = {
        let f = DateFormatter(); f.dateFormat = "E dd"; return f
    }()
    var body: some View {
        TabView(selection: $selection) {
            ForEach((-20000)...20000, id: \.self) { idx in
                let right = Calendar.current.date(byAdding: .day, value: idx, to: refDate)!
                let days = (-2...0).compactMap { Calendar.current.date(byAdding: .day, value: $0, to: right) }
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
                            HStack(spacing: 0) {
                                ForEach(days, id: \.self) { day in
                                    DayColumn(day: day,
                                              events: eventsFor(day: day),
                                              rowHeight: rowHeight)
                                        .frame(width: 100)
                                }
                            }
                            .overlay(alignment: .topLeading) {
                                GeometryReader { geo in
                                    let w = geo.size.width
                                    let colCount = 3.0
                                    let step = w / colCount
                                    Path { p in
                                        for i in 1..<Int(colCount) {
                                            let x = CGFloat(i) * step
                                            p.move(to: CGPoint(x: x, y: 0))
                                            p.addLine(to: CGPoint(x: x, y: geo.size.height))
                                        }
                                    }
                                    .stroke(Color.gray.opacity(0.3), lineWidth: 0.5)
                                }
                            }
                        }
                    }
                }
                .tag(idx)
            }
        }
        .tabViewStyle(.page(indexDisplayMode: .automatic))
        .onAppear { selection = daysBetween(refDate, selectedDate) }
        .onChange(of: selection) { newValue in
            if let right = Calendar.current.date(byAdding: .day, value: newValue, to: refDate) {
                selectedDate = right
            }
        }
    }
    private func eventsFor(day: Date) -> [PlannerEvent] {
        events.filter { ev in
            Calendar.current.isDate(ev.start, inSameDayAs: day) &&
            (tag == nil || ev.tag == tag) &&
            (project == nil || ev.project == project)
        }
    }
    private func daysBetween(_ start: Date, _ end: Date) -> Int {
        Calendar.current.dateComponents([.day], from: start, to: end).day ?? 0
    }
}
