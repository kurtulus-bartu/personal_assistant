import SwiftUI

public struct CalendarPage: View {
    @StateObject private var store = EventStore()
    @StateObject private var taskStore = TaskStore()
    @StateObject private var tagStore = TagStore()
    @StateObject private var projectStore = ProjectStore()
    @State private var selectedDate = Date()
    @State private var showKanban = false
    @State private var mode: Mode = .week
    @State private var selectedTag: String?
    @State private var selectedProject: String?

    enum Mode: String, CaseIterable { case day = "Gün", week = "Hafta" }
    public init() {}

    public var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                VStack(spacing: 4) {
                    Picker("", selection: $mode) {
                        ForEach(Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)

                    HStack {
                        Picker("Tag", selection: $selectedTag) {
                            Text("Tümü").tag(String?.none)
                            ForEach(tagStore.tags, id: \.id) { t in
                                Text(t.name).tag(String?.some(t.name))
                            }
                        }
                        Picker("Proje", selection: $selectedProject) {
                            Text("Tümü").tag(String?.none)
                            ForEach(projectStore.projects, id: \.id) { p in
                                Text(p.name).tag(String?.some(p.name))
                            }
                        }
                        DatePicker("", selection: $selectedDate, displayedComponents: .date)
                            .labelsHidden()
                    }
                }
                .padding(8)
                .background(Theme.primaryBG)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(Theme.secondaryBG, lineWidth: 1)
                )
                .padding(.horizontal)
                .padding(.top, 2)

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
            }
            .toolbar {
                ToolbarItem(placement: .principal) {
                    ZStack {
                        Text("Takvim").font(.headline)
                        HStack {
                              Button(action: { showKanban = true }) {
                                  Image(systemName: "square.grid.2x2")
                              }
                              Spacer()
                              Button(action: {
                                  Task {
                                      await SyncOrchestrator.initialPull(tags: tagStore,
                                                                         projects: projectStore,
                                                                         tasks: taskStore,
                                                                         events: store)
                                      let vm = HealthDashboardVM(weightStore: WeightStore())
                                      await vm.requestAuth()
                                      await vm.refresh()
                                  }
                              }) {
                                  Image(systemName: "arrow.down.circle")
                              }
                              Button(action: {
                                  Task {
                                      let hasAnyLocal = !tagStore.tags.isEmpty ||
                                         !projectStore.projects.isEmpty ||
                                         !taskStore.tasks.isEmpty ||
                                         !store.events.isEmpty

                                      guard hasAnyLocal else {
                                          print("Backup cancelled: Local stores are empty, replace would wipe remote.")
                                          return
                                      }

                                      await SyncOrchestrator.replaceRemoteWithLocal(
                                          tags: tagStore,
                                          projects: projectStore,
                                          tasks: taskStore,
                                          events: store
                                      )
                                      await SyncOrchestrator.initialPull(
                                          tags: tagStore,
                                          projects: projectStore,
                                          tasks: taskStore,
                                          events: store
                                      )
                                  }
                              }) {
                                  Image(systemName: "arrow.clockwise")
                              }
                          }
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .sheet(isPresented: $showKanban) { KanbanPage(store: taskStore) }
            .task {
                await tagStore.syncFromSupabase()
                await projectStore.syncFromSupabase()
                await taskStore.syncFromSupabase()
                await store.syncFromSupabase()
            }
            .background(Theme.primaryBG.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
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
    @Environment(\.displayScale) private var scale
    let day: Date
    let allEvents: [PlannerEvent]
    var tag: String?
    var project: String?
    var dayWidth: CGFloat? = nil
    let rowHeight: CGFloat
    @Binding var isDragging: Bool
    @State private var draggedEventId: Int? = nil
    @State private var resizingEventId: Int? = nil
    private var onePx: CGFloat { 1 / scale }

    // Görevler için kenar boşlukları
    private let eventMargin: CGFloat = 4

    var body: some View {
        ZStack(alignment: .topLeading) {
            Color.clear
                .frame(minHeight: rowHeight * 24)
                .contentShape(Rectangle())
                .gesture(
                    DragGesture(minimumDistance: 0)
                        .onChanged { _ in
                            if draggedEventId != nil || resizingEventId != nil {
                                isDragging = false
                                draggedEventId = nil
                                resizingEventId = nil
                            }
                        }
                )

            ForEach(orderedEvents) { ev in
                let y = yOffset(for: ev.start)
                let h = height(for: ev)
                let isSmall = isSmallestInCluster(ev, in: filteredEvents)
                let isDraggedEvent = draggedEventId == ev.id || resizingEventId == ev.id

                RoundedRectangle(cornerRadius: 8)
                    .fill(isSmall ? Theme.primaryBG : Theme.secondaryBG)
                    .overlay(alignment: .topLeading) {
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
                        .allowsHitTesting(false)
                    }
                    .overlay(alignment: .top) {
                        Rectangle()
                            .fill(Theme.primaryBG)
                            .frame(height: 6)
                            .overlay(Rectangle().stroke(Theme.accent, lineWidth: onePx))
                    }
                    .overlay(alignment: .bottom) {
                        Rectangle()
                            .fill(Theme.primaryBG)
                            .frame(height: 6)
                            .overlay(Rectangle().stroke(Theme.accent, lineWidth: onePx))
                            .highPriorityGesture(resizeGesture(ev))
                    }
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Theme.accent, lineWidth: onePx)
                    )
                    .frame(height: max(h, 24))
                    .offset(y: y)
                    .padding(.horizontal, eventMargin) // Kenar boşlukları eklendi
                    .zIndex(isDraggedEvent ? 10.0 : (isSmall ? 2.0 : 0.0))
                    .scaleEffect(isDraggedEvent ? 1.02 : 1.0)
                    .gesture(moveGesture(ev))
            }
        }
        .frame(minHeight: rowHeight * 24, alignment: .top)
        .clipped()
    }

    private var filteredEvents: [PlannerEvent] {
        allEvents.filter { ev in
            Calendar.current.isDate(ev.start, inSameDayAs: day) &&
            (tag == nil || ev.tag == tag) &&
            (project == nil || ev.project == project)
        }
    }

    private var orderedEvents: [PlannerEvent] {
        filteredEvents.sorted { a, b in
            if overlaps(a, b) && durationMin(a) != durationMin(b) {
                return durationMin(a) > durationMin(b)
            }
            return a.start < b.start
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

    private func durationMin(_ ev: PlannerEvent) -> Int {
        Int(ev.end.timeIntervalSince(ev.start) / 60)
    }

    private func overlaps(_ a: PlannerEvent, _ b: PlannerEvent) -> Bool {
        a.start < b.end && b.start < a.end
    }

    private func isSmallestInCluster(_ ev: PlannerEvent, in events: [PlannerEvent]) -> Bool {
        let cluster = events.filter { overlaps($0, ev) }
        guard cluster.count > 1 else { return false }
        let minDur = cluster.map(durationMin).min()!
        return durationMin(ev) == minDur
    }

    private func moveGesture(_ ev: PlannerEvent) -> some Gesture {
        DragGesture(minimumDistance: 3)
            .onChanged { value in
                if draggedEventId == nil && resizingEventId == nil {
                    isDragging = true
                    draggedEventId = ev.id
                }
            }
            .onEnded { value in
                guard draggedEventId == ev.id else { return }

                defer {
                    isDragging = false
                    draggedEventId = nil
                }

                let totalMovement = sqrt(value.translation.width * value.translation.width + value.translation.height * value.translation.height)
                guard totalMovement > 8 else { return }

                let minutes = (value.translation.height / rowHeight) * 60.0
                func snap(_ d: Date) -> Date {
                    let m = Int(minutes.rounded())
                    let s = (m / 15) * 15
                    return Calendar.current.date(byAdding: .minute, value: s, to: d)!
                }
                var newStart = snap(ev.start)
                var newEnd = snap(ev.end)

                if let dw = dayWidth {
                    let dShift = Int((value.translation.width / dw).rounded())
                    if dShift != 0 {
                        newStart = Calendar.current.date(byAdding: .day, value: dShift, to: newStart)!
                        newEnd = Calendar.current.date(byAdding: .day, value: dShift, to: newEnd)!
                    }
                }

                if let idx = store.events.firstIndex(where: { $0.id == ev.id }) {
                    store.events[idx].start = newStart
                    store.events[idx].end = newEnd
                    store.save()
                    Task { await store.backupToSupabase() }
                }
            }
    }

    private func resizeGesture(_ ev: PlannerEvent) -> some Gesture {
        DragGesture(minimumDistance: 3)
            .onChanged { _ in
                if resizingEventId == nil && draggedEventId == nil {
                    isDragging = true
                    resizingEventId = ev.id
                }
            }
            .onEnded { value in
                guard resizingEventId == ev.id else { return }

                defer {
                    isDragging = false
                    resizingEventId = nil
                }

                let minutes = (value.translation.height / rowHeight) * 60.0
                let m = Int(minutes.rounded())
                let s = (m / 15) * 15
                var newEnd = Calendar.current.date(byAdding: .minute, value: s, to: ev.end)!
                if newEnd <= ev.start {
                    newEnd = Calendar.current.date(byAdding: .minute, value: 15, to: ev.start)!
                }

                if let idx = store.events.firstIndex(where: { $0.id == ev.id }) {
                    store.events[idx].end = newEnd
                    store.save()
                    Task { await store.backupToSupabase() }
                }
            }
    }
}

private struct DayTimelineView: View {
    @EnvironmentObject var store: EventStore
    @Environment(\.displayScale) private var scale
    var date: Date
    var events: [PlannerEvent]
    private let hoursWidth: CGFloat = 44
    private let rowHeight: CGFloat = 60
    @State private var isDraggingEvent = false
    private var onePx: CGFloat { 1 / scale }
    var body: some View {
        ScrollView(.vertical) {
            ZStack(alignment: .topLeading) {
                HorizontalLines(rowHeight: rowHeight, onePx: onePx)
                    .frame(maxWidth: .infinity, alignment: .topLeading)
                    .frame(height: rowHeight * 24)
                    .allowsHitTesting(false)

                VStack(spacing: 0) {
                    ForEach(0..<24, id: \.self) { hr in
                        Text("\(hr):00")
                            .foregroundColor(Theme.text)
                            .font(.caption)
                            .frame(width: hoursWidth, height: rowHeight, alignment: .topLeading)
                    }
                }
                .frame(width: hoursWidth)
                .allowsHitTesting(false)

                DayColumnView(day: date, allEvents: events, tag: nil, project: nil, dayWidth: nil, rowHeight: rowHeight, isDragging: $isDraggingEvent)
                    .padding(.leading, hoursWidth)
            }
        }
        .scrollDisabled(isDraggingEvent)
    }
}

private struct WeekView: View {
    @Binding var selectedDate: Date
    var events: [PlannerEvent]
    var tag: String?
    var project: String?
    @Environment(\.displayScale) private var scale
    @State private var anchor: Int = 0
    @State private var scrollPosition: Int?
    private let headerHeight: CGFloat = 28
    private let hoursWidth: CGFloat = 44
    private let rowHeight: CGFloat = 60
    private let ref = Calendar.current.startOfDay(for: Date())
    private var onePx: CGFloat { 1 / scale }
    @State private var isDraggingEvent = false

    var body: some View {
        GeometryReader { geo in
            let dayWidth = (geo.size.width - hoursWidth) / 3
            VStack(spacing: 0) {
                HStack(spacing: 0) {
                    Color.clear.frame(width: hoursWidth)
                    ForEach(0..<3, id: \.self) { i in
                        let d = dateFor(index: anchor - (2 - i))
                        Text(dayLabel(d))
                            .font(.footnote.bold())
                            .foregroundColor(Theme.text)
                            .frame(width: dayWidth, height: headerHeight, alignment: .bottom)
                    }
                }
                .frame(height: headerHeight)
                .overlay(alignment: .bottom) {
                    Rectangle().fill(Color.gray.opacity(0.25))
                        .frame(height: onePx)
                        .allowsHitTesting(false)
                }

                ScrollView(.vertical) {
                    ZStack(alignment: .topLeading) {
                        HorizontalLines(rowHeight: rowHeight, onePx: onePx)
                            .frame(maxWidth: .infinity, alignment: .topLeading)
                            .frame(height: rowHeight * 24)
                            .allowsHitTesting(false)

                        VStack(spacing: 0) {
                            ForEach(0..<24, id: \.self) { hr in
                                Text("\(hr):00")
                                    .foregroundColor(Theme.text)
                                    .font(.caption)
                                    .frame(width: hoursWidth, height: rowHeight, alignment: .topLeading)
                            }
                        }
                        .frame(width: hoursWidth)
                        .allowsHitTesting(false)

        ScrollView(.horizontal) {
                            LazyHStack(spacing: 0) {
                                ForEach(-20000...20000, id: \.self) { idx in
                                    DayColumnView(day: dateFor(index: idx),
                                                  allEvents: events,
                                                  tag: tag,
                                                  project: project,
                                                  dayWidth: dayWidth,
                                                  rowHeight: rowHeight,
                                                  isDragging: $isDraggingEvent)
                                        .id(idx)
                                        .frame(width: dayWidth)
                                        .overlay(alignment: .trailing) {
                                            Rectangle().fill(Color.gray.opacity(0.3))
                                                .frame(width: onePx)
                                                .allowsHitTesting(false)
                                        }
                                }
                            }
                            .scrollTargetLayout()
                        }
                        .scrollDisabled(isDraggingEvent)
                        .scrollIndicators(.hidden)
                        .scrollTargetBehavior(.viewAligned)
                        .scrollPosition(id: $scrollPosition)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.leading, hoursWidth)
                    }
                }
                .scrollDisabled(isDraggingEvent)
            }
            .onAppear {
                anchor = daysBetween(ref, selectedDate)
                scrollPosition = anchor - 2
            }
            .onChange(of: selectedDate) { new in
                anchor = daysBetween(ref, new)
                scrollPosition = anchor - 2
            }
            .onChange(of: scrollPosition) { idx in
                guard let idx else { return }
                anchor = idx + 2
                selectedDate = dateFor(index: anchor)
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

private struct HorizontalLines: View {
    let rowHeight: CGFloat
    let onePx: CGFloat

    var body: some View {
        // Canvas ile tüm genişliğe tek katmanda çiz
        Canvas { ctx, size in
            let color = Color.gray.opacity(0.35)
            for i in 0...24 {
                let y = CGFloat(i) * rowHeight
                let rect = CGRect(x: 0, y: y, width: size.width, height: max(onePx, 0.5))
                ctx.fill(Path(rect), with: .color(color))
            }
        }
        .allowsHitTesting(false)
    }
}
