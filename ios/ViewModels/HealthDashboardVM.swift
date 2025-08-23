import Foundation
import HealthKit
import CoreMotion

@MainActor
public final class HealthDashboardVM: ObservableObject {
    @Published public var authorized = false
    @Published public var snapshot: ActivitySnapshot? = nil
    @Published public var steps7Days: [StepDay] = []
    @Published public var advice: [Advice] = []
    @Published public var liveSteps: Int? = nil
    @Published public var motionStatus: CMAuthorizationStatus = .notDetermined
    @Published public var selectedWeekStart: Date = Calendar.current.dateInterval(of: .weekOfYear, for: Date())!.start
    @Published public var selectedDay: Date = Date()
    @Published public var weekEnergies: [DayEnergy] = []
    @Published public var weekWorkouts: [WorkoutItem] = []
    @Published public var weekMenu: WeekMenu? = nil

    let activityService = HealthActivityService()
    let weightStore: WeightStore
    let adviceEngine = AdviceEngine()
    let motion = MotionService()

    public init(weightStore: WeightStore) { self.weightStore = weightStore }

    public func requestAuth() async {
        guard HKHealthStore.isHealthDataAvailable() else { authorized = false; return }
        do { authorized = try await HealthStoreManager.shared.requestAuthorization() } catch { authorized = false }
    }

    public func refresh() async {
        guard authorized else { return }
        do {
            let snap = try await activityService.fetchTodaySnapshot()
            let days = try await activityService.stepsLast7Days()
            snapshot = snap
            steps7Days = days
            advice = adviceEngine.makeAdvice(activity: snap, weights: weightStore.entries)
            await refreshWeek()
        } catch { print("refresh error:", error) }
    }

    public func refreshWeek() async {
        do {
            weekEnergies = try await activityService.energyByDay(weekStart: selectedWeekStart)
            weekWorkouts = try await activityService.workouts(weekStart: selectedWeekStart)
            if let interval = Calendar.current.dateInterval(of: .weekOfYear, for: Date()), interval.start == selectedWeekStart {
                selectedDay = Date()
            } else {
                selectedDay = selectedWeekStart
            }
            if weekMenu == nil || weekMenu?.weekStart != selectedWeekStart {
                weekMenu = WeekMenu(weekStart: selectedWeekStart, days: Self.defaultMenu(for: selectedWeekStart))
            }
        } catch { print("refreshWeek error:", error) }
    }

    public static func defaultMenu(for weekStart: Date) -> [MenuDay] {
        let names = [
            ("Yulaf + yoğurt + meyve", "Izgara tavuk + bulgur + salata", "Zeytinyağlı sebze + yoğurt"),
            ("Omlet + tam buğday tost", "Mercimek çorbası + salata", "Somon + kinoalı salata"),
            ("Menemen + peynir", "Tavuk sebzeli dürüm", "Kuru fasulye + pilav (az)"),
            ("Smoothie (yoğurt+muz)", "Ton balıklı sandviç", "Fırın sebze + köfte"),
            ("Peynir/zeytin + yumurta", "Zeytinyağlı barbunya + cacık", "Tavuk şiş + salata"),
            ("Lor + domates-salatalık", "Etli nohut + bulgur", "Sebzeli makarna + yoğurt"),
            ("Yulaf pankek", "Izgara hindi + patates", "Mercimek köfte + salata")
        ]
        return (0..<7).map { i in
            let d = Calendar.current.date(byAdding: .day, value: i, to: weekStart)!
            let t = names[i % names.count]
            return MenuDay(date: d, breakfast: t.0, lunch: t.1, dinner: t.2)
        }
    }

    public func startLiveSteps() {
        motionStatus = motion.authorizationStatus()
        guard motion.isAvailable(), motionStatus != .denied else { return }
        motion.startDaily { [weak self] steps in
            guard let self = self else { return }
            self.liveSteps = steps
            if var snap = self.snapshot {
                snap.steps = steps
                self.snapshot = snap
                self.advice = self.adviceEngine.makeAdvice(activity: snap, weights: self.weightStore.entries)
            }
        }
    }

    public func stopLiveSteps() { motion.stop() }
}
