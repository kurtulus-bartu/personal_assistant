import SwiftUI
import Charts

public struct HealthDashboardView: View {
    @StateObject var weightStore = WeightStore()
    @StateObject var vm: HealthDashboardVM
    public init() {
        let ws = WeightStore()
        _weightStore = StateObject(wrappedValue: ws)
        _vm = StateObject(wrappedValue: HealthDashboardVM(weightStore: ws))
    }
    public var body: some View {
        ZStack { Theme.primaryBG.ignoresSafeArea()
            ScrollView { VStack(spacing: 16) {
                header
                motionPermissionInfo
                weeklyHeader
                weeklyCalorieSummary
                weeklyEnergyChart
                workoutsSection
                weeklyMenuSection
                Divider().opacity(0.2)
                dailyTiles
            }.padding(.horizontal,16).padding(.bottom,24) }
        }
        .task { await vm.requestAuth(); await vm.refresh(); vm.startLiveSteps() }
        .refreshable { await vm.refresh() }
        .onDisappear { vm.stopLiveSteps() }
    }
}

// MARK: Subviews & helpers
extension HealthDashboardView {
    var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Sağlık Gösterge Paneli").font(.title2).bold().foregroundColor(Theme.text)
                Text(Date(), style: .date).foregroundColor(Theme.textMuted)
            }
            Spacer()
            Button { Task { await vm.refresh() } } label: {
                Image(systemName: "arrow.clockwise")
                    .foregroundColor(Theme.text)
                    .padding(10)
                    .background(Theme.secondaryBG)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }
    var motionPermissionInfo: some View {
        Group {
            if vm.motionStatus == .denied {
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "figure.walk.circle").foregroundColor(Theme.accent)
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Hareket & Fitness izni kapalı").foregroundColor(Theme.text).bold()
                        Text("Ayarlar → Gizlilik ve Güvenlik → Hareket ve Fitness → Fitness Takibi ve uygulama iznini aç.").foregroundColor(Theme.textMuted).font(.caption)
                    }
                    Spacer()
                }
                .padding(12)
                .background(Theme.secondaryBG)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }
    var weeklyHeader: some View {
        HStack {
            Button { shiftWeek(-1) } label: { Image(systemName: "chevron.left") }
                .buttonStyle(.plain).foregroundColor(Theme.text)
            VStack(spacing: 2) {
                let end = Calendar.current.date(byAdding: .day, value: 6, to: vm.selectedWeekStart)!
                Text("Hafta: \(dateString(vm.selectedWeekStart)) – \(dateString(end))")
                    .foregroundColor(Theme.text)
                Text("(Pzt–Paz)")
                    .foregroundColor(Theme.textMuted)
                    .font(.caption)
            }
            Spacer()
            Button { shiftWeek(1) } label: { Image(systemName: "chevron.right") }
                .buttonStyle(.plain).foregroundColor(Theme.text)
        }
    }
    func shiftWeek(_ delta: Int) {
        if let next = Calendar.current.date(byAdding: .weekOfYear, value: delta, to: vm.selectedWeekStart) {
            vm.selectedWeekStart = Calendar.current.dateInterval(of: .weekOfYear, for: next)!.start
            Task { await vm.refreshWeek() }
        }
    }
    func dateString(_ d: Date) -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "tr_TR"); f.dateFormat = "d MMM"; return f.string(from: d)
    }
    func shortWeekday(_ d: Date) -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "tr_TR"); f.dateFormat = "E"; return f.string(from: d)
    }
    var weeklyCalorieSummary: some View {
        VStack(alignment: .leading, spacing: 6) {
            let selected = vm.weekEnergies.first { Calendar.current.isDate($0.date, inSameDayAs: vm.selectedDay) }
            let kcal = selected?.kcal ?? 0
            Text("Seçili gün kalorisi: \(Int(kcal)) kcal").foregroundColor(Theme.text).bold()
            HStack(spacing: 8) {
                ForEach(vm.weekEnergies.map { $0.date }, id: \.self) { d in
                    let sel = Calendar.current.isDate(d, inSameDayAs: vm.selectedDay)
                    Button(action: { vm.selectedDay = d }) {
                        Text(shortWeekday(d))
                            .font(.caption)
                            .padding(.vertical, 6).padding(.horizontal, 10)
                            .background(sel ? Theme.accent : Theme.secondaryBG)
                            .foregroundColor(sel ? .black : Theme.text)
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                    }.buttonStyle(.plain)
                }
            }
        }
    }
    var weeklyEnergyChart: some View {
        VStack(alignment: .leading, spacing: 12) {
            Chart(vm.weekEnergies) { item in
                BarMark(x: .value("Gün", item.date, unit: .day), y: .value("kcal", item.kcal))
            }
            .chartYAxis { AxisMarks(position: .leading) }
            .frame(height: 180)
            .padding(12)
            .background(Theme.secondaryBG)
            .clipShape(RoundedRectangle(cornerRadius: 16))
        }
    }
    var workoutsSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            SectionTitle("Haftalık Aktiviteler")
            if vm.weekWorkouts.isEmpty {
                Text("Bu hafta kayıtlı aktivite yok.").foregroundColor(Theme.textMuted)
            } else {
                ForEach(vm.weekWorkouts) { w in
                    HStack {
                        Image(systemName: "figure.run").foregroundColor(Theme.accent)
                        VStack(alignment: .leading) {
                            Text(workoutName(w.activity)).foregroundColor(Theme.text)
                            Text("\(w.durationMin) dk • \(Int(w.energyKcal)) kcal").foregroundColor(Theme.textMuted).font(.caption)
                        }
                        Spacer()
                        Text(dateString(w.start)).foregroundColor(Theme.textMuted).font(.caption)
                    }
                    .padding(10)
                    .background(Theme.secondaryBG)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
            }
        }
    }
    func workoutName(_ t: HKWorkoutActivityType) -> String {
        switch t {
        case .running: return "Koşu"
        case .walking: return "Yürüyüş"
        case .cycling: return "Bisiklet"
        case .traditionalStrengthTraining: return "Ağırlık"
        case .swimming: return "Yüzme"
        default: return "Aktivite"
        }
    }
    var weeklyMenuSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            SectionTitle("Haftalık Menü")
            if let menu = vm.weekMenu {
                ForEach(menu.days) { d in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(dateString(d.date)).foregroundColor(Theme.text).bold()
                        Text("Kahvaltı: \(d.breakfast)").foregroundColor(Theme.textMuted)
                        Text("Öğle: \(d.lunch)").foregroundColor(Theme.textMuted)
                        Text("Akşam: \(d.dinner)").foregroundColor(Theme.textMuted)
                    }
                    .padding(10)
                    .background(Theme.secondaryBG)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
            }
        }
    }
    var dailyTiles: some View {
        let s = vm.snapshot
        let stepsText = vm.liveSteps.map { "\($0)" } ?? s.map { "\($0.steps)" } ?? "-"
        return LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            StatCard(title: "Adım", value: stepsText, subtitle: "bugün")
            StatCard(title: "Aktif Enerji", value: s.map { String(format: "%.0f kcal", $0.activeEnergyKcal) } ?? "-", subtitle: "bugün")
            StatCard(title: "Mesafe", value: s.map { String(format: "%.2f km", $0.distanceKm) } ?? "-", subtitle: "bugün")
            StatCard(title: "Nabız", value: s?.latestHeartRateBPM.map { "\(Int($0)) bpm" } ?? "-", subtitle: "son ölçüm")
        }
    }
}
