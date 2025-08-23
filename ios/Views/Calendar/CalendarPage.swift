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
                VStack(spacing: 8) {
                    Picker("", selection: $mode) {
                        ForEach(Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal)

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
                }

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
                    ZStack {
                        Text("Takvim").font(.headline)
                        HStack {
                            Spacer()
                            Button(action: { Task { await store.syncFromSupabase() } }) {
                                Image(systemName: "arrow.clockwise")
                            }
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

private struct DayColumnView: View {
    @EnvironmentObject var store: EventStore
    let day: Date
    let allEvents: [PlannerEvent]
    var tag: String?
    var project: String?
    let rowHeight: CGFloat = 60
    var body: some View {
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
            ForEach(filteredEvents) { ev in
                let y = yOffset(for: ev.start)
                let h = height(for: ev)
                let isSmall = ev.end.timeIntervalSince(ev.start) <= 45*60
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
                        .frame(maxWidth: .infinity, alignment: .topLeading)
                    )
                    .frame(height: h)
                    .offset(y: y)
                    .zIndex(isSmall ? 1 : 0)
                    .gesture(dragGesture15MinSnap(ev))
            }
        }
        .frame(minHeight: rowHeight * 24, alignment: .top)
    }

    private var filteredEvents: [PlannerEvent] {
        allEvents.filter { ev in
            Calendar.current.isDate(ev.start, inSameDayAs: day) &&
            (tag == nil || ev.tag == tag) &&
            (project == nil || ev.project == project)
        }
    }

    private func yOffset(for start: Date) -> CGFloat {
        let comps = Calendar.current.dateComponents([.hour, .minute], from: start)
        let h = CGFloat(comps.hour ?? 0)
        let m = CGFloat(comps.minute ?? 0) / 60
        return (h + m) * rowHeight
    }

    private func height(for ev: PlannerEvent) -> CGFloat {
        CGFloat(ev.end.timeIntervalSince(ev.start) / 3600) * rowHeight
    }

    private func dragGesture15MinSnap(_ ev: PlannerEvent) -> some Gesture {
        DragGesture()
            .onEnded { value in
                let minutes = (value.translation.height / rowHeight) * 60.0
                func snap(_ d: Date) -> Date {
                    let m = Int(minutes.rounded())
                    let s = (m / 15) * 15
                    return Calendar.current.date(byAdding: .minute, value: s, to: d)!
                }
                if let idx = store.events.firstIndex(where: { $0.id == ev.id }) {
                    store.events[idx].start = snap(ev.start)
                    store.events[idx].end = snap(ev.end)
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
    private let hoursWidth: CGFloat = 44
    private let rowHeight: CGFloat = 60
    var body: some View {
        ScrollView(.vertical) {
            ZStack(alignment: .topLeading) {
                VStack(spacing: 0) {
                    ForEach(0..<24, id: \.self) { hr in
                        Text("\(hr):00")
                            .foregroundColor(Theme.text)
                            .font(.caption)
                            .frame(width: hoursWidth, height: rowHeight, alignment: .topLeading)
                            .border(Color.gray.opacity(0.3), width: 0.5)
                    }
                }
                .frame(width: hoursWidth)
                .allowsHitTesting(false)

                DayColumnView(day: date, allEvents: events, tag: nil, project: nil)
                    .padding(.leading, hoursWidth)
            }
        }
    }
}

private struct WeekView: View {
    @Binding var selectedDate: Date
    var events: [PlannerEvent]
    var tag: String?
    var project: String?
    @State private var anchor: Int = 0
    @State private var scrollPosition: Int? = 0
    private let hoursWidth: CGFloat = 44
    private let rowHeight: CGFloat = 60
    private let ref = Calendar.current.startOfDay(for: Date())

    var body: some View {
        GeometryReader { geo in
            let dayWidth = (geo.size.width - hoursWidth) / 3
            VStack(spacing: 0) {
                HStack(spacing: 0) {
                    Color.clear.frame(width: hoursWidth)
                    ForEach(0..<3, id: \.self) { i in
                        let d = dateFor(index: anchor - (2 - i))
                        Text(dayLabel(d))
                            .frame(width: dayWidth)
                            .foregroundColor(Theme.text)
                    }
                }
                .padding(.vertical, 4)

                ScrollView(.vertical) {
                    ZStack(alignment: .topLeading) {
                        VStack(spacing: 0) {
                            ForEach(0..<24, id: \.self) { hr in
                                Text("\(hr):00")
                                    .foregroundColor(Theme.text)
                                    .font(.caption)
                                    .frame(width: hoursWidth, height: rowHeight, alignment: .topLeading)
                                    .border(Color.gray.opacity(0.3), width: 0.5)
                            }
                        }
                        .frame(width: hoursWidth)
                        .allowsHitTesting(false)

                        ScrollView(.horizontal) {
                            LazyHStack(spacing: 0) {
                                ForEach(-20000...20000, id: \.self) { idx in
                                    DayColumnView(day: dateFor(index: idx), allEvents: events, tag: tag, project: project)
                                        .frame(width: dayWidth)
                                        .border(Color.gray.opacity(0.3), width: 0.5)
                                }
                            }
                            .scrollTargetLayout()
                        }
                        .scrollIndicators(.hidden)
                        .scrollTargetBehavior(.viewAligned)
                        .scrollPosition(id: $scrollPosition)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.leading, hoursWidth)
                    }
                }
            }
            .onAppear {
                anchor = daysBetween(ref, selectedDate)
                scrollPosition = anchor - 2
            }
            .onChange(of: selectedDate) { new in
                anchor = daysBetween(ref, new)
                scrollPosition = anchor - 2
            }
        }
    }

    private func dayLabel(_ d: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "E dd"
        return f.string(from: d)
    }
    private func daysBetween(_ a: Date, _ b: Date) -> Int {
        let cal = Calendar.current
        let startA = cal.startOfDay(for: a)
        let startB = cal.startOfDay(for: b)
        return cal.dateComponents([.day], from: startA, to: startB).day ?? 0
    }
    private func dateFor(index: Int) -> Date {
        Calendar.current.date(byAdding: .day, value: index, to: ref)!
    }
}
